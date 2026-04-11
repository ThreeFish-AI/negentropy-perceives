<h1 align="center">Negentropy Perceives</h1>

<p align="center">
  <strong>面向下一代智能体的全天候感知引擎 (商业级 MCP Server)</strong><br/><br/>
  赋予 AI Agent 真正的“千里眼 x 顺风耳”。无论是动态加载的 SPA 网页、严苛的反爬虫矩阵，还是排版极其复杂的学术论文 PDF，统统手到擒来，咀嚼转化成最纯净清爽的 Markdown 原浆，直接投喂大模型。
</p>

<p align="center">
  <a href="#quick-start"><img src="https://img.shields.io/badge/Python-3.13+-blue?logo=python&logoColor=white" alt="Python" /></a>
  <a href="https://github.com/ThreeFish-AI/negentropy-perceives/blob/master/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License" /></a>
  <a href="https://pypi.org/project/negentropy-perceives/"><img src="https://img.shields.io/pypi/v/negentropy-perceives?color=orange" alt="PyPI" /></a>
  <a href="https://github.com/ThreeFish-AI/negentropy-perceives/stargazers"><img src="https://img.shields.io/github/stars/ThreeFish-AI/negentropy-perceives?style=social" alt="Stars" /></a>
  <img src="https://img.shields.io/badge/status-alpha-orange?logo=statuspage&logoColor=white" alt="Alpha" />
</p>

<p align="center">
  <b>MCP 原生支持</b> · <b>10+ 级流水线降级处理</b> · <b>LLM 智能裁决模式</b>
</p>

<br />

## ✨ 为什么它是您的首选？

当下的各种 AI 智能体项目中，信息感知这类“脏活累活”往往最容易随着时间推移变得极其丑陋且脆弱。基于**正交分解与熵减 (Negentropy)** 的底层工程哲学，我们替你彻底封锁了底层网络通信与格式解构的混沌，只向你的沙箱池中注入无可争议的确定性：

- 🕵️ **Web 隐形刺客**: 面对重度渲染的 SPA 和严防死守的反扒策略？引擎内置 5 级防线穿透机制（从极速并发到无头隐身浏览器轮换）。所见即所得，各类瀑布流如同探囊取物。
- 📑 **PDF 绞肉机**: 不要再妥协于错位的表格或丢失的符号。独创“引擎打擂”机制，启动 `Smart` 模式即可召唤 LLM 亲自督战，裁判调度 Docling、PyMuPDF 等 7 大专业引擎并发解构，精准萃取 LaTeX 公式、复杂表格矩阵甚至深层版面特征。
- 🦾 **工业级重载底座**: 摒弃玩具级的粗暴封装。内核植入指数量级退避重试网络、多重限速熔断防御，以及激进的内存预载机制 (Cache)。依托全双工 `asyncio` 跑满机器单节点极限吞吐量。
- 🔌 **零摩擦的 MCP 接驳**: 坚决拥抱标准 Model Context Protocol 协议规范。依托 HTTP / STDIO / SSE 标准传输模式，抛弃冗杂代码胶水，一键免密注入 Claude Desktop 或 Cursor 环境。

## 🚀 经典 Quick Start

只需不足百秒，开启通向干净数据的任意门。

### 1. 毫秒级装载

```bash
# 推荐使用极速丝滑的 uv 部署环境（提示: 需要 Python 3.13+）
uv add negentropy-perceives
```

### 2. 轰鸣启动引擎

一键挂载，开箱即用：

```bash
negentropy-perceives  # 服务已就绪：正默认监听 localhost:8081 提供 MCP-HTTP 通道
```

### 3. 一行代码见证感知力

通过自带的高阶 SDK 体验何为“瞬间感知”：

```python
import asyncio
from negentropy.perceives.sdk import NegentropyPerceivesClient

async def perceive_world():
    # 瞬间链接本地引擎底座
    async with NegentropyPerceivesClient() as client:
        result = await client.convert_webpage_to_markdown(
            url="https://zh.wikipedia.org/wiki/熵",
        )
        print("====== 萃取原浆 ======")
        print(result.markdown_content[:250], "......\n")
        print(f"📊 从噪音中汲取纯净字词: {result.word_count}")

asyncio.run(perceive_world())
```

> 💡 **进阶锦囊**: 首次深呼吸运转时，底座会自动生成专属的配置要塞至 `~/.negentropy/perceives.config.yaml`。里面潜藏着各类高端玩法的解锁机关。

## 🛠️ 决胜数据黑洞的军火库

我们拒绝拿只能跑通 Demo 的短命积木忽悠人。底座出场即标配 6 把锋利无匹的“手术刀”，由底层并发核心强劲驱动，专治乱象频发的数字深渊：

**🌐 Web 空间的降维打击**

- `convert_webpage_to_markdown`：**单兵网页蒸馏釜**。面对重度渲染的 SPA 应用或严密反爬风控？它能从容切入，绝情剥离成吨的广告与内容侧边栏，完美定格语义树，甚至能将图片提纯为 Base64 无损嵌于结果内。所见即所得。
- `batch_convert_webpages_to_markdown`：**超线程洗稿集群**。单线作战太磨叽？直接向它投喂一份庞大的 URL 阵列。异步引擎拉满配置，万千冗杂的动态页面眨眼间即可并行碾碎、蒸馏为清脆的顶级大模型语料。

**📄 硬核 PDF 的叹息之墙**

- `convert_pdf_to_markdown`：**骨灰级解构台**。还在因财报里的跨页畸形表格或学术顶会里的高密 LaTeX 公式而抓狂？抛给它！启动专属的 `smart 模式` 召唤多核心引擎竞技互搏，无损还原高维的图文混排。再难啃的 PDF 也给你嚼碎成最丝滑的文本流。
- `batch_convert_pdfs_to_markdown`：**全天候重装推土机**。彻底无视本地文件系统与远端云地址边界。不用管报表堆积如山，一口气推入并发洗稿队列，让你的专属 Knowledge Base 体验一把“暴风吸入”的爽快感。

**🔦 前沿阵地的情报嗅探**

- `extract_links`：**全域链路雷达**。它是大模型尝试“涌现与全自动漫游”的开路先锋。抛入一个靶点，瞬间摸出整站的爬行拓扑图，并支持防波堤级别的隐秘内外链精确剔除。
- `get_page_info`：**超频状态谍报兵**。在决定倾听长文前，为何不在毫秒内先掠取一发目标网站的状态码、载荷体量与隐性 Meta 标识？它专为你那充满好奇心的 Agent 提供绝佳的潜入行动预判依据。

## 🗺️ 架构剖析与高阶子路径 (模块引路)

在“功能正交分层”的信条下，我们备齐了 4 条截然不同的探险子径。阁下打算向何处发测？

| 探索域                      | 您将在此挖掘的宝藏...                                                                                                                   | 传送门                                     |
| :-------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------- | :----------------------------------------- |
| **📘 用户与作战指南**       | 6 大硬核 MCP 施法工具的终极参数图表、各类批处理实战组合拳、无缝接入 Claude Desktop 的快捷通道，以及 YAML 重金四层防线的优先级解构。     | `👉 `[前往用户指南](./docs/user-guide.md)  |
| **🏗️ 解析引擎的全景蓝图**   | 建立在有向无环图 (DAG) 上的 5 级沉降深网管线、引擎角斗比赛与融合判分的底层逻辑、主打死磕 OOM (Out Of Memory) 护栏的防御性编码设计手记。 | `👉 `[纵览架构设计](./docs/framework.md)   |
| **🛠️ 二次魔改与共创者契约** | TDD 本地极速炼丹环境的重生法则、苛求完美（但能大幅降低心智负担）的 PR 准入红线准则。                                                    | `👉 `[深入开发指引](./docs/development.md) |
| **📜 脱胎换骨的里程史书**   | 回首每个 Alpha / Beta 里我们铲除了多少荒唐 Bug，又酝酿着哪些即将颠覆传统的野望。                                                        | `👉 `[查阅 CHANGELOG](CHANGELOG.md)        |

## 🤝 社区联合作战网络

万维网页与海量非结构化文本的另一面是噪音深渊，唯有持续的代码演进方可稳步前行。
若您手中正握有将混沌拉回秩序的灵感，请务必不吝赐教：

1. 动键盘前，烦请顺路翻转一页 [开发指南](./docs/development.md) 校对贡献坐标系。
2. 将您的重磅想法掷向 [Issue 板](https://github.com/ThreeFish-AI/negentropy-perceives/issues) 或是直接提送带有改变战局力量的 [PR 通道](https://github.com/ThreeFish-AI/negentropy-perceives/pulls)。

## ⚖️ 知识产权与数字边界共识

全套底层源码依照最通透开放的 [MIT](LICENSE) 先锋许可协议颁发，© 2026 [ThreeFish-AI](https://github.com/ThreeFish-AI) 全权解释所有架构逻辑。

> [!WARNING]
>
> **写在执行回车键前**
>
> 技术力是一种到达真理的途径，绝非盲操的借口。我们交付这柄吹毛断发的利刃，但深切反对无节制、掠夺式的野蛮数据收割。
>
> 敬请以无上敬畏之心，时刻遵守并爱护目标服务器与服务方 (TOS) 的运作边界。在释放大规模自动抓取的咒语前，主动系牢温和请求频率的缰绳。
>
> 工具纵是冰冷钢铁，但驱动其意志的人类及智能体，当为文明本身。
