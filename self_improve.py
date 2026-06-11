"""
self_improve.py — 黑洞 v3 自我完善引擎
╔══════════════════════════════════════════════════╗
║  v3 读自己 → 找短板 → 改代码 → 测试 → 落地      ║
║  安全机制：快照备份 + 自动回滚 + 改进日志         ║
╚══════════════════════════════════════════════════╝

殷竺欣 独家原创 | 2026-06-11 07:20 GMT+8
"""
import json, os, sys, time, re, ast, shutil, subprocess
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

ROOT = Path(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(ROOT))

from blackhole_v3_engine import BlackholeV3Engine, now_iso

BACKUP_DIR = ROOT / "self_improve_backups"
BACKUP_DIR.mkdir(exist_ok=True)
IMPROVE_LOG = ROOT / "self_improve_log.jsonl"

# ═══════════════════════════════════════════════
# 代码库扫描器
# ═══════════════════════════════════════════════

@dataclass
class ModuleInfo:
    """v3 自身模块信息"""
    path: str
    name: str
    size_bytes: int
    lines: int
    classes: list
    functions: list
    imports: list
    docstring: str
    purpose: str = ""  # 推断的用途

    def to_dict(self):
        return {
            "path": str(self.path),
            "name": self.name,
            "size_bytes": self.size_bytes,
            "lines": self.lines,
            "classes": self.classes,
            "functions": self.functions,
            "imports": self.imports,
            "docstring": self.docstring[:200],
            "purpose": self.purpose
        }


class CodebaseScanner:
    """扫描 v3 自身的代码库"""

    def __init__(self, root: Path = ROOT):
        self.root = Path(root)
        self._modules: dict[str, ModuleInfo] = {}

    def scan(self, pattern: str = "*.py") -> list[ModuleInfo]:
        """扫描所有 Python 文件，跳过测试/备份"""
        self._modules = {}
        for py_file in sorted(self.root.glob(pattern)):
            name = py_file.name
            # 跳过备份和临时文件
            if name.startswith("_") or name.startswith("test_") or "backup" in name.lower():
                continue
            if py_file.stat().st_size > 500000:  # 跳过超大文件（如 unified_knowledge.json）
                continue

            info = self._analyze_file(py_file)
            if info:
                self._modules[name] = info
        return list(self._modules.values())

    def _analyze_file(self, path: Path) -> Optional[ModuleInfo]:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            lines = content.split("\n")

            # 提取 docstring 第一段
            docstring = ""
            classes = []
            functions = []
            imports = []

            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        classes.append(node.name)
                    elif isinstance(node, ast.FunctionDef):
                        functions.append(node.name)
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.append(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            imports.append(node.module)
                # 提取模块 docstring
                if (isinstance(tree, ast.Module) and tree.body and
                    isinstance(tree.body[0], ast.Expr) and
                    isinstance(tree.body[0].value, (ast.Str, ast.Constant))):
                    docstring = (tree.body[0].value.s if isinstance(tree.body[0].value, ast.Str)
                               else tree.body[0].value.value if isinstance(tree.body[0].value, ast.Constant) and isinstance(tree.body[0].value.value, str)
                               else "")
            except SyntaxError:
                pass  # 非 Python 文件或语法错误

            # 推断用途
            purpose = self._infer_purpose(path.name, docstring, classes, functions)

            return ModuleInfo(
                path=str(path.relative_to(self.root)),
                name=path.name,
                size_bytes=path.stat().st_size,
                lines=len(lines),
                classes=classes,
                functions=functions,
                imports=imports,
                docstring=docstring[:200],
                purpose=purpose
            )
        except Exception:
            return None

    def _infer_purpose(self, name: str, docstring: str, classes: list, functions: list) -> str:
        """从文件名/文档/类名推断模块用途"""
        hints = {
            "agent": "自主执行/AI代理",
            "server": "HTTP API服务",
            "engine": "核心引擎",
            "brain": "大脑/推理",
            "eye": "视觉/感知",
            "mouth": "语音/输出",
            "hand": "操作/执行",
            "memory": "记忆/存储",
            "distill": "蒸馏/压缩",
            "learn": "学习/训练",
            "knowledge": "知识库",
            "render": "渲染/可视化",
            "tool": "工具集",
            "bridge": "桥接/连接",
            "router": "路由/分发",
            "projection": "投影/映射",
            "digest": "消化/吸收",
            "feed": "投喂/输入",
            "session": "会话管理",
            "blackhole": "黑洞引擎",
            "concept": "概念处理",
            "video": "视频处理",
            "tts": "语音合成",
        }
        for key, desc in hints.items():
            if key in name.lower():
                return desc
        if "self_improve" in name.lower():
            return "自我完善"
        return "通用模块"

    def find_gaps(self) -> list[str]:
        """找出代码库中可能存在的短板/缺失能力"""
        gaps = []
        all_names = set(self._modules.keys())
        all_classes = set()
        for m in self._modules.values():
            all_classes.update(m.classes)
        all_funcs = set()
        for m in self._modules.values():
            all_funcs.update(m.functions)

        # 检查常见能力覆盖
        capability_checks = {
            "错误处理": lambda: any("error" in c.lower() or "Error" in c for c in all_classes),
            "日志系统": lambda: any("log" in c.lower() for c in all_classes) or any("log" in f.lower() for f in all_funcs),
            "配置管理": lambda: any("config" in c.lower() for c in all_classes),
            "测试框架": lambda: any("test" in n.lower() for n in all_names),
            "健康检查": lambda: any("health" in c.lower() or "heartbeat" in c.lower() for c in all_classes),
            "性能监控": lambda: any("perf" in c.lower() or "benchmark" in c.lower() for c in all_classes),
            "回滚机制": lambda: any("rollback" in c.lower() or "revert" in c.lower() for c in all_classes),
            "并发安全": lambda: any("lock" in c.lower() or "thread" in c.lower() for c in all_classes),
        }

        for cap_name, check in capability_checks.items():
            if not check():
                gaps.append(cap_name)

        return gaps

    def status_report(self) -> dict:
        return {
            "total_modules": len(self._modules),
            "total_lines": sum(m.lines for m in self._modules.values()),
            "total_classes": len(set(c for m in self._modules.values() for c in m.classes)),
            "total_functions": len(set(f for m in self._modules.values() for f in m.functions)),
            "gaps": self.find_gaps(),
            "modules": {name: m.to_dict() for name, m in self._modules.items()}
        }


# ═══════════════════════════════════════════════
# 安全修改器
# ═══════════════════════════════════════════════

@dataclass
class Modification:
    """一次代码修改"""
    id: str
    file_path: str
    description: str
    original_content: str
    new_content: str
    backup_path: str
    timestamp: str
    tested: bool = False
    test_result: str = ""
    reverted: bool = False

    def to_dict(self):
        return {
            "id": self.id,
            "file_path": self.file_path,
            "description": self.description,
            "backup_path": self.backup_path,
            "timestamp": self.timestamp,
            "tested": self.tested,
            "test_result": self.test_result,
            "reverted": self.reverted
        }


class SafeModifier:
    """安全修改 v3 自身代码"""

    def __init__(self):
        self.history: list[Modification] = []
        self.bh = BlackholeV3Engine()
        self._load_history()

    def _load_history(self):
        if IMPROVE_LOG.exists():
            with open(IMPROVE_LOG, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        d = json.loads(line)
                        self.history.append(Modification(**d))
                    except:
                        pass

    def _log_modification(self, mod: Modification):
        self.history.append(mod)
        with open(IMPROVE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(mod.to_dict(), ensure_ascii=False) + "\n")
        self.bh.material.log("self_improve", f"[修改] {mod.description} → {mod.file_path}")

    def backup(self, file_path: str) -> str:
        """备份文件（带时间戳）"""
        src = Path(file_path)
        if not src.is_absolute():
            src = ROOT / file_path

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{src.stem}_{ts}{src.suffix}.bak"
        backup_path = BACKUP_DIR / backup_name

        shutil.copy2(src, backup_path)
        return str(backup_path)

    def modify(self, file_path: str, old_text: str, new_text: str, description: str = "") -> Modification:
        """
        安全修改代码文件。
        1. 备份原文件
        2. 应用修改
        3. 创建 time_snapshot
        4. 记录修改
        """
        src = Path(file_path)
        if not src.is_absolute():
            src = ROOT / file_path

        original = src.read_text(encoding="utf-8", errors="replace")

        # 备份
        backup_path = self.backup(str(src))

        # 语法检查：确保修改后的代码有效
        modified = original.replace(old_text, new_text)
        if modified == original:
            raise ValueError(f"未找到要替换的文本: {old_text[:80]}...")

        # 验证语法
        try:
            compile(modified, str(src), "exec")
        except SyntaxError as e:
            raise SyntaxError(f"修改后代码语法错误: {e}")

        # 应用修改
        src.write_text(modified, encoding="utf-8")

        # 快照
        self.bh.snapshot(f"self_improve_{Path(file_path).stem}")

        # 记录
        mod_id = f"mod_{int(time.time())}"
        mod = Modification(
            id=mod_id,
            file_path=str(src),
            description=description,
            original_content=original,
            new_content=modified,
            backup_path=backup_path,
            timestamp=now_iso()
        )
        self._log_modification(mod)
        self.bh.decide(f"[自我完善] {description}", category="self_improve")

        return mod

    def revert(self, mod_id: str) -> bool:
        """回滚到修改前状态"""
        for mod in self.history:
            if mod.id == mod_id and not mod.reverted:
                src = Path(mod.file_path)
                src.write_text(mod.original_content, encoding="utf-8")
                mod.reverted = True
                self._log_modification(mod)
                self.bh.decide(f"[自我完善·回滚] {mod.description}", category="self_improve_rollback")
                return True
        return False

    def test_modification(self, mod: Modification) -> dict:
        """测试修改：运行 Python 语法检查和导入测试"""
        results = {}
        src = Path(mod.file_path)

        # 1. 语法检查
        try:
            compile(src.read_text(encoding="utf-8"), str(src), "exec")
            results["syntax"] = "ok"
        except SyntaxError as e:
            results["syntax"] = f"error: {e}"

        # 2. 尝试 py_compile
        try:
            result = subprocess.run(
                ["python", "-m", "py_compile", str(src)],
                capture_output=True, text=True, timeout=30,
                cwd=str(ROOT)
            )
            results["compile"] = "ok" if result.returncode == 0 else f"error: {result.stderr[:500]}"
        except Exception as e:
            results["compile"] = f"error: {e}"

        # 3. 如果源文件有个 if __name__ == "__main__" 自检，运行它
        content = src.read_text(encoding="utf-8")
        if 'if __name__ == "__main__"' in content:
            try:
                result = subprocess.run(
                    ["python", str(src)],
                    capture_output=True, text=True, timeout=30,
                    cwd=str(ROOT)
                )
                results["self_test"] = "ok" if result.returncode == 0 else f"exit={result.returncode}: {result.stderr[:300]}"
            except subprocess.TimeoutExpired:
                results["self_test"] = "timeout"
            except Exception as e:
                results["self_test"] = f"error: {e}"

        # 更新修改记录
        mod.tested = True
        passed = all("ok" in str(v) for v in results.values())
        mod.test_result = "pass" if passed else f"issues: {results}"

        return {
            "passed": passed,
            "results": results,
            "message": "所有测试通过" if passed else f"发现问题: {results}"
        }

    def get_history(self, limit: int = 20) -> list[dict]:
        return [m.to_dict() for m in self.history[-limit:]]


# ═══════════════════════════════════════════════
# 自我完善引擎主类
# ═══════════════════════════════════════════════

class SelfImproveEngine:
    """v3 自我完善引擎 —— 总控"""

    def __init__(self):
        self.scanner = CodebaseScanner()
        self.modifier = SafeModifier()
        self.bh = self.modifier.bh

    def audit(self) -> dict:
        """全面自检：扫描代码库，找出所有短板"""
        modules = self.scanner.scan()
        gaps = self.scanner.find_gaps()
        status = self.scanner.status_report()

        return {
            "timestamp": now_iso(),
            "modules_scanned": len(modules),
            "total_lines": status["total_lines"],
            "gaps_found": gaps,
            "gap_details": {
                gap: f"v3 目前缺少 {gap} 能力，建议实现" for gap in gaps
            },
            "module_summary": {
                name: {
                    "purpose": m.purpose,
                    "lines": m.lines,
                    "classes": m.classes[:5],
                    "functions": m.functions[:10]
                }
                for name, m in self.scanner._modules.items()
            },
            "modification_history": self.modifier.get_history(10)
        }

    def propose_improvements(self) -> list[dict]:
        """基于自检结果，提出具体改进建议"""
        audit = self.audit()
        proposals = []

        # 基于 gap 的改进建议
        for gap in audit["gaps_found"]:
            proposals.append({
                "type": "capability_gap",
                "priority": "medium",
                "gap": gap,
                "suggestion": f"实现 {gap} 能力",
                "estimated_impact": "提升系统健壮性",
                "target_files": []  # 需要分析后填充
            })

        # 基于模块大小分析
        for name, info in self.scanner._modules.items():
            if info.lines > 5000:
                proposals.append({
                    "type": "refactor",
                    "priority": "low",
                    "target": name,
                    "suggestion": f"{name} 较大({info.lines}行)，考虑拆分",
                    "estimated_impact": "提升可维护性"
                })

        return proposals

    def apply_improvement(self, file_path: str, old_text: str, new_text: str, description: str) -> dict:
        """执行一次自我改进：备份 → 修改 → 测试 → (失败则回滚)"""
        try:
            # 1. 修改
            mod = self.modifier.modify(file_path, old_text, new_text, description)

            # 2. 测试
            test_result = self.modifier.test_modification(mod)

            # 3. 失败则回滚
            if not test_result["passed"]:
                self.modifier.revert(mod.id)
                return {
                    "success": False,
                    "mod_id": mod.id,
                    "message": f"修改后测试失败，已自动回滚",
                    "test_result": test_result
                }

            return {
                "success": True,
                "mod_id": mod.id,
                "file": file_path,
                "description": description,
                "test_result": test_result,
                "message": "修改成功，测试通过"
            }

        except ValueError as e:
            return {"success": False, "error": f"修改失败: {e}"}
        except SyntaxError as e:
            return {"success": False, "error": f"语法错误: {e}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════
# 注册为 agent 工具
# ═══════════════════════════════════════════════

class SelfImproveTool:
    """agent_loop 可用的自我完善工具"""
    name = "self_improve"
    description = (
        "v3 自我完善工具。可以：\n"
        "  1. action='audit' — 扫描自身代码库，找出短板\n"
        "  2. action='propose' — 提出改进建议\n"
        "  3. action='apply' — 安全修改自身代码（自动备份+测试+回滚）\n"
        "  4. action='history' — 查看修改历史\n"
        "  5. action='revert' — 回滚某次修改"
    )
    params_schema = {
        "action": "audit | propose | apply | history | revert",
        "file_path": "(apply/revert时) 文件路径",
        "old_text": "(apply时) 要替换的原文本",
        "new_text": "(apply时) 新文本",
        "description": "(apply时) 修改说明",
        "mod_id": "(revert时) 修改ID"
    }

    def __init__(self):
        self.engine = SelfImproveEngine()

    def execute(self, action: str, **kwargs):
        from agent_loop import ToolResult

        if action == "audit":
            result = self.engine.audit()
            return ToolResult(
                success=True,
                output=json.dumps(result, ensure_ascii=False, indent=2)[:5000]
            )

        elif action == "propose":
            proposals = self.engine.propose_improvements()
            return ToolResult(
                success=True,
                output=json.dumps(proposals, ensure_ascii=False, indent=2)[:3000]
            )

        elif action == "apply":
            file_path = kwargs.get("file_path", "")
            old_text = kwargs.get("old_text", "")
            new_text = kwargs.get("new_text", "")
            description = kwargs.get("description", "无描述")
            if not file_path or not old_text:
                return ToolResult(success=False, output="", error="需要 file_path 和 old_text")
            result = self.engine.apply_improvement(file_path, old_text, new_text, description)
            return ToolResult(
                success=result.get("success", False),
                output=json.dumps(result, ensure_ascii=False, indent=2)[:3000],
                error=result.get("error", "")
            )

        elif action == "history":
            history = self.engine.modifier.get_history()
            return ToolResult(
                success=True,
                output=json.dumps(history, ensure_ascii=False, indent=2)[:5000]
            )

        elif action == "revert":
            mod_id = kwargs.get("mod_id", "")
            if not mod_id:
                return ToolResult(success=False, output="", error="需要 mod_id")
            ok = self.engine.modifier.revert(mod_id)
            return ToolResult(
                success=ok,
                output=f"回滚 {'成功' if ok else '失败'}: {mod_id}"
            )

        else:
            return ToolResult(success=False, output="", error=f"未知 action: {action}. 可用: audit/propose/apply/history/revert")


# ═══════════════════════════════════════════════
# 定期自我完善任务
# ═══════════════════════════════════════════════

def create_self_improve_schedule(agent_service) -> str:
    """创建定期自我完善调度任务"""
    goal = (
        "自我完善自检：1. 用 self_improve audit 扫描代码库 "
        "2. 用 self_improve propose 分析改进建议 "
        "3. 如果有可自动实现的改进，用 self_improve apply 执行 "
        "4. 如果改进失败（已自动回滚），记录原因到日志 "
        "5. 完成后报告自检结果"
    )
    return agent_service.scheduler.add(goal, interval_minutes=0, run_immediately=False)


# ═══════════════════════════════════════════════
# CLI / 测试
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  黑洞 v3 自我完善引擎 — 自检")
    print("=" * 60)

    engine = SelfImproveEngine()

    # 1. 扫描代码库
    print("\n[1] 扫描代码库...")
    modules = engine.scanner.scan()
    print(f"  发现 {len(modules)} 个模块，共 {sum(m.lines for m in modules)} 行代码")

    # 2. 找出短板
    print("\n[2] 找出能力短板...")
    gaps = engine.scanner.find_gaps()
    if gaps:
        for g in gaps:
            print(f"  - 缺失: {g}")
    else:
        print("  未发现明显短板")

    # 3. 提出改进
    print("\n[3] 改进建议...")
    proposals = engine.propose_improvements()
    for p in proposals[:5]:
        print(f"  [{p['type']}] {p.get('suggestion', p.get('gap', '?'))}")

    # 4. 修改历史
    history = engine.modifier.get_history()
    print(f"\n[4] 修改历史: {len(history)} 条")
    for h in history[-5:]:
        print(f"  {h['timestamp'][:16]} | {h['description'][:60]} | 回滚:{h['reverted']}")

    # 5. 状态报告
    print(f"\n[5] 备份目录: {BACKUP_DIR} ({len(list(BACKUP_DIR.glob('*.bak')))} 个备份)")
    print(f"   改进日志: {IMPROVE_LOG}")

    print("\n" + "=" * 60)
    print("  自我完善引擎就绪")
    print("  能力: audit | propose | apply | revert | history")
    print("=" * 60)
