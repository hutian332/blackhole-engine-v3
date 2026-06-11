"""
v3_learn.py — V3 例子学习管线
概念路由 → 匹配最佳例子 → 注入知识 → 照着生成

殷竺欣 独家原创 | 2026-06-11
"""
import json, os, sys
from pathlib import Path
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
EXAMPLES_DIR = os.path.join(ROOT, 'examples')

# ═══ 例子库注册表 ═══
EXAMPLE_REGISTRY = {
    'desktop_pet': {
        'file': 'frenchie_pet_gold.html',
        'desc': '法斗桌宠金标版 — 透明悬浮窗/6状态动画/拖动/提醒',
        'domains': ['桌宠', '动画', '动物', 'UI', 'HTML'],
        'style': 'cute_interactive',
        'quality': 'gold',
    },
    'building_svg': {
        'file': 'building_svg_gold.svg',
        'desc': '建筑SVG金标版 — 两点透视/窗户均分/屋顶/街道',
        'domains': ['建筑', 'SVG', '风景'],
        'style': 'architectural',
        'quality': 'gold',
    },
    'figure_portrait': {
        'file': 'figure_portrait_gold.svg',
        'desc': '人物肖像SVG金标版 — 比例/面部/光影',
        'domains': ['人物', 'SVG', '肖像'],
        'style': 'portrait',
        'quality': 'gold',
    },
    'ui_panel': {
        'file': 'ui_panel_gold.html',
        'desc': '管理面板金标版 — 深色主题/卡片布局/表单',
        'domains': ['UI', 'HTML', '面板'],
        'style': 'dark_modern',
        'quality': 'gold',
    },
}


def load_example(example_id: str) -> dict:
    """加载一个金标例子"""
    if example_id not in EXAMPLE_REGISTRY:
        return None
    info = EXAMPLE_REGISTRY[example_id]
    fp = os.path.join(EXAMPLES_DIR, info['file'])
    if not os.path.exists(fp):
        return None
    content = open(fp, encoding='utf-8').read()
    return {
        'id': example_id,
        'meta': info,
        'content': content,
        'chars': len(content)
    }


def match_examples(concepts: list, max_examples: int = 3) -> list:
    """根据概念域匹配最佳例子"""
    scored = []
    for eid, info in EXAMPLE_REGISTRY.items():
        score = 0
        for c in concepts:
            if c in info['domains']:
                score += 5  # 精确匹配
            for d in info['domains']:
                if c.lower() in d.lower() or d.lower() in c.lower():
                    score += 2
        if score > 0:
            fp = os.path.join(EXAMPLES_DIR, info['file'])
            if os.path.exists(fp):
                scored.append((eid, score, info))
    
    scored.sort(key=lambda x: -x[1])
    return [{'id': s[0], 'meta': s[2]} for s in scored[:max_examples]]


def build_few_shot_prompt(user_input: str, concept: dict, knowledge: dict, 
                          examples: list) -> str:
    """构建 few-shot 提示词：例子 + 知识 + 要求"""
    
    example_text = ""
    for i, ex in enumerate(examples):
        content = load_example(ex['id'])
        if content:
            example_text += f"""
### 金标范例{i+1}: {ex['meta']['desc']}
```{ex['meta']['file'].split('.')[-1]}
{content['content'][:3000]}
```
"""
    
    knowledge_text = ""
    for k in knowledge.get('chunks', [])[:3]:
        knowledge_text += f"\n- {k['source']}: {k['content'][:800]}\n"
    
    prompt = f"""你是V3概念引擎的生成层。请**参照以下金标范例的质量和风格**，生成新的代码。

【参考范例 — 照着这个质量做】
{example_text if example_text else '(无匹配范例，使用知识库)'}

【知识库参考】
{knowledge_text if knowledge_text else '(无匹配知识)'}

【任务】
{user_input}

【要求】
- 代码质量和结构参照金标范例
- 完整的、可直接运行的代码
- 代码放在 ``` 标记内
- 充分利用知识库中的画法技巧
- 概念匹配: {concept.get('subjects', [])}
- 风格: {concept.get('style', 'sketch')}
"""
    return prompt


class V3LearnPipeline:
    """V3 例子学习管线：路由→匹配例子→注入知识→few-shot生成"""
    
    def __init__(self, generate_fn=None):
        self.generate_fn = generate_fn
        self.examples_loaded = 0
    
    def process(self, user_input: str, output_format: str = 'html') -> dict:
        """完整管线"""
        # 延迟导入避免循环
        from v3_multimodal import parse_visual_concept, inject_knowledge
        from blackhole_v3_engine import BlackholeV3Engine
        
        engine = BlackholeV3Engine()
        try:
            engine.bootstrap(goal='learn', identity='V3')
        except RuntimeError:
            pass
        
        # Step 1: 概念解析
        concept = parse_visual_concept(user_input)
        
        # Step 2: 匹配例子
        examples = match_examples(concept.get('concepts', []))
        
        # Step 3: 知识注入
        knowledge = inject_knowledge(engine, concept.get('concepts', []))
        
        # Step 4: 构建 few-shot 提示词
        prompt = build_few_shot_prompt(user_input, concept, knowledge, examples)
        
        result = {
            'concept': concept,
            'examples_matched': [e['id'] for e in examples],
            'knowledge_sources': knowledge.get('sources', []),
            'prompt': prompt,
            'output': None,
            'error': None
        }
        
        # Step 5: 生成
        if self.generate_fn:
            try:
                result['output'] = self.generate_fn(prompt)
            except Exception as e:
                result['error'] = str(e)
        
        return result


# ═══ 自检 ═══
if __name__ == '__main__':
    print("=" * 60)
    print("  V3 例子学习管线 — 自检")
    print("=" * 60)
    
    # 列出可用的例子
    available = []
    for eid, info in EXAMPLE_REGISTRY.items():
        fp = os.path.join(EXAMPLES_DIR, info['file'])
        exists = os.path.exists(fp)
        available.append((eid, info['desc'], exists))
        mark = '[OK]' if exists else '[MISS]'
        print(f"  {mark} {eid}: {info['desc'][:50]}")
    
    # 测试匹配
    print("\n[匹配测试] 概念=['桌宠', '动画']")
    matches = match_examples(['桌宠', '动画'])
    print(f"  匹配: {[m['id'] for m in matches]}")
    
    print("\n[匹配测试] 概念=['建筑', 'SVG']")
    matches = match_examples(['建筑', 'SVG'])
    print(f"  匹配: {[m['id'] for m in matches]}")
    
    print("\n[匹配测试] 概念=['人物']")
    matches = match_examples(['人物'])
    print(f"  匹配: {[m['id'] for m in matches]}")
    
    print(f"\n  例子库: {len(available)} 个注册 | {sum(1 for _,_,e in available if e)} 个可用")
