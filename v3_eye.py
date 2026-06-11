"""
v3_eye.py — 把视觉模型拆成零件，自己实现能做的部分

视觉模型在"看图评价"时做了什么？拆成8个能力：
1. 对象识别 → "这是法斗吗？"       → 模板匹配
2. 部位定位 → "耳朵在哪？"         → SVG坐标分析（已做）
3. 比例检查 → "身体太窄？"         → 数学计算（已做）
4. 风格判断 → "卡通还是写实？"     → 需视觉模型 / 用户
5. 审美评价 → "好看吗？"           → 需视觉模型 / 用户
6. 异常检测 → "腿断了？"           → 连通性分析
7. 完整性   → "少了尾巴？"         → 元素计数
8. 色彩和谐 → "配色冲突？"         → 色彩理论

4和5需要真视觉模型。1、2、3、6、7、8可以代码实现。

殷竺欣 独家原创 | 2026-06-11 01:15 GMT+8
"""
import re, json, os, math
from pathlib import Path
from collections import Counter
from dataclasses import dataclass, field

ROOT = os.path.dirname(os.path.abspath(__file__))

# ═══ 色彩理论 ═══
class ColorHarmony:
    """判断配色是否和谐"""
    
    @staticmethod
    def hex_to_rgb(h):
        h = h.lstrip('#')
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    
    @staticmethod
    def rgb_to_hsl(r, g, b):
        r, g, b = r/255, g/255, b/255
        mx, mn = max(r, g, b), min(r, g, b)
        d = mx - mn
        l = (mx + mn) / 2
        if d == 0:
            h = s = 0
        else:
            s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
            if mx == r:
                h = ((g - b) / d + (6 if g < b else 0)) / 6
            elif mx == g:
                h = ((b - r) / d + 2) / 6
            else:
                h = ((r - g) / d + 4) / 6
        return h * 360, s * 100, l * 100
    
    @staticmethod
    def check_palette(colors_hex: list) -> dict:
        """检查一组颜色是否和谐"""
        if len(colors_hex) < 2:
            return {'harmonious': True, 'issues': []}
        
        issues = []
        hsls = []
        for c in colors_hex:
            try:
                rgb = ColorHarmony.hex_to_rgb(c)
                hsls.append(ColorHarmony.rgb_to_hsl(*rgb))
            except:
                continue
        
        if len(hsls) < 2:
            return {'harmonious': True, 'issues': []}
        
        # 检查饱和度差距（不应同时用极高饱和和极低饱和）
        saturations = [h[1] for h in hsls]
        if max(saturations) - min(saturations) > 60:
            issues.append('饱和度差距过大，部分颜色太鲜艳、部分太灰')
        
        # 检查是否有冲突色（补色且高饱和）  
        for i in range(len(hsls)):
            for j in range(i+1, len(hsls)):
                h_diff = abs(hsls[i][0] - hsls[j][0])
                h_diff = min(h_diff, 360 - h_diff)
                if 150 < h_diff < 210 and hsls[i][1] > 70 and hsls[j][1] > 70:
                    issues.append(f'冲突色: hue {hsls[i][0]:.0f} vs {hsls[j][0]:.0f} (补色+高饱和)')
        
        return {
            'harmonious': len(issues) == 0,
            'issues': issues,
            'colors': len(colors_hex),
            'saturation_range': f'{min(saturations):.0f}-{max(saturations):.0f}'
        }


# ═══ 对象模板 ═══
class ObjectTemplate:
    """检查'像不像'某类对象——通过结构特征匹配"""
    
    FRENCHIE = {
        'name': '法斗',
        'required_elements': [
            {'type': 'ellipse', 'min_rx': 60, 'max_rx': 120, 'hint': '身体椭圆(宽>高)'},
            {'type': 'ellipse', 'min_rx': 30, 'max_rx': 55, 'hint': '脸椭圆'},
            {'type': 'ellipse', 'min_rx': 5, 'max_rx': 15, 'hint': '鼻子'},
            {'type': 'path', 'min_count': 2, 'hint': '耳朵(至少2个path)'},
        ],
        'expected_leg_count': 4,
        'expected_eye_count': 2,
        'body_ratio': (1.3, 2.1),  # 宽/高
        'head_position': 'upper_body',  # 头在身体上半部
    }
    
    BUILDING = {
        'name': '建筑',
        'required_elements': [
            {'type': 'rect', 'min_count': 1, 'hint': '主体矩形'},
        ],
        'expected_roof': True,
        'expected_windows': 2,
    }
    
    @classmethod
    def match(cls, elements: list, template_name: str) -> dict:
        """检查元素列表是否匹配模板"""
        template = getattr(cls, template_name.upper(), None)
        if not template:
            return {'match': False, 'reason': f'无模板: {template_name}'}
        
        missing = []
        extras = []
        score = 10
        
        # 检查必需元素
        for req in template.get('required_elements', []):
            count = sum(1 for el in elements 
                       if el.get('type') == req['type'] 
                       and req.get('min_rx', 0) <= el.get('rx', 0) <= req.get('max_rx', 999))
            
            min_count = req.get('min_count', 1)
            if count < min_count:
                missing.append(req['hint'])
                score -= 2
        
        # 检查特征比例
        if 'body_ratio' in template:
            bodies = [el for el in elements if el.get('type') == 'ellipse' and el.get('rx', 0) > 60]
            if bodies:
                body = max(bodies, key=lambda b: b['rx'] * b['ry'])
                ratio = body['rx'] / max(body['ry'], 1)
                lo, hi = template['body_ratio']
                if not (lo <= ratio <= hi):
                    score -= 1
        
        # 检查腿
        if 'expected_leg_count' in template:
            legs = [el for el in elements if el.get('type') == 'ellipse' 
                   and 10 < el.get('rx', 0) < 25 and 15 < el.get('ry', 0) < 35]
            if len(legs) < template['expected_leg_count']:
                missing.append(f'腿(找到{len(legs)}/{template["expected_leg_count"]})')
                score -= 1
        
        # 检查眼睛
        if 'expected_eye_count' in template:
            eyes = [el for el in elements if el.get('type') == 'ellipse'
                   and 5 < el.get('rx', 0) < 15 and 5 < el.get('ry', 0) < 15
                   and '1a1a1a' in el.get('fill', '')]
            if len(eyes) < template['expected_eye_count']:
                missing.append(f'眼睛(找到{len(eyes)}/{template["expected_eye_count"]})')
                score -= 1
        
        return {
            'match': score >= 5,
            'score': max(0, score),
            'template': template['name'],
            'missing': missing,
            'extras': extras,
        }


# ═══ 连通性分析 ═══
class ConnectivityAnalyzer:
    """检查元素是否'漂浮'（不与其他元素连接）"""
    
    @staticmethod
    def check(elements: list) -> dict:
        """检查各元素是否有重叠/连接"""
        floating = []
        
        # 找所有有位置信息的元素
        positioned = []
        for i, el in enumerate(elements):
            if el.get('type') == 'ellipse':
                positioned.append({
                    'idx': i,
                    'cx': el.get('cx', 0), 'cy': el.get('cy', 0),
                    'rx': el.get('rx', 0), 'ry': el.get('ry', 0),
                    'type': 'ellipse'
                })
        
        if len(positioned) < 2:
            return {'floating': [], 'all_connected': True}
        
        # 构建重叠图
        n = len(positioned)
        connected = [False] * n
        connected[0] = True  # 从身体开始
        
        for iteration in range(3):  # BFS
            for i in range(n):
                if not connected[i]:
                    continue
                for j in range(n):
                    if connected[j]:
                        continue
                    # 检查重叠
                    a, b = positioned[i], positioned[j]
                    dx = abs(a['cx'] - b['cx'])
                    dy = abs(a['cy'] - b['cy'])
                    if dx < (a['rx'] + b['rx']) * 0.8 and dy < (a['ry'] + b['ry']) * 0.8:
                        connected[j] = True
        
        floating = [positioned[i] for i in range(n) if not connected[i]]
        
        return {
            'floating': [f'元素{c["idx"]}({c["type"]}) at ({c["cx"]:.0f},{c["cy"]:.0f}) 漂浮' for c in floating],
            'all_connected': len(floating) == 0,
            'float_count': len(floating)
        }


# ═══ 完整性检查 ═══
class CompletenessChecker:
    """检查是否缺了应该有的部位"""
    
    @staticmethod
    def check(elements: list, concept: str) -> dict:
        """根据概念检查元素完整性"""
        checks = {
            'dog': ['身体', '头/脸', '耳朵', '眼睛', '鼻子', '嘴', '腿', '尾巴'],
            'building': ['主体', '屋顶', '窗户', '门'],
            'person': ['头', '身体', '手臂', '腿', '眼睛', '嘴'],
            'frenchie': ['宽体', '扁脸', '蝙蝠耳', '大黑眼', '黑鼻', 'W嘴', '短腿', '锥尾'],
        }
        
        concept_lower = concept.lower()
        for key in checks:
            if key in concept_lower:
                expected = checks[key]
                break
        else:
            return {'complete': True, 'missing': [], 'note': 'unknown concept'}
        
        # 按元素类型统计
        has_ellipse = any(el.get('type') == 'ellipse' for el in elements)
        has_path = any(el.get('type') == 'path' for el in elements)
        has_rect = any(el.get('type') == 'rect' for el in elements)
        
        missing = []
        
        # 简单启发式
        ellipse_count = sum(1 for el in elements if el.get('type') == 'ellipse')
        path_count = sum(1 for el in elements if el.get('type') == 'path')
        
        if ellipse_count < 5:
            missing.append('元素太少，可能缺多个部位')
        if path_count < 2 and '蝙蝠耳' in expected:
            missing.append('可能缺少耳朵(path)')
        
        return {
            'complete': len(missing) == 0,
            'missing': missing,
            'expected': expected,
            'found_ellipses': ellipse_count,
            'found_paths': path_count,
        }


# ═══ 综合视觉分析器（V3的眼睛） ═══
class V3Eye:
    """
    V3 的眼睛——不靠大模型，靠程序化视觉分析
    拆解视觉模型的8个能力，实现能做的6个
    """
    
    def __init__(self):
        self.color_checker = ColorHarmony()
        self.connectivity = ConnectivityAnalyzer()
        self.completeness = CompletenessChecker()
    
    def analyze(self, svg_text: str, concept: str = '') -> dict:
        """完整分析SVG"""
        elements = self._parse_elements(svg_text)
        
        results = {
            'concept': concept,
            'total_elements': len(elements),
            'checks': {}
        }
        
        # 1. 对象识别（模板匹配）
        if concept:
            template_result = ObjectTemplate.match(elements, concept)
            results['checks']['template_match'] = template_result
        
        # 2. 部位定位（坐标分析）
        from v3_self_refine import V3CoordinateValidator
        validator = V3CoordinateValidator()
        coord_result = validator.validate(svg_text)
        results['checks']['coordinates'] = {
            'valid': coord_result['valid'],
            'issues': coord_result['issues'],
            'issue_count': coord_result['issue_count']
        }
        
        # 3. 连通性
        conn = self.connectivity.check(elements)
        results['checks']['connectivity'] = conn
        
        # 4. 完整性
        comp = self.completeness.check(elements, concept)
        results['checks']['completeness'] = comp
        
        # 5. 色彩
        colors = self._extract_colors(svg_text)
        if colors:
            harmony = self.color_checker.check_palette(colors)
            results['checks']['colors'] = {
                'palette': colors[:10],
                'harmony': harmony
            }
        
        # 6. 汇总
        all_issues = []
        for check_name, check_result in results['checks'].items():
            if isinstance(check_result, dict):
                if 'issues' in check_result and isinstance(check_result['issues'], list):
                    all_issues.extend([f"[{check_name}] {str(i)}" for i in check_result['issues']])
                if 'missing' in check_result and isinstance(check_result['missing'], list):
                    all_issues.extend([f"[{check_name}] 缺失: {m}" for m in check_result['missing']])
        
        results['all_issues'] = all_issues
        results['issue_count'] = len(all_issues)
        
        # 综合评分
        score = 10
        score -= results['checks'].get('coordinates', {}).get('issue_count', 0) * 0.5
        if not results['checks'].get('connectivity', {}).get('all_connected', True):
            score -= results['checks']['connectivity'].get('float_count', 0) * 1
        score -= len(results['checks'].get('completeness', {}).get('missing', [])) * 1
        score -= len(results['checks'].get('colors', {}).get('harmony', {}).get('issues', [])) * 0.5
        
        # 模板匹配影响
        tm = results['checks'].get('template_match', {})
        if tm:
            score = (score + tm.get('score', 5)) / 2
        
        results['score'] = max(0, min(10, round(score, 1)))
        
        return results
    
    def _parse_elements(self, svg_text: str) -> list:
        """解析SVG元素"""
        elements = []
        
        # ellipse
        for m in re.finditer(r'<ellipse\s+([^>]+)/?>', svg_text):
            attrs = self._parse_attrs(m.group(1))
            if 'cx' in attrs:
                elements.append({
                    'type': 'ellipse',
                    'cx': attrs.get('cx', 0), 'cy': attrs.get('cy', 0),
                    'rx': attrs.get('rx', 0), 'ry': attrs.get('ry', 0),
                    'fill': attrs.get('fill', ''),
                    'class': attrs.get('class', ''),
                })
        
        # rect
        for m in re.finditer(r'<rect\s+([^>]+)/?>', svg_text):
            attrs = self._parse_attrs(m.group(1))
            elements.append({
                'type': 'rect',
                'x': attrs.get('x', 0), 'y': attrs.get('y', 0),
                'w': attrs.get('width', 0), 'h': attrs.get('height', 0),
                'fill': attrs.get('fill', ''),
            })
        
        # path
        for m in re.finditer(r'<path\s+([^>]+)/?>', svg_text):
            attrs = self._parse_attrs(m.group(1))
            elements.append({
                'type': 'path',
                'fill': attrs.get('fill', ''),
                'class': attrs.get('class', ''),
            })
        
        # circle
        for m in re.finditer(r'<circle\s+([^>]+)/?>', svg_text):
            attrs = self._parse_attrs(m.group(1))
            elements.append({
                'type': 'circle',
                'cx': attrs.get('cx', 0), 'cy': attrs.get('cy', 0),
                'r': attrs.get('r', 0),
                'fill': attrs.get('fill', ''),
            })
        
        # line
        for m in re.finditer(r'<line\s+([^>]+)/?>', svg_text):
            attrs = self._parse_attrs(m.group(1))
            elements.append({
                'type': 'line',
                'fill': attrs.get('stroke', ''),
            })
        
        return elements
    
    def _parse_attrs(self, attr_str: str) -> dict:
        attrs = {}
        for m in re.finditer(r'(\w+)\s*=\s*"([^"]*)"', attr_str):
            key, val = m.group(1), m.group(2)
            try:
                attrs[key] = float(val)
            except ValueError:
                attrs[key] = val
        return attrs
    
    def _extract_colors(self, svg_text: str) -> list:
        """提取用到的颜色"""
        colors = set()
        for m in re.finditer(r'(?:fill|stroke|stop-color)\s*=\s*"#([0-9a-fA-F]{6})"', svg_text):
            colors.add('#' + m.group(1))
        # 也找var颜色
        for m in re.finditer(r'var\((--[\w-]+)\)', svg_text):
            var_name = m.group(1)
            # 在CSS中找定义
            css_match = re.search(rf'{var_name}\s*:\s*(#[0-9a-fA-F]{{6}})', svg_text)
            if css_match:
                colors.add(css_match.group(1))
        return list(colors)


# ═══ 挂载 ═══
def mount_eye(engine):
    """给V3装上程序化视觉分析"""
    eye = V3Eye()
    
    def v3_eye_analyze(svg_text, concept=''):
        """V3用眼睛分析自己的生成"""
        return eye.analyze(svg_text, concept)
    
    engine.eye_analyze = v3_eye_analyze
    engine._eye = eye
    
    print(f"[V3] 程序化视觉分析已挂载: eye_analyze()")
    print(f"  内含: 模板匹配 + 坐标验证 + 连通性 + 完整性 + 色彩和谐")
    return engine


# ═══ 自检 ═══
if __name__ == '__main__':
    print("=" * 60)
    print("  V3 眼睛 — 拆解视觉模型")
    print("=" * 60)
    
    eye = V3Eye()
    
    # 测试法斗V2
    v2_path = Path(ROOT) / 'frenchie_pet_v3_refined.html'
    if v2_path.exists():
        content = v2_path.read_text(encoding='utf-8')
        svg_match = re.search(r'(<svg[^>]*>.*?</svg>)', content, re.DOTALL)
        svg = svg_match.group(1) if svg_match else content
        
        print("\n分析: frenchie_pet_v3_refined.html")
        result = eye.analyze(svg, 'frenchie')
        
        print(f"综合评分: {result['score']}/10")
        print(f"元素总数: {result['total_elements']}")
        print(f"问题总数: {result['issue_count']}")
        
        for check_name, check in result['checks'].items():
            print(f"\n[{check_name}]")
            if isinstance(check, dict):
                for k, v in check.items():
                    if k != 'issues' and k != 'missing':
                        print(f"  {k}: {v}")
                    elif k == 'issues' and v:
                        for issue in v[:3]:
                            print(f"  ! {str(issue)[:100]}")
                    elif k == 'missing' and v:
                        for m in v[:3]:
                            print(f"  - 缺: {m}")
    
    print("\n" + "=" * 60)
    print("程序化视觉分析可替代视觉模型的能力:")
    print("  [OK] 1.对象识别 → 模板匹配")
    print("  [OK] 2.部位定位 → 坐标分析")
    print("  [OK] 3.比例检查 → 数学计算")
    print("  [NEED MODEL] 4.风格判断 → 需视觉模型/用户")
    print("  [NEED MODEL] 5.审美评价 → 需视觉模型/用户")
    print("  [OK] 6.异常检测 → 连通性分析")
    print("  [OK] 7.完整性   → 元素计数")
    print("  [OK] 8.色彩和谐 → 色彩理论")
    print(f"  自实现: 6/8 | 需模型: 2/8")
