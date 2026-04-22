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
