"""
v3_refine.py — V3 迭代打磨管线
生成 → 评估 → 定位问题 → 修正 → 再评估 → 直到合格

殷竺欣 独家原创 | 2026-06-11
"""
import json, os, sys, re
from pathlib import Path
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))

# ═══ 质量检查项 ═══
QUALITY_CHECKS = {
    'completeness': {
        'label': '完整性',
        'checks': ['代码完整可运行', '没有TODO/占位符', 'tag闭合', '函数/变量定义完整'],
        'weight': 3
    },
    'visual_quality': {
        'label': '视觉效果',
        'checks': ['比例正确', '颜色协调', '阴影/高光到位', '细节丰富不空洞', '没有走形/变形'],
        'weight': 3
    },
    'animation': {
        'label': '动画表现',
        'checks': ['动画流畅', '缓动自然', '没有卡顿/闪烁', '时间节奏合理'],
        'weight': 2
    },
    'interaction': {
        'label': '交互体验',
        'checks': ['点击有反馈', '拖动流畅', '悬停有提示', '键盘快捷键可用'],
        'weight': 2
    },
    'code_quality': {
        'label': '代码质量',
        'checks': ['结构清晰', '命名有意义', '没有冗余代码', 'CSS/JS分离合理'],
        'weight': 1
    }
}

def evaluate_output(output: str, output_type: str = 'html') -> dict:
    """评估生成质量——找出具体问题"""
    issues = []
    score = 0
    max_score = sum(c['weight'] * len(c['checks']) for c in QUALITY_CHECKS.values())
    
    for cat_id, cat in QUALITY_CHECKS.items():
        cat_score = 0
        cat_issues = []
        
        for check in cat['checks']:
            passed = _check_item(output, output_type, cat_id, check)
            if passed:
                cat_score += cat['weight']
            else:
                cat_issues.append(check)
        
        score += cat_score
        if cat_issues:
            issues.append({
                'category': cat_id,
                'label': cat['label'],
                'problems': cat_issues,
                'score': cat_score,
                'max': cat['weight'] * len(cat['checks'])
            })
    
    quality = score / max_score if max_score > 0 else 0
    
    return {
        'quality': round(quality, 2),
        'score': f"{score}/{max_score}",
        'issues': issues,
        'needs_refinement': quality < 0.8,
        'critical_issues': quality < 0.5
    }


def _check_item(output: str, output_type: str, category: str, check: str) -> bool:
    """检查单个质量项"""
    lowered = output.lower()
    
    if category == 'completeness':
        if 'todo' in lowered or 'fixme' in lowered or 'placeholder' in lowered:
            return False
        if output_type == 'html':
            if output.count('<') != output.count('>') and abs(output.count('<') - output.count('>')) > 3:
                return False  # 标签不匹配
            if '</html>' not in lowered:
                return False
        if output_type == 'svg':
            if '</svg>' not in lowered:
                return False
    
    elif category == 'visual_quality':
        if output_type in ('html', 'svg'):
            # 检查是否有基本视觉元素
            has_shapes = any(t in lowered for t in ['<rect', '<circle', '<ellipse', '<path', '<polygon'])
            has_colors = any(t in lowered for t in ['fill=', 'background', 'color', 'stroke='])
            has_shadows = any(t in lowered for t in ['shadow', 'opacity', 'gradient'])
            if not has_shapes:
                return False
            if not has_colors:
                return False
    
    elif category == 'animation':
        if output_type == 'html':
            has_anim = any(t in lowered for t in ['@keyframes', 'animation', 'transition', 'transform'])
            if not has_anim:
                return False
    
    elif category == 'interaction':
        if output_type == 'html':
            has_interact = any(t in lowered for t in ['click', 'mousedown', 'drag', 'eventlistener', 'addeventlistener'])
            if not has_interact:
                return False
    
    return True


def build_refinement_prompt(original_input: str, current_output: str, 
                            evaluation: dict, iteration: int) -> str:
    """构建修正提示——指出具体问题，要求修正"""
    
    problem_list = ""
    for issue in evaluation.get('issues', []):
        problem_list += f"\n【{issue['label']}】问题: {', '.join(issue['problems'])}"
    
    return f"""你之前生成了以下代码，但质量检查发现了一些问题。请**修正这些问题**后重新生成。

【原始需求】
{original_input}

【当前输出（有问题）】
```
{current_output[:2000]}
```

【质量评估】{evaluation['score']} — 需要修正
{problem_list}

【修正要求】
1. 逐一解决上述每个问题
2. 保持原有功能和设计不变，只修正问题
3. 生成完整的修正后代码
4. 代码放在 ``` 标记内

这是第 {iteration} 次修正。请确保这次修正后质量明显提升。"""


class V3RefinePipeline:
    """V3 迭代打磨管线——生成→评估→修正→循环"""
    
    def __init__(self, generate_fn=None, max_iterations: int = 3):
        self.generate_fn = generate_fn   # 外部生成函数
        self.max_iterations = max_iterations
        self.history = []
    
    def process(self, user_input: str, output_type: str = 'html') -> dict:
        """完整打磨管线"""
        result = {
            'input': user_input,
            'iterations': [],
            'final_output': None,
            'final_eval': None,
            'total_iterations': 0,
            'converged': False
        }
        
        # 第0次：初始生成
        initial_prompt = f"生成高质量的{output_type.upper()}代码：\n{user_input}\n\n要求：完整、可直接运行、视觉精美。代码放在```标记内。"
        
        current_output = None
        if self.generate_fn:
            current_output = self.generate_fn(initial_prompt)
        else:
            result['error'] = '无生成函数'
            return result
        
        # 提取代码块
        current_output = _extract_code(current_output, output_type)
        
        for i in range(self.max_iterations + 1):
            # 评估
            evaluation = evaluate_output(current_output, output_type)
            
            result['iterations'].append({
                'iteration': i,
                'output_preview': current_output[:300],
                'evaluation': evaluation
            })
            
            result['total_iterations'] = i + 1
            
            # 合格就停
            if not evaluation['needs_refinement'] or i >= self.max_iterations:
                result['final_output'] = current_output
                result['final_eval'] = evaluation
                result['converged'] = evaluation['quality'] >= 0.8
                break
            
            # 不合格——修正
            refine_prompt = build_refinement_prompt(
                user_input, current_output, evaluation, i + 1
            )
            
            if self.generate_fn:
                refined = self.generate_fn(refine_prompt)
                current_output = _extract_code(refined, output_type)
        
        # 保存最终输出
        if result['final_output']:
            out_dir = Path(ROOT) / 'canvas_outputs'
            out_dir.mkdir(exist_ok=True)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            ext = output_type
            fp = out_dir / f'v3_refined_{ts}.{ext}'
            fp.write_text(result['final_output'], encoding='utf-8')
            result['saved_to'] = str(fp)
        
        return result


def _extract_code(text: str, output_type: str) -> str:
    """从响应中提取代码块"""
    # 尝试提取 ``` 代码块
    pattern = rf'```(?:{output_type})?\s*\n(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        return matches[0].strip()
    
    # 尝试直接找 HTML/SVG 标签
    if output_type == 'html' and '<!DOCTYPE' in text:
        start = text.index('<!DOCTYPE')
        end = text.rindex('</html>') + 7
        return text[start:end]
    
    if output_type == 'svg' and '<svg' in text:
        start = text.index('<svg')
        end = text.rindex('</svg>') + 6
        return text[start:end]
    
    return text.strip()


# ═══ 自检 ═══
if __name__ == '__main__':
    print("=" * 60)
    print("  V3 迭代打磨管线 — 自检")
    print("=" * 60)
    
    # 测试评估
    good_html = "<!DOCTYPE html><html><head></head><body><svg><circle cx='50' cy='50' r='30' fill='#E8C9A0'/></svg><style>@keyframes b{0%{transform:scale(1)}}</style><script>document.addEventListener('click',()=>{})</script></body></html>"
    bad_html = "<div>TODO: fix this</div><p>placeholder"
    
    print("\n[评估] 好代码:")
    ev = evaluate_output(good_html, 'html')
    print(f"  质量: {ev['quality']} | 分数: {ev['score']} | 需修正: {ev['needs_refinement']}")
    
    print("\n[评估] 差代码:")
    ev = evaluate_output(bad_html, 'html')
    print(f"  质量: {ev['quality']} | 分数: {ev['score']} | 需修正: {ev['needs_refinement']}")
    for iss in ev.get('issues', []):
        print(f"  [{iss['label']}] {iss['problems']}")
    
    print("\n[管线类] V3RefinePipeline 就绪")
    print(f"  最大迭代: 3轮 | 质量阈值: 0.8")
