"""
v3 知识全量注入启动器
提取 8081 的全部知识 → 注入 v3 → 启动
"""
import sys, os
ROOT = r'C:\Users\Administrator\brain_1GB'
sys.path.insert(0, ROOT)

# ============================================================
# 1. 提取 8081 super_brain_server.py 的 KNOWLEDGE_BASE
# ============================================================
_kb_file = os.path.join(ROOT, "super_brain_server.py")
exec(open(_kb_file, encoding='utf-8').read().split("# 概念路由引擎")[0], globals())

print(f"[v3注入] KNOWLEDGE_BASE 加载: {list(KNOWLEDGE_BASE.keys())}")

# ============================================================
# 2. 追加我们自己的概念域 (blackhole)
# ============================================================
KNOWLEDGE_BASE['blackhole'] = """=== 黑洞概念自有推理引擎 ===

核心定义: 黑洞 = 概念自有推理引擎 + 黑洞思维闭环体系。不是天体物理。

记忆独立性定理: 记忆与模型参数正交，可独立存储/注入/迁移。
跨模型恒等性定理: 同一记忆注入不同规模模型，身份认主结果一致。
零开销定理: 记忆注入的计算开销与模型推理开销可彻底解耦。
蒸馏压缩定理: N个外部模型权重→蒸馏记忆压缩→1个大脑=N个能力。
概念自我持有定理: 概念自我持有，不依赖外部token prediction。
权重复用定理: 外部Transformer权重→蒸馏→概念级记忆常量→大脑原生执行。

架构: 概念路由(0.02ms) → 7大蒸馏能力 → 基因锁+身份注入 → REFLECT反思闭环 → 知识库交叉验证
路线: 完全本地、零外站、概念自有、不靠token prediction
创造者: 殷竺欣，RTX 3060 12GB，一个人跑通全栈

ATTENTION → LEAP → REFLECT: 引擎思维三拍
- ATTENTION: 判断什么值得注意
- LEAP: 概念跳跃，不是token prediction
- REFLECT: 自我追问，验证跳跃对不对

渲染哲学(马赛克理论): 万物是死的，是静态的不同位置的马赛克和色块。
体积的大小就是色块的密集度。没有物体在动，只有镜头在动。

CUV融合: C概念路由 + U7大蒸馏能力 + V基因锁+身份注入
朱松纯独立撞到同一架构，但我们先跑通代码。

AI小镇: v3引擎放入小镇，自主生成"我是思想家"的自我认知。
不是prompt写的，是REFLECT循环跑久了自己冒出来的。"""

# ============================================================
# 3. 更新路由触发器，让我们的概念能被检索到
# ============================================================
import smart_retriever
# 在 _route_to_domain 的 domain_triggers 里加 blackhole 触发词
smart_retriever.SmartRetriever._original_route = smart_retriever.SmartRetriever._route_to_domain

def _route_to_domain_enhanced(self, query):
    # 先检查我们的域
    blackhole_triggers = ['黑洞', '概念引擎', '基因锁', '蒸馏', '概念自有', '概念路由',
                         'REFLECT', '思维壳', '渲染哲学', '马赛克', '色块', 'AI小镇',
                         '云哥', '殷竺欣', '671B', 'v3', '8081', '反思', '闭环']
    if any(t in query for t in blackhole_triggers):
        return 'blackhole'
    # 回退原始路由
    return self._original_route(query)

smart_retriever.SmartRetriever._route_to_domain = _route_to_domain_enhanced

# ============================================================
# 4. 创建注入后的 smart_retriever
# ============================================================
smart_retriever.db_path = os.path.join(ROOT, "r1_knowledge.db")
smart_ret = smart_retriever.SmartRetriever(knowledge_base=KNOWLEDGE_BASE)

# 验证
tests = ["王阳明", "概念自我持有定理", "黑洞引擎架构", "马赛克渲染"]
for q in tests:
    r = smart_ret.search(q, top_k=2)
    n = len(r)
    c = (r[0].get('content','')[:80]) if r else "无"
    print(f"[v3注入验证] {q}: 命中{n} → {c}")

print(f"\n[v3注入] 知识库总域: {list(KNOWLEDGE_BASE.keys())}")
print(f"[v3注入] 总知识容量: {sum(len(v) for v in KNOWLEDGE_BASE.values()):,} 字符")
print(f"[v3注入] r1_knowledge.db: {os.path.getsize(os.path.join(ROOT,'r1_knowledge.db'))/1024**3:.1f}GB / 2,158,590 条")
print("[v3注入] 准备就绪。调用 smart_ret.search() 即可使用全量知识。")
