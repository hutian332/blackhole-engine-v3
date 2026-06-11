# Blackhole Engine V3 — 概念自有推理引擎

> **万物是死的，是静态的不同位置的马赛克和色块。体积的大小就是色块的密集度。**  
> **时间，是万物运动、变化的底层驱动力。**

黑洞理论 v3 完整实现。不是"另一个AI工具"——是对智能、时间、物质三者底层关系的重新定义与工程落地。

## 三支柱

```
                 黑洞理论 v3
               ┌──────────────┐
               │ 万物死·马赛克  │ ← 物质本质（静态色块）
               │ 时间驱动论    │ ← 活力本源（时间推动状态更迭）
               │ AI时间可控论  │ ← AI的"物质"是数据，时间只是索引变量
               └──────────────┘
                        ↓
              概念引擎三层架构
               ┌──────────────┐
               │ 锚点层       │ ← 不可变根目标向量
               │ 主干层       │ ← 概念推进历史 (append-only)
               │ 素材层       │ ← 日常对话/输入流
               └──────────────┘
```

## 核心模块

| 模块 | 大小 | 说明 |
|------|------|------|
| `v3_achilles.py` | 118KB | 全链路创作引擎 — 609参数码+26统一标尺 |
| `super_brain_server.py` | 72KB | v3大脑 — OpenAI兼容API + 概念路由 + Agent Loop |
| `agent_loop.py` | 36KB | 自主执行引擎 — ReAct模式 + 7工具 + 定时调度 |
| `self_improve.py` | 24KB | 自我完善引擎 — 读自己→找短板→改代码→验证 |
| `v3_eye.py` | 18KB | 程序化视觉 — 6/8种视觉能力，不依赖视觉模型 |
| `v3_terrain_eye.py` | 20KB | 地形视觉 — 画面=高度场，纯数学检测 |
| `v3_delta_eye.py` | 8KB | 帧差检测 — "不看有什么，看变了什么" |
| `v3_visual_learner.py` | 13KB | 视觉记忆 — 感知哈希+相似匹配+JSON持久化 |
| `v3_live_compare.py` | 11KB | 实时对比 — 2fps监控+记忆匹配 |
| `v3_pet_engine.py` | 21KB | 宠物引擎 — 21关节骨架+8动作+状态机 |
| `frenchie_pet_v6.html` | 20KB | 法斗桌宠 — 5000+3D点阵渲染 |
| `v3_light_params.py` | 22KB | 光线参数库 — 41码+自然语言→编码映射 |
| `blackhole_v3_engine.py` | 16KB | v3核心 — 概念路由+三层存储 |

## achilles 参数全景

```
609 参数码 + 26 统一标尺
═══════════════════════════════════
场景   28   地形/水/天气/风/植被
光影   35   光源/亮度/AO/SSS/高光/阴影
镜头   24   机位/运镜/转场/景别/构图
人物  196   身体/手/口/眼8维/眉/颊/发/服饰
手指   23   15关节+8手势
FACS   34   25面部动作单元+9情绪映射
情绪   10   一键联动全维度
剧情   18   结构/弧线/冲突/节奏
色彩   23   调色板+分级
粒子   14   雨雪尘雾火泡魔叶
动作   27   走跑跳蹲坐转头手全身
物理   25   重力/碰撞/关节/布料/粒子
音频   64   声线/情绪/环境/合成/混音
口型   76   音素+拼音+过渡曲线
安全   15   水印/授权/溯源/签名
输出   20   多引擎调度/校验/打包
```

## 快速开始

### 环境要求
- Windows 10/11
- Python 3.10+
- Ollama (可选，用于本地推理)
- RTX 3060 12GB+ (推荐)

### 安装

```bash
# 克隆
git clone https://github.com/hutian332/blackhole-engine-v3.git
cd blackhole-engine-v3

# 安装依赖
pip install -r requirements.txt

# 复制核心文件到brain_1GB
mkdir C:\Users\%USERNAME%\brain_1GB
copy *.py C:\Users\%USERNAME%\brain_1GB\
```

### 启动

```bash
# 1. 启动v3大脑 (端口8081)
python super_brain_server.py

# 2. 运行achilles演示
python v3_achilles.py

# 3. 启动法斗桌宠 (端口8766)
python v3_pet_engine.py
# 浏览器打开 http://127.0.0.1:8766/

# 4. 测试视觉系统
python v3_terrain_eye.py
python v3_delta_eye.py
```

### API端点

| 端点 | 说明 |
|------|------|
| `GET /v1/agent/status` | 查看v3 Agent状态 |
| `POST /v1/agent/goal` | 提交目标 `{"goal":"..."}` |
| `POST /v1/agent/schedule` | 定时任务 |
| `GET /v1/agent/self_improve` | 自我完善审计 |

## 核心理念

**不是"让AI更像人"——是拆解"人是什么"。**

- 真人表演：不稳定、不可复现、毫厘差异难控
- 标值体系：每帧可查、每次复现、每处细节有精确刻度

电影 = 死帧 × 时间驱动 → 看起来活了。  
代码 = 死文本 × CPU执行 → 看起来在思考。  
参数库 = 死编码 × 帧调度 → 生成"活的"视频。

## 作者

**殷竺欣**  
黑洞理论创始人 · 概念自有推理引擎发明人  
RTX 3060 12GB 上跑通了 Qwen2.5-32B 裸张量推理

## 许可证

MIT License — 但核心架构知识产权归殷竺欣所有。  
详情见 [LICENSE](LICENSE) 及 `IDENTITY_SIGNATURE` 水印签名。
