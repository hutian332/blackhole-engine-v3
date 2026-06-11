"""
v3_vision.py — V3 视觉馈送
把 llama3.2-vision:11b 接进 V3，让它能"看"自己生成的东西
生成 → 渲染PNG → 视觉模型看图 → 评价 → 自动修正 → 循环

殷竺欣 独家原创 | 2026-06-11 01:14 GMT+8
"""
import json, os, sys, re, base64, io
from pathlib import Path
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
OLLAMA_URL = 'http://localhost:11434/api/generate'
VISION_MODEL = 'moondream:latest'  # llava too weak, moondream may be better

# ═══ 渲染器 ═══
def svg_to_png_base64(svg_or_html: str, width=300, height=380) -> str:
    """把SVG/HTML渲染成PNG base64"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(viewport={'width': width, 'height': height})
            
            if '<html' in svg_or_html.lower():
                # 完整HTML
                page.set_content(svg_or_html)
            else:
                # 纯SVG
                html = f'<html><body style="margin:0;background:transparent">{svg_or_html}</body></html>'
                page.set_content(html)
            
            page.wait_for_timeout(500)
            
            # 截SVG区域
            svg_el = page.query_selector('svg')
            if svg_el:
                screenshot = svg_el.screenshot()
            else:
                screenshot = page.screenshot()
            
            b.close()
            return base64.b64encode(screenshot).decode()
    except Exception as e:
        print(f"[V3视觉] 渲染失败: {e}")
        return None


# ═══ 视觉评价 ═══
def vision_evaluate(b64_image: str, concept: str, target_style: str = '') -> dict:
    """用视觉模型看图评价"""
    import urllib.request
    
    if target_style:
        prompt = f"""This image should be a {concept}. Style: {target_style}.

Answer these questions concisely:
1. Does this look like a {concept}? (YES/NO)
2. Score 1-10: ___
3. What is wrong? List specific issues.
4. What to fix? List specific fixes."""
    else:
        prompt = f"""This image should be a {concept}.

Answer concisely:
1. Does this look like a {concept}? (YES/NO)
2. Score 1-10: ___
3. Issues (list specific problems):
4. Fixes (list what to change):"""
    
    req_body = json.dumps({
        'model': VISION_MODEL,
        'prompt': prompt,
        'images': [b64_image],
        'stream': False,
        'options': {'temperature': 0.3, 'num_predict': 500}
    }).encode()
    
    try:
        req = urllib.request.Request(OLLAMA_URL, req_body, {
            'Content-Type': 'application/json'
        })
        resp = urllib.request.urlopen(req, timeout=120)
        data = json.loads(resp.read())
        response_text = data.get('response', '')
        
        # 尝试提取JSON
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        # 纯文本解析
        return {
            'looks_like': 'yes' in response_text.lower() and 'looks like' in response_text.lower(),
            'score': 5,
            'issues': [response_text],
            'fixes': [],
            'summary': response_text[:200],
            'raw': response_text
        }
    except Exception as e:
        return {'error': str(e), 'looks_like': False, 'score': 0, 'issues': [], 'fixes': []}


# ═══ V3 视觉闭环 ═══
class V3VisionLoop:
    """
    V3 视觉闭环：
    SVG生成 → 渲染PNG → 视觉模型看图 → 评价 → 不够好就修正 → 循环
    """
    
    def __init__(self, generate_fn=None, max_rounds=3, min_score=7):
        self.generate_fn = generate_fn  # V3生成函数
        self.max_rounds = max_rounds
        self.min_score = min_score
        self.history = []
    
    def run(self, concept: str, style: str = '', initial_svg: str = None) -> dict:
        """运行完整视觉闭环"""
        
        current_svg = initial_svg
        if not current_svg and self.generate_fn:
            print(f"[V3视觉] 第0轮: 初始生成 '{concept}'")
            current_svg = self.generate_fn(concept)
        
        if not current_svg:
            return {'error': '没有初始SVG', 'success': False}
        
        for round_num in range(1, self.max_rounds + 1):
            print(f"\n[V3视觉] === 第{round_num}轮 ===")
            
            # Step 1: 渲染
            print(f"[V3视觉] 渲染PNG...")
            b64 = svg_to_png_base64(current_svg)
            if not b64:
                print(f"[V3视觉] 渲染失败，用坐标验证")
                # 回退到坐标验证
                from v3_self_refine import V3CoordinateValidator
                validator = V3CoordinateValidator()
                coord_result = validator.validate(current_svg)
                issues = [i['msg'] for i in coord_result['issues']]
                score = 7 if coord_result['valid'] else 4
            else:
                # Step 2: 视觉模型评价
                print(f"[V3视觉] 视觉模型评价...")
                result = vision_evaluate(b64, concept, style)
                
                if 'error' in result:
                    print(f"[V3视觉] 视觉模型错误: {result['error']}")
                    self.history.append({'round': round_num, 'error': result['error']})
                    break
                
                score = result.get('score', 5)
                issues = result.get('issues', [])
                fixes = result.get('fixes', [])
                looks_like = result.get('looks_like', False)
                
                print(f"[V3视觉] 评分: {score}/10 | 像吗: {looks_like} | 问题: {len(issues)}个")
                for issue in issues[:3]:
                    print(f"  - {issue[:80]}")
                
                self.history.append({
                    'round': round_num,
                    'score': score,
                    'looks_like': looks_like,
                    'issues': issues,
                    'fixes': fixes,
                })
            
            # Step 3: 判断是否通过
            if score >= self.min_score:
                print(f"[V3视觉] 通过! (评分{score} >= {self.min_score})")
                return {
                    'success': True,
                    'final_svg': current_svg,
                    'history': self.history,
                    'rounds': round_num,
                    'final_score': score
                }
            
            # Step 4: 修正
            print(f"[V3视觉] 评分不够({score} < {self.min_score})，修正中...")
            fixed = self._apply_vision_fixes(current_svg, issues, fixes, concept)
            if fixed and fixed != current_svg:
                current_svg = fixed
            else:
                print(f"[V3视觉] 无法自动修正，停止")
                break
        
        return {
            'success': self.history[-1].get('score', 0) >= self.min_score if self.history else False,
            'final_svg': current_svg,
            'history': self.history,
            'rounds': len(self.history),
            'final_score': self.history[-1].get('score', 0) if self.history else 0,
            'note': '未达到目标分数' if not (self.history and self.history[-1].get('score', 0) >= self.min_score) else ''
        }
    
    def _apply_vision_fixes(self, svg: str, issues: list, fixes: list, concept: str) -> str:
        """根据视觉反馈修正SVG"""
        # 策略1: 用修正建议生成新版本
        if fixes and self.generate_fn:
            fix_prompt = f"""The current {concept} SVG has these issues:
{chr(10).join(f'- {f}' for f in fixes[:5])}

Regenerate the SVG with these issues fixed. Do NOT include the issues. Make it look correct.
Return ONLY the SVG code in ```svg ``` block."""
            try:
                new_svg = self.generate_fn(fix_prompt)
                if new_svg and len(new_svg) > 100:
                    return new_svg
            except:
                pass
        
        # 策略2: 坐标自动修正（回退方案）
        from v3_self_refine import V3CoordinateValidator, V3AutoFixer
        validator = V3CoordinateValidator()
        fixer = V3AutoFixer()
        coord_result = validator.validate(svg)
        if coord_result['issues']:
            return fixer.apply_fixes(svg, coord_result['issues'])
        
        return svg


# ═══ 挂载到 V3 ═══
def mount_vision(engine):
    """给V3装上视觉能力"""
    
    # 把生成函数包装一下
    def v3_generate(concept_prompt):
        """用V3的多模态管线生成SVG"""
        # 尝试用inject_knowledge + visualize
        if hasattr(engine, 'inject_knowledge'):
            engine.inject_knowledge(concept_prompt)
        if hasattr(engine, 'visualize'):
            result = engine.visualize(concept_prompt)
            if result:
                return result
        
        # 回退：用draw方法
        if hasattr(engine, 'draw'):
            return engine.draw(concept_prompt)
        
        return None
    
    loop = V3VisionLoop(generate_fn=v3_generate, max_rounds=3, min_score=7)
    
    def v3_see_and_refine(concept, style=''):
        """V3 看自己的生成并打磨"""
        print(f"[V3视觉] 启动视觉闭环: '{concept}'")
        
        # 先生成初版
        initial = v3_generate(concept)
        if not initial:
            return {'error': 'V3生成失败', 'success': False}
        
        # 走视觉闭环
        result = loop.run(concept=concept, style=style, initial_svg=initial)
        
        # 保存最终版
        if result.get('final_svg'):
            out_dir = Path(ROOT) / 'canvas_outputs'
            out_dir.mkdir(exist_ok=True)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            fp = out_dir / f'v3_vision_{concept[:10]}_{ts}.svg'
            fp.write_text(result['final_svg'], encoding='utf-8')
            result['saved_to'] = str(fp)
        
        return result
    
    engine.see_and_refine = v3_see_and_refine
    engine._vision_loop = loop
    engine._vision_model = VISION_MODEL
    
    print(f"[V3] 视觉已挂载: see_and_refine() via {VISION_MODEL}")
    return engine


# ═══ 自检 ═══
if __name__ == '__main__':
    print("=" * 60)
    print("  V3 视觉馈送 — 自检")
    print("=" * 60)
    
    # 检查Ollama
    import urllib.request
    try:
        r = urllib.request.urlopen('http://localhost:11434/api/tags', timeout=5)
        models = json.loads(r.read())
        vision_models = [m['name'] for m in models.get('models', []) if 'vision' in m['name'] or 'llava' in m['name'] or 'moondream' in m['name']]
        print(f"可用视觉模型: {vision_models}")
    except Exception as e:
        print(f"Ollama不可用: {e}")
        vision_models = []
    
    if vision_models:
        print(f"\n将使用: {VISION_MODEL}")
        
        # 测试渲染+评价
        test_svg = '''<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
  <circle cx="100" cy="100" r="80" fill="#E8C9A0" stroke="#C4A882" stroke-width="2"/>
  <circle cx="70" cy="85" r="8" fill="#1a1a1a"/>
  <circle cx="130" cy="85" r="8" fill="#1a1a1a"/>
  <ellipse cx="100" cy="110" rx="10" ry="7" fill="#1a1a1a"/>
</svg>'''
        
        b64 = svg_to_png_base64(test_svg, 200, 200)
        if b64:
            print(f"渲染PNG: {len(b64)} chars base64")
            print("发送给视觉模型...")
            result = vision_evaluate(b64, 'dog face')
            if 'error' not in result:
                print(f"评分: {result.get('score', '?')}/10")
                print(f"像吗: {result.get('looks_like', '?')}")
                print(f"问题: {len(result.get('issues', []))}个")
            else:
                print(f"错误: {result['error']}")
        else:
            print("渲染失败")
    
    print("\nV3VisionLoop 就绪 | mount_vision() 可用")
