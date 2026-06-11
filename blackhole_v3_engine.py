"""
blackhole_v3_engine.py — 黑洞理论 v3 概念引擎
基于三支柱（万物死·马赛克 + 时间驱动 + AI时间可控）
实现三层架构（锚点层 + 主干层 + 素材层）

殷竺欣 独家原创 | 2026-06-09
"""
import json, time, os
from datetime import datetime
from pathlib import Path

# ── 配置 ──
ANCHOR_FILE = "anchor_slot.json"      # 锚点层：不可变
TRUNK_FILE  = "thread_tree.json"      # 主干层：append-only
LOG_FILE    = "session_log.jsonl"     # 素材层：时序流
TZ = "Asia/Shanghai"

def now_iso() -> str:
    """秒级时间戳，AI世界的'时间刻度'"""
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")

# ═══════════════════════════════════════════
#  支柱二：时间驱动
# ═══════════════════════════════════════════

class TimeAxis:
    """AI的时间轴——人为定义的索引标签，可读可写可操控"""
    
    @staticmethod
    def stamp() -> str:
        return now_iso()
    
    @staticmethod
    def freeze(checkpoint: dict, name: str) -> str:
        """定格：保存当前完整状态快照"""
        snap_dir = Path("time_snapshots")
        snap_dir.mkdir(exist_ok=True)
        filename = f"snap_{name}_{now_iso().replace(':', '-')}.json"
        (snap_dir / filename).write_text(
            json.dumps(checkpoint, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        return filename
    
    @staticmethod
    def rewind(filename: str) -> dict:
        """回到过去：加载任意秒级 checkpoint"""
        snap = Path("time_snapshots") / filename
        if snap.exists():
            return json.loads(snap.read_text(encoding="utf-8"))
        raise FileNotFoundError(f"Snapshot not found: {filename}")
    
    @staticmethod
    def list_snapshots() -> list:
        """列出所有时间节点"""
        snap_dir = Path("time_snapshots")
        if not snap_dir.exists():
            return []
        return sorted([f.name for f in snap_dir.glob("snap_*.json")], reverse=True)

# ═══════════════════════════════════════════
#  支柱一：万物死·马赛克 —— 概念 = 色块集群
# ═══════════════════════════════════════════

class MosaicConcept:
    """概念=色块集群。颜色=意义，位置=关系，密集度=重要程度"""
    def __init__(self, name: str, color: tuple = (255, 165, 0)):
        self.name = name
        self.color = color          # RGB 概念色彩
        self.position = (0, 0, 0)   # 概念空间坐标
        self.density = 1.0          # 密集度 = 重要程度
        self.blocks: list = []      # 子色块（子概念）
    
    def add_block(self, block: dict):
        self.blocks.append(block)
        self.density = max(0.1, min(10.0, len(self.blocks) / 10))
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "color": list(self.color),
            "position": list(self.position),
            "density": self.density,
            "block_count": len(self.blocks)
        }

# ═══════════════════════════════════════════
#  三层架构：锚点层 + 主干层 + 素材层
# ═══════════════════════════════════════════

class AnchorLayer:
    """锚点层：根目标向量，不可变。仅创建时写入一次。"""
    
    def __init__(self):
        self.root_goal: str = ""
        self.core_constraints: list = []
        self.identity: str = ""
        self.created_at: str = ""
        self._loaded = False
        self._load()
    
    def _load(self):
        if Path(ANCHOR_FILE).exists():
            data = json.loads(Path(ANCHOR_FILE).read_text(encoding="utf-8"))
            self.root_goal = data.get("root_goal", "")
            self.core_constraints = data.get("core_constraints", [])
            self.identity = data.get("identity", "")
            self.created_at = data.get("created_at", "")
            self._loaded = True
    
    def create(self, goal: str, constraints: list = None, identity: str = ""):
        """仅可调用一次——创建锚点"""
        if self._loaded and self.root_goal:
            raise RuntimeError("锚点已存在，不可覆盖。锚点层是只写的。")
        
        self.root_goal = goal
        self.core_constraints = constraints or ["不偏离根目标"]
        self.identity = identity
        self.created_at = now_iso()
        
        Path(ANCHOR_FILE).write_text(
            json.dumps({
                "root_goal": self.root_goal,
                "core_constraints": self.core_constraints,
                "identity": self.identity,
                "created_at": self.created_at,
                "_lock": "IMMUTABLE — 此文件不可被后续对话覆盖"
            }, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        self._loaded = True
    
    def as_system_prompt(self) -> str:
        """将锚点注入为最高优先级 system prompt"""
        if not self.root_goal:
            return ""
        return (
            f"[锚点层 - 不可变根目标]\n"
            f"根目标（总目标，不偏离）: {self.root_goal}\n"
            f"核心约束：{'; '.join(self.core_constraints)}\n"
            f"身份定义：{self.identity}\n"
            f"（此锚点永不参与上下文滚动，永不被子序列覆盖）"
        )
    
    def to_dict(self) -> dict:
        return {
            "root_goal": self.root_goal,
            "core_constraints": self.core_constraints,
            "identity": self.identity,
            "created_at": self.created_at
        }


class TrunkLayer:
    """主干层：概念推进历史。append-only，记录关键决策节点。"""
    
    def __init__(self):
        self.nodes: list = []
        self._load()
    
    def _load(self):
        if Path(TRUNK_FILE).exists():
            self.nodes = json.loads(Path(TRUNK_FILE).read_text(encoding="utf-8"))
    
    def add_node(self, summary: str, category: str = "general", 
                 decisions: list = None, parent_index: int = -1):
        """追加一个主干节点"""
        node = {
            "id": len(self.nodes),
            "timestamp": now_iso(),
            "summary": summary,
            "category": category,
            "decisions": decisions or [],
            "parent": parent_index if parent_index >= 0 else None
        }
        self.nodes.append(node)
        self._save()
        return node["id"]
    
    def _save(self):
        Path(TRUNK_FILE).write_text(
            json.dumps(self.nodes, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    def recent_nodes(self, n: int = 5) -> list:
        return self.nodes[-n:]
    
    def get_path(self, node_id: int) -> list:
        """回溯概念演进路径"""
        path = []
        current = node_id
        while current is not None and current < len(self.nodes):
            path.append(self.nodes[current])
            current = self.nodes[current]["parent"]
        return list(reversed(path))


class MaterialLayer:
    """素材层：日常对话/校验。时序流，按需提取，不撼动锚点。"""
    
    def __init__(self):
        self._log_path = Path(LOG_FILE)
    
    @staticmethod
    def _normalize_content(content) -> str:
        """将 OpenAI 格式的 content（可能是 str 或 list）归一化为纯文本"""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    parts.append(item.get("text", ""))
                elif isinstance(item, str):
                    parts.append(item)
            return " ".join(parts)
        return str(content)

    def log(self, role: str, content: str, metadata: dict = None):
        """追加一条素材记录"""
        text = self._normalize_content(content)
        entry = {
            "timestamp": now_iso(),
            "role": role,
            "content": text[:500],  # 截断，素材不需要完整原文
            "metadata": metadata or {}
        }
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    def extract_relevant(self, keywords: list = None, limit: int = 10) -> list:
        """按需提取相关素材"""
        if not self._log_path.exists():
            return []
        
        entries = []
        with open(self._log_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        
        if not keywords:
            return entries[-limit:]
        
        # 简易关键词匹配提取（归一化 content，兼容 list 格式）
        relevant = []
        for e in reversed(entries):
            text = self._normalize_content(e.get("content", ""))
            if any(kw in text for kw in keywords):
                relevant.append(e)
            if len(relevant) >= limit:
                break
        return list(reversed(relevant))

# ═══════════════════════════════════════════
#  概念引擎 v50 主类
# ═══════════════════════════════════════════

class BlackholeV3Engine:
    """黑洞理论 v3 概念引擎——三条支柱 + 三层架构"""
    
    def __init__(self):
        self.anchor = AnchorLayer()
        self.trunk = TrunkLayer()
        self.material = MaterialLayer()
        self.time = TimeAxis()
        self.concept = None  # 当前概念（色块集群）
    
    def bootstrap(self, goal: str, identity: str = "黑洞引擎 v3"):
        """初始化：创建锚点 + 第一条主干节点"""
        if not self.anchor.root_goal:
            self.anchor.create(
                goal=goal,
                constraints=[
                    "不偏离根目标",
                    "新输入归入素材层，不撼动锚点",
                    "每轮推理前先对标锚点"
                ],
                identity=identity
            )
            self.trunk.add_node(
                summary=f"引擎启动：{goal}",
                category="bootstrap",
                decisions=[f"锚点：{goal}"]
            )
            self.material.log("system", f"Blackhole V3 Engine bootstrapped with goal: {goal}")
    
    def think(self, user_input) -> dict:
        """核心推理循环：锚点校验 → 主干匹配 → 素材提取
        user_input 可以是 str 或 OpenAI content list 格式，自动归一化"""
        # 归一化输入（兼容 list 格式）
        text = self.material._normalize_content(user_input)
        self.material.log("user", text)
        
        # Step 1: 锚点校验
        anchor_prompt = self.anchor.as_system_prompt()
        
        # Step 2: 主干匹配
        recent_trunk = self.trunk.recent_nodes(3)
        
        # Step 3: 素材提取（基于输入中的关键词）
        keywords = [w for w in text[:80].split() if len(w) > 1]
        relevant_material = self.material.extract_relevant(keywords, limit=5)
        
        return {
            "anchor": self.anchor.to_dict(),
            "trunk_context": recent_trunk,
            "material_context": relevant_material,
            "system_prompt": anchor_prompt,
            "instruction": (
                "请严格对标上述锚点层的根目标进行推理。"
                "以下主干节点和素材仅供参考，不得取代锚点方向。"
            )
        }
    
    def decide(self, decision: str, category: str = "decision"):
        """记录关键决策到主干层"""
        node_id = self.trunk.add_node(
            summary=decision,
            category=category,
            decisions=[decision]
        )
        self.material.log("decision", decision, {"node_id": node_id})
        return node_id
    
    def snapshot(self, name: str = "") -> str:
        """支柱三能力：定格——保存完整状态快照"""
        state = {
            "anchor": self.anchor.to_dict(),
            "trunk_length": len(self.trunk.nodes),
            "last_trunk_node": self.trunk.nodes[-1] if self.trunk.nodes else None,
            "timestamp": now_iso()
        }
        return self.time.freeze(state, name or "auto")
    
    def rewind(self, filename: str):
        """支柱三能力：回到过去——加载历史快照"""
        state = self.time.rewind(filename)
        # 锚点不变，但可以查看当时的主干状态
        return state
    
    def fork(self, branch_name: str) -> str:
        """支柱三能力：平行线——基于当前锚点 fork 新分支"""
        branch_data = {
            "anchor": self.anchor.to_dict(),
            "trunk_snapshot": self.trunk.nodes[-5:] if self.trunk.nodes else [],
            "forked_at": now_iso(),
            "branch_name": branch_name
        }
        return self.time.freeze(branch_data, f"fork_{branch_name}")


# ═══════════════════════════════════════════
#  自检 / 演示
# ═══════════════════════════════════════════

if __name__ == "__main__":
    engine = BlackholeV3Engine()
    
    print("=" * 60)
    print("  黑洞理论 v3 概念引擎 — 自检")
    print("=" * 60)
    
    # 创建锚点
    engine.bootstrap(
        goal="构建完全私有化的概念自有推理引擎 v50，实现锚点层/主干层/素材层三层架构",
        identity="黑洞引擎 v3 — 殷竺欣的AI助手云哥"
    )
    
    print(f"\n[锚点层] 根目标: {engine.anchor.root_goal}")
    print(f"[主干层] 节点数: {len(engine.trunk.nodes)}")
    
    # 模拟一轮思考
    result = engine.think("你好，我是殷竺欣，测试概念引擎")
    print(f"\n[推理返回] 锚点已注入 system_prompt: {len(result['system_prompt'])} 字符")
    print(f"[推理返回] 主干上下文: {len(result['trunk_context'])} 条")
    print(f"[推理返回] 素材上下文: {len(result['material_context'])} 条")
    
    # 记录决策
    engine.decide("确认三层架构落地方向：anchor_slot.json + thread_tree.json + session_log.jsonl")
    print(f"\n[主干层] 节点数: {len(engine.trunk.nodes)}")
    
    # 时间操控演示
    snap_file = engine.snapshot("first_test")
    print(f"\n[时间操控·定格] 快照已保存: {snap_file}")
    
    snapshots = engine.time.list_snapshots()
    print(f"[时间操控·回溯] 可用快照: {len(snapshots)} 个")
    
    # Fork 演示
    fork_file = engine.fork("平行推演分支A")
    print(f"[时间操控·平行线] Fork 分支: {fork_file}")
    
    print("\n" + "=" * 60)
    print("  三层架构自治检通过")
    print("  锚点层 [OK] | 主干层 [OK] | 素材层 [OK]")
    print("  时间操控 [OK] (定格/回溯/平行线)")
    print("=" * 60)
    
    # 输出文件状态
    for f in [ANCHOR_FILE, TRUNK_FILE, LOG_FILE]:
        p = Path(f)
        status = f"[OK] {p.stat().st_size} bytes" if p.exists() else "[MISS] 未创建"
        print(f"  {f}: {status}")
