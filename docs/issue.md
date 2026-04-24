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

## [2026-04-24] perceives prefetch-models 在 mineru 步骤“看似卡死”

### 问题描述
执行 `uv run perceives prefetch-models`，docling / marker 顺利完成后停在：

```
执行：…/.venv/bin/mineru-models-download -s huggingface -m all
```

长时间无任何回显——既看不到 tqdm 进度条，也无错误抛出，无法判断是“真的卡死”还是“在下只是没回声”。最终用户被迫盲等，或 `Ctrl-C` 后重试时担心丢失已下载的分片。

### 表因
- 终端无任何输出（无进度条、无 ETA、无 `Fetching ...` 日志）；
- `~/.cache/huggingface/hub/models--opendatalab--*` 目录的 mtime 仍在更新、`.locks/` 在写——**实际下载在进行**，但用户看不到；
- 默认 `-s huggingface` 在大陆从 `huggingface.co` 直拉 ~9GB，带宽通常 ≪ modelscope 国内 CDN，叠加“无回显”观感更强。

### 根因（两个独立维度同时退化）
1. **进度通道被 `capture_output=True` 吞没** — `_prefetch_mineru()` 中 `subprocess.run(cmd, capture_output=True, text=True)` 把子进程 stdout/stderr 全收进内存。huggingface_hub 内嵌的 tqdm 在检测到非 TTY 后自动降级为静默或极低频刷新，**视觉上等同卡死**；外加无 `timeout=` 参数，遇到 huggingface_hub TCP 静默断流（参见 [huggingface_hub#3580](https://github.com/huggingface/huggingface_hub/issues/3580)、[#4085](https://github.com/huggingface/huggingface_hub/issues/4085)）会无限期阻塞。
2. **传输源默认值在大陆带宽较差** — 默认硬编码 `-s huggingface`，未利用 MinerU 官方推荐的 `MINERU_MODEL_SOURCE=modelscope`（[官方文档](https://opendatalab.github.io/MinerU/usage/model_source/)）；modelscope 国内 CDN 带宽通常 10× 于直连 HF。

两个维度叠加：传输慢 → 等待时间长；进度通道哑 → 用户无从判断进度。任一维度单独存在都不至于“看似卡死”，组合则放大。

### 处理方式
- **`prefetch_models.py` 三点最小重写**（仅作用于 mineru 引擎，docling/marker 不变）：
  1. 移除 `capture_output=True`、`text=True`，让子进程 stdout/stderr 直接继承父进程终端，tqdm 即可正常实时渲染；
  2. 默认 `--mineru-source` 改为 `modelscope`，优先级 `CLI 参数 > MINERU_MODEL_SOURCE 环境变量 > 默认 modelscope`；命令行 `-s` 与环境变量双写以同时兼容老/新版 mineru CLI；
  3. 新增 `--mineru-timeout`（默认 1800 秒）；超时抛 `RuntimeError("mineru 模型下载超时（{}s）；可加大 --mineru-timeout 或切换 --mineru-source")`，由 `_dispatch` 收敛为 error 状态；保留 `_SkipEngine` 与 `shutil.which` 守门。
- **失败提示改写**：不再提供“末尾 5 行日志”——既然 stdout 已直通终端，错误信息改为引导用户“查看终端上方的 mineru-models-download 输出”，配 `returncode` 与生效 source 一并打印。
- **测试覆盖（新增/更新 6 条用例）**：默认 modelscope、CLI 覆盖源、环境变量优先级、TimeoutExpired → RuntimeError、白盒回归（`subprocess.run` kwargs 不含 `capture_output`/`stdout=PIPE`/`stderr=PIPE`）、CLI 选项透传到 `_dispatch`；新增 `_restore_mineru_source` autouse fixture 隔离环境污染。

### 后续防范
- **任何**内嵌 tqdm/进度条的子进程一律避免 `capture_output=True`/`stdout=PIPE`/`stderr=PIPE`——若真要采集日志，应使用 PTY (`pexpect` / `ptyprocess`) 或 `tee`，绝不可静默吞掉用户的进度反馈。
- **任何**下载类子进程必须显式带 `timeout=`，并将 `subprocess.TimeoutExpired` 转为可读 `RuntimeError`，避免上游 TCP 半断流时无限阻塞。
- 跨地域大体量模型下载，CLI 默认值应倾向于“目标用户群带宽更优”的源（本仓主要服务大陆开发者 → 默认 modelscope）；同时**始终**留出 `--source` 与环境变量两个出口，禁止把默认值锁死。
- Issue 排查时复用诊断三件套：`watch -n 5 'du -sh ~/.cache/huggingface/hub'` 看缓存增长、`pgrep -fl mineru-models-download` + `lsof -p <PID> | grep ESTABLISHED` 看 TCP 连接、`sudo nettop -p <PID> -P` 看实时带宽——三者综合可秒判“在下/卡死/已退出”。

### 同类问题影响与注意事项
- `_prefetch_docling()` 与 `_prefetch_marker()` 走的是 Python 函数调用（`DocumentConverter(...)` / `create_model_dict()`），不经过 `subprocess`，本次不受影响；但若未来引入新的子进程下载入口（如 paddle/easyocr 模型），**必须**照搬本规约（不捕获 stdout + 显式 timeout + 默认源覆盖）。
- modelscope 与 huggingface 在 `~/.cache` 下落点不同、不互通：切源会让已下载的 HF 副本变成沉默成本，但这是一次性代价；切源后通常十几分钟可补回。如海外环境下默认 modelscope 反而更慢，用户可显式 `--mineru-source huggingface` 或设环境变量回退。
- CI 环境是非 TTY，tqdm 在非 TTY 下会自动改为“按行输出”（每个 epoch/file 一行），不会刷屏；当前“零输出”反而更可疑——本次 stdout 直通的改动对 CI 友好。
- `--mineru-timeout` 默认 1800s 对家宽下载 ~9GB 偏紧（按 5MB/s 需 ~30 min 整）；modelscope 国内通常 ≫ 5MB/s 故已足够，但若部署在偏远节点请显式调大。

## [2026-04-24] parse_pdf_to_markdown Marker 引擎始终报 "daemonic processes are not allowed to have children"

### 问题描述
真实 PDF 处理日志中 Marker 工具每次都以 `daemonic processes are not allowed to have children` 失败退出；`layout_analysis / table_extraction / formula_extraction / code_detection` 四 Stage 的 Marker 竞争者全部失效，竞争模式不再具备对 Marker 的覆盖。

### 表因
`WARNING negentropy.perceives.pdf.engines.marker: Marker 转换失败: daemonic processes are not allowed to have children` 在 MCP server 每次处理 PDF 时都会出现。

### 根因
`EngineWorkerPool` 在 `EngineWorker.start()` 中用 `ctx.Process(..., daemon=True)` 启动子进程（`infra/engine_worker.py:106`）。Python 的硬性限制：**daemon 进程不能再派生自己的子进程**。而 Marker 内部依赖 torch `DataLoader` 的 `num_workers>0` 与 Surya OCR 的进程池，一旦需要派生子进程即抛 `AssertionError`。Docling / MinerU 目前走纯 Python 推理（或自带独立进程管理），因而表现正常。

### 处理方式
1. `infra/engine_worker.py:106` 将 `daemon=True` 改为 `daemon=False`，并在上方加 WHY 注释。
2. 在模块末尾新增 `_cleanup_on_exit()` + `atexit.register(_cleanup_on_exit)`：遍历 `_pool_singleton._workers`，对仍存活的 worker 依次 `terminate → join(0.5s) → kill → join(0.5s) → os.kill(SIGKILL)` 兜底强杀（解释器退出路径不可 `await`，全程同步且吞异常）。
3. 与 `apps/app.py:main()` 中既有的 `finally + atexit` 双路径互为防御，`_shutdown_engine_pool_sync()` 已有幂等 flag，无冲突。

### 后续防范
- 任何计划派生子进程的引擎（Marker 风格）都**必须**跑在 `daemon=False` 的 worker 上；如未来新增引擎，遵循本规约，不要回退到 daemon=True。
- `daemon=False` 后父进程异常退出会阻塞在子进程回收；`atexit` 兜底 + `apps/app.py` 生命周期 hook 必须同时存在，否则裸脚本/测试场景会出现孤儿进程。
- 单测 `tests/unit/test_engine_worker_daemon.py` 固化 `daemon=False` 与 `_cleanup_on_exit` 行为契约，防止回归。

### 同类问题影响与注意事项
- 子进程改为 non-daemon 后，若 `EngineWorker.terminate()` 路径异常早退，可能遗留 `proc` 存活；`_cleanup_on_exit` 是最后一道防线。若未来新增 worker 管理路径，复用 `_cleanup_on_exit` 模式即可。
- `pytest` 环境下使用 `_fake_fast` 引擎做 Pool 存活断言，避免真实 PDF 依赖；真实 Marker 可用性由集成测试或人工冒烟验证。

## [2026-04-24] parse_pdf_to_markdown 在 Apple Silicon 上 MPS 被误判不可用，Docling 回退 CPU

### 问题描述
`parse_pdf_to_markdown` 日志高频出现：
```
WARNING engine_worker.docling.utils.accelerator_utils:
  MPS is not available in the system. Fall back to 'CPU'.
```
Mac M 系列芯片虽然硬件与 PyTorch 均支持 MPS（`torch.backends.mps.is_built() == True`），但 Docling 的 `accelerator_utils` 检测依旧 `False`，整条推理管线降级 CPU，单次 37 页 PDF 的 Docling 推理从预期 <30s 膨胀到 >120s（layout/tables/formulas/code 四阶段各占满超时）。

### 表因
子进程内 `torch.backends.mps.is_available()` 首次调用返回 `False`；Docling 据此选择 CPU。

### 根因
**`multiprocessing` spawn 子进程内的 MPS 懒初始化缺口。** MPS 的统一内存 allocator 依赖 first-touch（首次真实分配一个 MPS tensor）才会就绪；而 `torch.backends.mps.is_available()` **自身不触发** first-touch。父进程虽已 `set_start_method('spawn')`，但 spawn 子进程是一个全新解释器，torch 在子进程里重新 `import` 后就必须再做一次 first-touch，否则 `is_available()` 会稳定返回 False。Docling 的内部设备探测跑在 worker 子进程中，恰好踩进这个缺口。

### 处理方式
1. **`infra/_engine_worker_entry.py` 新增 `_preinit_torch_device(logger)`**，`worker_main` 在子进程启动、`conn.send(ready)` 之后、首次 `call` 之前调用，仅对 `docling/mineru/marker` 三类真实 torch 引擎执行：
   - `os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")`：算子 fallback 兜底，不禁用 MPS；
   - 采集 `torch_version / start_method / mps_built / mps_available_raw`，darwin + mps_built 时执行 `torch.zeros(1, device="mps")` 作为 first-touch smoke_test；
   - 结果写入 `NEGENTROPY_MPS_READY=1/0` 环境变量，供下游 `hardware.detection._check_mps_available` 免再探测直接信任；
   - `logger.warning("子进程 torch 诊断 %s", diag)` 以 WARNING 级输出单行诊断（包含 smoke_test 结果、版本、`is_available_raw` 的首次返回值），无论成功失败都可在线上日志一眼排查。
2. **`pdf/hardware/detection.py::_check_mps_available` 防御性兜底**：`is_available()=False` 时先读 `NEGENTROPY_MPS_READY==1`，有则直接走“可用”分支；否则尝试一次 first-touch 再复查，彻底堵住“worker 内已 ok 但 Docling 子模块二次探测再次失败”的回归可能。
3. **单元测试 `tests/unit/test_mps_subprocess.py`** 8 条：torch 缺失、smoke_test ok / fail / skip（未 built）、非 darwin 跳过、默认 `PYTORCH_ENABLE_MPS_FALLBACK=1`、以及 darwin-only 真实环境断言 `READY ∈ {0,1}`，全部通过。

### 后续防范
- 任何在 spawn 子进程内依赖 torch 硬件的引擎都**必须**在 `worker_main` 的早期窗口显式 first-touch 一次设备，不能信任 `is_available()` 的首次返回。
- `_preinit_torch_device` 必须保持“永不抛异常”的契约：任何路径失败都静默降级到 `NEGENTROPY_MPS_READY=0`，避免连 worker 本身都起不来；失败原因写进诊断日志即可。
- Docling / MinerU / Marker 之外如新增真实 torch 引擎，`worker_main` 的 `engine_name in (...)` 白名单必须同步更新。

### 同类问题影响与注意事项
- CUDA 子进程无类似缺口（CUDA 初始化走 cudaInit 常规路径，不依赖 first-touch），但 XPU（Intel oneAPI）未来接入时建议同样跑一次 `torch.zeros(1, device="xpu")` first-touch 兜底。
- `PYTORCH_ENABLE_MPS_FALLBACK=1` 仅作为“少数算子不支持 MPS 时回 CPU”的兜底，**不会**整体禁用 MPS；若后续出现算子回 CPU 但整体仍过慢，需对 Docling 个别算子做 profile，而不是误以为 fallback 本身是问题。
- 若在 Intel Mac 上运行（`mps_built=False`），`smoke_test=skip:mps_not_built`、`NEGENTROPY_MPS_READY=0`，Docling 正确降级 CPU，无任何回归。

## [2026-04-24] parse_pdf_to_markdown 四个 Stage 重复调用 Docling convert，单 PDF 耗时 >250s

### 问题描述
37 页 PDF 经 `parse_pdf_to_markdown` 总耗时约 **249 秒**，日志显示 Docling 在 `layout_analysis → table_extraction → code_detection → formula_extraction` 四个 Stage 中**各完整跑了一次推理**，分别触发 120s / 75s / 30s / 126s 的 Stage 超时。

### 表因
`StageScheduler` 在 4 个 Stage 分别调用 `get_engine_pool().run("docling", method="convert", ...)`，每一次都是一次完整的 Docling DocumentConverter 推理（layout + TableFormer + 公式 + 代码一起算）。

### 根因
`EngineWorkerPool` 只复用 worker 进程与模型权重，**不缓存 `convert()` 的返回值**。而 Docling 的 `DoclingConversionResult` 已一次性聚合全部四类信息（tables / formulas / code / layout），上层 Stage 只是各取所需一个字段——但必须重跑整条管线。

### 处理方式
- **`infra/_engine_worker_entry.py` 新增 `_ConvertCache` + `_pdf_fingerprint` + `_make_cache_key`**：
  - 子进程内 LRU(capacity=4) + TTL(300s) 缓存，仅对 `docling/mineru` 白名单引擎的 `method="convert"` 生效；
  - 键 = `(engine_name, size + mtime_ns + blake2b(head_64KB), page_range, embed_images, init_kwargs_hash)`，覆盖 PDF 内容/时间/切片/选项/初始化参数五个维度；
  - 读前 64KB 算指纹，常见 PDF I/O <1ms；业务层覆盖写必改 mtime 自动失效；
  - `result is None` 不入缓存以便下次重试（对齐引擎“不可用/转换失败”语义）。
- **`worker_main` 缓存查询点**：call 分支按“load engine → cache.get → miss 时执行 → cache.put → send”调用路径织入，对上层调用协议完全透明（Stage 代码不改一行）。
- **竞争模式 / 并行度保持**：scheduler 的“4 工具并行”一字未动；docling/mineru/marker/pymupdf 仍并行，但 docling 与 mineru 在首个 Stage 之后的 3 次 convert 直接命中缓存，耗时 <1ms。
- **新增 `tests/unit/test_convert_cache.py` 24 条**覆盖指纹、键构造、LRU、TTL、Stage 重放、PDF 内容变更失效、白名单契约；全部通过。

### 后续防范
- 任何“全流程推理 → 多字段消费”的引擎（未来可能的 `sycamore / nougat / pix2text` 等）如想接入 `EngineWorkerPool`，其 `convert()` 只要保持“**纯函数 + 不可变返回值**”语义就能白盒接入本缓存，仅需在 `_CACHEABLE_ENGINES` 中补白名单。
- 同时缓存**多** PDF 时 capacity=4 是“4 Stage + 1 备用”的粗估；长跑场景若观察到 cache-thrashing（eviction 频繁），可以把 capacity 上调到 8~16，TTL 维持 5min 防止长 lived worker RSS 膨胀。
- Marker 因其内部 DataLoader 与显存占用叠加后风险偏高，暂**不**接入缓存；若后续证明必要，再单独评估。

### 同类问题影响与注意事项
- 缓存键**不可漏掉** `init_kwargs_hash`：否则同一 PDF 用不同 `DoclingEngine(...)` 配置会错误复用旧结果；已在 `_make_cache_key` 中显式纳入键。
- Pipeline 未来若引入“编辑/标注后重算”场景，务必通过 `mtime_ns` 自动失效（`os.utime` 或覆盖写）；切勿人为旁路缓存键，否则引入 stale 风险。
- 读前 64KB 指纹对“在 64KB 之后篡改内容但保留头部 + 同 size + 同 mtime_ns”的攻击向量是**不设防**的；本项目语境下 PDF 来源可信，但如未来引入不可信 PDF 来源，应改为全文件 blake2b。

## [2026-04-24] parse_pdf_to_markdown 图片提取阶段逐页串行、37 页耗时 ~15s

### 问题描述
同一份 37 页 PDF 在 `image_extraction` Stage 中提取 18 张图片耗时约 **15 秒**，日志每秒打印一条 `Extracted image img_*_...`，明显是“逐页 → 逐图”的串行流。

### 表因
`pipeline/stages/pdf/image_extraction.py` 的 `FitzImageExtractor._run` 原本：
```python
doc = fitz.open(pdf_path)
for page_idx in range(start_page, end_page):
    page_images = await processor.extract_images_from_pdf_page(doc, page_idx)
    ...
doc.close()
```
所有页共享同一个 `fitz.Document`，且没有任何并发包装，等同于 `O(pages)` 串行。

### 根因
- PyMuPDF 官方 FAQ 明确指出 `Document` 对象**非线程/非重入安全**（同一 Document 并行访问会触发 SIGSEGV 或数据损坏）<sup>[[1]](#ref-pymupdf-thread)</sup>，因此不能用 `asyncio.to_thread` 把同一 Document 丢进线程池；
- 但 `fitz.open()` 本身是 <10ms 的轻量操作，完全可以“每页一个独立 Document”，再通过 `asyncio.gather + Semaphore(4)` 限制同时打开的文件句柄。

### 处理方式
- **`image_extraction.py` 重写 `_run`**：
  1. 先一次性 `with fitz.open(pdf_path) as probe_doc:` 读取 `page_count`，保证“探测”与“抽取”阶段隔离；
  2. 为每一页协程 `_extract_one_page(page_idx)` 内部独立 `fitz.open()` + `EnhancedPDFProcessor()`，抽取完立即 `doc.close()`；
  3. `asyncio.Semaphore(4)` 限制同时在跑的页数，避免 37 页 PDF 打开 37 个 fitz 句柄；
  4. `asyncio.gather(*(_extract_one_page(p) for p in range(start, end)))` 并行触发；
  5. `metadata` 追加 `concurrency` 与 `page_count`，便于线上排查；
  6. `page_range=(5, 5)` 等空区间返回空列表，不再触发 gather 空参数。
- **`tests/unit/test_image_extraction_concurrency.py` 新增 7 条**：全量页抽取、Semaphore 限流峰值 ≤4、墙钟优于串行基线 60%、`page_range` 尊重、空区间、异常透传、`bbox` 缺省。全部通过。

### 后续防范
- 任何基于 PyMuPDF 的并发路径都必须遵循“**每协程独立 Document**”约束，不要试图在 `asyncio.to_thread` / `ThreadPoolExecutor` 中共享 `fitz.Document`；否则测试环境可能偶发通过，生产 workload 下 SIGSEGV 概率线性上升。
- `_IMAGE_EXTRACT_CONCURRENCY = 4` 与 `docling/mineru` 竞争的 Pool 并发度对齐；若未来出现“CPU 打满但 I/O 闲置”现象，再单独调参。
- 上一版本依赖全局 `doc` 在 `extract_images_from_pdf_page` 中回看 cross-page 信息（例如 caption 在相邻页）的代码**必须**走独立通道（例如把 `text_blocks` 预先计算好作为参数传入），否则并发路径无法感知跨页上下文。

### 同类问题影响与注意事项
- 其他 `PyMuPDF` 绑定 Stage（如 `text_extraction`、`extract_tables_with_geometry`）若也观察到单页耗时线性 × 页数、且 workload profile 显示 CPU 闲置，可沿用同一“每页 open + Semaphore 限流 + gather”方案；注意 Semaphore 上限要与全局 `engine_pool` 并发度协调，避免压爆系统句柄。
- 并发化后 `logger.info("Extracted image ... from page N")` 的打印顺序不再与页号递增对齐。线上排查若依赖顺序关系，请以 `page_number` 字段为准，不要以日志顺序推断页号。

<a id="ref-pymupdf-thread"></a>[1] Artifex Software, "PyMuPDF FAQ: Is PyMuPDF thread-safe?," *PyMuPDF Documentation*, 2025. [Online]. Available: https://pymupdf.readthedocs.io/en/latest/faq.html#is-pymupdf-thread-safe
