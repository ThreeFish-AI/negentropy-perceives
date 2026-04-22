# Changelog

All notable changes to the Negentropy Perceives project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### 📦 变更

- **默认 HTTP 端口迁移 `8092` → `2992`** — 同步更新 `src/negentropy/perceives/config.default.yaml`（`http.port`）与 `config.py` 中 `http_port` Pydantic `Field(default=...)`、SDK 向后兼容常量 `DEFAULT_BASE_URL`、`apps/app.py` 用户配置模板注释、`examples/sdk/python_sdk_usage.py` 示例 URL，以及单元测试断言（`tests/unit/test_config.py`、`test_app_entrypoint.py`、`test_sdk.py`）。文档同步刷新：`README.md`、`docs/zh-CN/README.md`、`docs/user-guide.md`（快速入门、SDK 示例、环境变量默认值表 ×2、YAML 示例、Claude MCP JSON 示例、SSE 启动命令、`netstat` 调试提示）、`docs/framework.md` SDK 默认端点。用户显式设置 `http.port` 或 `NEGENTROPY_PERCEIVES_HTTP_PORT` 不受影响；使用默认配置的本地 Claude MCP 客户端需将 `url` 中的端口同步更新为 `2992`。

### 🔧 修复

- **WebPage Pipeline HTML 预处理正则误匹配导致内容大量丢失** — `preprocess_html()` 中 `unwanted_patterns` 的正则 `.*(ad|...).*` 误匹配 CSS Module 类名中的子串（如 `reading` 含 `ad`），导致大量正文 `<p>` 元素被错误删除（约 87% 内容丢失）。修复方式：为关键词匹配添加词边界约束 `(?<![a-zA-Z0-9])...(?![a-zA-Z0-9])`，确保独立 `ad` 类名被命中而复合词中的子串不被误匹配。同时扩展 `unwanted_patterns` 新增 newsletter/social/cookie/copy-button/carousel/tooltip 等非内容模式；新增移除交互元素（`<button>`/`<noscript>`/无文字 `<svg>`）及剥离 `class`/`style` 属性的逻辑，消除原始 HTML/CSS 类名泄漏。涉及文件：`markdown/html_preprocessor.py`
- **WebPage Pipeline 视频/嵌入媒体元素丢失** — `<video>`/`<audio>`/`<iframe>`（YouTube/Vimeo/Bilibili）/`<embed>`/`<object>` 等媒体元素在预处理后既未被移除也未被转换为 Markdown 友好形式，导致 MarkItDown/html2text 转换时输出中完全缺失。修复方式：新增 `_convert_media_elements()` 函数，在 `unwanted_patterns` 移除之前将媒体元素转换为可转换的等价 HTML（`<video>` → `<a>[视频]</a>`、iframe 视频 → 平台播放页链接、`<audio>` → `<a>[音频]</a>`、视频 `<embed>`/`<object>` → 链接），支持提取 `poster` 封面、`<source>` 子元素 URL、相对路径解析。涉及文件：`markdown/html_preprocessor.py`
- **Next.js 图片优化代理 URL 未解析** — 使用 Next.js 图片优化代理 `/_next/image?url=<encoded_cdn_url>&w=...&q=...` 的 `<img>` 标签，其 `src`/`srcset` 指向代理服务而非真实 CDN，导致 `embed_images_in_markdown` 下载时失败或返回非预期内容。修复方式：在 `_convert_media_elements()` 中识别并解析 Next.js 代理 URL，提取 `url` 查询参数中的真实 CDN URL 并替换原始属性。同时新增 `<picture>` 元素展平逻辑，从 `<source srcset>` 中选取最高分辨率 URL 写入关联 `<img>` 的 `src`。涉及文件：`markdown/html_preprocessor.py`
- **残余 HTML 媒体标签泄漏** — `_basic_cleanup()` 防御性后处理未覆盖 `video|audio|picture|source|iframe|embed|object` 标签，若媒体转换因异常未完全处理，残留标签会泄漏到最终 Markdown。修复方式：扩展 `_basic_cleanup()` 的标签清除正则，新增上述媒体标签类型。涉及文件：`markdown/formatter.py`
- **trafilatura 主内容提取路径下图片全量丢失** — S4 `TrafilaturaTool` 以 `output_format='html'` 提取时，会将所有 `<img>` 降级为 TEI `<graphic src="..." alt=".../>`（trafilatura 内部为保持 TEI 兼容）。下游 S5 `_convert_media_elements`、S9 `rich_elements/image.py`、S10 MarkItDown/html2text 均只识别标准 `<img>`，导致 Next.js 代理 URL 未解析、图片 Markdown 完全缺失。仅在运行环境安装 trafilatura 且 S4 竞争获胜时触发（beautifulsoup_heuristic 兜底路径不受影响）。修复方式：在 `TrafilaturaTool._run()` 输出口新增 `_rehydrate_trafilatura_graphics()`，以 BS4 将所有 `<graphic>` 标签名就地改回 `<img>`，保留全部属性；上游/下游零侵入。涉及文件：`pipeline/stages/webpage/main_content_extraction.py`
- **懒加载 `<img>` 与 srcset-only 图片不识别** — `_convert_media_elements()` 仅消费 `src` 属性，而 Next.js/Medium/知乎/CMS 类站点常将真实 URL 放在 `data-src` / `data-original` / `data-lazy-src` / `data-url` / `data-srcset`，或仅提供 `srcset`（无 `src`），导致这些图片在 S9/S10 阶段被丢弃。修复方式：遍历 `<img>` 时新增懒加载属性兜底（占位符 src 或空 src 时迁移 `data-*` 真实 URL），若仅有 `srcset` 则通过 `_pick_best_srcset_url()` 回填 `src`；同时将 `srcset` 中的 Next.js 代理 URL 也解析后回写到 `src`，确保 `srcset-only` 图片被 MarkItDown 正常识别。涉及文件：`markdown/html_preprocessor.py`
- **正文媒体轮播被误当作广告整体移除** — `preprocess_html()` 的 `unwanted_patterns` 中 `carousel|slider|gallery|swiper|slick`（以及 `modal|dialog|overlay|tooltip|popover|toast` 等）会整体 `decompose` 匹配类名/ID 的容器。而现代 CMS（如 Next.js `MediaCarousel-module-scss-module__..._media-carousel`）常将正文内的多图展示包装为 `media-carousel`/`gallery` 容器，导致文章关键正文图片（如 Anthropic engineering 博客中 Opening screen/Sprite editor/Game play 三张配图）被一并删除。修复方式：在这些容器命中 `unwanted_patterns` 时，新增“内容媒体保护”判定——若容器内存在 `<img>`/`<figure>`/`<picture>`/`<video>`/`<audio>` 中任一内容元素，则跳过移除，让后续清洗流程保留真实正文。涉及文件：`markdown/html_preprocessor.py`
- **trafilatura 整页丢图兜底** — 即使 `<graphic>` 被还原为 `<img>`，仍存在 trafilatura 在部分 Next.js / 复杂 figure 结构下直接在主内容提取阶段丢弃全部图片的情况。修复方式：在 `TrafilaturaTool._run()` 的输出处比对 `raw_html` 与提取结果的 `<img>` 数量——若 `raw_html` 至少含 3 张图而主内容为 0 张，则主动返回 `success=False`，触发 S4 竞争模式降级到 `readability` 或 `beautifulsoup_heuristic` 兜底。涉及文件：`pipeline/stages/webpage/main_content_extraction.py`
- **Ruff 代码检查 (47 错)** — 清除全项目 ruff lint 错误至零：
  - F401 未使用导入（34 处）— 自动移除 `src/` 和 `tests/` 中 34 个未使用导入
  - F841 未使用变量（10 处）— 移除或加 `_` 前缀标记有意忽略的变量
  - E741 歧义变量名（2 处）— `l` → `link` / `line`
  - E402 导入位置（1 处）— `conftest.py` 中 `Path` 导入上移至文件顶部
- **Ruff 格式化 (62 files)** — 统一全项目代码格式

## v0.3.0-fix.2 — MCP 取消传导彻底修复

> 修复 MCP Client 取消/超时后 PDF→Markdown 进程仍在后台持续吞噬 CPU/GPU/内存的资源泄漏问题。取消信号可从 MCP 传输层一路下钻至原生引擎，真正做到"叫得停"。

### 🔧 修复

- **取消信号传导链路缺失** — 此前 `docling/mineru/marker_engine.convert(...)` 同步阻塞事件循环，外层 `asyncio.timeout` / FastMCP anyio.CancelScope 无法在 await 检查点抛出 `CancelledError`；即便包入 `asyncio.to_thread`，Python 也无法强制终止线程，原生 C++/CUDA 推理继续吃满资源直至自然结束
- **原生引擎进程隔离** — Docling/MinerU/Marker 全部下沉到独立子进程执行；取消时走 `SIGTERM → grace → SIGKILL` 真正释放 GPU/CPU/显存
- **Pipeline Stage 迁移** — `pipeline/stages/pdf/{layout_analysis,table_extraction,code_detection,formula_extraction,text_extraction}.py` 七处 `engine.convert` 调用点统一改走 `EngineWorkerPool.run(...)`
- **ops 层超时治理** — `ops/pdf.py`、`ops/markdown.py` 原先各自的 `asyncio.timeout(...)` 替换为 ContextVar 级 `bind_cancel_scope(...)`，保持 `PDFResponse.error="任务超时：..."` 既有语义的同时，新增 `"任务已取消：..."` 客户端主动取消路径
- **Middleware 观测性** — `tools/_middleware.py` 在 `on_call_tool` 捕获 `CancelledError` 时登记 `scope.mark_cancelled("client_cancelled")` 并输出"任务取消 tool=... reason=... elapsed=..."日志

### ✨ 新增

- **`core/cancellation.py`** — `CancelScope` 数据类（`threading.Event` + `deadline_monotonic` + `reason`）+ `cancel_scope_var` ContextVar + `bind_cancel_scope(timeout=...)` 异步上下文管理器；同步/线程/子进程代码均可轮询 event 协作式退出
- **`infra/engine_worker.py` + `_engine_worker_entry.py`** — `EngineWorker`（单子进程包装，支持 `SIGTERM/SIGKILL`）+ `EngineWorkerPool`（Supervisor 模式，按引擎维护常驻 worker，取消时 pop + 后台 terminate + 懒启动替身）；子进程侧按 `init_kwargs` 哈希缓存引擎实例，避免重复冷启动
- **配置项** — `pdf_engine_isolation`（`process`/`thread`/`inline`，默认 `process`）、`pdf_worker_pool_size`（默认 `1`）、`pdf_worker_max_tasks`（默认 `50`，周期性回收防内存泄漏）、`pdf_worker_kill_grace_seconds`（默认 `2.0`）；同步暴露为 `NEGENTROPY_PERCEIVES_PDF_*` 环境变量
- **应用生命周期** — `apps/app.py:main()` 退出路径 `finally + atexit.register` 双保险调用 `shutdown_engine_pool()`，确保进程退出时所有 worker 子进程被回收
- **测试覆盖** — `tests/unit/test_cancellation.py`（21 用例，CancelScope 各维度）+ `tests/integration/test_cancellation_flow.py`（10 用例，覆盖超时杀进程、客户端取消、pool 复原、thread 降级、子进程 PID 已消失等场景）

### 📚 参考设计模式

- **Cancel Scope**（Trio/Anyio/Go `context.Context`）— 跨层隐式上下文传递取消信号
- **Warm Worker Pool + Kill-on-Revoke**（Celery `terminate=True` / Gunicorn worker 重启）— 取消即杀，按需懒启动补齐
- **Supervisor Pattern**（Erlang/OTP）— Pool 作为 supervisor，worker 崩溃/被 kill 后自动 respawn
- **Process Isolation for Native Code**（Chromium 渲染进程 / CPython GIL 规避）— 把不可中断的 C++/CUDA 推理放独立进程

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
