# Changelog

All notable changes to the Negentropy Perceives project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## v0.3.0-fix.1 — CI 流水线修复

> 修复 GitHub Actions CI 全线失败问题，恢复 7/7 Job 全绿。

### 🔧 修复

- **Ruff 代码检查 (34 错)** — 清除 Pipeline 模块中 32 个未使用导入（F401）、1 个未使用变量（F841）、1 个 availability-check 导入标记（noqa）
- **Ruff 格式化 (24 files)** — 统一 Pipeline + Tools 模块代码格式（`ruff format`）
- **Bandit 安全扫描 (B110)** — 将 `asset_bundling.py` 和 `page_fetching.py` 中 2 处空 `except: pass` 替换为 `logging.debug()` 异常日志
- **文档完整性测试** — 创建 `docs/configuration.md` 重定向页，修复 `test_configuration_doc_exists` 断言
- **表格覆盖度测试** — 修正 `test_docs_configuration.py` 正则表达式，兼容 Markdown 表格列对齐空格
- **安全依赖升级** — `cryptography` 46.0.6 → 46.0.7 (CVE-2026-39892)、`pypdf` 6.9.2 → 6.10.0 (GHSA-3crg-w4f6-42mx)
- **CVE 豁免** — `transformers` CVE-2026-1839 暂时豁免（修复版本 5.0.0rc3 为 major 跳升，需单独评估）
- **Mypy 类型检查 (93 错)** — 修复此前被 ruff 失败遮蔽的全部预存 mypy 错误：
  - `callable` → `Callable[[Any], Any]`：修正 `figure_text_filter.py` 中 4 处类型注解误用
  - 隐式 Optional 修复：`converter.py` 中 `str = None` → `Optional[str] = None`
  - 类型安全加固：`processor.py` `Optional[EnhancedPDFProcessor]` 注解、`config.py` `transport_mode` Literal 化、`engine.py` driver 类型注解
  - 添加 `types-PyYAML` 开发依赖解决 `yaml` 模块 import-untyped 错误
  - 精准 `# type: ignore[error-code]` 注释处理 BeautifulSoup 联合类型等 ~70 处无法通过代码修改解决的类型问题

## v0.3.0 — 流水线觉醒，工具瘦身

> 引入 Stage 化 Pipeline 编排框架，将文档处理拆解为可组合、可竞争的流水线；同时精简 MCP 工具至 6 个，聚焦核心转换能力。

### ✨ 核心亮点

- **Pipeline 编排框架** — 全新 `pipeline/` 子包，Stage 基类 + 竞争 Stage + 工具注册表 + 调度器 + 编排器，配置驱动
- **PDF Pipeline（S0-S9）** — 10 阶段管线：预处理 → 文档扫描 → 版面分析 → 并行提取（文本/表格/公式/图片/代码） → 组装 → 资源打包
- **WebPage Pipeline（S1-S12）** — 12 阶段管线：合规检查 → 网页获取 → 反检测 → 主内容提取 → 并行抽取（公式/代码/表格/图片） → Markdown 转换 → 资源打包
- **竞争模式** — 不稳定 Stage（版面分析、表格/公式/代码识别、主内容提取）支持多工具并行竞争、择优返回
- **工具精简（12 → 6）** — 删除 6 个低价值/可内化工具，保留核心转换入口；`method="auto"` 优先走 Pipeline，降级走原有路径

### 🔧 更多特性

- **配置驱动**: `config.default.yaml` 新增 `pipeline:` 节，Stage 级工具列表、rank 排序、竞争参数全部可配置
- **引擎级门控**: `docling_enabled` / `mineru_enabled` / `marker_enabled` 统一控制 Pipeline 中的引擎可用性
- **PASSTHROUGH_KEYS**: 配置展平桥接函数新增 `pipeline` 透传，保持嵌套结构完整性

## v0.2.0 — 隐身的眼睛，睁开了

> 给 AI Agent 装上一双能看懂网页和 PDF 的眼睛，而且这双眼睛会隐身。

### ✨ 核心亮点

- **复杂 PDF，一句话搞定** — 5 引擎自动降级 + LLM 三阶段编排（分析→并行调度→择优融合）
- **反爬墙？穿墙** — Selenium / Playwright 隐身双引擎，鼠标轨迹 + 随机延迟，无感绕过
- **网页→Markdown，9 道工序精炼** — 去噪、表格对齐、代码检测、排版复原，一步到位
- **12 工具 · 6 领域 · 5 层架构** — 退避 + 限速 + 缓存三层弹性护盾，生产级底座

### 🔧 更多特性

- **结构化提取**: CSS 选择器精准映射 + 5 种数据模板，内置 robots.txt 合规检查
- **PDF 深度内容**: 表格识别、LaTeX 公式保持、图像 base64 嵌入，增强模式可选
- **4 层配置体系**: 内置默认 → 用户 YAML → 环境变量 → CLI（pydantic-settings 驱动）
- **多传输模式**: STDIO / StreamableHTTP / SSE，默认 StreamableHTTP，开箱即用
- **异步 SDK**: NegentropyPerceivesClient，类型安全，async/await 原生
- **批量并发**: 网页批抓、PDF 批转均走 asyncio，吞吐拉满
