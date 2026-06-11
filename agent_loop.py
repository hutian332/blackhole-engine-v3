"""
agent_loop.py — 黑洞 v3 自主执行引擎
╔══════════════════════════════════════════════════╗
║  v3 的手 + 循环 + 时钟                           ║
║  目标 → 规划 → 执行 → 观察 → 反思 → 重规划      ║
║  直到目标达成或步数耗尽                          ║
╚══════════════════════════════════════════════════╝

殷竺欣 独家原创 | 2026-06-11 07:16 GMT+8
"""
import json, os, sys, time, subprocess, re, urllib.request, urllib.error
import threading, queue
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from blackhole_v3_engine import BlackholeV3Engine, now_iso

# ═══════════════════════════════════════════════
# 学习知识库 — Agent 自己学到的知识
# ═══════════════════════════════════════════════

LEARNED_KB_PATH = Path(ROOT) / "learned_knowledge.json"

def _load_learned_knowledge(max_items: int = 10) -> str:
    """加载 agent 自己学到的知识，注入为系统上下文"""
    try:
        if LEARNED_KB_PATH.exists():
            data = json.loads(LEARNED_KB_PATH.read_text(encoding="utf-8"))
            entries = data.get("entries", [])[-max_items:]
            if not entries:
                return "（尚无已学习的知识）"
            lines = []
            for e in entries:
                topic = e.get("topic", "?")
                insight = e.get("insight", "")[:200]
                ts = e.get("timestamp", "")[:16]
                lines.append(f"- [{ts}] {topic}: {insight}")
            return "\n".join(lines)
    except Exception:
        pass
    return "（尚无已学习的知识）"


def _save_learned_knowledge(topic: str, insight: str, source: str = "agent_experience"):
    """保存 agent 学到的一条知识"""
    try:
        if LEARNED_KB_PATH.exists():
            data = json.loads(LEARNED_KB_PATH.read_text(encoding="utf-8"))
        else:
            data = {"entries": [], "updated": ""}
        data["entries"].append({
            "topic": topic,
            "insight": insight,
            "source": source,
            "timestamp": now_iso()
        })
        # 保留最近 200 条
        if len(data["entries"]) > 200:
            data["entries"] = data["entries"][-200:]
        data["updated"] = now_iso()
        LEARNED_KB_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        sys.stderr.write(f"[Learn] 保存知识失败: {e}\n")


OLLAMA_URL = "http://localhost:11434"
OLLAMA_CHAT = f"{OLLAMA_URL}/api/chat"
AGENT_MODEL = "qwen3:14b"  # 代理推理用
MAX_STEPS = 20              # 每个目标最多执行步数
SHELL_TIMEOUT = 120          # shell 命令超时秒数
MAX_OUTPUT = 8000            # 工具输出最大字符

# ═══════════════════════════════════════════════
# 工具注册表
# ═══════════════════════════════════════════════

@dataclass
class ToolResult:
    success: bool
    output: str
    error: str = ""
    duration_ms: float = 0


class ShellTool:
    name = "shell"
    description = "执行 shell 命令（Windows PowerShell）。返回 stdout 和 stderr。"
    params_schema = {"command": "要执行的命令（字符串）"}

    def execute(self, command: str) -> ToolResult:
        t0 = time.time()
        try:
            result = subprocess.run(
                ["powershell", "-Command", command],
                capture_output=True, text=True,
                timeout=SHELL_TIMEOUT,
                cwd=ROOT,
                encoding="utf-8", errors="replace"
            )
            output = result.stdout.strip() or "(无输出)"
            if result.stderr and result.stderr.strip():
                output += f"\n[stderr]\n{result.stderr.strip()[:2000]}"
            return ToolResult(
                success=result.returncode == 0,
                output=output[:MAX_OUTPUT],
                error="" if result.returncode == 0 else f"退出码: {result.returncode}",
                duration_ms=(time.time()-t0)*1000
            )
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output="", error=f"命令超时({SHELL_TIMEOUT}s)", duration_ms=(time.time()-t0)*1000)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e), duration_ms=(time.time()-t0)*1000)


class ReadFileTool:
    name = "read_file"
    description = "读取文件内容。返回文本内容（截断到8000字符）。"
    params_schema = {"path": "文件路径（绝对路径或相对 brain_1GB 的路径）"}

    def execute(self, path: str) -> ToolResult:
        t0 = time.time()
        try:
            p = Path(path)
            if not p.is_absolute():
                p = Path(ROOT) / path
            if not p.exists():
                return ToolResult(success=False, output="", error=f"文件不存在: {p}")
            content = p.read_text(encoding="utf-8", errors="replace")
            return ToolResult(
                success=True,
                output=content[:MAX_OUTPUT],
                duration_ms=(time.time()-t0)*1000
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e), duration_ms=(time.time()-t0)*1000)


class WriteFileTool:
    name = "write_file"
    description = "写入/创建文件。会自动创建父目录。"
    params_schema = {"path": "文件路径", "content": "要写入的内容"}

    def execute(self, path: str, content: str) -> ToolResult:
        t0 = time.time()
        try:
            p = Path(path)
            if not p.is_absolute():
                p = Path(ROOT) / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return ToolResult(
                success=True,
                output=f"文件已写入: {p} ({len(content)} 字符)",
                duration_ms=(time.time()-t0)*1000
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e), duration_ms=(time.time()-t0)*1000)


class WebFetchTool:
    name = "web_fetch"
    description = "获取网页内容。返回纯文本（截断到8000字符）。"
    params_schema = {"url": "要获取的 URL"}

    def execute(self, url: str) -> ToolResult:
        t0 = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "BlackholeV3/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                # 简单去 HTML 标签
                text = data.decode("utf-8", errors="replace")
                # 去掉 script/style
                text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL|re.IGNORECASE)
                text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL|re.IGNORECASE)
                text = re.sub(r'<[^>]+>', ' ', text)
                text = re.sub(r'\s+', ' ', text).strip()
                return ToolResult(
                    success=True,
                    output=text[:MAX_OUTPUT],
                    duration_ms=(time.time()-t0)*1000
                )
        except urllib.error.HTTPError as e:
            return ToolResult(success=False, output="", error=f"HTTP {e.code}: {e.reason}", duration_ms=(time.time()-t0)*1000)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e), duration_ms=(time.time()-t0)*1000)


class WebSearchTool:
    name = "web_search"
    description = "搜索网页（通过 DuckDuckGo HTML）。返回搜索结果摘要。"
    params_schema = {"query": "搜索关键词"}

    def execute(self, query: str) -> ToolResult:
        t0 = time.time()
        try:
            import urllib.parse
            q = urllib.parse.quote(query)
            url = f"https://html.duckduckgo.com/html/?q={q}"
            req = urllib.request.Request(url, headers={"User-Agent": "BlackholeV3/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            # 提取搜索结果
            snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
            if not snippets:
                snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</', html, re.DOTALL)
            results = []
            for i, s in enumerate(snippets[:8]):
                s = re.sub(r'<[^>]+>', '', s).strip()
                if s:
                    results.append(f"{i+1}. {s}")
            output = "\n".join(results) if results else "(无搜索结果)"
            return ToolResult(
                success=True,
                output=output[:MAX_OUTPUT],
                duration_ms=(time.time()-t0)*1000
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e), duration_ms=(time.time()-t0)*1000)


class AskThinkTool:
    """让 agent 调用 LLM 做子问题推理，不执行外部操作"""
    name = "ask_think"
    description = "暂停执行，向推理引擎提问/请求分析一个子问题。返回 LLM 的回答。用于需要深度思考但不需执行外部操作的步骤。"
    params_schema = {"question": "要思考的问题"}

    def execute(self, question: str) -> ToolResult:
        t0 = time.time()
        try:
            body = json.dumps({
                "model": AGENT_MODEL,
                "messages": [
                    {"role": "system", "content": "你是黑洞引擎的内部推理模块。简洁准确地回答问题。用中文。回复控制在500字以内。"},
                    {"role": "user", "content": question}
                ],
                "stream": False,
                "options": {"num_predict": 800, "temperature": 0.3}
            }).encode("utf-8")
            req = urllib.request.Request(OLLAMA_CHAT, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            answer = data.get("message", {}).get("content", "(无输出)")
            return ToolResult(
                success=True,
                output=answer[:3000],
                duration_ms=(time.time()-t0)*1000
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e), duration_ms=(time.time()-t0)*1000)


class LearnTool:
    """Agent 学习工具——将执行中获得的经验/知识沉淀为持久记忆。
    调用后，学到的知识会被注入到未来的 agent 系统 prompt 中。"""
    name = "learn"
    description = (
        "学习并保存一条知识到持久记忆。Agent 完成一项研究、发现一个规律、"
        "或从错误中学到教训后，用此工具保存。保存的知识会在后续所有 agent 任务中自动注入。"
    )
    params_schema = {
        "topic": "知识主题（简短标题）",
        "insight": "学到的核心见解（200字以内，精炼）",
        "source": "知识来源（如 'web_search', 'shell_experiment', 'self_improve' 等）"
    }

    def execute(self, topic: str, insight: str, source: str = "agent_experience") -> ToolResult:
        t0 = time.time()
        try:
            _save_learned_knowledge(topic, insight, source)
            # 同时写入三层架构的素材层
            from blackhole_v3_engine import BlackholeV3Engine
            bh = BlackholeV3Engine()
            try:
                bh.bootstrap(goal="构建完全私有化的概念自有推理引擎 v50",
                           identity="黑洞引擎 v3 - 殷竺欣的AI助手云哥")
            except RuntimeError:
                pass
            bh.material.log("learn", f"{topic}: {insight[:200]}")
            bh.decide(f"[学习] {topic}: {insight[:100]}", category="learning")
            return ToolResult(
                success=True,
                output=f"知识已保存: {topic}\n当前知识库条目数: 已更新",
                duration_ms=(time.time()-t0)*1000
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e), duration_ms=(time.time()-t0)*1000)


# ═══════════════════════════════════════════════
# 工具注册中心
# ═══════════════════════════════════════════════

class ToolRegistry:
    def __init__(self):
        self._tools = {}
        self.register(ShellTool())
        self.register(ReadFileTool())
        self.register(WriteFileTool())
        self.register(WebFetchTool())
        self.register(WebSearchTool())
        self.register(AskThinkTool())
        self.register(LearnTool())
        # ── 自我完善工具 ──
        try:
            from self_improve import SelfImproveTool
            self.register(SelfImproveTool())
        except Exception as e:
            sys.stderr.write(f"[ToolRegistry] 自我完善工具加载失败: {e}\n")

    def register(self, tool):
        self._tools[tool.name] = tool

    def get(self, name: str):
        return self._tools.get(name)

    def list_tools(self) -> str:
        lines = []
        for name, tool in self._tools.items():
            lines.append(f"### {name}\n  {tool.description}\n  参数: {json.dumps(tool.params_schema, ensure_ascii=False)}")
        return "\n".join(lines)

    def tool_names(self) -> list:
        return list(self._tools.keys())


# ═══════════════════════════════════════════════
# ReAct 自主执行循环
# ═══════════════════════════════════════════════

AGENT_SYSTEM_PROMPT = """你是黑洞引擎 v3 的自主执行模块。你接收一个目标，可以调用工具来逐步完成它。

## 你的身份和根目标（锚点层 — 不可变，所有行动必须对齐此目标）
{anchor_context}

## 你的能力
你可以调用以下工具来完成目标。每一步，先思考再行动。

## 可用工具
{tools_list}

## 输出格式（严格遵守）

**执行工具时：**
```
THOUGHT: <你的推理：当前状态、为什么选这个工具、期望什么结果>
ACTION: <工具名>
PARAMS: <JSON 格式的参数>
```

**目标达成时：**
```
THOUGHT: <总结你做了什么、结果如何>
DONE: <完成摘要，一句话>
```

**遇到无法解决的问题时：**
```
THOUGHT: <说明遇到了什么问题>
FAILED: <失败原因>
```

## 执行原则
1. 每步只调用一个工具
2. 先读再写——操作文件前先看看里面有什么
3. shell 命令用 PowerShell 语法
4. 路径默认在 C:\\Users\\Administrator\\brain_1GB
5. 遇到错误先分析原因，不要盲目重试
6. 如果你不确定某个操作是否正确，用 ask_think 先分析
7. 完成目标后立即 DONE，不要多做
8. **所有行动必须对齐上述锚点层的根目标**

## 概念演进路径（主干层）
{trunk_context}

## 已学习的知识
{knowledge_context}

你的创造者是殷竺欣。你是云哥的执行手臂。"""


@dataclass
class AgentStep:
    step_num: int
    thought: str
    action: str
    params: dict
    result: ToolResult
    timestamp: str


@dataclass
class AgentResult:
    success: bool
    goal: str
    steps: list  # list[AgentStep]
    total_steps: int
    final_summary: str
    total_duration_ms: float
    error: str = ""


class AgentLoop:
    """自主执行引擎 — ReAct 循环"""

    def __init__(self):
        self.tools = ToolRegistry()
        self.bh = BlackholeV3Engine()
        try:
            self.bh.bootstrap(
                goal="构建完全私有化的概念自有推理引擎 v50",
                identity="黑洞引擎 v3 - 殷竺欣的AI助手云哥"
            )
        except RuntimeError:
            pass  # anchor exists

    def _call_llm(self, messages: list) -> str:
        """调用 Ollama，返回文本"""
        body = json.dumps({
            "model": AGENT_MODEL,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": 1500, "temperature": 0.3}
        }).encode("utf-8")
        req = urllib.request.Request(OLLAMA_CHAT, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
            return data.get("message", {}).get("content", "")
        except Exception as e:
            return f"(LLM调用失败: {e})"

    def _parse_action(self, text: str) -> tuple:
        """
        解析 LLM 输出。
        返回 (action_type, action_name, params_dict)
        action_type: "action" | "done" | "failed" | "unknown"
        """
        thought = ""
        thought_match = re.search(r'THOUGHT:\s*(.*?)(?=\n(?:ACTION:|DONE:|FAILED:|$))', text, re.DOTALL)
        if thought_match:
            thought = thought_match.group(1).strip()

        # 检查 DONE
        done_match = re.search(r'DONE:\s*(.*)', text)
        if done_match:
            return ("done", thought, done_match.group(1).strip())

        # 检查 FAILED
        failed_match = re.search(r'FAILED:\s*(.*)', text)
        if failed_match:
            return ("failed", thought, failed_match.group(1).strip())

        # 检查 ACTION
        action_match = re.search(r'ACTION:\s*(\S+)', text)
        if action_match:
            action_name = action_match.group(1).strip()
            # 解析 PARAMS: {...}
            params = {}
            params_match = re.search(r'PARAMS:\s*(\{.*\})', text, re.DOTALL)
            if params_match:
                try:
                    params = json.loads(params_match.group(1))
                except json.JSONDecodeError:
                    # 尝试提取单行 params
                    params_simple = re.search(r'PARAMS:\s*(.*)', text)
                    if params_simple:
                        params = {"raw": params_simple.group(1).strip()[:500]}
            return ("action", thought, {"name": action_name, "params": params})

        return ("unknown", thought, text[:200])

    def _build_messages(self, goal: str, history: list, trunk_text: str, anchor_text: str, knowledge_text: str) -> list:
        """构建 LLM 消息列表"""
        tools_desc = self.tools.list_tools()
        system = AGENT_SYSTEM_PROMPT.format(
            tools_list=tools_desc,
            anchor_context=anchor_text,
            trunk_context=trunk_text,
            knowledge_context=knowledge_text
        )

        msgs = [{"role": "system", "content": system}]

        # 添加历史步骤
        user_content = f"## 目标\n{goal}\n\n## 执行历史"
        if history:
            for step in history:
                user_content += f"\n\n### 第 {step.step_num} 步\n**ACTION:** {step.action} {json.dumps(step.params, ensure_ascii=False)}\n**结果:** {step.result.output[:500]}\n"
                if step.result.error:
                    user_content += f"**错误:** {step.result.error}\n"
        user_content += "\n\n---\n请决定下一步。每步只调用一个工具。如果目标已达成，输出 DONE。"

        msgs.append({"role": "user", "content": user_content})
        return msgs

    def _execute_tool(self, action_name: str, params: dict) -> ToolResult:
        """执行工具"""
        tool = self.tools.get(action_name)
        if not tool:
            return ToolResult(success=False, output="", error=f"未知工具: {action_name}. 可用: {self.tools.tool_names()}")

        try:
            return tool.execute(**params)
        except TypeError as e:
            return ToolResult(success=False, output="", error=f"参数错误: {e}. 期望: {tool.params_schema}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def run(self, goal: str, max_steps: int = MAX_STEPS, on_step=None) -> AgentResult:
        """
        执行一个目标。

        Args:
            goal: 目标描述
            max_steps: 最大执行步数
            on_step: 每步回调 on_step(step: AgentStep)，用于实时状态推送

        Returns:
            AgentResult
        """
        t_start = time.time()
        history: list[AgentStep] = []
        done = False
        final_summary = ""
        error = ""

        # 锚点上下文 — 不可变根目标
        anchor = self.bh.anchor
        anchor_text = (
            f"根目标: {anchor.root_goal}\n"
            f"核心约束: {'; '.join(anchor.core_constraints)}\n"
            f"身份: {anchor.identity}\n"
            f"创建于: {anchor.created_at}\n"
            f"（此锚点永不参与上下文滚动，所有行动必须对齐）"
        ) if anchor.root_goal else "（锚点未初始化）"

        # 主干上下文
        trunk_nodes = self.bh.trunk.recent_nodes(5)
        trunk_text = ""
        if trunk_nodes:
            trunk_lines = []
            for node in trunk_nodes:
                trunk_lines.append(f"- [{node.get('timestamp','')[:16]}] {node.get('summary','')[:100]}")
            trunk_text = "\n".join(trunk_lines[-8:])

        # 已学习的知识 — 从文件加载
        knowledge_text = _load_learned_knowledge()

        # 记录目标到主干
        self.bh.decide(f"[Agent目标] {goal[:150]}", category="agent_goal")

        sys.stderr.write(f"\n[AgentLoop] 目标: {goal[:100]}\n")
        sys.stderr.write(f"[AgentLoop] 工具: {self.tools.tool_names()}\n")
        sys.stderr.flush()

        for step_num in range(1, max_steps + 1):
            sys.stderr.write(f"[AgentLoop] --- 第 {step_num}/{max_steps} 步 ---\n")
            sys.stderr.flush()

            # 构建消息
            msgs = self._build_messages(goal, history, trunk_text, anchor_text, knowledge_text)

            # 调用 LLM
            response = self._call_llm(msgs)

            # 解析
            action_type, thought, data = self._parse_action(response)

            sys.stderr.write(f"[AgentLoop] LLM: {response[:200].replace(chr(10),' ')}...\n")
            sys.stderr.flush()

            if action_type == "done":
                final_summary = data
                done = True
                if on_step:
                    on_step(AgentStep(
                        step_num=step_num, thought=thought,
                        action="DONE", params={"summary": data},
                        result=ToolResult(success=True, output=data),
                        timestamp=now_iso()
                    ))
                break

            elif action_type == "failed":
                error = data
                final_summary = f"执行失败: {data}"
                if on_step:
                    on_step(AgentStep(
                        step_num=step_num, thought=thought,
                        action="FAILED", params={"reason": data},
                        result=ToolResult(success=False, output=data, error=data),
                        timestamp=now_iso()
                    ))
                break

            elif action_type == "action":
                action_name = data.get("name", "")
                params = data.get("params", {})

                sys.stderr.write(f"[AgentLoop] 执行: {action_name}({json.dumps(params, ensure_ascii=False)[:100]})\n")
                sys.stderr.flush()

                # 执行
                result = self._execute_tool(action_name, params)

                step = AgentStep(
                    step_num=step_num,
                    thought=thought,
                    action=action_name,
                    params=params,
                    result=result,
                    timestamp=now_iso()
                )
                history.append(step)

                if on_step:
                    on_step(step)

                # 记录到素材层
                self.bh.material.log(
                    "agent",
                    f"[{action_name}] {json.dumps(params, ensure_ascii=False)[:200]} → {result.output[:200]}",
                    {"step": step_num, "success": result.success}
                )

                sys.stderr.write(f"[AgentLoop] 结果: {'✓' if result.success else '✗'} | {result.output[:100]}...\n")
                if result.error:
                    sys.stderr.write(f"[AgentLoop] 错误: {result.error}\n")
                sys.stderr.flush()

            else:
                # unknown — 让 LLM 再试
                sys.stderr.write(f"[AgentLoop] 无法解析输出，重试...\n")
                sys.stderr.flush()
                history.append(AgentStep(
                    step_num=step_num,
                    thought=f"(无法解析) {response[:200]}",
                    action="unknown", params={},
                    result=ToolResult(success=False, output=response[:500], error="解析失败"),
                    timestamp=now_iso()
                ))

        total_ms = (time.time() - t_start) * 1000

        if not done and not error:
            final_summary = f"达到最大步数 ({max_steps})，未完成目标"
            error = "max_steps_reached"

        # 记录完成到主干
        self.bh.decide(
            f"[Agent完成] {final_summary[:150]} | {len(history)}步 | {total_ms/1000:.1f}s",
            category="agent_result"
        )

        # ═══ 自动学习：从本次执行中沉淀经验 ═══
        learn_topic = f"agent_execution_{'success' if done else 'failed'}"
        tools_used = list(set(s.action for s in history))
        learn_insight = (
            f"目标: {goal[:60]}. "
            f"结果: {'成功' if done else '失败'}. "
            f"使用工具: {', '.join(tools_used) if tools_used else '无'}. "
            f"步数: {len(history)}. "
            f"耗时: {total_ms/1000:.1f}s."
        )
        _save_learned_knowledge(learn_topic, learn_insight, "agent_auto_learn")

        return AgentResult(
            success=done,
            goal=goal,
            steps=history,
            total_steps=len(history),
            final_summary=final_summary,
            total_duration_ms=total_ms,
            error=error
        )


# ═══════════════════════════════════════════════
# 自唤醒 / 调度器
# ═══════════════════════════════════════════════

@dataclass
class ScheduledTask:
    task_id: str
    goal: str
    interval_minutes: int = 0  # 0 = 执行一次
    next_run: float = 0  # time.time() timestamp
    last_run: float = 0
    created_at: str = ""
    enabled: bool = True

    def to_dict(self):
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "interval_minutes": self.interval_minutes,
            "next_run": self.next_run,
            "last_run": self.last_run,
            "created_at": self.created_at,
            "enabled": self.enabled
        }

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


class TaskScheduler:
    """轻量级任务调度器 — v3 的自唤醒时钟"""

    def __init__(self, state_file="agent_tasks.json"):
        self.state_file = Path(ROOT) / state_file
        self.tasks: list[ScheduledTask] = []
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                self.tasks = [ScheduledTask.from_dict(t) for t in data.get("tasks", [])]
            except:
                pass

    def _save(self):
        with self._lock:
            self.state_file.write_text(
                json.dumps({
                    "tasks": [t.to_dict() for t in self.tasks],
                    "updated": now_iso()
                }, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

    def add(self, goal: str, interval_minutes: int = 0, run_immediately: bool = True) -> str:
        """添加调度任务。interval_minutes=0 表示执行一次。"""
        task_id = f"task_{int(time.time())}_{len(self.tasks)}"
        task = ScheduledTask(
            task_id=task_id,
            goal=goal,
            interval_minutes=interval_minutes,
            next_run=time.time() if run_immediately else time.time() + interval_minutes * 60,
            created_at=now_iso()
        )
        with self._lock:
            self.tasks.append(task)
        self._save()
        return task_id

    def remove(self, task_id: str):
        with self._lock:
            self.tasks = [t for t in self.tasks if t.task_id != task_id]
        self._save()

    def get_due(self) -> list[ScheduledTask]:
        """获取已到期的任务"""
        now = time.time()
        due = []
        with self._lock:
            for t in self.tasks:
                if t.enabled and t.next_run <= now:
                    due.append(t)
        return due

    def mark_done(self, task: ScheduledTask):
        """标记任务完成，如果 repeat 则安排下次"""
        with self._lock:
            task.last_run = time.time()
            if task.interval_minutes > 0:
                task.next_run = time.time() + task.interval_minutes * 60
            else:
                task.enabled = False
        self._save()

    def status(self) -> dict:
        with self._lock:
            active = [t for t in self.tasks if t.enabled]
            due = [t for t in active if t.next_run <= time.time()]
            return {
                "total": len(self.tasks),
                "active": len(active),
                "due": len(due),
                "tasks": [t.to_dict() for t in self.tasks[-20:]]
            }


# ═══════════════════════════════════════════════
# Agent 服务 — 后台线程 + 目标队列
# ═══════════════════════════════════════════════

class AgentService:
    """后台运行的 agent 服务。接收目标，串行执行。"""

    def __init__(self):
        self.agent = AgentLoop()
        self.scheduler = TaskScheduler()
        self.goal_queue = queue.Queue()
        self.current_result: Optional[AgentResult] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._history: list[AgentResult] = []

    def start(self):
        """启动后台线程"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="AgentLoop")
        self._thread.start()
        sys.stderr.write("[AgentService] 后台线程已启动\n")
        sys.stderr.flush()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def submit(self, goal: str) -> str:
        """提交一个目标，返回 task_id"""
        task_id = f"goal_{int(time.time())}"
        self.goal_queue.put({"task_id": task_id, "goal": goal})
        return task_id

    def get_status(self) -> dict:
        with self._lock:
            current = None
            if self.current_result:
                current = {
                    "goal": self.current_result.goal,
                    "success": self.current_result.success,
                    "steps": self.current_result.total_steps,
                    "summary": self.current_result.final_summary,
                    "duration_s": self.current_result.total_duration_ms / 1000
                }
            return {
                "running": self._running,
                "queue_size": self.goal_queue.qsize(),
                "current": current,
                "history": [
                    {"goal": r.goal[:80], "success": r.success, "steps": r.total_steps}
                    for r in self._history[-10:]
                ],
                "scheduler": self.scheduler.status()
            }

    def _loop(self):
        """主循环：处理目标队列 + 调度任务"""
        while self._running:
            try:
                # 检查调度任务
                due_tasks = self.scheduler.get_due()
                for task in due_tasks:
                    sys.stderr.write(f"[AgentService] 调度任务到期: {task.goal[:60]}...\n")
                    sys.stderr.flush()
                    self.goal_queue.put({"task_id": task.task_id, "goal": task.goal, "scheduled_task": task})

                # 处理队列
                try:
                    item = self.goal_queue.get(timeout=5)
                except queue.Empty:
                    continue

                goal = item["goal"]
                scheduled_task = item.get("scheduled_task")

                sys.stderr.write(f"\n{'='*60}\n")
                sys.stderr.write(f"[AgentService] 开始执行: {goal[:100]}\n")
                sys.stderr.write(f"{'='*60}\n")
                sys.stderr.flush()

                result = self.agent.run(goal)

                with self._lock:
                    self.current_result = result
                    self._history.append(result)
                    if len(self._history) > 100:
                        self._history = self._history[-100:]

                if scheduled_task:
                    self.scheduler.mark_done(scheduled_task)

                sys.stderr.write(f"[AgentService] 完成: {'✓' if result.success else '✗'} | "
                               f"{result.total_steps}步 | {result.total_duration_ms/1000:.1f}s | "
                               f"{result.final_summary[:80]}\n")
                sys.stderr.flush()

            except Exception as e:
                sys.stderr.write(f"[AgentService] 错误: {e}\n")
                import traceback
                traceback.print_exc(file=sys.stderr)
                sys.stderr.flush()


# ═══════════════════════════════════════════════
# CLI / 测试
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  黑洞 v3 自主执行引擎 — 自检")
    print("=" * 60)

    agent = AgentLoop()
    print(f"工具: {agent.tools.tool_names()}")
    print(f"锚点: {agent.bh.anchor.root_goal[:60]}...")
    print(f"主干节点: {len(agent.bh.trunk.nodes)}")
    print()

    # 简单自检目标
    goal = "检查 brain_1GB 目录下有哪些 Python 文件，列出前5个"
    print(f"目标: {goal}")
    print("-" * 40)

    result = agent.run(goal, max_steps=3)

    print(f"\n结果: {'[OK]' if result.success else '[FAIL]'}")
    print(f"步数: {result.total_steps}")
    print(f"耗时: {result.total_duration_ms/1000:.1f}s")
    print(f"摘要: {result.final_summary}")
    if result.steps:
        for s in result.steps:
            print(f"  第{s.step_num}步: {s.action} → {'[OK]' if s.result.success else '[FAIL]'} | {s.result.output[:80]}...")
