---
id: configuration
sidebar_position: 4
title: Configuration
description: Configuration System Guide
last_update:
  author: Aurelius
  date: 2026-03-22
tags:
  - Configuration
  - Settings
  - Environment
---

## 配置系统架构

Negentropy Perceives 采用基于 [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) 的分层配置系统，按优先级从高到低：

1. **运行时参数** - 函数调用时直接传递（详见[用户指南 - 数据提取配置](./user-guide.md)）
2. **环境变量** - `NEGENTROPY_PERCEIVES_` 前缀的环境变量
3. **环境文件** - `.env` 系列文件（详见下方搜索路径）
4. **默认配置** - [`NegentropyPerceivesSettings`](../src/negentropy/perceives/config.py) 中定义的默认值

### `.env` 文件搜索路径

系统按以下顺序搜索 `.env` 文件，后者覆盖前者（不存在的文件被静默跳过）：

1. **项目根目录** `.env` — 通过 `pyproject.toml` 哨兵文件自动检测项目根目录位置
2. **当前工作目录** `.env` — pydantic-settings 原生行为
3. **显式指定** — 通过 `NEGENTROPY_PERCEIVES_ENV_FILE` 环境变量指定自定义路径（最高优先级）

> **提示**：项目根目录检测使得 `.env` 文件无论从哪个目录执行命令都能被正确加载。如需使用非标准路径的配置文件，可通过 `NEGENTROPY_PERCEIVES_ENV_FILE=/path/to/.env` 显式指定。

## 环境变量配置

所有环境变量统一使用 `NEGENTROPY_PERCEIVES_` 前缀，由 Pydantic 自动完成类型转换与校验。

### 服务标识

| 环境变量 | 类型 | 默认值 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `NEGENTROPY_PERCEIVES_SERVER_NAME` | `str` | `negentropy-perceives` | - | 服务器标识名称 |
| `NEGENTROPY_PERCEIVES_SERVER_VERSION` | `str` | 自动读取 | - | 版本号（从 `pyproject.toml` 自动获取） |

### 传输层

| 环境变量 | 类型 | 默认值 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `NEGENTROPY_PERCEIVES_TRANSPORT_MODE` | `str` | `http` | `stdio` / `http` / `sse` | MCP 传输协议模式 |
| `NEGENTROPY_PERCEIVES_HTTP_HOST` | `str` | `localhost` | - | HTTP 服务器绑定主机 |
| `NEGENTROPY_PERCEIVES_HTTP_PORT` | `int` | `8081` | - | HTTP 服务器端口 |
| `NEGENTROPY_PERCEIVES_HTTP_PATH` | `str` | `/mcp` | - | HTTP 端点路径 |
| `NEGENTROPY_PERCEIVES_HTTP_CORS_ORIGINS` | `str?` | `*` | - | CORS 来源白名单（`null` 禁用） |

### 抓取引擎

| 环境变量 | 类型 | 默认值 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `NEGENTROPY_PERCEIVES_CONCURRENT_REQUESTS` | `int` | `16` | `> 0` | 并发请求数 |
| `NEGENTROPY_PERCEIVES_DOWNLOAD_DELAY` | `float` | `1.0` | `>= 0` | 下载间隔（秒） |
| `NEGENTROPY_PERCEIVES_RANDOMIZE_DOWNLOAD_DELAY` | `bool` | `true` | - | 随机化下载间隔 |
| `NEGENTROPY_PERCEIVES_AUTOTHROTTLE_ENABLED` | `bool` | `true` | - | 启用自动节流 |
| `NEGENTROPY_PERCEIVES_AUTOTHROTTLE_START_DELAY` | `float` | `1.0` | `>= 0` | 自动节流初始延迟（秒） |
| `NEGENTROPY_PERCEIVES_AUTOTHROTTLE_MAX_DELAY` | `float` | `60.0` | `>= 0` | 自动节流最大延迟（秒） |
| `NEGENTROPY_PERCEIVES_AUTOTHROTTLE_TARGET_CONCURRENCY` | `float` | `1.0` | `>= 0` | 自动节流目标并发度 |

### 速率限制

| 环境变量 | 类型 | 默认值 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `NEGENTROPY_PERCEIVES_RATE_LIMIT_REQUESTS_PER_MINUTE` | `int` | `60` | `>= 1` | 每分钟请求频率上限 |

### 重试策略

| 环境变量 | 类型 | 默认值 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `NEGENTROPY_PERCEIVES_MAX_RETRIES` | `int` | `3` | `>= 0` | 失败重试最大次数 |
| `NEGENTROPY_PERCEIVES_RETRY_DELAY` | `float` | `1.0` | `>= 0` | 重试间隔（秒） |

### 日志系统

| 环境变量 | 类型 | 默认值 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `NEGENTROPY_PERCEIVES_LOG_LEVEL` | `str` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` | 日志记录级别 |
| `NEGENTROPY_PERCEIVES_LOG_REQUESTS` | `bool?` | `null` | - | 记录请求详情 |
| `NEGENTROPY_PERCEIVES_LOG_RESPONSES` | `bool?` | `null` | - | 记录响应详情 |

### 浏览器引擎

| 环境变量 | 类型 | 默认值 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `NEGENTROPY_PERCEIVES_ENABLE_JAVASCRIPT` | `bool` | `false` | - | 启用 JavaScript 执行 |
| `NEGENTROPY_PERCEIVES_BROWSER_HEADLESS` | `bool` | `true` | - | 无头浏览器模式 |
| `NEGENTROPY_PERCEIVES_BROWSER_TIMEOUT` | `int` | `30` | `>= 0` | 浏览器操作超时（秒） |
| `NEGENTROPY_PERCEIVES_BROWSER_WINDOW_SIZE` | `str` | `1920x1080` | - | 浏览器窗口尺寸 |

### 用户代理

| 环境变量 | 类型 | 默认值 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `NEGENTROPY_PERCEIVES_USE_RANDOM_USER_AGENT` | `bool` | `true` | - | 启用随机 User-Agent 轮换 |
| `NEGENTROPY_PERCEIVES_DEFAULT_USER_AGENT` | `str` | Chrome 120 UA | - | 默认 User-Agent 字符串 |

### 代理服务

| 环境变量 | 类型 | 默认值 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `NEGENTROPY_PERCEIVES_USE_PROXY` | `bool` | `false` | - | 启用代理服务器 |
| `NEGENTROPY_PERCEIVES_PROXY_URL` | `str?` | `null` | - | 代理服务器 URL（启用代理时必填） |

### 请求设置

| 环境变量 | 类型 | 默认值 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `NEGENTROPY_PERCEIVES_REQUEST_TIMEOUT` | `float` | `30.0` | `> 0` | HTTP 请求超时（秒） |

### LLM 编排（Smart 模式）

`method="smart"` 使用 LLM 编排多引擎并行处理 PDF。需安装可选依赖 `litellm`（`uv pip install litellm`）。

| 环境变量 | 类型 | 默认值 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `NEGENTROPY_PERCEIVES_LLM_API_KEY` | `str?` | `null` | - | LLM API Key（ZhipuAI），也可通过 `ZHIPU_API_KEY` 设置 |
| `NEGENTROPY_PERCEIVES_LLM_MODEL` | `str` | `zhipu/glm-5-plus-250414` | - | LiteLLM 模型标识 |
| `NEGENTROPY_PERCEIVES_LLM_TEMPERATURE` | `float` | `0.1` | `0.0 ~ 2.0` | LLM 温度参数 |
| `NEGENTROPY_PERCEIVES_LLM_MAX_TOKENS` | `int` | `4096` | `> 0` | LLM 最大输出 token |
| `NEGENTROPY_PERCEIVES_LLM_TIMEOUT` | `float` | `60.0` | `> 0` | LLM API 超时（秒） |
| `NEGENTROPY_PERCEIVES_LLM_MAX_RETRIES` | `int` | `2` | `>= 0` | LLM API 重试次数 |

### 硬件加速

| 环境变量 | 类型 | 默认值 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `NEGENTROPY_PERCEIVES_ACCELERATOR_DEVICE` | `str` | `auto` | `auto` / `cpu` / `cuda` / `mps` / `xpu` | 推理设备选择，按运行环境自动或显式指定 |
| `NEGENTROPY_PERCEIVES_ACCELERATOR_NUM_THREADS` | `int` | `4` | `>= 1` | CPU 推理线程数 |
| `NEGENTROPY_PERCEIVES_ACCELERATOR_OCR_BATCH_SIZE` | `int` | `0` | `>= 0` | OCR 推理 batch size（0 = 根据设备显存自动推断） |
| `NEGENTROPY_PERCEIVES_ACCELERATOR_LAYOUT_BATCH_SIZE` | `int` | `0` | `>= 0` | Layout 推理 batch size（0 = 根据设备显存自动推断） |
| `NEGENTROPY_PERCEIVES_ACCELERATOR_TABLE_BATCH_SIZE` | `int` | `0` | `>= 0` | Table 推理 batch size（0 = 根据设备显存自动推断） |

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

| 特性 | 行为 | 原因 |
| --- | --- | --- |
| Formula Enrichment | **自动禁用** | Docling CodeFormula VLM 不支持 MPS，启用时整个管道回退 CPU<sup>[[1]](#ref-mps-formula)</sup> |
| Flash Attention 2 | 不可用 | 仅 CUDA 支持 |
| Batch Sizes | 自动优化 | 基于统一内存大小推断（8-32），详见下表 |
| OCR 引擎 | macOS Vision 可选 | 自动偏好 `OcrMacOptions`（Apple Vision Framework 原生 OCR） |
| TableFormer | 透明回退 CPU | Docling 内部处理，无需干预 |
| 公式降级 | Markdown 正则 + PyMuPDF | 参考 [`math_formula.py`](../src/negentropy/perceives/pdf/math_formula.py) |

> **注意**：公式提取被禁用后，系统自动通过 PyMuPDF 字体分析 + Unicode→LaTeX 映射进行降级补偿，覆盖大部分常见数学公式场景。

##### NVIDIA CUDA

| 特性 | 行为 | 原因 |
| --- | --- | --- |
| Flash Attention 2 | **自动启用** | 需安装 `flash-attn` 包（`pip install flash-attn`） |
| Batch Sizes | 自动优化 | 基于专用显存大小推断（8-64），详见下表 |
| 全功能支持 | Formula + Table + OCR | 所有 Docling 功能完全兼容 |

##### Intel XPU

| 特性 | 行为 | 原因 |
| --- | --- | --- |
| Flash Attention 2 | 不可用 | 仅 CUDA 支持 |
| Batch Sizes | 自动优化 | 使用中等策略（8-16） |

##### Batch Size 自动推断规则

| 设备类型 | 可用显存 | ocr / layout batch | table batch |
| --- | --- | --- | --- |
| **CPU** | - | 4 | 4 |
| **MPS** | < 12 GB | 8 | 4 |
| **MPS** | 12-24 GB | 12 | 6 |
| **MPS** | 24-48 GB | 16 | 8 |
| **MPS** | ≥ 48 GB | 32 | 16 |
| **CUDA** | < 8 GB | 8 | 4 |
| **CUDA** | 8-12 GB | 16 | 8 |
| **CUDA** | 12-24 GB | 32 | 16 |
| **CUDA** | ≥ 24 GB | 64 | 32 |

> MPS 统一内存说明：Apple Silicon 的 GPU 可用显存按物理内存 × 75% 估算（如 32GB 物理内存 → ~24GB GPU 可用）。由于统一内存与 CPU 共享，MPS 采用更保守的 batch size 映射。

#### 未来优化方向：SmolDocling-MLX

[SmolDocling-MLX](https://docling-project.github.io/docling/usage/vision_models/) 是 Docling 的 VlmPipeline 在 Apple Silicon 上的原生优化路径，基于 [MLX](https://ml-explore.github.io/mlx/) 框架实现 M-series 芯片加速。在 M3 Max 上单页处理仅需约 6 秒（对比 Transformers 的约 102 秒，提速 ~16x）<sup>[[2]](#ref-smoldocling)</sup>。

此路径提供**端到端文档理解能力**（含公式识别），可突破当前 MPS 上 formula enrichment 被禁用的限制。当前状态：**规划中**，VlmPipeline 与 StandardPdfPipeline 架构差异较大，需独立评估集成方案。

<a id="ref-mps-formula"></a>[1] MPS + Formula Enrichment 不兼容讨论, https://github.com/docling-project/docling/discussions/2505

<a id="ref-smoldocling"></a>[2] SmolDocling Vision Models 文档, https://docling-project.github.io/docling/usage/vision_models/

### Docling PDF 引擎

| 环境变量 | 类型 | 默认值 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `NEGENTROPY_PERCEIVES_DOCLING_ENABLED` | `bool` | `false` | - | 启用 Docling 作为可选 PDF 提取引擎 |
| `NEGENTROPY_PERCEIVES_DOCLING_OCR_ENABLED` | `bool` | `true` | - | 为扫描版 PDF 启用 OCR |
| `NEGENTROPY_PERCEIVES_DOCLING_TABLE_EXTRACTION_ENABLED` | `bool` | `true` | - | 启用 Docling 高级表格提取 |
| `NEGENTROPY_PERCEIVES_DOCLING_FORMULA_EXTRACTION_ENABLED` | `bool` | `true` | - | 启用 Docling 数学公式提取（MPS 上自动禁用） |
| `NEGENTROPY_PERCEIVES_MINERU_ENABLED` | `bool` | `false` | - | 启用 MinerU 引擎（Apache 2.0，最佳 LaTeX 公式提取） |
| `NEGENTROPY_PERCEIVES_MINERU_DEVICE` | `str` | `auto` | `auto`/`cpu`/`mlx`/`cuda` | - | MinerU 设备选择 |
| `NEGENTROPY_PERCEIVES_MINERU_BACKEND` | `str` | `auto` | `auto`/`pipeline`/`vlm` | - | MinerU 后端选择 |
| `NEGENTROPY_PERCEIVES_MARKER_ENABLED` | `bool` | `false` | - | 启用 Marker 引擎（GPL-3.0，最佳整体准确率） |
| `NEGENTROPY_PERCEIVES_MARKER_LLM_ENHANCED` | `bool` | `false` | - | 启用 Marker LLM 增强模式 |
| `NEGENTROPY_PERCEIVES_MARKER_LICENSE_ACKNOWLEDGED` | `bool` | `false` | - | 确认 GPL-3.0 许可证条款 |
| `NEGENTROPY_PERCEIVES_MINERU_ENABLED` | `bool` | `false` | - | 启用 MinerU（最佳 LaTeX 公式提取） |
| `NEGENTROPY_PERCEIVES_MINERU_DEVICE` | `str` | `auto` | `auto` / `cpu` / `mlx` / `cuda` | MinerU 设备选择 |
| `NEGENTROPY_PERCEIVES_MINERU_BACKEND` | `str` | `auto` | `auto` / `pipeline` / `vlm` | MinerU 后端选择 |
| `NEGENTROPY_PERCEIVES_MARKER_ENABLED` | `bool` | `false` | - | 启用 Marker（最佳整体准确率，GPL-3.0） |
| `NEGENTROPY_PERCEIVES_MARKER_LLM_ENHANCED` | `bool` | `false` | - | 启用 Marker LLM 增强模式 |
| `NEGENTROPY_PERCEIVES_MARKER_LICENSE_ACKNOWLEDGED` | `bool` | `false` | - | 确认 GPL-3.0 许可证条款（需设为 `true` 方可启用 Marker） |

## 配置验证规则

### 字段验证器

系统内置三个 `@field_validator`，在加载时自动规范化输入：

- **`log_level`** — 自动转为大写，仅接受 `DEBUG`、`INFO`、`WARNING`、`ERROR`、`CRITICAL`
- **`transport_mode`** — 自动转为小写，仅接受 `stdio`、`http`、`sse`
- **`accelerator_device`** — 自动转为小写，仅接受 `auto`、`cpu`、`cuda`、`mps`、`xpu`

### 配置不可变性

全局实例 `settings` 通过 `frozen=True` 配置为不可变对象，创建后不可修改，保障运行时配置一致性。

### Scrapy 设置映射

`get_scrapy_settings()` 方法将抓取引擎配置映射为 Scrapy 原生设置字典，供 Scrapy 框架直接消费。

## 环境配置模板

### 开发环境

```bash
# .env.development
NEGENTROPY_PERCEIVES_TRANSPORT_MODE=stdio
NEGENTROPY_PERCEIVES_LOG_LEVEL=DEBUG
NEGENTROPY_PERCEIVES_ENABLE_JAVASCRIPT=true
NEGENTROPY_PERCEIVES_BROWSER_HEADLESS=false
NEGENTROPY_PERCEIVES_CONCURRENT_REQUESTS=4
```

### 生产环境

```bash
# .env.production
NEGENTROPY_PERCEIVES_TRANSPORT_MODE=http
NEGENTROPY_PERCEIVES_HTTP_HOST=0.0.0.0
NEGENTROPY_PERCEIVES_HTTP_PORT=8081
NEGENTROPY_PERCEIVES_LOG_LEVEL=INFO
NEGENTROPY_PERCEIVES_ENABLE_JAVASCRIPT=true
NEGENTROPY_PERCEIVES_BROWSER_HEADLESS=true
NEGENTROPY_PERCEIVES_CONCURRENT_REQUESTS=32
NEGENTROPY_PERCEIVES_USE_RANDOM_USER_AGENT=true
```

## 配置管理最佳实践

- `.env` — 本地开发配置（不纳入版本控制，权限 `600`）
- `.env.example` — 配置模板（纳入版本控制）
- `.env.development` / `.env.production` — 环境专用配置
- 启用代理时务必同时配置 `PROXY_URL`，否则启动验证将报错

## 故障诊断

### 启动诊断输出

服务启动时会自动输出配置来源信息：

```text
Config sources: Loaded: /path/to/project/.env
```

如果未加载任何 `.env` 文件，则显示：

```text
Config sources: No .env files loaded (using env vars and defaults)
```

### 常用排查命令

```bash
# 查看所有 Negentropy Perceives 环境变量
env | grep NEGENTROPY_PERCEIVES_

# 检查配置文件内容
cat .env

# 验证最终生效的配置
uv run python -c "from negentropy.perceives.config import settings; print(settings.model_dump())"

# 检查 .env 搜索路径
uv run python -c "from negentropy.perceives.config import describe_config_sources; print(describe_config_sources())"
```

### 常见问题

- **端口配置不生效**：检查启动日志中的 `Config sources:` 行，确认 `.env` 文件是否被成功加载。如未加载，确认 `.env` 位于项目根目录或当前工作目录。
- **环境变量优先级**：环境变量始终覆盖 `.env` 文件中的同名配置。如需强制使用 `.env` 中的值，先清除对应的环境变量。
- **自定义配置文件路径**：使用 `NEGENTROPY_PERCEIVES_ENV_FILE=/path/to/.env` 指定非标准路径。

---

更多配置详情请参考 [`.env.example`](../.env.example) 和 [`src/negentropy/perceives/config.py`](../src/negentropy/perceives/config.py)。
