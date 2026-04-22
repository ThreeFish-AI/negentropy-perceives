# Issue 处理档案

> 记录已处理的 Issue 摘要，便于同类问题跨上下文复用。
> 按“问题描述 / 表因 / 根因 / 处理方式 / 后续防范 / 同类问题影响与注意事项”结构化维护。

## [2026-04-22] parse_webpage_to_markdown 图片元素丢失（Phase 1 / 2 / 3）

### 问题描述
用户上报 `parse_webpage_to_markdown` 在真实网页（如 `https://www.anthropic.com/engineering/harness-design-long-running-apps`）下的 Markdown 输出出现如下问题：
- 大段正文 `<p>` 元素缺失（约 87% 内容丢失）
- `<video>`/`<iframe>`/`<embed>` 媒体元素缺失
- Next.js `/_next/image?url=...` 代理 URL 未解析为真实 CDN 地址
- 文章内 `Opening screen` / `Sprite editor` / `Game play` 三张配图（属 `MediaCarousel` 容器）完整丢失

### 表因
`preprocess_html()` 后段 `<p>` 与 `<img>` 数量远低于 `extract_content_area()` 阶段；`<video>` / `<iframe>` 直接消失；Markdown 中的图片 URL 仍指向代理域或根本没有图片条目。

### 根因
1. **Phase 1 — CSS Module 类名误匹配**：`unwanted_patterns` 使用 `.*(ad|...).*` 正则去匹配 class/id，CSS Module 类名（如 `reading-column`）中子串 `ad` 被命中，整段正文 `<p>` 被 `decompose`。
2. **Phase 2 — 媒体元素未转 Markdown 友好形式**：`<video>`/`<audio>`/`<iframe>`/`<embed>`/`<object>` 既未被保留也未被转链接；Next.js 图片代理 URL 未被解析为真实 CDN URL。
3. **Phase 3a — trafilatura `<img>` 降级为 TEI `<graphic>`**：`trafilatura.extract(output_format='html')` 会把 `<img>` 改写成 `<graphic>`；下游 `_convert_media_elements` / MarkItDown / html2text 仅识别 `<img>`，图片全量丢失。
4. **Phase 3b — 懒加载 / srcset-only**：真实 URL 放在 `data-src`/`data-srcset` 或只有 `srcset` 时，`<img>` 因无 `src` 被判为空。
5. **Phase 3c — trafilatura 整页丢图**：某些 Next.js / 复杂 figure 结构下 trafilatura 会直接丢弃全部图片（既非 `<graphic>` 也非 `<img>`）。
6. **Phase 3d — 媒体轮播被当广告整体移除**：`unwanted_patterns` 中 `carousel|slider|gallery|swiper|slick|modal|dialog|overlay|tooltip|popover|toast` 对 CMS 正文 `MediaCarousel` 容器过度误杀。

### 处理方式
- 为 `ad|sidebar|nav|menu` 添加词边界约束 `(?<![a-zA-Z0-9])...(?![a-zA-Z0-9])`，避免 CSS Module 子串误命中。
- 新增 `_convert_media_elements()`：`<video>/<audio>` → `[视频]/[音频]` 链接；`<iframe>`（YouTube/Vimeo/Bilibili）→ 平台播放页链接；`<picture>` 展平；`<embed>/<object>` 视频转链接；Next.js 代理 URL 解析回真实 CDN URL。
- 扩展 `_basic_cleanup()` 防御性清理残余 `video|audio|picture|source|iframe|embed|object` 标签。
- 新增 `_rehydrate_trafilatura_graphics()`：S4 `TrafilaturaTool` 输出口将 `<graphic>` 就地改名为 `<img>`，保留全部属性。
- 懒加载兜底：当 `src` 缺失或为占位符时，顺序从 `data-src`/`data-original`/`data-lazy-src`/`data-url` 迁移真实 URL；若仅有 `srcset`，取最高分辨率回填 `src`；`srcset` 中的 Next.js 代理也解析后回写。
- 轮播图片保护：`unwanted_patterns` 命中的容器若含 `<img>/<figure>/<picture>/<video>/<audio>`，跳过移除。
- trafilatura 整页丢图兜底：`raw_html` 含 ≥3 张图而主内容 0 张时，`TrafilaturaTool` 主动返回失败，触发 S4 竞争模式降级到 `readability` / `beautifulsoup_heuristic`。

### 后续防范
- 任何 `find_all(class_=pattern)` / `find_all(id=pattern)` 的 `.*` 通配正则都必须上词边界，杜绝 CSS Module 哈希误命中。
- 凡对 CMS/语义容器（carousel/gallery/modal/slider 等）执行整体 `decompose` 前，必须先做“内容元素保护”判定，避免误杀正文媒体。
- S4 / S10 类“多工具竞争”Stage 中的单个工具若对输出做了**格式改写**（如 TEI `<graphic>`），应在工具出口处就地归一化为标准 HTML，不让歧义格式外泄到下游。
- S4 这类“可能整体丢内容”的工具，应在输出口设兜底检查，一旦发现关键信号（图片、正文长度）严重偏离 `raw_html`，主动返回失败由竞争模式降级，而不是静默输出劣化结果。

### 同类问题影响与注意事项
- 其他依赖 `beautifulsoup_heuristic` 启发式路径的 Stage（如后续新增的抽取工具）若做类似“整体删除”，也需套用“内容元素保护”逻辑。
- 所有走 `output_format='html'` 的外部抽取库（如 readability 未来版本、article-extractor 等）都应假定可能存在非标准标签，建议在 S4/S5 出口统一做一次 BS4 归一化。
- 懒加载兜底也适用于 `<picture>` 内的 `<source>`；需注意某些站点（如 Medium）会把真实 URL 放在 `data-*` 外的自定义属性，必要时扩展兜底属性集合。

## [2026-04-22] parse_pdf_to_markdown 四工具全报 AttributeError 并触发 300s 兜底超时

### 问题描述
`parse_pdf_to_markdown` 在 `assets/2603.05344v3.pdf` / `assets/Context Engineering 2.0 - The Context of Context Engineering.pdf` 等 PDF 上失败，MCP 日志出现三连反应：
- `layout_analysis` 四工具（Docling / MinerU / Marker / PyMuPDF）同时报 `'DocumentCharacteristics' object has no attribute 'local_path'`；
- Stage 全败后触发旧版 Docling 全文档兜底路径，卡死在 300 秒超时；
- 会话最终以 `anyio.ClosedResourceError` 抛出，MCP 通道被阻塞。

用户进一步要求 **Docling/MinerU/Marker/PyMuPDF 四工具在 `layout_analysis` 中必须“全部可用且被充分利用”**。

### 表因
`layout_analysis` 各工具从入参读 `local_path` 时拿到的是 `DocumentCharacteristics` 实例而非 `PreprocessingOutput`，直接抛属性不存在；旧版兜底路径本就慢（300s），Stage 失败又触发它，最终 MCP 超时断链。

### 根因（三层叠加）
1. **L1 输入路由错配**：`PipelineOrchestrator.run()` 采用“上一 Stage 的 output 即下一 Stage 的 input”的隐式链式语义。S1 `quick_scan` 的 output 是 `DocumentCharacteristics`，会覆盖 `current_input` 里 S0 的 `PreprocessingOutput`，于是 S2 `layout_analysis` 及其后所有需要 `local_path` 的 Stage 全部拿错输入；同时 `assembly`/`asset_bundling` 这种需要**汇聚多个前序 Stage 结果**的复合输入，也根本无法用单一链式语义构造。
2. **L2 竞争并发上限硬截断**：`StageScheduler._run_competition()` 第 133 行 `candidates = tools[:max_concurrent]`；`layout_analysis` 配了 4 个工具但 `max_concurrent: 2`，rank=3 的 Marker 与 rank=4 的 PyMuPDF **完全不进入竞争调度**，用户观感是“只有两个工具在跑”。
3. **L3 引擎门控 + 依赖不可达**：`settings.docling_enabled / mineru_enabled / marker_enabled` 默认均为 `False`，被 `_apply_engine_gates()` 提前过滤；mineru / marker 又属于 `pyproject.toml [all-engines]` 可选依赖组，默认 `uv sync` 装不上，双重过滤导致三引擎在开箱即用下根本进不了场。

### 处理方式
- **Phase 1 · 数据路由（YAML 声明式）**：
  - `pipeline_config.StageConfig` 新增 Optional 字段 `input_from` / `input_builder`；
  - `PipelineOrchestrator.__init__` 新增 `input_builders: Dict[str, Callable]` 参数；
  - 新增 `_resolve_input(stage_cfg, results, initial_input, chain_input) -> (resolved, error)`，按「`input_builder` 优先 → `input_from` → `chain_input`」顺序解析每个 Stage 的输入；缺失/失败返回结构化错误而非抛 `AttributeError`；
  - `run()` 顺序组对每个 Stage 先 resolve 再 execute；并行组对组内每个 Stage 各自 resolve 后再 `asyncio.gather`，杜绝同一 `current_input` 污染不同并行 Stage；
  - `convenience._PDF_INPUT_BUILDERS` 注册 `assembly` / `asset_bundling` 两个复合构造器，分别汇聚 preprocessing/layout/text/tables/formulas/images/code 与 assembly/image_extraction/preprocessing；
  - `config.default.yaml` 的 `pipeline.pdf.stages` 各 Stage 显式声明 `input_from: preprocessing` 或 `input_builder: <key>`；webpage 分支不改（保持链式语义）。
- **Phase 2 · 四工具充分利用**：
  - `config.default.yaml` 放开 `layout_analysis.max_concurrent` 2→4、`table_extraction.max_concurrent` 2→4、`formula_extraction.max_concurrent` 2→3，让“声明工具数 == 参与竞争数”；
  - `config.py` 将 `docling_enabled / mineru_enabled / marker_enabled` 默认值从 `False` 翻转为 `True`，语义下沉为“允许参与调度；真实是否运行由 `is_available()` 能力检测决定”，未装依赖仍自动跳过；
  - `scheduler._resolve_tools()` 将工具 `is_available()=False` 跳过日志从 `debug` 提升为 `info`，并打印 `Stage 'X' 参与竞争 tools=[...]（声明=[...]，已过滤不可用）`；
  - `convenience._log_pdf_engines_summary_once()` 在首次调用 PDF 管线时 INFO 级打印 `[PDF engines] docling=ok(...), mineru=..., marker=..., pymupdf=ok(...)` 摘要，缺失引擎给出 `uv sync --extra all-engines` 指引。
- **Phase 3 · 文档闭环**：`docs/user-guide.md` 新增「启用四大 PDF 引擎」章节，给出 extras 安装命令与启动日志样例；同步更新 CHANGELOG 与本档。

### 后续防范
- Stage 间输入来源必须由 YAML 显式声明，严禁再依赖“上一 Stage 的 output 作为下一 Stage 的 input”的隐式约定——隐式链式语义遇到复合输入或多分支时必然断链。
- `competition.max_concurrent` 原则上等于声明工具数；若出于资源考虑要收紧，必须在注释中写明原因并确保 rank 靠后的工具在业务上确实是“备胎”。
- 引擎能力检测只允许有**一个事实源**：优先 `is_available()`（运行时可导入）；`*_enabled` 配置项退化为“显式关闭开关”，不承担能力判定。
- 新加 Stage 时，若输入需要来自非紧邻的前序 Stage 或多个前序 Stage，先在 `convenience` 注册构造器并在 YAML 用 `input_builder: <key>` 声明；单一前序用 `input_from: <name>`。

### 同类问题影响与注意事项
- webpage 管线当前通过 `StageContext` 这个**可变聚合对象**在 Stage 间共享状态，与 PDF 的 dataclass 纯值传递是两套机制；`input_from` 对 webpage 不产生影响，但未来若 webpage 也要切到纯值传递，应复用同一路由机制。
- `EngineWorkerPool` 已对每个 PDF 引擎做进程级串行化锁，`max_concurrent=4` 即便四个子进程同时启动，实际仍会串行执行昂贵模型推理，不会 OOM；但若未来引入无锁引擎需重新评估。
- 任何“竞争模式 Stage 声明 N 个工具”的改动都要同步检查 `max_concurrent ≥ N`，否则 rank 靠后的候选将无声丢失——这是 pipeline 层长期隐性缺陷，新增 Stage 时需自查。
- 引擎门控默认值翻转为 `True` 后，CI 环境若原先依赖 `*_enabled=False` 隐式禁用某引擎，应改用环境变量 `NEGENTROPY_PERCEIVES_DOCLING_ENABLED=false` 或 YAML 显式覆盖。

## [2026-04-22] PDF 管线二次修复：MinerU backend / PyMuPDF 表格 caller / 模型预热缺位

### 问题描述
前一次（Phase 1~3）修复落地后，再次跑 `parse_pdf_to_markdown`，日志暴露三处独立缺陷：

1. MinerU 子进程秒级报错 `Invalid value for '-b' / '--backend': 'vlm-mlx-engine'`，`exit_code=2`；
2. Marker 在用户请求中现场下载 `layout/2025_09_23` 模型（总量 ~1.35GB），下载到 131M/1.35G 时被 `layout_analysis` 120s 工具超时取消，最终 Stage 以 `Stage 'layout_analysis' 工具 'marker' 超时` 结束；
3. `table_extraction` 的 PyMuPDF 分支 100% 报 `EnhancedPDFProcessor.extract_tables_with_geometry() missing 1 required positional argument: 'text_blocks'`。

用户明确要求：在修复以上三项的同时，**将引擎模型通过“预触发”方式在请求外下载**，避免首请求 1.35GB 下载必超时。

### 表因
- `layout_analysis` / `formula_extraction` 中 MinerU 工具即时失败（CLI 拒绝 backend 值）；
- `layout_analysis` 中 Marker 工具在 ~120s 处超时取消（正在下载模型）；
- `table_extraction` 中 PyMuPDF 工具每次立即抛 `TypeError: missing positional argument: 'text_blocks'`。

### 根因
1. **D1 · MinerU backend 字符串错误**：`pdf/engines/mineru.py` 在 `device=mps` 与 Apple Silicon 自动检测分支把 `_resolved_backend` 硬编码为 `vlm-mlx-engine`。MinerU CLI `--backend` 的合法值只有 `pipeline / vlm-http-client / hybrid-http-client / vlm-auto-engine / hybrid-auto-engine`；`vlm-mlx-engine` 并不存在，触发 Click 的参数校验失败。
2. **D2 · 模型下载延后到首请求**：三个引擎（docling/mineru/marker）的 `is_available()` 只检查 import，`create_model_dict()` / `DocumentConverter(...)` 的模型拉取延后到第一次 `convert()` 调用。Marker layout 模型 ~1.35GB，常规家宽下载远超 120s 工具超时上限，且超时后 HuggingFace Hub 缓存可能处于半下载状态；此外，仓里没有任何预热入口可供运维在部署阶段离线拉取。
3. **D3 · PyMuPDF 表格 caller 多重错误**：`pipeline/stages/pdf/table_extraction.py` 中 `FitzTableExtractor._run()` 循环体同时犯三个错——（a）传 `page`（页对象）而不是 `doc`（文档对象）；（b）漏掉必需位置参数 `text_blocks`；（c）把 `(bbox_map, all_tables)` 返回元组当 `List[ExtractedTable]` 迭代。历史 `# type: ignore[call-arg] / [union-attr]` 注释还压住了 mypy 告警。

### 处理方式
- **D1 · backend 字符串替换**：`mineru.py` 两处 `vlm-mlx-engine` → `vlm-auto-engine`（语义：由 MinerU 自动挑选最佳 VLM 后端，MLX 可用时走 MLX，否则 fallback）；`settings.mineru_device="mlx"` / `settings.mineru_backend="auto"` 对外 API 不变；同步修正 `tests/unit/test_mineru_engine.py` 三处断言，并将 `test_mps_device_maps_to_mlx` 重命名为 `test_mps_device_maps_to_vlm_auto` 使测试意图与断言一致。
- **D3 · PyMuPDF 表格 caller 改写**：`table_extraction.py` 按仓内已通过的 `pdf/processor.py:1321-1325` 调用范式重写循环体：
  ```python
  text_blocks = page.get_text("blocks")
  _, page_tables = processor.extract_tables_with_geometry(doc, page_idx, text_blocks)
  ```
  同时移除该函数中所有 `# type: ignore[call-arg] / [union-attr]` 注释，让 mypy 重新校验。
- **D2 · `perceives prefetch-models` CLI**：
  - 新增 `src/negentropy/perceives/cli/commands/prefetch_models.py`，暴露 `run()` 作为 Typer 子命令；
  - `src/negentropy/perceives/cli/app.py` 注册 `app.command("prefetch-models")(prefetch_models.run)`；
  - 每个引擎独立 try/except + `_SkipEngine` 信号异常：docling → `DocumentConverter(format_options={...})`；marker → `from marker.models import create_model_dict; create_model_dict()`；mineru → `subprocess.run([shutil.which("mineru-models-download"), "-s", "huggingface", "-m", "all"])`；未安装引擎返回 `skipped` 并提示 `uv sync --extra <engine>`；
  - 支持 `--engines docling,marker,mineru|all` 过滤与 `--hf-home <path>` 设置 `os.environ["HF_HOME"]`；
  - 任一引擎 error → 退出码 1，全部 ok/skipped → 退出码 0；
  - `pipeline/convenience.py` 的 `[PDF engines]` 汇总日志尾追加一句 `首次使用前建议预热模型... uv run perceives prefetch-models` 提示；
  - 新增 `tests/unit/test_prefetch_models_cli.py`（11 条单测，覆盖引擎选择、未安装跳过、subprocess 失败、HF_HOME 传导、非法引擎名拒绝）。
- **文档**：`docs/development.md` 在“详细环境配置”后追加“模型预热（推荐）”小节；`docs/user-guide.md` 在 PDF 章节引用该小节；`CHANGELOG.md` Unreleased 追加 🔧 修复（D1/D3）与 ✨ 新增（prefetch-models）。

### 后续防范
- 任何调用签名形如 `f(doc, page_idx, text_blocks)` 的辅助函数，在 Stage 适配器中务必配齐位置参数并正确解包返回值；禁止用 `# type: ignore[call-arg]` 压制签名错误告警——应让 mypy 在 CI 就把错误拦下。
- 外部 CLI 的 `choices` 类参数值不要硬编码在多处（如 `vlm-mlx-engine`），应在 engine 层集中维护可选值常量，并尽量以 `auto` 类自适配值作为默认，把具体后端的选择权交回外部工具；重大版本升级需把合法值对照 Release Notes 过一遍。
- 任何涉及“首请求下载大模型”的引擎，必须提供独立的“预热 / warm-up”入口，**把下载与服务路径解耦**。CI / 部署流水线应在部署阶段执行预热，而不是把它暴露在用户请求路径上。
- 引入新引擎时需在 `is_available()`（import 级）之外补充一个可选的“模型是否已缓存”探测，或直接在部署文档写明预热命令。

### 同类问题影响与注意事项
- 虽然 `settings.mineru_backend` 允许显式覆盖（例如 `pipeline`），但在默认路径上 macOS 用户最常见；这类“平台自适配默认值”在 PR 里一定要加集成测试或至少让 `mineru --help` 的合法列表在单测中显式断言，防止再被字符串 typo 击穿。
- `extract_tables_with_geometry` 之外，仓里还有若干工具类函数被多个 Stage 适配器复用；同类 Stage 适配器在迁入新版 pipeline 时，**必须**以 `pdf/processor.py` 中的成熟调用为蓝本，不要凭直觉简化参数。
- Prefetch CLI 对未安装引擎走 `skipped` 分支，对 CI 轻量环境友好；但在镜像构建脚本里应**显式**检查 `exit_code == 0` 且 `skipped` 集合为空，否则会出现“镜像里缺 marker 依赖却没人发现”的情况。
- 首次请求预热模型会在本地缓存 HuggingFace 目录产生 GB 级数据，Docker 镜像/共享开发机请用 `--hf-home` 指向持久化卷避免重复下载。
