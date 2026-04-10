---
id: user-guide
sidebar_position: 3
title: User Guide
description: Negentropy Perceives MCP Server 终端用户使用指南，涵盖 MCP Server 部署配置、12 个 MCP 工具参考、API 编程接口、高级使用场景及开发者命令速查。
last_update:
  author: Aurelius
  date: 2026-04-07
tags:
  - User Guide
  - MCP Server
  - MCP Tools
  - API Usage
---

## 概述

Negentropy Perceives 是一个基于 FastMCP 和 Scrapy、markdownify、pypdf、pymupdf 联合构建的强大、稳定的网页内容、PDF 内容提取 MCP Server，具备转换 Web Page、PDF Document 为 Markdown 的能力，专为商业环境中的长期使用而设计。

**核心特性**

- **12 个专业 MCP 工具**：涵盖网页抓取、PDF 转换、链接提取、表单自动化等
- **多种抓取方法**：支持 simple、scrapy、selenium、playwright 等方法，智能选择最佳策略
- **反检测能力**：隐身抓取和表单自动化功能，绕过反爬虫检测
- **智能内容处理**：自动识别主要内容、格式化 Markdown，支持 8 种格式化选项
- **PDF 深度处理**：图像、表格、数学公式提取，支持增强内容处理
- **企业级特性**：速率限制、缓存、重试、监控、代理支持、错误处理

## 快速开始

### 安装

推荐使用 `uvx` 从 GitHub 直接安装：

```bash
uvx --with git+https://github.com/ThreeFish-AI/data-negentropy.perceives.git@v0.1.6 negentropy-perceives
```

### 验证

```bash
# 检查服务器是否正常运行
curl http://localhost:3000/health

# 检查工具列表
curl http://localhost:3000/tools
```

### 配置系统架构

Negentropy Perceives 采用分层配置系统，按优先级从**高到低**：

| 优先级        | 配置源                 | 说明                                     |
| ------------- | ---------------------- | ---------------------------------------- |
| **1（最高）** | `-c/--config` 显式配置 | 通过构造参数传入，覆盖一切               |
| **2**         | 环境变量               | `NEGENTROPY_PERCEIVES_` 前缀             |
| **3**         | 用户 YAML 配置         | `~/.negentropy/perceives.config.yaml`    |
| **4（最低）** | 内置默认配置           | `config.default.yaml`（打包在 wheel 内） |

> **更多信息**
>
> - 系统要求与开发环境搭建 -> [开发指南](./development.md#环境配置)
> - 环境变量完整参考 -> [环境变量完整参考](#环境变量完整参考)

## 开发者命令速查

> 本章节收录 Negentropy Perceives 开发者日常使用的 CLI 命令速查。完整环境配置见[开发指南](./development.md#环境配置)，完整测试流程见[开发指南 > 测试执行](./development.md#测试执行)。

### 服务器启动

#### 基本启动

```bash
# 启动 MCP 服务器（主要启动命令）
uv run negentropy-perceives

# 以 Python 模块方式运行服务器
uv run python -m negentropy.perceives
```

命令入口统一为 `negentropy-perceives`。

#### 开发模式启动

```bash
# 启用调试级别日志输出
uv run --env NEGENTROPY_PERCEIVES_LOG_LEVEL=DEBUG negentropy-perceives

# 启用完整功能特性的开发配置
uv run --env NEGENTROPY_PERCEIVES_ENABLE_JAVASCRIPT=true \
          --env NEGENTROPY_PERCEIVES_USE_RANDOM_USER_AGENT=true \
          negentropy-perceives
```

> 全部环境变量配置项见[环境变量完整参考](#环境变量完整参考)

### 代码质量检查

> 基础 Ruff / MyPy / Pre-commit 命令见[开发指南 · 代码质量保障](./development.md#代码质量保障)

#### 高级用法

```bash
# 查看 Ruff 所有可用的检查规则
uv run ruff rule --all

# MyPy 显示详细的错误代码信息
uv run mypy src/negentropy/perceives/ --show-error-codes

# MyPy 生成 HTML 格式的类型检查报告
uv run mypy src/negentropy/perceives/ --html-report mypy-report
```

### 项目依赖管理

#### 依赖包操作

```bash
# 添加生产环境依赖包
uv add <package-name>

# 添加开发环境依赖包
uv add --dev <package-name>

# 移除不需要的依赖包
uv remove <package-name>

# 更新所有依赖到最新版本
uv lock --upgrade

# 检查项目中过时的依赖
uv tree --outdated
```

#### 依赖信息查询

```bash
# 显示完整的依赖关系树
uv tree

# 列出当前虚拟环境中安装的所有包
uv list

# 显示特定包的详细信息
uv pip show <package-name>
```

### 项目维护

#### 版本号查询

```bash
# 版本号在 pyproject.toml 中维护，运行时由 src/negentropy/perceives/__init__.py 动态读取
# 查看当前项目版本号
uv run python -c "from negentropy.perceives import __version__; print(__version__)"
```

#### 缓存清理

```bash
# 清理 uv 包管理器的缓存
uv cache clean

# 清理 pip 包管理器的缓存
uv pip cache purge

# 清理 Python 编译产生的字节码文件
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete
```

> 完整构建发布流程见[开发指南 · 发布流程](./development.md#发布流程)

### 系统调试与诊断

```bash
# 检查 Negentropy Perceives 相关的环境变量
printenv | grep NEGENTROPY_PERCEIVES

# 验证配置文件的正确性
uv run python -c "from negentropy.perceives.config import settings; print(settings.model_dump())"

# 测试项目模块导入是否正常
uv run python -c "import negentropy.perceives; print('Import successful')"

# 检查 MCP 服务器可用的工具列表
uv run python -c "from negentropy.perceives.tools import app; print([tool.name for tool in app.tools])"
```

> 更多配置排查命令见下方补充。

```bash
# 检查配置来源
uv run python -c "from negentropy.perceives.config import describe_config_sources; print(describe_config_sources())"

# 生成默认用户配置
uv run negentropy-perceives --init-config
```

## MCP Server 配置

### 传输模式

Negentropy Perceives 支持三种传输模式，您可以根据使用场景选择最合适的方式：

| 特性         | STDIO          | HTTP (默认)        | SSE (传统)   |
| ------------ | -------------- | ------------------ | ------------ |
| **适用场景** | 本地开发、调试 | 生产环境、远程访问 | 遗留系统兼容 |
| **部署方式** | 子进程通信     | HTTP 服务器        | HTTP 服务器  |
| **远程访问** | ❌ 不支持      | ✅ 支持            | ✅ 支持      |
| **并发性能** | 良好           | 优秀               | 良好         |
| **会话管理** | 客户端管理     | 服务器管理         | 服务器管理   |
| **推荐度**   | ⭐⭐⭐         | ⭐⭐⭐⭐⭐         | ⭐⭐         |

### 方式一：STDIO 传输模式

从 GitHub 仓库直接安装和运行：

```json
{
  "mcpServers": {
    "negentropy-perceives": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "git+https://github.com/ThreeFish-AI/data-negentropy.perceives.git@v0.1.6",
        "negentropy-perceives"
      ]
    }
  }
}
```

> 开发环境推荐使用 STDIO 模式并启用调试日志，YAML 配置参考：
>
> ```yaml
> # ~/.negentropy/perceives.config.yaml（开发环境）
> # 支持层级化与扁平两种格式，可混用
> transport:
>   mode: stdio
> log:
>   level: DEBUG
> enable_javascript: true
> browser:
>   headless: false
> concurrent_requests: 4
> ```

### 方式二：HTTP 传输模式（生产推荐）

适用于生产环境、远程部署和多客户端访问。

**传输层环境变量：**

| 环境变量                                 | 类型   | 默认值      | 说明                                         |
| ---------------------------------------- | ------ | ----------- | -------------------------------------------- |
| `NEGENTROPY_PERCEIVES_TRANSPORT_MODE`    | `str`  | `http`      | MCP 传输协议模式（`stdio` / `http` / `sse`） |
| `NEGENTROPY_PERCEIVES_HTTP_HOST`         | `str`  | `localhost` | HTTP 服务器绑定主机                          |
| `NEGENTROPY_PERCEIVES_HTTP_PORT`         | `int`  | `8081`      | HTTP 服务器端口                              |
| `NEGENTROPY_PERCEIVES_HTTP_PATH`         | `str`  | `/mcp`      | HTTP 端点路径                                |
| `NEGENTROPY_PERCEIVES_HTTP_CORS_ORIGINS` | `str?` | `*`         | CORS 来源白名单（`null` 禁用）               |

**服务端启动：**

```bash
# 通过环境变量启动
NEGENTROPY_PERCEIVES_TRANSPORT_MODE=http \
NEGENTROPY_PERCEIVES_HTTP_HOST=0.0.0.0 \
NEGENTROPY_PERCEIVES_HTTP_PORT=8081 \
negentropy-perceives
```

也可通过用户 YAML 配置文件 `~/.negentropy/perceives.config.yaml` 进行持久化配置：

```yaml
# ~/.negentropy/perceives.config.yaml（生产环境）
# 支持层级化与扁平两种格式，可混用
transport:
  mode: http
http:
  host: "0.0.0.0"
  port: 8081
log:
  level: INFO
enable_javascript: true
browser:
  headless: true
concurrent_requests: 32
use_random_user_agent: true
```

**客户端配置：**

```json
{
  "mcpServers": {
    "negentropy-perceives": {
      "url": "http://localhost:8081/mcp",
      "transport": "http"
    }
  }
}
```

**Python SDK 连接：**

```python
from negentropy.perceives.sdk import NegentropyPerceivesClient

async with NegentropyPerceivesClient("http://localhost:8081/mcp") as client:
    result = await client.scrape_webpage(
        url="https://example.com",
        method="auto",
    )
```

### 方式三：SSE 传输模式（传统兼容）

适用于需要向后兼容的遗留系统。

**服务端启动：**

```bash
NEGENTROPY_PERCEIVES_TRANSPORT_MODE=sse \
NEGENTROPY_PERCEIVES_HTTP_PORT=8081 \
negentropy-perceives
```

**客户端配置：**

```json
{
  "mcpServers": {
    "negentropy-perceives": {
      "url": "http://localhost:8081/mcp",
      "transport": "sse"
    }
  }
}
```

### Claude Desktop 配置示例

在 Claude Desktop 的 `claude_desktop_config.json` 文件中添加：

```json
{
  "mcpServers": {
    "negentropy-perceives": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "git+https://github.com/ThreeFish-AI/data-negentropy.perceives.git@v0.1.6",
        "negentropy-perceives"
      ],
      "env": {
        "NEGENTROPY_PERCEIVES_ENABLE_JAVASCRIPT": "true",
        "NEGENTROPY_PERCEIVES_CONCURRENT_REQUESTS": "8"
      }
    }
  }
}
```

**注意事项：**

- GitHub 仓库地址：`https://github.com/ThreeFish-AI/data-negentropy.perceives.git`
- 使用当前最新稳定版本

### 安全配置建议

**CORS 配置：**

```bash
# 限制访问域名
NEGENTROPY_PERCEIVES_HTTP_CORS_ORIGINS=https://app.example.com,https://admin.example.com
```

**客户端认证：**

```python
# 使用认证头连接
transport = StreamableHttpTransport(
    url="https://api.example.com/mcp",
    headers={
        "Authorization": "Bearer your-jwt-token",
        "X-API-Key": "your-api-key"
    }
)
```

### 环境变量完整参考

Negentropy Perceives 采用基于 [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) 的分层配置系统，按优先级从**高到低**：

| 优先级        | 配置源                 | 说明                                     |
| ------------- | ---------------------- | ---------------------------------------- |
| **1（最高）** | `-c/--config` 显式配置 | 通过构造参数传入，覆盖一切               |
| **2**         | 环境变量               | `NEGENTROPY_PERCEIVES_` 前缀             |
| **3**         | 用户 YAML 配置         | `~/.negentropy/perceives.config.yaml`    |
| **4（最低）** | 内置默认配置           | `config.default.yaml`（打包在 wheel 内） |

所有环境变量统一使用 `NEGENTROPY_PERCEIVES_` 前缀，由 Pydantic 自动完成类型转换与校验。

#### 服务标识

| 环境变量                              | 类型  | 默认值                 | 约束 | 说明                                   |
| ------------------------------------- | ----- | ---------------------- | ---- | -------------------------------------- |
| `NEGENTROPY_PERCEIVES_SERVER_NAME`    | `str` | `negentropy-perceives` | -    | 服务器标识名称                         |
| `NEGENTROPY_PERCEIVES_SERVER_VERSION` | `str` | 自动读取               | -    | 版本号（从 `pyproject.toml` 自动获取） |

#### 传输层

| 环境变量                                 | 类型   | 默认值      | 约束                     | 说明                           |
| ---------------------------------------- | ------ | ----------- | ------------------------ | ------------------------------ |
| `NEGENTROPY_PERCEIVES_TRANSPORT_MODE`    | `str`  | `http`      | `stdio` / `http` / `sse` | MCP 传输协议模式               |
| `NEGENTROPY_PERCEIVES_HTTP_HOST`         | `str`  | `localhost` | -                        | HTTP 服务器绑定主机            |
| `NEGENTROPY_PERCEIVES_HTTP_PORT`         | `int`  | `8081`      | -                        | HTTP 服务器端口                |
| `NEGENTROPY_PERCEIVES_HTTP_PATH`         | `str`  | `/mcp`      | -                        | HTTP 端点路径                  |
| `NEGENTROPY_PERCEIVES_HTTP_CORS_ORIGINS` | `str?` | `*`         | -                        | CORS 来源白名单（`null` 禁用） |

#### 抓取引擎

| 环境变量                                               | 类型    | 默认值 | 约束   | 说明                   |
| ------------------------------------------------------ | ------- | ------ | ------ | ---------------------- |
| `NEGENTROPY_PERCEIVES_CONCURRENT_REQUESTS`             | `int`   | `16`   | `> 0`  | 并发请求数             |
| `NEGENTROPY_PERCEIVES_DOWNLOAD_DELAY`                  | `float` | `1.0`  | `>= 0` | 下载间隔（秒）         |
| `NEGENTROPY_PERCEIVES_RANDOMIZE_DOWNLOAD_DELAY`        | `bool`  | `true` | -      | 随机化下载间隔         |
| `NEGENTROPY_PERCEIVES_AUTOTHROTTLE_ENABLED`            | `bool`  | `true` | -      | 启用自动节流           |
| `NEGENTROPY_PERCEIVES_AUTOTHROTTLE_START_DELAY`        | `float` | `1.0`  | `>= 0` | 自动节流初始延迟（秒） |
| `NEGENTROPY_PERCEIVES_AUTOTHROTTLE_MAX_DELAY`          | `float` | `60.0` | `>= 0` | 自动节流最大延迟（秒） |
| `NEGENTROPY_PERCEIVES_AUTOTHROTTLE_TARGET_CONCURRENCY` | `float` | `1.0`  | `>= 0` | 自动节流目标并发度     |

#### 速率限制

| 环境变量                                              | 类型  | 默认值 | 约束   | 说明               |
| ----------------------------------------------------- | ----- | ------ | ------ | ------------------ |
| `NEGENTROPY_PERCEIVES_RATE_LIMIT_REQUESTS_PER_MINUTE` | `int` | `60`   | `>= 1` | 每分钟请求频率上限 |

#### 重试策略

| 环境变量                           | 类型    | 默认值 | 约束   | 说明             |
| ---------------------------------- | ------- | ------ | ------ | ---------------- |
| `NEGENTROPY_PERCEIVES_MAX_RETRIES` | `int`   | `3`    | `>= 0` | 失败重试最大次数 |
| `NEGENTROPY_PERCEIVES_RETRY_DELAY` | `float` | `1.0`  | `>= 0` | 重试间隔（秒）   |

#### 缓存系统

| 环境变量                               | 类型   | 默认值 | 约束  | 说明                 |
| -------------------------------------- | ------ | ------ | ----- | -------------------- |
| `NEGENTROPY_PERCEIVES_ENABLE_CACHING`  | `bool` | `true` | -     | 启用响应缓存         |
| `NEGENTROPY_PERCEIVES_CACHE_TTL_HOURS` | `int`  | `24`   | `> 0` | 缓存生存时间（小时） |

#### 日志系统

| 环境变量                             | 类型    | 默认值 | 约束                                                | 说明         |
| ------------------------------------ | ------- | ------ | --------------------------------------------------- | ------------ |
| `NEGENTROPY_PERCEIVES_LOG_LEVEL`     | `str`   | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` | 日志记录级别 |
| `NEGENTROPY_PERCEIVES_LOG_REQUESTS`  | `bool?` | `null` | -                                                   | 记录请求详情 |
| `NEGENTROPY_PERCEIVES_LOG_RESPONSES` | `bool?` | `null` | -                                                   | 记录响应详情 |

#### 浏览器引擎

| 环境变量                                   | 类型   | 默认值      | 约束   | 说明                 |
| ------------------------------------------ | ------ | ----------- | ------ | -------------------- |
| `NEGENTROPY_PERCEIVES_ENABLE_JAVASCRIPT`   | `bool` | `false`     | -      | 启用 JavaScript 执行 |
| `NEGENTROPY_PERCEIVES_BROWSER_HEADLESS`    | `bool` | `true`      | -      | 无头浏览器模式       |
| `NEGENTROPY_PERCEIVES_BROWSER_TIMEOUT`     | `int`  | `30`        | `>= 0` | 浏览器操作超时（秒） |
| `NEGENTROPY_PERCEIVES_BROWSER_WINDOW_SIZE` | `str`  | `1920x1080` | -      | 浏览器窗口尺寸       |

#### 用户代理

| 环境变量                                     | 类型   | 默认值        | 约束 | 说明                     |
| -------------------------------------------- | ------ | ------------- | ---- | ------------------------ |
| `NEGENTROPY_PERCEIVES_USE_RANDOM_USER_AGENT` | `bool` | `true`        | -    | 启用随机 User-Agent 轮换 |
| `NEGENTROPY_PERCEIVES_DEFAULT_USER_AGENT`    | `str`  | Chrome 120 UA | -    | 默认 User-Agent 字符串   |

#### 代理服务

| 环境变量                         | 类型   | 默认值  | 约束 | 说明                             |
| -------------------------------- | ------ | ------- | ---- | -------------------------------- |
| `NEGENTROPY_PERCEIVES_USE_PROXY` | `bool` | `false` | -    | 启用代理服务器                   |
| `NEGENTROPY_PERCEIVES_PROXY_URL` | `str?` | `null`  | -    | 代理服务器 URL（启用代理时必填） |

#### 请求设置

| 环境变量                               | 类型    | 默认值 | 约束  | 说明                |
| -------------------------------------- | ------- | ------ | ----- | ------------------- |
| `NEGENTROPY_PERCEIVES_REQUEST_TIMEOUT` | `float` | `30.0` | `> 0` | HTTP 请求超时（秒） |

#### LLM 编排（Smart 模式）

`method="smart"` 使用 LLM 编排多引擎并行处理 PDF。需安装可选依赖 `litellm`（`uv pip install litellm`）。

| 环境变量                               | 类型    | 默认值                    | 约束        | 说明                                                  |
| -------------------------------------- | ------- | ------------------------- | ----------- | ----------------------------------------------------- |
| `NEGENTROPY_PERCEIVES_LLM_API_KEY`     | `str?`  | `null`                    | -           | LLM API Key（ZhipuAI），也可通过 `ZHIPU_API_KEY` 设置 |
| `NEGENTROPY_PERCEIVES_LLM_MODEL`       | `str`   | `zhipu/glm-5-plus-250414` | -           | LiteLLM 模型标识                                      |
| `NEGENTROPY_PERCEIVES_LLM_TEMPERATURE` | `float` | `0.1`                     | `0.0 ~ 2.0` | LLM 温度参数                                          |
| `NEGENTROPY_PERCEIVES_LLM_MAX_TOKENS`  | `int`   | `4096`                    | `> 0`       | LLM 最大输出 token                                    |
| `NEGENTROPY_PERCEIVES_LLM_TIMEOUT`     | `float` | `60.0`                    | `> 0`       | LLM API 超时（秒）                                    |
| `NEGENTROPY_PERCEIVES_LLM_MAX_RETRIES` | `int`   | `2`                       | `>= 0`      | LLM API 重试次数                                      |

#### 硬件加速

| 环境变量                                             | 类型  | 默认值 | 约束                                    | 说明                                               |
| ---------------------------------------------------- | ----- | ------ | --------------------------------------- | -------------------------------------------------- |
| `NEGENTROPY_PERCEIVES_ACCELERATOR_DEVICE`            | `str` | `auto` | `auto` / `cpu` / `cuda` / `mps` / `xpu` | 推理设备选择，按运行环境自动或显式指定             |
| `NEGENTROPY_PERCEIVES_ACCELERATOR_NUM_THREADS`       | `int` | `4`    | `>= 1`                                  | CPU 推理线程数                                     |
| `NEGENTROPY_PERCEIVES_ACCELERATOR_OCR_BATCH_SIZE`    | `int` | `0`    | `>= 0`                                  | OCR 推理 batch size（0 = 根据设备显存自动推断）    |
| `NEGENTROPY_PERCEIVES_ACCELERATOR_LAYOUT_BATCH_SIZE` | `int` | `0`    | `>= 0`                                  | Layout 推理 batch size（0 = 根据设备显存自动推断） |
| `NEGENTROPY_PERCEIVES_ACCELERATOR_TABLE_BATCH_SIZE`  | `int` | `0`    | `>= 0`                                  | Table 推理 batch size（0 = 根据设备显存自动推断）  |

> 硬件加速的详细平台行为、Batch Size 推断规则见 [硬件加速配置](#7-硬件加速配置)。

#### Docling PDF 引擎

| 环境变量                                                  | 类型   | 默认值  | 约束                            | 说明                                                     |
| --------------------------------------------------------- | ------ | ------- | ------------------------------- | -------------------------------------------------------- |
| `NEGENTROPY_PERCEIVES_DOCLING_ENABLED`                    | `bool` | `false` | -                               | 启用 Docling 作为可选 PDF 提取引擎                       |
| `NEGENTROPY_PERCEIVES_DOCLING_OCR_ENABLED`                | `bool` | `true`  | -                               | 为扫描版 PDF 启用 OCR                                    |
| `NEGENTROPY_PERCEIVES_DOCLING_TABLE_EXTRACTION_ENABLED`   | `bool` | `true`  | -                               | 启用 Docling 高级表格提取                                |
| `NEGENTROPY_PERCEIVES_DOCLING_FORMULA_EXTRACTION_ENABLED` | `bool` | `true`  | -                               | 启用 Docling 数学公式提取（MPS 上自动禁用）              |
| `NEGENTROPY_PERCEIVES_MINERU_ENABLED`                     | `bool` | `false` | -                               | 启用 MinerU（最佳 LaTeX 公式提取）                       |
| `NEGENTROPY_PERCEIVES_MINERU_DEVICE`                      | `str`  | `auto`  | `auto` / `cpu` / `mlx` / `cuda` | MinerU 设备选择                                          |
| `NEGENTROPY_PERCEIVES_MINERU_BACKEND`                     | `str`  | `auto`  | `auto` / `pipeline` / `vlm`     | MinerU 后端选择                                          |
| `NEGENTROPY_PERCEIVES_MARKER_ENABLED`                     | `bool` | `false` | -                               | 启用 Marker（最佳整体准确率，GPL-3.0）                   |
| `NEGENTROPY_PERCEIVES_MARKER_LLM_ENHANCED`                | `bool` | `false` | -                               | 启用 Marker LLM 增强模式                                 |
| `NEGENTROPY_PERCEIVES_MARKER_LICENSE_ACKNOWLEDGED`        | `bool` | `false` | -                               | 确认 GPL-3.0 许可证条款（需设为 `true` 方可启用 Marker） |

### 配置验证规则

#### 字段验证器

系统内置三个 `@field_validator`，在加载时自动规范化输入：

- **`log_level`** — 自动转为大写，仅接受 `DEBUG`、`INFO`、`WARNING`、`ERROR`、`CRITICAL`
- **`transport_mode`** — 自动转为小写，仅接受 `stdio`、`http`、`sse`
- **`accelerator_device`** — 自动转为小写，仅接受 `auto`、`cpu`、`cuda`、`mps`、`xpu`

#### 配置不可变性

全局实例 `settings` 通过 `frozen=True` 配置为不可变对象，创建后不可修改，保障运行时配置一致性。

#### Scrapy 设置映射

`get_scrapy_settings()` 方法将抓取引擎配置映射为 Scrapy 原生设置字典，供 Scrapy 框架直接消费。

### 配置管理最佳实践

- `~/.negentropy/perceives.config.yaml` — 用户本地配置（不纳入版本控制）
- `--init-config` — 从内置模板生成初始用户配置
- `-c /path/to/config.yaml` — 显式指定自定义配置文件（适用于多环境部署）
- 环境变量 `NEGENTROPY_PERCEIVES_*` — 容器化/CI 场景下的配置方式
- 启用代理时务必同时配置 `proxy_url`，否则启动验证将报错

## MCP 工具详细

### 📋 返回值规范

所有 MCP 工具都遵循 FastMCP 标准，使用强类型的 Pydantic BaseModel 定义返回值：

**通用字段说明**

- **`success`**: `bool` - 所有工具都包含此字段，表示操作是否成功执行
- **`error`**: `str` (可选) - 失败时包含具体的错误信息
- **时间戳**: 大部分工具包含时间相关字段，如 `timestamp`、`operation_time` 等

**响应模型类型**

| 响应类型              | 用途          | 主要字段                                       |
| --------------------- | ------------- | ---------------------------------------------- |
| `ScrapeResponse`      | 单页面抓取    | `url`, `method`, `data`, `metadata`            |
| `BatchScrapeResponse` | 批量抓取      | `total_urls`, `successful_count`, `results`    |
| `LinksResponse`       | 链接提取      | `total_links`, `links`, `internal_links_count` |
| `MarkdownResponse`    | Markdown 转换 | `markdown_content`, `word_count`, `metadata`   |
| `PDFResponse`         | PDF 转换      | `content`, `page_count`, `word_count`          |

### 1. scrape_webpage - 基础网页抓取

**功能描述**：抓取单个网页内容，支持多种抓取方法和自定义数据提取配置

**参数**：

- `url` (required): 目标网页 URL
- `method` (optional): 抓取方法，默认 "auto"
- `extract_config` (optional): 数据提取配置
- `wait_for_element` (optional): 等待的 CSS 选择器

**抓取方法选择**：

- `auto`: 智能选择最佳方法
- `simple`: 快速 HTTP 请求，适合静态网页
- `scrapy`: Scrapy 框架，适合复杂页面
- `selenium`: 浏览器渲染，支持 JavaScript

**返回值类型:** `ScrapeResponse`

| 字段名      | 类型             | 描述               |
| ----------- | ---------------- | ------------------ |
| `success`   | `bool`           | 操作是否成功       |
| `url`       | `str`            | 被抓取的 URL       |
| `method`    | `str`            | 使用的抓取方法     |
| `data`      | `Dict[str, Any]` | 抓取到的数据       |
| `metadata`  | `Dict[str, Any]` | 页面元数据         |
| `error`     | `str`            | 错误信息（如果有） |
| `timestamp` | `datetime`       | 抓取时间戳         |

**基础使用示例**：

```json
{
  "url": "https://example.com",
  "method": "auto"
}
```

**高级数据提取示例**：

```json
{
  "url": "https://news.example.com",
  "method": "auto",
  "extract_config": {
    "title": "h1",
    "content": {
      "selector": ".article-content p",
      "multiple": true,
      "attr": "text"
    },
    "author": {
      "selector": ".author",
      "multiple": false,
      "attr": "text"
    },
    "publish_date": {
      "selector": "time",
      "multiple": false,
      "attr": "datetime"
    }
  }
}
```

**返回结果结构**：

```json
{
  "success": true,
  "url": "https://example.com",
  "method": "auto",
  "data": {
    "title": "网页标题",
    "content": ["段落1", "段落2"],
    "author": "作者名称",
    "publish_date": "2025-01-15T10:30:00"
  },
  "metadata": {
    "status_code": 200,
    "content_type": "text/html",
    "response_time": 1.23
  },
  "timestamp": "2025-01-15T10:30:00Z"
}
```

### 2. scrape_multiple_webpages - 批量网页抓取

**功能描述**：并发抓取多个网页，提高处理效率

**参数**：

- `urls` (required): URL 列表
- `method` (optional): 统一抓取方法
- `extract_config` (optional): 全局数据提取配置

**返回值类型:** `BatchScrapeResponse`

| 字段名             | 类型                   | 描述                |
| ------------------ | ---------------------- | ------------------- |
| `success`          | `bool`                 | 整体操作是否成功    |
| `total_urls`       | `int`                  | 总 URL 数量         |
| `successful_count` | `int`                  | 成功抓取的数量      |
| `failed_count`     | `int`                  | 失败的数量          |
| `results`          | `List[ScrapeResponse]` | 每个 URL 的抓取结果 |
| `summary`          | `Dict[str, Any]`       | 批量操作摘要信息    |

**使用示例**：

```json
{
  "urls": [
    "https://example1.com",
    "https://example2.com",
    "https://example3.com"
  ],
  "method": "simple",
  "extract_config": {
    "title": "h1",
    "description": "meta[name='description']"
  }
}
```

**返回结果**：

```json
{
  "success": true,
  "total_urls": 3,
  "successful_count": 3,
  "failed_count": 0,
  "results": [
    {
      "url": "https://example1.com",
      "success": true,
      "data": { "title": "网站1标题" }
    },
    {
      "url": "https://example2.com",
      "success": true,
      "data": { "title": "网站2标题" }
    },
    {
      "url": "https://example3.com",
      "success": true,
      "data": { "title": "网站3标题" }
    }
  ],
  "summary": {
    "total_processing_time": 5.67,
    "average_response_time": 1.89
  }
}
```

### 3. scrape_with_stealth - 反检测抓取

**功能描述**：使用高级反检测技术抓取有防护的网站

**参数**：

- `url` (required): 目标 URL
- `method` (optional): 反检测方法，默认 "selenium"
- `extract_config` (optional): 数据提取配置
- `wait_for_element` (optional): 等待元素
- `scroll_page` (optional): 是否滚动页面

**反检测特性**：

- 随机 User-Agent 轮换
- 人类行为模拟
- 浏览器指纹隐藏
- IP 代理支持

**使用示例**：

```json
{
  "url": "https://protected-website.com",
  "method": "selenium",
  "scroll_page": true,
  "wait_for_element": ".dynamic-content",
  "extract_config": {
    "content": {
      "selector": ".protected-content",
      "multiple": true,
      "attr": "text"
    }
  }
}
```

### 4. fill_and_submit_form - 表单自动化

**功能描述**：自动填写和提交网页表单

**参数**：

- `url` (required): 包含表单的页面 URL
- `form_data` (required): 表单字段数据
- `submit` (optional): 是否提交，默认 false
- `submit_button_selector` (optional): 提交按钮选择器
- `method` (optional): 自动化方法

**表单字段配置**：

```json
{
  "url": "https://example.com/contact",
  "form_data": {
    "input[name='name']": "张三",
    "input[name='email']": "zhangsan@example.com",
    "input[type='tel']": "13800138000",
    "select[name='country']": "China",
    "input[value='agree']": true,
    "textarea[name='message']": "这是一条测试消息"
  },
  "submit": true,
  "submit_button_selector": "button[type='submit']",
  "method": "selenium"
}
```

**支持的表单元素**：

- `input[type='text']`: 文本输入框
- `input[type='email']`: 邮箱输入框
- `input[type='password']`: 密码输入框
- `input[type='tel']`: 电话输入框
- `select`: 下拉选择框
- `textarea`: 多行文本框
- `input[type='checkbox']`: 复选框
- `input[type='radio']`: 单选按钮

### 5. extract_links - 专业链接提取

**功能描述**：专门用于提取网页中的链接，支持过滤和分类

**参数**：

- `url` (required): 目标网页 URL
- `filter_domains` (optional): 只包含指定域名的链接
- `exclude_domains` (optional): 排除指定域名的链接
- `internal_only` (optional): 只提取内部链接

**返回值类型:** `LinksResponse`

| 字段名                 | 类型             | 描述               |
| ---------------------- | ---------------- | ------------------ |
| `success`              | `bool`           | 操作是否成功       |
| `url`                  | `str`            | 源页面 URL         |
| `total_links`          | `int`            | 总链接数量         |
| `links`                | `List[LinkItem]` | 提取的链接列表     |
| `internal_links_count` | `int`            | 内部链接数量       |
| `external_links_count` | `int`            | 外部链接数量       |
| `error`                | `str`            | 错误信息（如果有） |

**基础使用**：

```json
{
  "url": "https://example.com",
  "internal_only": true
}
```

**高级过滤**：

```json
{
  "url": "https://news.example.com",
  "filter_domains": ["news.example.com", "blog.example.com"],
  "exclude_domains": ["ads.example.com", "tracker.example.com"],
  "internal_only": false
}
```

**返回结果**：

```json
{
  "success": true,
  "url": "https://example.com",
  "total_links": 45,
  "internal_links_count": 32,
  "external_links_count": 13,
  "links": [
    {
      "url": "https://example.com/about",
      "text": "关于我们",
      "type": "internal"
    },
    {
      "url": "https://partner.com",
      "text": "合作伙伴",
      "type": "external"
    }
  ]
}
```

### 6. extract_structured_data - 结构化数据提取

**功能描述**：自动识别和提取网页中的结构化数据(联系信息、社交媒体链接等)。

**参数**：

- `url` (required): 目标 URL
- `data_type` (optional): 数据类型，默认 "all"

**数据类型选择**：

- `all`: 提取所有类型数据
- `contact`: 仅提取联系方式
- `social`: 仅提取社交媒体链接
- `content`: 仅提取文章内容
- `products`: 仅提取产品信息
- `addresses`: 仅提取地址信息

**使用示例**：

```json
{
  "url": "https://company.com/contact",
  "data_type": "contact"
}
```

**返回结果**：

```json
{
  "success": true,
  "data": {
    "emails": ["info@company.com", "support@company.com"],
    "phone_numbers": ["+86-10-12345678", "+1-555-0123"],
    "addresses": ["北京市朝阳区xxx街道xxx号"],
    "social_media": [
      { "platform": "twitter", "url": "https://twitter.com/company" },
      { "platform": "linkedin", "url": "https://linkedin.com/company/company" }
    ]
  }
}
```

### 7. get_page_info - 页面基础信息

**功能描述**：快速获取网页的基础元数据信息

**参数**：

- `url` (required): 目标 URL

**使用示例**：

```json
{
  "url": "https://example.com"
}
```

**返回结果**：

```json
{
  "success": true,
  "data": {
    "url": "https://example.com",
    "title": "Example Website",
    "description": "This is an example website",
    "keywords": ["example", "website", "demo"],
    "status_code": 200,
    "content_type": "text/html",
    "content_length": 15420,
    "last_modified": "2025-01-15T10:00:00Z",
    "response_time": 0.856
  }
}
```

### 8. check_robots_txt - 爬虫规则检查

**功能描述**：检查网站的 robots.txt 文件，确认爬取规则

**参数**：

- `url` (required): 网站域名 URL

**使用示例**：

```json
{
  "url": "https://example.com"
}
```

**返回结果**：

```json
{
  "success": true,
  "data": {
    "url": "https://example.com",
    "robots_txt_exists": true,
    "can_crawl": true,
    "allowed_paths": ["/public", "/articles"],
    "disallowed_paths": ["/admin", "/private"],
    "crawl_delay": 1.0,
    "sitemap_url": "https://example.com/sitemap.xml"
  }
}
```

### 9. convert_webpage_to_markdown - 网页转 Markdown

**功能描述**：将网页内容转换为结构化的 Markdown 格式

**功能特性:**

- **智能内容提取**: 自动识别并提取网页主要内容区域
- **清理处理**: 移除广告、导航栏、侧边栏等无关内容
- **URL 转换**: 将相对 URL 转换为绝对 URL
- **格式优化**: 清理多余空白行，优化 Markdown 格式
- **元数据丰富**: 包含标题、描述、字数统计等信息
- **高级格式化**: 提供 8 种可配置的格式化选项
  - 表格自动对齐和格式化
  - 代码块语言自动检测 (支持 Python、JavaScript、HTML、SQL 等)
  - 引用块格式优化
  - 图片描述自动生成和增强
  - 链接格式优化和去重
  - 列表格式统一化
  - 标题层级和间距优化
  - 排版增强 (智能引号、em 破折号、空格清理)

**参数:**

- `url`: 要抓取和转换的 URL
- `method`: 抓取方法 (auto/simple/scrapy/selenium，默认 auto)
- `extract_main_content`: 是否仅提取主要内容区域 (默认 true)
- `include_metadata`: 是否包含页面元数据 (默认 true)
- `custom_options`: 自定义 Markdown 转换选项 (可选)
- `wait_for_element`: 等待的 CSS 选择器 (Selenium 专用)
- `formatting_options`: 高级格式化选项，包含以下配置:
  - `format_tables`: 表格对齐格式化 (默认 true)
  - `detect_code_language`: 自动检测代码语言 (默认 true)
  - `format_quotes`: 引用块格式化 (默认 true)
  - `enhance_images`: 图片描述增强 (默认 true)
  - `optimize_links`: 链接格式优化 (默认 true)
  - `format_lists`: 列表格式化 (默认 true)
  - `format_headings`: 标题格式化和间距 (默认 true)
  - `apply_typography`: 排版优化 (智能引号、破折号等，默认 true)
- `embed_images` (boolean): 是否将页面中的图片以 data URI 形式嵌入 Markdown (默认 false)
- `embed_options` (object): 图片嵌入行为配置
  - `max_images` (int): 最大嵌入图片数量 (默认 50)
  - `max_bytes_per_image` (int): 单张图片最大字节数上限，超过则保留原链接 (默认 2,000,000)
  - `timeout_seconds` (int): 下载图片的超时时间 (默认 10)

**高级格式化选项**：

```json
{
  "format_tables": true,
  "detect_code_language": true,
  "format_quotes": true,
  "enhance_images": true,
  "optimize_links": true,
  "format_lists": true,
  "format_headings": true,
  "apply_typography": true
}
```

**图片嵌入配置**：

```json
{
  "max_images": 50,
  "max_bytes_per_image": 2000000,
  "timeout_seconds": 10
}
```

**完整使用示例**：

```json
{
  "url": "https://example.com/article",
  "method": "auto",
  "extract_main_content": true,
  "include_metadata": true,
  "formatting_options": {
    "format_tables": true,
    "detect_code_language": true,
    "apply_typography": true
  },
  "embed_images": true,
  "embed_options": {
    "max_images": 10,
    "max_bytes_per_image": 1500000
  }
}
```

**返回结果**：

```json
{
  "success": true,
  "data": {
    "url": "https://example.com/article",
    "markdown": "# 文章标题\n\n这是文章的主要内容...",
    "metadata": {
      "title": "文章标题",
      "description": "文章描述",
      "word_count": 1250,
      "character_count": 7500,
      "domain": "example.com",
      "images_embedded": 3
    }
  }
}
```

### 10. batch_convert_webpages_to_markdown - 批量网页转 Markdown

**功能描述**：批量抓取多个网页并转换为 Markdown 格式，支持并发处理提升效率。

**功能特性:**

- **并发处理**: 同时处理多个 URL 提升效率
- **一致格式**: 所有页面使用相同的转换配置
- **详细统计**: 提供成功/失败统计和汇总信息
- **错误处理**: 单个页面失败不影响其他页面处理
- **批量优化**: 针对大量页面优化的性能配置

**参数:**

- `urls`: 要抓取和转换的 URL 列表
- `method`: 抓取方法 (auto/simple/scrapy/selenium，默认 auto)
- `extract_main_content`: 是否仅提取主要内容区域 (默认 true)
- `include_metadata`: 是否包含页面元数据 (默认 true)
- `custom_options`: 自定义 Markdown 转换选项 (可选)
- `formatting_options`: 高级格式化选项 (与单页转换相同配置)
- `embed_images` / `embed_options`: 与单页相同，用于批量图片嵌入

**使用示例**：

```json
{
  "urls": [
    "https://blog.example.com/post1",
    "https://blog.example.com/post2",
    "https://blog.example.com/post3"
  ],
  "method": "auto",
  "extract_main_content": true,
  "formatting_options": {
    "format_tables": true,
    "detect_code_language": true
  }
}
```

### 11. convert_pdf_to_markdown - PDF 转 Markdown

**功能描述**：将 PDF 文档转换为 Markdown 格式，支持 URL 和本地文件路径，适用于文档处理、内容分析和知识管理。

**标准功能:**

- **多源支持**: 支持 PDF URL 和本地文件路径
- **多引擎支持**: PyMuPDF (fitz)、PyPDF、Docling 和 LLM 智能编排四种引擎
- **部分提取**: 支持指定页面范围的部分提取
- **元数据提取**: 包含标题、作者、创建日期等完整元数据
- **智能转换**: 自动检测标题层级和格式化
- **错误恢复**: 引擎失败时自动切换备用方法

**增强功能:**

- **🖼️ 图像提取**: 从 PDF 页面中提取所有图像元素，支持本地存储和 Markdown 集成
- **📊 表格提取**: 智能识别各种格式的表格，转换为标准 Markdown 表格格式
- **🧮 数学公式提取**: 识别多种 LaTeX 格式的数学公式，保持原始 LaTeX 格式

**参数:**

- `pdf_source`: PDF URL 或本地文件路径
- `method`: 提取方法 (auto/pymupdf/pypdf/docling/smart，默认 auto)。`smart` 模式使用 LLM 编排多引擎并行处理并择优融合（需安装 `litellm` 并配置 API Key）
- `include_metadata`: 是否包含 PDF 元数据 (默认 true)
- `page_range`: 页面范围 [start, end] 用于部分提取 (可选)
- `output_format`: 输出格式 (markdown/text，默认 markdown)
- `extract_images`: 是否从 PDF 中提取图像并保存为本地文件 (默认 true)
- `extract_tables`: 是否从 PDF 中提取表格并转换为 Markdown 表格格式 (默认 true)
- `extract_formulas`: 是否从 PDF 中提取数学公式并保持 LaTeX 格式 (默认 true)
- `embed_images`: 是否将提取的图像以 base64 格式嵌入到 Markdown 文档中 (默认 false)
- `enhanced_options`: 增强处理选项 (可选)

**enhanced_options 详细配置:**

```json
{
  "output_dir": "./extracted_assets", // 输出目录路径
  "image_size": [800, 600], // 图像尺寸调整 [width, height]
  "image_format": "png", // 图像格式 (png, jpg)
  "image_quality": 90 // 图像质量 (1-100，仅适用于JPEG)
}
```

**转换 Markdown 示例:**

```markdown
# 原始文档内容

...

## Extracted Images

![图表 1](img_0_0_001.png)

_Dimensions: 800×600px_
_Source: Page 1_

## Extracted Tables

**数据统计表**

| 项目   | 数值   | 单位 |
| ------ | ------ | ---- |
| 销售额 | 125000 | 元   |

_Table: 3 rows × 3 columns_
_Source: Page 2_

## Mathematical Formulas

爱因斯坦质能方程：$E = mc^2$

$$
\int_{-\infty}^{\infty} e^{-x^2} dx = \sqrt{\pi}
$$

_Source: Page 3_
```

**基础示例:**

```json
{
  "pdf_source": "https://example.com/document.pdf",
  "method": "auto",
  "include_metadata": true,
  "page_range": [0, 10],
  "output_format": "markdown"
}
```

**启用所有增强功能:**

```json
{
  "pdf_source": "https://example.com/document.pdf",
  "method": "pymupdf",
  "output_format": "markdown",
  "extract_images": true,
  "extract_tables": true,
  "extract_formulas": true,
  "embed_images": false,
  "enhanced_options": {
    "output_dir": "./extracted_assets",
    "image_size": [800, 600]
  }
}
```

**返回示例 (包含增强资源):**

```json
{
  "success": true,
  "data": {
    "text": "原始提取的文本内容",
    "markdown": "# 文档标题\n\n转换后的 Markdown 内容...",
    "metadata": {
      "title": "文档标题",
      "author": "作者姓名",
      "total_pages": 50,
      "pages_processed": 10,
      "file_size_bytes": 1024000
    },
    "source": "https://example.com/document.pdf",
    "method_used": "pymupdf",
    "word_count": 2500,
    "character_count": 15000,
    "enhanced_assets": {
      "images": {
        "count": 3,
        "files": ["img_0_0_001.png", "img_1_0_002.png"],
        "total_size_mb": 2.4
      },
      "tables": {
        "count": 2,
        "total_rows": 8,
        "total_columns": 6
      },
      "formulas": {
        "count": 5,
        "inline_count": 3,
        "block_count": 2
      },
      "output_directory": "/path/to/extracted_assets"
    }
  }
}
```

**PDF 引擎配置：**

以下环境变量控制 PDF 提取引擎的启用和行为：

| 环境变量                                                  | 类型   | 默认值  | 约束                            | 说明                                                     |
| --------------------------------------------------------- | ------ | ------- | ------------------------------- | -------------------------------------------------------- |
| `NEGENTROPY_PERCEIVES_DOCLING_ENABLED`                    | `bool` | `false` | -                               | 启用 Docling 作为可选 PDF 提取引擎                       |
| `NEGENTROPY_PERCEIVES_DOCLING_OCR_ENABLED`                | `bool` | `true`  | -                               | 为扫描版 PDF 启用 OCR                                    |
| `NEGENTROPY_PERCEIVES_DOCLING_TABLE_EXTRACTION_ENABLED`   | `bool` | `true`  | -                               | 启用 Docling 高级表格提取                                |
| `NEGENTROPY_PERCEIVES_DOCLING_FORMULA_EXTRACTION_ENABLED` | `bool` | `true`  | -                               | 启用 Docling 数学公式提取（MPS 上自动禁用）              |
| `NEGENTROPY_PERCEIVES_MINERU_ENABLED`                     | `bool` | `false` | -                               | 启用 MinerU（最佳 LaTeX 公式提取）                       |
| `NEGENTROPY_PERCEIVES_MINERU_DEVICE`                      | `str`  | `auto`  | `auto` / `cpu` / `mlx` / `cuda` | MinerU 设备选择                                          |
| `NEGENTROPY_PERCEIVES_MINERU_BACKEND`                     | `str`  | `auto`  | `auto` / `pipeline` / `vlm`     | MinerU 后端选择                                          |
| `NEGENTROPY_PERCEIVES_MARKER_ENABLED`                     | `bool` | `false` | -                               | 启用 Marker（最佳整体准确率，GPL-3.0）                   |
| `NEGENTROPY_PERCEIVES_MARKER_LLM_ENHANCED`                | `bool` | `false` | -                               | 启用 Marker LLM 增强模式                                 |
| `NEGENTROPY_PERCEIVES_MARKER_LICENSE_ACKNOWLEDGED`        | `bool` | `false` | -                               | 确认 GPL-3.0 许可证条款（需设为 `true` 方可启用 Marker） |

### 12. batch_convert_pdfs_to_markdown - 批量 PDF 转 Markdown

**功能描述**：批量转换多个 PDF 文档为 Markdown 格式，支持并发处理提升效率，适用于大规模文档处理。

**功能特性:**

- **并发处理**: 同时处理多个 PDF 文档提升效率
- **一致配置**: 所有 PDF 使用相同的转换设置
- **详细统计**: 提供成功/失败统计和汇总信息
- **错误容错**: 单个 PDF 失败不影响其他文档处理
- **批量优化**: 针对大量文档优化的内存和性能配置

**参数**：

- `pdf_sources` (required): PDF 文件列表（URL 或路径）
- `method` (optional): 提取方法 (auto/pymupdf/pypdf2，默认 auto)，默认 "auto"
- `page_range` (optional): 页面范围 [start, end]，应用于所有 PDF
- `output_format` (optional): 输出格式 (markdown/text)，默认 "markdown"
- `include_metadata` (optional): 是否包含元数据 (默认 true)

**示例:**

```json
{
  "pdf_sources": [
    "https://example.com/doc1.pdf",
    "/local/path/doc2.pdf",
    "https://example.com/doc3.pdf"
  ],
  "method": "auto",
  "include_metadata": true,
  "output_format": "markdown"
}
```

**返回示例:**

```json
{
  "success": true,
  "data": {
    "results": [
      {
        "success": true,
        "source": "https://example.com/doc1.pdf",
        "text": "原始文本内容",
        "markdown": "# 文档1标题\n\n内容...",
        "metadata": {...},
        "word_count": 1500
      },
      {
        "success": true,
        "source": "/local/path/doc2.pdf",
        "text": "原始文本内容",
        "markdown": "# 文档2标题\n\n内容...",
        "metadata": {...},
        "word_count": 2000
      }
    ],
    "summary": {
      "total_pdfs": 3,
      "successful": 2,
      "failed": 1,
      "total_pages_processed": 45,
      "total_words_extracted": 3500,
      "method_used": "auto",
      "output_format": "markdown"
    }
  }
}
```

## API 编程接口

虽然主要通过 MCP 协议使用，但也支持直接 Python 调用：

### Negentropy Perceives 核心引擎使用方式

#### 1. 直接使用核心引擎

```python
from negentropy.perceives.scraping import WebScraper
from negentropy.perceives.scraping import AntiDetectionScraper
from negentropy.perceives.scraping import FormHandler

# 基础抓取
scraper = WebScraper()
result = await scraper.scrape_url("https://example.com", method="simple")

# 反检测抓取
stealth_scraper = AntiDetectionScraper()
result = await stealth_scraper.scrape_with_stealth("https://protected-site.com")

# 表单自动化
form_handler = FormHandler()
result = await form_handler.fill_and_submit_form(
    "https://example.com/contact",
    {"input[name='email']": "test@example.com"}
)
```

#### 2. 配置化数据提取

```python
# 简单配置
extract_config = {
    "title": "h1",
    "content": ".article-content"
}

# 高级配置
extract_config = {
    "products": {
        "selector": ".product-item",
        "multiple": True,
        "attr": "text"
    },
    "prices": {
        "selector": ".price",
        "multiple": True,
        "attr": "data-price"
    },
    "images": {
        "selector": "img.product-image",
        "multiple": True,
        "attr": "src"
    }
}

result = await scraper.scrape_url(url, extract_config=extract_config)
```

#### 3. 企业级功能集成

```python
from negentropy.perceives.infra import rate_limiter
from negentropy.perceives.infra import retry_manager

# 集成完整功能的抓取流程
async def enterprise_scrape(url: str):
    # 速率限制
    await rate_limiter.wait()

    # 重试机制
    try:
        result = await retry_manager.retry_async(
            scraper.scrape_url, url, method="auto"
        )

        return result

    except Exception as e:
        error_handler.handle_error(e, "enterprise_scrape")
        raise
```

### Negentropy Perceives Python SDK 使用方式

#### 1. 通过 SDK 连接 HTTP 服务

```python
from negentropy.perceives.sdk import NegentropyPerceivesClient

async with NegentropyPerceivesClient(
    "http://127.0.0.1:8081/mcp",
    headers={"X-Trace-Id": "demo-request"},
) as client:
    tools = await client.list_tools()
    print([tool.name for tool in tools])
```

#### 2. 通过 SDK 调用 MCP 工具

```python
async with NegentropyPerceivesClient("http://127.0.0.1:8081/mcp") as client:
    result = await client.call_tool(
        "scrape_webpage",
        {
            "url": "https://example.com",
            "method": "simple",
        },
    )
```

#### 3. 使用类型化快捷方法

```python
async with NegentropyPerceivesClient("http://127.0.0.1:8081/mcp") as client:
    result = await client.convert_webpage_to_markdown(
        url="https://example.com/docs",
        method="auto",
        extract_main_content=True,
    )
```

### Negentropy Perceives MCP 工具集使用方式

#### 通过 MCP 协议调用工具

```python
import asyncio
from negentropy.perceives.tools.scraping import scrape_webpage, scrape_multiple_webpages
from negentropy.perceives.tools.stealth import scrape_with_stealth
from negentropy.perceives.tools.form import fill_and_submit_form

# 基础页面抓取
async def basic_scraping_example():
    result = await scrape_webpage(
        url="https://example.com",
        method="auto",
        extract_config={
            "title": "h1",
            "content": ".main-content"
        }
    )
    print(f"页面标题: {result['data']['extracted_data']['title']}")

# 批量抓取
async def batch_scraping_example():
    urls = [
        "https://site1.com",
        "https://site2.com",
        "https://site3.com"
    ]

    results = await scrape_multiple_webpages(
        urls=urls,
        method="simple",
        extract_config={"title": "h1"}
    )

    for result in results['data']:
        print(f"URL: {result['url']}, 标题: {result.get('title', 'N/A')}")
```

## 高级使用场景

### 1. 电商数据抓取

**推荐提取配置模板**：

```json
{
  "product_name": {
    "selector": "h1.product-title, .product-name h1",
    "attr": "text",
    "multiple": false
  },
  "price": {
    "selector": ".price, .product-price",
    "attr": "text",
    "multiple": false
  },
  "description": {
    "selector": ".product-description, .description",
    "attr": "text",
    "multiple": false
  },
  "images": {
    "selector": ".product-image img, .gallery img",
    "attr": "src",
    "multiple": true
  }
}
```

**完整流程示例**：

```python
async def ecommerce_scraping():
    # 抓取产品列表
    products_result = await scrape_webpage(
        url="https://shop.example.com/products",
        extract_config={
            "products": {
                "selector": ".product-card",
                "multiple": True,
                "attr": "text"
            },
            "prices": {
                "selector": ".price",
                "multiple": True,
                "attr": "text"
            },
            "product_links": {
                "selector": ".product-card a",
                "multiple": True,
                "attr": "href"
            }
        }
    )

    # 批量抓取产品详情
    product_urls = products_result['data']['extracted_data']['product_links']
    details = await scrape_multiple_webpages(
        urls=product_urls[:10],  # 限制前10个产品
        extract_config={
            "description": ".product-description",
            "specifications": ".specs-table",
            "images": {
                "selector": ".product-images img",
                "multiple": True,
                "attr": "src"
            }
        }
    )

    return {
        "products_overview": products_result,
        "product_details": details
    }
```

### 2. 新闻监控系统

**推荐提取配置模板**：

```json
{
  "headline": {
    "selector": "h1, .headline, .article-title",
    "attr": "text",
    "multiple": false
  },
  "author": {
    "selector": ".author, .byline, [rel='author']",
    "attr": "text",
    "multiple": false
  },
  "article_body": {
    "selector": ".article-body p, .content p",
    "attr": "text",
    "multiple": true
  }
}
```

**完整流程示例**：

```python
async def news_monitoring_system():
    news_sites = [
        "https://news.ycombinator.com",
        "https://techcrunch.com",
        "https://arstechnica.com"
    ]

    # 批量抓取新闻标题
    news_results = await scrape_multiple_webpages(
        urls=news_sites,
        extract_config={
            "headlines": {
                "selector": "h1, h2, .headline",
                "multiple": True,
                "attr": "text"
            },
            "timestamps": {
                "selector": ".timestamp, time",
                "multiple": True,
                "attr": "text"
            }
        }
    )

    # 提取所有链接用于深度分析
    all_links = []
    for site in news_sites:
        links_result = await extract_links(
            url=site,
            internal_only=True
        )
        all_links.extend(links_result['data']['links'])

    return {
        "news_headlines": news_results,
        "discovered_links": all_links
    }
```

### 3. 合规性检查流程

```python
async def compliance_check_workflow(target_url: str):
    # 1. 检查 robots.txt
    robots_result = await check_robots_txt(target_url)

    if not robots_result['data']['can_crawl']:
        return {"error": "网站禁止爬取", "robots_txt": robots_result}

    # 2. 获取页面基础信息
    page_info = await get_page_info(target_url)

    # 3. 执行合规的数据抓取
    scrape_result = await scrape_webpage(
        url=target_url,
        method="simple",  # 使用最轻量的方法
        extract_config={
            "public_content": ".main-content, .article",
            "meta_info": "meta[name='description']"
        }
    )

    return {
        "compliance_check": robots_result,
        "page_info": page_info,
        "extracted_data": scrape_result
    }
```

### 4. 学术论文处理

```python
async def academic_paper_processing():
    # 批量处理学术论文PDF
    pdf_sources = [
        "paper1.pdf",
        "paper2.pdf",
        "paper3.pdf"
    ]

    results = await batch_convert_pdfs_to_markdown(
        pdf_sources=pdf_sources,
        method="pymupdf",
        extract_formulas=True,
        extract_images=True,
        extract_tables=True,
        output_format="markdown"
    )

    return results
```

### 5. LLM 智能编排（Smart 模式）

使用 `method="smart"` 启用 LLM 编排多引擎并行处理，自动择优融合最佳输出。适用于含公式、表格、代码、图像的复杂学术文档。

**前置条件**：安装 `litellm`（`uv pip install litellm`），并配置 `ZHIPU_API_KEY` 或 `NEGENTROPY_PERCEIVES_LLM_API_KEY` 环境变量。

**LLM 编排环境变量：**

| 环境变量                               | 类型    | 默认值                    | 约束        | 说明                                                  |
| -------------------------------------- | ------- | ------------------------- | ----------- | ----------------------------------------------------- |
| `NEGENTROPY_PERCEIVES_LLM_API_KEY`     | `str?`  | `null`                    | -           | LLM API Key（ZhipuAI），也可通过 `ZHIPU_API_KEY` 设置 |
| `NEGENTROPY_PERCEIVES_LLM_MODEL`       | `str`   | `zhipu/glm-5-plus-250414` | -           | LiteLLM 模型标识                                      |
| `NEGENTROPY_PERCEIVES_LLM_TEMPERATURE` | `float` | `0.1`                     | `0.0 ~ 2.0` | LLM 温度参数                                          |
| `NEGENTROPY_PERCEIVES_LLM_MAX_TOKENS`  | `int`   | `4096`                    | `> 0`       | LLM 最大输出 token                                    |
| `NEGENTROPY_PERCEIVES_LLM_TIMEOUT`     | `float` | `60.0`                    | `> 0`       | LLM API 超时（秒）                                    |
| `NEGENTROPY_PERCEIVES_LLM_MAX_RETRIES` | `int`   | `2`                       | `>= 0`      | LLM API 重试次数                                      |

> 完整环境变量参考见 [环境变量完整参考](#环境变量完整参考)。

```python
async def smart_pdf_processing():
    result = await convert_pdf_to_markdown(
        pdf_source="academic_paper.pdf",
        method="smart",
        extract_formulas=True,
        extract_images=True,
        extract_tables=True,
    )

    # smart 模式返回额外的编排信息
    orch_info = result.get("orchestration_info", {})
    print(f"使用引擎: {orch_info.get('engines_used')}")
    print(f"融合策略: {orch_info.get('synthesis_strategy')}")
    return result
```

### 6. 技术文档转换

```python
async def technical_docs_conversion():
    # 将技术文档PDF转换为结构化Markdown
    result = await convert_pdf_to_markdown(
        pdf_source="technical_manual.pdf",
        extract_images=True,
        extract_tables=True,
        embed_images=True,
        enhanced_options={
            "output_dir": "./extracted_assets",
            "image_size": [1200, 900]
        }
    )

    return result
```

### 7. 硬件加速配置

PDF 处理（尤其是 Docling 引擎的 OCR、表格识别、公式提取）支持 GPU 加速。以下是硬件加速的完整配置参考。

**环境变量：**

| 环境变量                                             | 类型  | 默认值 | 约束                                    | 说明                                               |
| ---------------------------------------------------- | ----- | ------ | --------------------------------------- | -------------------------------------------------- |
| `NEGENTROPY_PERCEIVES_ACCELERATOR_DEVICE`            | `str` | `auto` | `auto` / `cpu` / `cuda` / `mps` / `xpu` | 推理设备选择，按运行环境自动或显式指定             |
| `NEGENTROPY_PERCEIVES_ACCELERATOR_NUM_THREADS`       | `int` | `4`    | `>= 1`                                  | CPU 推理线程数                                     |
| `NEGENTROPY_PERCEIVES_ACCELERATOR_OCR_BATCH_SIZE`    | `int` | `0`    | `>= 0`                                  | OCR 推理 batch size（0 = 根据设备显存自动推断）    |
| `NEGENTROPY_PERCEIVES_ACCELERATOR_LAYOUT_BATCH_SIZE` | `int` | `0`    | `>= 0`                                  | Layout 推理 batch size（0 = 根据设备显存自动推断） |
| `NEGENTROPY_PERCEIVES_ACCELERATOR_TABLE_BATCH_SIZE`  | `int` | `0`    | `>= 0`                                  | Table 推理 batch size（0 = 根据设备显存自动推断）  |

> **Batch Size 自动推断**：当值为 `0` 时，系统根据检测到的设备类型和可用显存自动推断最优 batch size。GPU 设备通常可从默认值 4 提升至 8-64，显著提升批处理吞吐量。手动设置非零值将覆盖自动推断结果。

#### 设备自动检测优先级

系统按以下顺序检测可用设备（`auto` 模式）：

1. **CUDA** (NVIDIA GPU) — 通过 `torch.cuda.is_available()` 检测
2. **MPS** (Apple Silicon) — 通过 `torch.backends.mps.is_available()` 检测
3. **XPU** (Intel GPU) — 通过 `torch.xpu.is_available()` 检测
4. **CPU** — 通用回退

#### 平台特定行为

##### Apple Silicon (MPS)

Apple Silicon M 系芯片通过 Metal Performance Shaders (MPS) 提供 GPU 加速。由于 MPS 采用统一内存架构（CPU/GPU 共享），配置策略相对保守。

| 特性               | 行为                    | 原因                                                                                         |
| ------------------ | ----------------------- | -------------------------------------------------------------------------------------------- |
| Formula Enrichment | **自动禁用**            | Docling CodeFormula VLM 不支持 MPS，启用时整个管道回退 CPU<sup>[[1]](#ref-mps-formula)</sup> |
| Flash Attention 2  | 不可用                  | 仅 CUDA 支持                                                                                 |
| Batch Sizes        | 自动优化                | 基于统一内存大小推断（8-32），详见下表                                                       |
| OCR 引擎           | macOS Vision 可选       | 自动偏好 `OcrMacOptions`（Apple Vision Framework 原生 OCR）                                  |
| TableFormer        | 透明回退 CPU            | Docling 内部处理，无需干预                                                                   |
| 公式降级           | Markdown 正则 + PyMuPDF | 参考 [`math_formula.py`](../src/negentropy/perceives/pdf/math_formula.py)                    |

> **注意**：公式提取被禁用后，系统自动通过 PyMuPDF 字体分析 + Unicode→LaTeX 映射进行降级补偿，覆盖大部分常见数学公式场景。

##### NVIDIA CUDA

| 特性              | 行为                  | 原因                                               |
| ----------------- | --------------------- | -------------------------------------------------- |
| Flash Attention 2 | **自动启用**          | 需安装 `flash-attn` 包（`pip install flash-attn`） |
| Batch Sizes       | 自动优化              | 基于专用显存大小推断（8-64），详见下表             |
| 全功能支持        | Formula + Table + OCR | 所有 Docling 功能完全兼容                          |

##### Intel XPU

| 特性              | 行为     | 原因                 |
| ----------------- | -------- | -------------------- |
| Flash Attention 2 | 不可用   | 仅 CUDA 支持         |
| Batch Sizes       | 自动优化 | 使用中等策略（8-16） |

##### Batch Size 自动推断规则

| 设备类型 | 可用显存 | ocr / layout batch | table batch |
| -------- | -------- | ------------------ | ----------- |
| **CPU**  | -        | 4                  | 4           |
| **MPS**  | < 12 GB  | 8                  | 4           |
| **MPS**  | 12-24 GB | 12                 | 6           |
| **MPS**  | 24-48 GB | 16                 | 8           |
| **MPS**  | ≥ 48 GB  | 32                 | 16          |
| **CUDA** | < 8 GB   | 8                  | 4           |
| **CUDA** | 8-12 GB  | 16                 | 8           |
| **CUDA** | 12-24 GB | 32                 | 16          |
| **CUDA** | ≥ 24 GB  | 64                 | 32          |

> MPS 统一内存说明：Apple Silicon 的 GPU 可用显存按物理内存 × 75% 估算（如 32GB 物理内存 → ~24GB GPU 可用）。由于统一内存与 CPU 共享，MPS 采用更保守的 batch size 映射。

#### 未来优化方向：SmolDocling-MLX

[SmolDocling-MLX](https://docling-project.github.io/docling/usage/vision_models/) 是 Docling 的 VlmPipeline 在 Apple Silicon 上的原生优化路径，基于 [MLX](https://ml-explore.github.io/mlx/) 框架实现 M-series 芯片加速。在 M3 Max 上单页处理仅需约 6 秒（对比 Transformers 的约 102 秒，提速 ~16x）<sup>[[2]](#ref-smoldocling)</sup>。

此路径提供**端到端文档理解能力**（含公式识别），可突破当前 MPS 上 formula enrichment 被禁用的限制。当前状态：**规划中**，VlmPipeline 与 StandardPdfPipeline 架构差异较大，需独立评估集成方案。

<a id="ref-mps-formula"></a>[1] MPS + Formula Enrichment 不兼容讨论, https://github.com/docling-project/docling/discussions/2505

<a id="ref-smoldocling"></a>[2] SmolDocling Vision Models 文档, https://docling-project.github.io/docling/usage/vision_models/

## 常见问题

> **配置诊断基础**：遇到配置相关问题时，服务启动日志会输出配置来源信息（如 `Config sources: Loaded: bundled-default(config.default.yaml), user-config(...)`）。可通过 `uv run python -c "from negentropy.perceives.config import describe_config_sources; print(describe_config_sources())"` 检查配置来源，通过 `uv run negentropy-perceives --init-config` 生成默认用户配置。
>
> **常见配置原因**：端口配置不生效通常因用户 YAML 未被加载（检查启动日志 `Config sources:`）；环境变量覆盖 YAML 同名配置（符合 12-factor 原则）；`-c` 参数配置拥有最高优先级。

### 1. 连接超时

**问题**：请求经常超时

**服务端超时时间**：

```bash
# 增加超时时间
NEGENTROPY_PERCEIVES_REQUEST_TIMEOUT=60

# 使用更稳定的抓取方法
{
  "url": "https://example.com",
  "method": "simple"
}
```

**客户端超时时间**：

```python
# 客户端设置超时
async with NegentropyPerceivesClient("http://127.0.0.1:8081/mcp") as client:
    result = await client.call_tool(
        "scrape_webpage",
        {"url": "https://example.com"},
        timeout=30.0,
    )
```

### 2. JavaScript 内容无法抓取

**问题**：动态内容无法提取

**解决方案**：

```bash
# 启用 JavaScript 支持
NEGENTROPY_PERCEIVES_ENABLE_JAVASCRIPT=true

# 使用浏览器方法
{
  "url": "https://example.com",
  "method": "selenium",
  "wait_for_element": ".dynamic-content"
}
```

### 3. 反爬虫检测

**问题**：被网站反爬虫系统识别

**解决方案**：

```json
{
  "url": "https://protected-site.com",
  "method": "selenium",
  "use_stealth": true,
  "random_user_agent": true,
  "scroll_page": true
}
```

### 4. 端口被占用

```bash
# 检查端口占用
netstat -tlnp | grep 8081
# 更换端口
NEGENTROPY_PERCEIVES_HTTP_PORT=8082 negentropy-perceives
```

### 5. 配了 YAML 但端口没生效

```bash
# 1. 检查当前命令是否为新入口
which negentropy-perceives

# 2. 检查最终读取到的配置
uv run python -c "from negentropy.perceives.config import settings; print(settings.model_dump())"

# 3. 检查用户配置文件是否存在且有效
cat ~/.negentropy/perceives.config.yaml
NEGENTROPY_PERCEIVES_HTTP_PORT=8082 negentropy-perceives
```

### 6. CORS 错误

```bash
# 检查 CORS 配置
NEGENTROPY_PERCEIVES_HTTP_CORS_ORIGINS="http://localhost:3000,https://yourdomain.com"
```

### 7. 代理配置不生效

**问题**：配置了代理但请求未走代理

**解决方案**：

```bash
# 必须同时启用代理开关和配置代理 URL
NEGENTROPY_PERCEIVES_USE_PROXY=true \
NEGENTROPY_PERCEIVES_PROXY_URL=http://proxy.example.com:8080 \
negentropy-perceives
```

> 代理配置详情见 [代理服务](#代理服务)。

### 8. 缓存导致内容陈旧

**问题**：抓取结果返回旧内容

**解决方案**：

```bash
# 禁用缓存或缩短 TTL
NEGENTROPY_PERCEIVES_ENABLE_CACHING=false negentropy-perceives

# 或调整缓存生存时间（小时）
NEGENTROPY_PERCEIVES_CACHE_TTL_HOURS=1 negentropy-perceives
```

> 缓存系统详情见 [缓存系统](#缓存系统)。

### 9. 硬件加速设备选择

**问题**：PDF 处理速度慢，希望启用 GPU 加速

**解决方案**：

```bash
# 显式指定设备（默认 auto 自动检测）
NEGENTROPY_PERCEIVES_ACCELERATOR_DEVICE=cuda negentropy-perceives  # NVIDIA GPU
NEGENTROPY_PERCEIVES_ACCELERATOR_DEVICE=mps negentropy-perceives   # Apple Silicon
```

> 设备检测优先级、batch size 自动推断规则及平台特定行为见 [硬件加速配置](#7-硬件加速配置)。

## 安全与合规

使用数据抓取工具时，请遵守以下合规要求：

- **遵守 robots.txt**：抓取前使用 `check_robots_txt` 工具检查网站爬虫规则
- **合理请求频率**：通过环境变量设置适当的请求间隔和并发限制，详见 [环境变量完整参考](#环境变量完整参考)
- **数据隐私保护**：不记录敏感信息（密码、个人信息等），遵守数据保护法规（GDPR、CCPA 等）
- **身份标识**：使用明确的 User-Agent，避免伪装身份

## 相关文档

| 文档                                           | 内容                         | 适用读者        |
| ---------------------------------------------- | ---------------------------- | --------------- |
| [架构设计](./framework.md)                     | 系统架构与设计原则           | 架构师 / 贡献者 |
| [开发指南](./development.md)                   | 环境搭建、编码规范、性能优化 | 开发者          |
| [开发指南 > 测试](./development.md#测试)       | 测试体系与执行方法           | 开发者 / QA     |
| [用户指南 > MCP Server 配置](#mcp-server-配置) | 环境变量与配置管理           | 运维 / 开发者   |
