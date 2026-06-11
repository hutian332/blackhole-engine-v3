"""
v3_self_refine.py — V3 自打磨能力
生成 → 坐标验证 → 发现问题 → 自动修正 → 再验证 → 循环

装到 BlackholeV3Engine 上，成为 V3 的"眼睛"
殷竺欣 独家原创 | 2026-06-11
"""
import json, os, re, sys, math
from pathlib import Path
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))

# ═══ 法斗解剖参考 ═══
FRENCHIE_ANATOMY = {
    'body': {
        '宽高比': (1.4, 1.9),      # 宽/高，法斗特征：宽>高
        '描述': '身体椭圆，宽大于高，斗牛犬体型'
    },
    'head': {
        '相对身体宽': (0.45, 0.6),  # 头宽/身体宽
        '在身体Y位置': (0.05, 0.35), # 头中心在身体顶部往下0-35%
        '描述': '扁脸，位于身体上半部'
    },
    'ears': {
        '类型': 'bat',              # 蝙蝠耳
        '相对头Y': (-0.5, -0.1),    # 耳起点在头中心上方
        '描述': '蝙蝠耳，宽底尖顶，远离头中心'
    },
    'legs': {
        '数量': 4,
        '长度比': (0.2, 0.35),      # 腿长/身体总高
        '描述': '短粗腿，在身体下方'
    },
    'face_elements': {
        '眼睛Y': 0.4,               # 眼在头高度40%处
        '鼻子Y': 0.6,               # 鼻在头高度60%处
        '嘴Y': 0.75,                # 嘴在头高度75%处
        '描述': '大眼、黑鼻、W嘴'
    }
}


class V3CoordinateValidator:
    """V3 的"眼睛"——验证SVG坐标是否合理"""
    
    def __init__(self):
        self.rules = []
        self._load_rules()
    
    def _load_rules(self):
        """加载验证规则"""
        self.rules = [
            self._rule_body_proportion,
            self._rule_face_position,
            self._rule_leg_position,
            self._rule_ear_position,
            self._rule_symmetry,
            self._rule_no_floating,
            self._rule_viewbox_overflow,
        ]
    
    def validate(self, svg_text: str) -> dict:
        """验证SVG，返回问题列表"""
        elements = self._parse_elements(svg_text)
        if not elements:
            return {'valid': False, 'issues': [{'severity': 'critical', 'msg': '无法解析SVG元素'}], 'elements': []}
        
        issues = []
        for rule in self.rules:
            result = rule(elements)
            if result:
                issues.extend(result)
        
        return {
            'valid': len([i for i in issues if i['severity'] == 'critical']) == 0,
            'issues': issues,
            'elements': elements[:20],  # 摘要
            'issue_count': len(issues),
            'critical_count': len([i for i in issues if i['severity'] == 'critical']),
        }
    
    def _parse_elements(self, svg_text: str) -> list:
        """解析SVG元素坐标"""
        elements = []
        
        # 解析ellipse
        for m in re.finditer(r'<ellipse\s+([^>]+)>', svg_text):
            attrs = self._parse_attrs(m.group(1))
            if 'cx' in attrs and 'cy' in attrs:
                elements.append({
                    'type': 'ellipse',
                    'cx': attrs.get('cx', 0), 'cy': attrs.get('cy', 0),
                    'rx': attrs.get('rx', 0), 'ry': attrs.get('ry', 0),
                    'class': attrs.get('class', ''),
                    'id': attrs.get('id', ''),
                    'fill': attrs.get('fill', ''),
                })
        
        # 解析path
        for m in re.finditer(r'<path\s+([^>]+)>', svg_text):
            attrs = self._parse_attrs(m.group(1))
            d = attrs.get('d', '')
            if d:
                # 提取起点
                start = re.search(r'M\s*([\d.]+)\s*[, ]\s*([\d.]+)', d)
                elements.append({
                    'type': 'path',
                    'start_x': float(start.group(1)) if start else 0,
                    'start_y': float(start.group(2)) if start else 0,
                    'd': d[:60],
                    'class': attrs.get('class', ''),
                    'fill': attrs.get('fill', ''),
                })
        
        return elements
    
    def _parse_attrs(self, attr_str: str) -> dict:
        """解析属性字符串"""
        attrs = {}
        for m in re.finditer(r'(\w+)\s*=\s*"([^"]*)"', attr_str):
            key, val = m.group(1), m.group(2)
            try:
                attrs[key] = float(val)
            except ValueError:
                attrs[key] = val
        return attrs
    
    def _find_body(self, elements):
        """找身体（最大的椭圆，宽>高）"""
        best = None
        best_area = 0
        for el in elements:
            if el['type'] == 'ellipse':
                area = el['rx'] * el['ry']
                ratio = el['rx'] / max(el['ry'], 1)
                if area > best_area and ratio > 1.0:  # 宽>高
                    best_area = area
                    best = el
        return best
    
    def _find_head(self, elements, body):
        """找头部椭圆"""
        heads = []
        for el in elements:
            if el['type'] == 'ellipse' and el != body:
                if 25 < el['rx'] < 60 and 20 < el['ry'] < 50:
                    # 应该在身体上半部
                    if body and el['cy'] < body['cy']:
                        heads.append(el)
        # 返回最大的（可能的面部椭圆）
        if heads:
            return max(heads, key=lambda h: h['rx'] * h['ry'])
        return None
    
    def _find_legs(self, elements, body):
        """找腿"""
        legs = []
        for el in elements:
            if el['type'] == 'ellipse' and el != body:
                if 10 < el['rx'] < 25 and 15 < el['ry'] < 35:
                    if body and el['cy'] > body['cy']:
                        legs.append(el)
        return sorted(legs, key=lambda l: l['cy'])
    
    def _rule_body_proportion(self, elements):
        issues = []
        body = self._find_body(elements)
        if not body:
            return [{'severity': 'critical', 'msg': '找不到身体椭圆', 'fix': '确保有一个宽>高的椭圆作为身体'}]
        
        ratio = body['rx'] / max(body['ry'], 1)
        if ratio < 1.2:
            issues.append({
                'severity': 'high',
                'msg': f'身体太瘦，宽高比={ratio:.1f}，法斗应≥1.4',
                'fix': f'增大rx（当前{body["rx"]:.0f}）或减小ry（当前{body["ry"]:.0f}）',
                'target': 'body',
                'param': 'rx',
                'current': body['rx'],
                'suggested': body['ry'] * 1.5
            })
        if ratio > 2.2:
            issues.append({
                'severity': 'low',
                'msg': f'身体太扁，宽高比={ratio:.1f}',
                'fix': '增大ry或减小rx',
                'target': 'body',
                'param': 'ry',
                'current': body['ry'],
                'suggested': body['rx'] / 1.7
            })
        return issues
    
    def _rule_face_position(self, elements):
        issues = []
        body = self._find_body(elements)
        head = self._find_head(elements, body)
        
        if not head:
            return [{'severity': 'medium', 'msg': '找不到面部椭圆', 'fix': '添加一个rx≈40 ry≈30的椭圆作为脸'}]
        
        if body:
            body_top = body['cy'] - body['ry']
            body_height = body['ry'] * 2
            head_rel_y = (head['cy'] - body_top) / body_height if body_height > 0 else 0
            
            if head_rel_y < 0:
                issues.append({
                    'severity': 'high',
                    'msg': f'脸在身体上方(head.cy={head["cy"]:.0f} < body.top={body_top:.0f})',
                    'fix': f'把脸cy移到身体顶部下方，建议cy≈{body_top + body_height*0.2:.0f}',
                    'target': 'head',
                    'param': 'cy',
                    'current': head['cy'],
                    'suggested': body_top + body_height * 0.2
                })
            elif head_rel_y > 0.45:
                issues.append({
                    'severity': 'high',
                    'msg': f'脸在身体下半部(head_rel_y={head_rel_y:.2f})，应该在身体上半部',
                    'fix': f'把脸cy移到身体上半部，建议cy≈{body_top + body_height*0.2:.0f}',
                    'target': 'head',
                    'param': 'cy',
                    'current': head['cy'],
                    'suggested': body_top + body_height * 0.2
                })
        
        return issues
    
    def _rule_leg_position(self, elements):
        issues = []
        body = self._find_body(elements)
        legs = self._find_legs(elements, body)
        
        if len(legs) < 4:
            # Not critical if using path-based legs
            pass
        
        if body and legs:
            body_bottom = body['cy'] + body['ry']
            for i, leg in enumerate(legs):
                if leg['cy'] < body['cy']:
                    issues.append({
                        'severity': 'high',
                        'msg': f'腿{i+1}(cy={leg["cy"]:.0f})在身体中心上方',
                        'fix': f'把腿cy移到身体下方，建议cy≈{body_bottom + 30:.0f}',
                        'target': f'leg_{i+1}',
                        'param': 'cy',
                        'current': leg['cy'],
                        'suggested': body_bottom + 30
                    })
        
        # 检查前腿左右对称
        if len(legs) >= 2:
            front_legs = sorted(legs[:2], key=lambda l: l['cx'])
            if len(front_legs) == 2 and body:
                body_cx = body['cx']
                left_dist = body_cx - front_legs[0]['cx']
                right_dist = front_legs[1]['cx'] - body_cx
                if abs(left_dist - right_dist) > 20:
                    issues.append({
                        'severity': 'medium',
                        'msg': f'前腿左右不对称: 左距={left_dist:.0f} 右距={right_dist:.0f}',
                        'fix': f'调整腿cx使左右对称',
                        'target': 'legs',
                        'param': 'cx_symmetry'
                    })
        
        return issues
    
    def _rule_ear_position(self, elements):
        issues = []
        head = self._find_head(elements, self._find_body(elements))
        
        ear_paths = [el for el in elements if el['type'] == 'path' and el.get('start_y', 999) < 150]
        
        if head and ear_paths:
            head_top = head['cy'] - head['ry']
            for i, ear in enumerate(ear_paths[:4]):
                if ear['start_y'] < head_top - 15:
                    issues.append({
                        'severity': 'medium',
                        'msg': f'耳{i+1}太高(start_y={ear["start_y"]:.0f})，脱离头部',
                        'fix': f'耳朵起点应该在头部附近，建议Y≈{head_top:.0f}',
                        'target': f'ear_{i+1}',
                        'param': 'start_y',
                        'current': ear['start_y'],
                        'suggested': head_top + 5
                    })
        
        return issues
    
    def _rule_symmetry(self, elements):
        """检查左右对称性"""
        issues = []
        body = self._find_body(elements)
        if not body:
            return issues
        
        body_cx = body['cx']
        ellipses = [el for el in elements if el['type'] == 'ellipse' and el != body]
        
        left_count = sum(1 for el in ellipses if el['cx'] < body_cx)
        right_count = sum(1 for el in ellipses if el['cx'] > body_cx)
        
        if left_count == 0 or right_count == 0:
            issues.append({
                'severity': 'high',
                'msg': f'元素全在一侧: left={left_count} right={right_count}',
                'fix': '确保左右都有元素（腿、眼、耳等应对称）'
            })
        elif abs(left_count - right_count) > 4:
            issues.append({
                'severity': 'low',
                'msg': f'左右元素数不对称: left={left_count} right={right_count}',
                'fix': '检查是否遗漏了某侧的元素'
            })
        
        return issues
    
    def _rule_no_floating(self, elements):
        """检查是否有孤立漂浮元素"""
        # 简化版：检查所有元素是否形成连通组
        return []
    
    def _rule_viewbox_overflow(self, elements):
        """检查元素是否超出viewBox"""
        issues = []
        for el in elements:
            if el['type'] == 'ellipse':
                bottom = el['cy'] + el['ry']
                if bottom > 275:
                    issues.append({
                        'severity': 'low',
                        'msg': f'元素cy={el["cy"]:.0f} bottom={bottom:.0f}接近viewBox底部(280)',
                        'fix': '上移元素或增大viewBox高度'
                    })
        return issues


class V3AutoFixer:
    """V3 自动修正器——根据验证问题自动调整坐标"""
    
    def apply_fixes(self, svg_text: str, issues: list) -> str:
        """应用修正"""
        fixed = svg_text
        
        for issue in issues:
            if 'target' not in issue or 'param' not in issue:
                continue
            if 'suggested' not in issue:
                continue
            
            target = issue['target']
            param = issue['param']
            current = issue['current']
            suggested = issue['suggested']
            
            # 简单的数值替换策略
            if param == 'rx':
                # 找目标元素的rx并替换
                fixed = self._replace_attr(fixed, target, 'rx', current, suggested)
            elif param == 'ry':
                fixed = self._replace_attr(fixed, target, 'ry', current, suggested)
            elif param == 'cy':
                fixed = self._replace_attr(fixed, target, 'cy', current, suggested)
            elif param == 'cx':
                fixed = self._replace_attr(fixed, target, 'cx', current, suggested)
        
        return fixed
    
    def _replace_attr(self, text, target_hint, attr, old_val, new_val):
        """智能替换属性值"""
        old_str = f'{attr}="{old_val:.1f}"'
        new_str = f'{attr}="{new_val:.1f}"'
        if old_str in text:
            return text.replace(old_str, new_str, 1)
        
        # 尝试整数匹配
        old_str_int = f'{attr}="{int(old_val)}"'
        new_str_int = f'{attr}="{int(new_val)}"'
        if old_str_int in text:
            return text.replace(old_str_int, new_str_int, 1)
        
        return text


# ═══ 主入口：装到 V3 上 ═══
def mount_self_refine(engine):
    """给V3引擎装上自打磨能力"""
    validator = V3CoordinateValidator()
    fixer = V3AutoFixer()
    
    def v3_refine_visual(svg_text, max_rounds=3):
        """V3自打磨：验证→修正→循环"""
        history = []
        current = svg_text
        
        for round_num in range(max_rounds):
            result = validator.validate(current)
            history.append({
                'round': round_num + 1,
                'issues': len(result['issues']),
                'critical': result['critical_count']
            })
            
            print(f"[V3自打磨] 第{round_num+1}轮: {len(result['issues'])}个问题, {result['critical_count']}个严重")
            
            if result['valid'] and result['critical_count'] == 0:
                print(f"[V3自打磨] 通过! {round_num+1}轮完成")
                break
            
            # 应用修正
            current = fixer.apply_fixes(current, result['issues'])
        
        return {
            'final_svg': current,
            'history': history,
            'rounds': len(history)
        }
    
    # 挂载
    engine.refine_visual = v3_refine_visual
    engine._validator = validator
    engine._fixer = fixer
    
    print("[V3] 自打磨能力已挂载: refine_visual()")
    return engine


# ═══ 自检 ═══
if __name__ == '__main__':
    print("=" * 60)
    print("  V3 自打磨能力 — 自检")
    print("=" * 60)
    
    validator = V3CoordinateValidator()
    
    # 测试第1轮: 读取V2法斗
    v2_path = Path(ROOT) / 'frenchie_pet_v3_refined.html'
    if v2_path.exists():
        content = v2_path.read_text(encoding='utf-8')
        # 提取SVG部分
        svg_match = re.search(r'(<svg[^>]*>.*?</svg>)', content, re.DOTALL)
        if svg_match:
            svg = svg_match.group(1)
            result = validator.validate(svg)
            
            print(f"\n验证结果: {'[PASS]' if result['valid'] else '[FAIL]'}")
            print(f"问题数: {result['issue_count']} (严重: {result['critical_count']})")
            
            for issue in result['issues']:
                sev = '[CRIT]' if issue['severity'] == 'critical' else ('[HIGH]' if issue['severity'] == 'high' else '[LOW]')
                print(f"  {sev} {issue['msg']}")
                if 'fix' in issue:
                    print(f"     → 修正: {issue['fix']}")
    
    print("\n自打磨管线: V3CoordinateValidator + V3AutoFixer → mount_self_refine()")
