<h1 align="center">Negentropy Perceives</h1>

<p align="center">
  <strong>商业级 MCP Server</strong> — 让 AI Agent 看懂任意网页和 PDF，不管对面是 SPA、反爬墙还是密密麻麻的学术公式。
</p>

<p align="center">
  <a href="#快速开始"><img src="https://img.shields.io/badge/Python-3.13+-blue?logo=python&logoColor=white" alt="Python" /></a>
  <a href="https://github.com/ThreeFish-AI/negentropy-perceives/blob/master/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License" /></a>
  <a href="https://pypi.org/project/negentropy-perceives/"><img src="https://img.shields.io/pypi/v/negentropy-perceives?color=orange" alt="PyPI" /></a>
  <a href="https://github.com/ThreeFish-AI/negentropy-perceives/stargazers"><img src="https://img.shields.io/github/stars/ThreeFish-AI/negentropy-perceives?style=social" alt="Stars" /></a>
  <img src="https://img.shields.io/badge/status-alpha-orange?logo=statuspage&logoColor=white" alt="Alpha" />
</p>

<p align="center">
  <b>6 个 MCP 工具</b> · <b>7 种 PDF 处理方法</b> · <b>Pipeline 编排</b> · <b>LLM Smart 模式</b>
</p>

<br />

## ✨ 为什么选它？

| 🧠 Smart 模式 | 🕵️ 隐身抓取 | ⚡ 引擎降级 |
| :--- | :--- | :--- |
| **LLM 当裁判，多引擎并行出卷，最优答案胜出**<br/>分析文档特征 → 并行调度 Docling / PyMuPDF → 择优融合。学术论文、财报、技术手册，一个 `method="smart"` 搞定。需安装 `litellm` 并配置 API Key。 | **5 种策略，对付一切网页**<br/>`auto` / `simple` / `selenium` / `stealth_selenium` / `stealth_playwright`。随机 UA 轮换 + 浏览器隐身，动态页面照抓不误。 | **Docling → MineRU → Marker → PyMuPDF → PyPDF**<br/>缺一个引擎？接着跑。缺五个？那可能需要检查一下安装了什么。GPU 加速（CUDA / MPS / XPU）可选开启。 |

<details>
<summary>📖 更多企业级特性</summary>

- 🔀 **Pipeline 编排框架**: Stage 化处理管线，竞争/降级双模式，PDF 10 Stages + WebPage 9 Stages（含 4 个并行富元素子任务）
- 🚀 **并发批处理**: `batch_convert_webpages_to_markdown` / `batch_convert_pdfs_to_markdown` 支持 asyncio 并发
- 🖼️ **深度内容提取**: 表格识别、LaTeX 公式保持、图像 base64 嵌入
- 🔄 **弹性保障**: 指数退避重试（×3）、频率限速（2 req/s）、内存缓存三层防护
- ⚙️ **YAML 四层配置**: 内置默认 → 用户 YAML → 环境变量 → `-c` 显式（最高），优先级清晰
- 🎯 **Python SDK**: `NegentropyPerceivesClient` 一行连接，类型化便捷方法开箱即用
- 📡 **三种传输模式**: HTTP（默认） / STDIO / SSE，Claude Desktop 一键接入

</details>

## 🚀 快速开始

### 安装

```bash
uv add negentropy-perceives
```

> 需要 [uv](https://docs.astral.sh/uv/) 包管理器和 **Python >= 3.13**。

### Hello World

```python
import asyncio
from negentropy.perceives.sdk import NegentropyPerceivesClient

async def main():
    async with NegentropyPerceivesClient() as client:   # 默认连接 localhost:8081/mcp
        result = await client.convert_webpage_to_markdown(
            url="https://example.com",
        )
        print(result.markdown_content)     # 干净的 Markdown 正文
        print(f"字数: {result.word_count}")

asyncio.run(main())
```

> 首次运行会自动生成用户配置至 `~/.negentropy/perceives.config.yaml`。

### 启动 MCP Server

```bash
negentropy-perceives               # 默认 HTTP 模式（localhost:8081/mcp）
negentropy-perceives --init-config # 生成用户配置模板至 ~/.negentropy/
negentropy-perceives -c my.yaml    # 使用自定义配置文件
```

<details>
<summary>⌨️ 更多示例：PDF 转换 · 链接提取 · 批量转换</summary>

#### PDF 转 Markdown

```python
async with NegentropyPerceivesClient() as client:
    result = await client.call_tool("convert_pdf_to_markdown", {
        "pdf_source": "report.pdf",
        "method": "auto",           # auto / pymupdf / pypdf / docling / mineru / marker / smart
        "page_range": [0, 9],       # 可选：[start, end]，从 0 开始
        "extract_tables": True,
        "extract_formulas": True,
    })
```

#### 链接提取

```python
async with NegentropyPerceivesClient() as client:
    result = await client.call_tool("extract_links", {
        "url": "https://docs.example.com",
        "internal_only": True,       # 仅提取站内链接
    })
    # result.links — 链接列表
    # result.total_links / result.internal_links_count / result.external_links_count
```

#### 批量网页转 Markdown

```python
async with NegentropyPerceivesClient() as client:
    result = await client.call_tool("batch_convert_webpages_to_markdown", {
        "urls": [
            "https://blog.example.com/post1",
            "https://blog.example.com/post2",
        ],
        "method": "auto",
        "extract_main_content": True,
    })
```

完整 API 参考与高级用法详见 [用户指南](docs/user-guide.md)。

</details>

## 🛠️ 工具全景（6 个 MCP 工具）

### 🔍 数据提取（2 工具）

| 工具 | 一句话 | 核心能力 |
| :--- | :--- | :--- |
| `extract_links` | 链接提取 | 域名过滤、内外链分类、白/黑名单过滤 |
| `get_page_info` | 页面侦察 | 标题、状态码、描述、Content-Type、Content-Length 一键获取 |

### 🌐 Markdown 转换（2 工具）

| 工具 | 一句话 | 核心能力 |
| :--- | :--- | :--- |
| `convert_webpage_to_markdown` | **页面 → MD** | 5 种抓取策略 + 主内容提取 + 格式化选项 + 图片嵌入 + Pipeline 编排 |
| `batch_convert_webpages_to_markdown` | 批量转 MD | 多 URL 并发转换 + 统计摘要 |

### 📄 PDF 处理（2 工具）

| 工具 | 一句话 | 核心能力 |
| :--- | :--- | :--- |
| `convert_pdf_to_markdown` | **PDF → MD** | 7 种提取方法 + 图像/表格/公式提取 + Smart 模式 + Pipeline 编排 |
| `batch_convert_pdfs_to_markdown` | 批量 PDF | 多文档并发 + 统计摘要（URL/本地路径混用） |

<details>
<summary>🔧 PDF 处理方法与依赖说明</summary>

```
7 种 method 可选值：
  auto          → 自动选择最佳引擎（优先 Pipeline 编排）
  smart         → LLM 三阶段编排（分析→执行→综合），需 [llm] 依赖
  docling       → AI 布局分析 + TableFormer 表格（核心依赖）
  mineru        → 深度学习文档结构分析（可选，Apache 2.0）
  marker        → 基于 Nougat 模型（可选，GPL-3.0）
  pymupdf       → 快速纯文本提取（核心依赖）
  pypdf         → 基础文本兜底（核心依赖）

降级链（method=auto 时自动触发）：
  Docling → MineRU → Marker → PyMuPDF → PyPDF
```

**依赖安装说明：**

| 引擎 | 依赖类型 | 安装命令 |
| :--- | :--- | :--- |
| **Docling** | 核心依赖（随包安装） | 已内置，需在配置中 `docling.enabled: true` 启用 |
| **PyMuPDF / PyPDF** | 核心依赖（随包安装） | 已内置，开箱即用 |
| **MineRU** | 可选 | `uv add "negentropy-perceives[mineru]"` |
| **Marker** | 可选（GPL-3.0） | `uv add "negentropy-perceives[marker]"` |
| **Smart 模式 (LLM)** | 可选 | `uv add "negentropy-perceives[llm]"` + 配置 API Key |
| **全部引擎** | — | `uv add "negentropy-perceives[all-engines,llm]"` |

> 未安装的可选引擎会通过 `is_available()` 自动跳过，不影响基础功能运行。

**Smart 模式** (`method="smart"`): LLM 三阶段编排 — 分析文档特征 → 并行调度多引擎 → 择优融合输出。默认使用智谱 GLM-5 (`zhipu/glm-5-plus-250414`)。未配置 API Key 时自动降级到 Docling + PyMuPDF 双引擎。

</details>

### 🔄 传输模式

| 模式 | 适用场景 | 推荐度 |
| :--- | :--- | :---: |
| **HTTP**（默认） | 生产环境、远程访问、多客户端 | ⭐⭐⭐⭐⭐ |
| **STDIO** | 本地开发、Claude Desktop | ⭐⭐⭐ |
| **SSE** | 遗留系统兼容 | ⭐⭐ |

> 详细配置（host / port / CORS / 认证）参见 [用户指南 > MCP Server 配置](docs/user-guide.md#mcp-server-配置)。

## ⚙️ 配置与集成

### YAML 四层优先级（低 → 高）

```
内置默认 (config.default.yaml)
  └→ 用户配置 (~/.negentropy/perceives.config.yaml)
       └→ 环境变量 (NEGENTROPY_PERCEIVES_*)
            └→ CLI 显式 (negentropy-perceives -c my.yaml)  ← 最高优先级
```

生成用户配置模板：

```bash
negentropy-perceives --init-config
```

### Smart 模式启用

```bash
# 安装 LLM 依赖
uv add "negentropy-perceives[llm]"
```

在 `~/.negentropy/perceives.config.yaml` 中配置：

```yaml
llm:
  api_key: "your-api-key"
  model: zhipu/glm-5-plus-250414  # 默认模型：智谱 GLM-5
```

> 未配置 API Key 时，`method="smart"` 自动降级到 Docling + PyMuPDF 双引擎处理。

### Claude Desktop 集成（STDIO 模式）

```json
{
  "mcpServers": {
    "negentropy-perceives": {
      "command": "negentropy-perceives",
      "env": {
        "NEGENTROPY_PERCEIVES_TRANSPORT__MODE": "stdio"
      }
    }
  }
}
```

## 🏗️ 架构一览

```mermaid
graph TD
    subgraph CLIENT["客户端层"]
        A1["Claude Desktop / Cursor<br/>AI Agent"]
        A2["NegentropyPerceivesClient<br/>Python SDK"]
    end

    subgraph TOOLS["MCP 工具层 · 6 Tools · @app.tool()"]
        T1["extract_links<br/>链接提取"]
        T2["get_page_info<br/>页面元数据"]
        T3["convert_webpage_to_markdown<br/>网页 → Markdown"]
        T4["batch_convert_webpages<br/>批量网页 → Markdown"]
        T5["convert_pdf_to_markdown<br/>PDF → Markdown"]
        T6["batch_convert_pdfs<br/>批量 PDF → Markdown"]
    end

    subgraph PIPELINE["Pipeline 编排层 · method=auto 触发"]
        PW["WebPage Pipeline<br/>9 Stages · 降级+竞争双模式<br/>合规→获取→反检测→主内容→清洗→转换→格式化"]
        PP["PDF Pipeline<br/>10 Stages · 降级+竞争双模式<br/>预处理→快扫→布局→文本→表格→公式→图片→代码→组装"]
    end

    subgraph ENGINES["处理引擎层"]
        E1["WebScraper<br/>simple / selenium / stealth_selenium / stealth_playwright"]
        E2["Docling · MineRU · Marker<br/>PyMuPDF · PyPDF"]
        E3["LLM Smart<br/>zhipu/glm-5-plus · litellm"]
        E4["MarkdownConverter<br/>markitdown + 格式化管线"]
    end

    subgraph INFRA["基础设施层"]
        I1["RateLimiter · 2 req/s"]
        I2["RetryManager · 指数退避 ×3"]
        I3["Config · 4 层优先级 · YAML"]
    end

    A1 & A2 -->|"MCP over HTTP/STDIO/SSE"| TOOLS
    T3 & T4 -->|"method=auto → Pipeline"| PW
    T3 & T4 -->|"method=simple/selenium/... → 传统路径"| E1
    T5 & T6 -->|"method=auto → Pipeline"| PP
    T5 & T6 -->|"method=docling/smart/... → 传统路径"| E2 & E3
    T1 & T2 --> E1
    PW --> E1 & E4
    PP --> E2 & E3
    E1 & E2 & E3 & E4 --> INFRA

    style CLIENT fill:#1e1b4b,stroke:#6366f1,color:#e0e7ff
    style TOOLS fill:#1e3a8a,stroke:#3b82f6,color:#ffffff
    style PIPELINE fill:#78350f,stroke:#f59e0b,color:#fef3c7
    style ENGINES fill:#14532d,stroke:#22c55e,color:#dcfce7
    style INFRA fill:#134e4a,stroke:#14b8a6,color:#ccfbf1
```

**典型工具协同场景：**

| 场景 | 工具链路 |
| :--- | :--- |
| 网站内容归档 | `get_page_info` → `extract_links` → `batch_convert_webpages_to_markdown` |
| 学术论文处理 | `convert_pdf_to_markdown`（method=smart）→ Knowledge Base |
| 快速文档提取 | `extract_links`（内链列表）→ `batch_convert_webpages_to_markdown`（并发转换） |
| 多格式批量处理 | `batch_convert_pdfs_to_markdown` + `batch_convert_webpages_to_markdown` 并行 |

> 完整架构设计（5 层分解、模块依赖、数据流）详见 [架构设计](docs/framework.md)。

## 🎯 典型场景

<details>
<summary>📰 网站内容归档</summary>

提取站内所有链接 → 并发转换为 Markdown 归档：

```python
async with NegentropyPerceivesClient() as client:
    # 1. 获取站内所有链接
    links_result = await client.call_tool("extract_links", {
        "url": "https://docs.example.com",
        "internal_only": True,
    })

    urls = [link["url"] for link in links_result["links"]]

    # 2. 批量转换为 Markdown
    await client.call_tool("batch_convert_webpages_to_markdown", {
        "urls": urls,
        "extract_main_content": True,
    })
```

</details>

<details>
<summary>🎓 学术论文智能处理</summary>

利用 Smart 模式自动处理含公式、表格、代码、图像的复杂学术 PDF：

```python
async with NegentropyPerceivesClient() as client:
    result = await client.call_tool("convert_pdf_to_markdown", {
        "pdf_source": "arxiv_paper.pdf",
        "method": "smart",              # LLM 编排多引擎，择优融合
        "extract_formulas": True,
        "extract_tables": True,
    })
    # 返回包含 LaTeX 公式、Markdown 表格、代码块的高质量输出
```

</details>

<details>
<summary>📄 批量 PDF 处理</summary>

混合 URL 和本地路径，并发批量转换：

```python
async with NegentropyPerceivesClient() as client:
    result = await client.call_tool("batch_convert_pdfs_to_markdown", {
        "pdf_sources": [
            "https://example.com/report2024.pdf",
            "/local/archive/manual.pdf",
            "https://arxiv.org/pdf/2401.00001",
        ],
        "method": "auto",
        "extract_images": True,
        "extract_tables": True,
        "extract_formulas": True,
    })
    # 返回每个文档的转换结果和统计摘要
```

</details>

## 📚 文档导航

| 文档 | 目标读者 | 内容概要 |
| :--- | :--- | :--- |
| [用户指南](docs/user-guide.md) | 所有用户 | Quick Start、6 工具详解、API 参考、FAQ |
| [架构设计](docs/framework.md) | 架构师 / 贡献者 | 5 层架构、Pipeline 框架、引擎设计 |
| [开发指南](docs/development.md) | 开发者 / QA | 环境搭建、测试体系、编码规范、发布流程 |
| [用户指南 > MCP Server 配置](docs/user-guide.md#mcp-server-配置) | 运维 / 开发者 | YAML 四层配置、环境变量速查 |
| [版本里程](CHANGELOG.md) | 所有用户 | 版本历史与变更记录 |

## 🤝 参与贡献

欢迎通过 [Issue](https://github.com/ThreeFish-AI/negentropy-perceives/issues) 反馈问题，或提交 [Pull Request](https://github.com/ThreeFish-AI/negentropy-perceives/pulls) 改进项目。

贡献前请阅读 [开发指南](docs/development.md) 了解代码规范与提交流程。

## 📄 许可证

[MIT](LICENSE) © 2025 [ThreeFish-AI](https://github.com/ThreeFish-AI)

---

> ⚠️ 当前版本 **0.2.0a1（Alpha）**，API 可能随时迭代，生产环境请锁定版本。
>
> ⚠️ **伦理提醒**: 技术本身是中立的，但使用者的选择定义了它的价值。请负责任地使用本工具——尊重目标网站的服务条款、知识产权，合理控制请求频率。
