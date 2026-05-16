"""HTML 预处理模块：清理、内容区域提取、URL 归一化。"""

import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
from urllib.parse import parse_qs, unquote, urljoin, urlparse

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 图片尺寸占位符登记簿
#
# 解决方案核心：MarkItDown/markdownify 永远把 <img> 转成 ![alt](src)，
# 硬性丢弃 width/height/style，导致下游渲染器把图片放到最大。我们在
# preprocess_html 阶段把带尺寸的 <img> 替换为纯字母数字 sentinel
# NavigableString 节点，让 markdownify 把它当成普通文本透传，再由
# MarkdownFormatter 在 _basic_cleanup 之后还原为内嵌 HTML <img> 标签。
#
# sentinel 使用全字母数字（[A-Za-z0-9]+），不命中 markdownify 默认
# 启用的 escape_asterisks/escape_underscores 字符集（``*_[]\&<`[>~=+|``），
# 保证字面量穿透。
# ---------------------------------------------------------------------------

SENTINEL_PREFIX = "XIMGPLACEHOLDER"
SENTINEL_SUFFIX = "ENDX"
SENTINEL_RE = re.compile(rf"{SENTINEL_PREFIX}[0-9a-f]{{32}}{SENTINEL_SUFFIX}")


@dataclass
class ImgDimensionRegistry:
    """图片占位符登记簿：sentinel → 原始 <img> 元信息。

    在 ``preprocess_html`` 中由调用方实例化并以关键字参数传入，
    遍历 ``<img>`` 时为每张带尺寸的图片登记并返回 sentinel；后续在
    ``MarkdownFormatter`` 还原阶段读取 ``placeholders`` 重建 HTML。
    """

    placeholders: Dict[str, Dict[str, Optional[str]]] = field(default_factory=dict)

    def issue(
        self,
        *,
        src: str,
        alt: str,
        width: Optional[str],
        height: Optional[str],
        title: str = "",
    ) -> str:
        """登记一条图片元信息并返回 sentinel 字符串。"""
        sentinel = f"{SENTINEL_PREFIX}{uuid.uuid4().hex}{SENTINEL_SUFFIX}"
        self.placeholders[sentinel] = {
            "src": src,
            "alt": alt,
            "width": width,
            "height": height,
            "title": title,
        }
        return sentinel


# 尺寸解析正则
_PURE_NUM_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*$")
_PX_VALUE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*px\b", re.IGNORECASE)
_STYLE_WIDTH_RE = re.compile(r"(?:^|;)\s*width\s*:\s*([^;]+)", re.IGNORECASE)
_STYLE_HEIGHT_RE = re.compile(r"(?:^|;)\s*height\s*:\s*([^;]+)", re.IGNORECASE)


def _parse_dim(value: Optional[str]) -> Optional[str]:
    """解析单一尺寸值，返回整数像素字符串或 None。

    支持的输入：
        ``"100"``、``"100px"``、``" 100 px "`` → ``"100"``

    忽略（返回 None）：
        ``"100%"``、``"auto"``、``"0"``、``"3em"``、``"50vw"``、空串、None
    """
    if not value or not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw or raw.lower() in ("auto", "0", "inherit", "initial", "unset"):
        return None
    if raw.endswith("%"):
        return None
    m = _PURE_NUM_RE.match(raw)
    if m:
        n = float(m.group(1))
        return str(int(n)) if n > 0 else None
    m = _PX_VALUE_RE.search(raw)
    if m:
        n = float(m.group(1))
        return str(int(n)) if n > 0 else None
    return None


def _extract_img_dimensions(img: Tag) -> Tuple[Optional[str], Optional[str]]:
    """从 ``<img>`` 标签提取 width/height。

    优先级：``style`` 内的 ``width:Xpx`` > ``width`` 属性（height 同理）。
    与 W3C CSS 计算值优先级一致——内联 style 覆盖 HTML presentational 属性。
    """
    style = img.get("style", "")
    style_w = style_h = None
    if isinstance(style, str) and style:
        sw_match = _STYLE_WIDTH_RE.search(style)
        if sw_match:
            style_w = _parse_dim(sw_match.group(1))
        sh_match = _STYLE_HEIGHT_RE.search(style)
        if sh_match:
            style_h = _parse_dim(sh_match.group(1))
    attr_w_val = img.get("width")
    attr_h_val = img.get("height")
    attr_w = _parse_dim(attr_w_val if isinstance(attr_w_val, str) else None)
    attr_h = _parse_dim(attr_h_val if isinstance(attr_h_val, str) else None)
    return (style_w or attr_w, style_h or attr_h)


def _register_img_placeholders(
    soup: BeautifulSoup, registry: ImgDimensionRegistry
) -> None:
    """遍历 ``<img>``：对带尺寸的图片登记 sentinel 并替换原节点。

    无可解析尺寸的图片保留原 ``<img>`` 节点，走默认 ``![alt](src)`` 路径。
    必须在 ``_convert_media_elements``（懒加载/srcset/Next.js 解析）之后、
    在 ``preprocess_html`` 剥离 ``class``/``style`` 之前调用。
    """
    for img in list(soup.find_all("img")):
        src_val = img.get("src", "")
        if not isinstance(src_val, str) or not src_val.strip():
            continue
        if _is_placeholder_src(src_val):
            continue
        width, height = _extract_img_dimensions(img)
        if not width and not height:
            continue
        alt_val = img.get("alt", "")
        title_val = img.get("title", "")
        sentinel = registry.issue(
            src=src_val,
            alt=alt_val if isinstance(alt_val, str) else "",
            width=width,
            height=height,
            title=title_val if isinstance(title_val, str) else "",
        )
        img.replace_with(NavigableString(sentinel))


def preprocess_html(
    html_content: str,
    base_url: Optional[str] = None,
    *,
    img_registry: Optional[ImgDimensionRegistry] = None,
) -> str:
    """
    Preprocess HTML content before MarkItDown conversion.

    Args:
        html_content: Raw HTML content
        base_url: Base URL for resolving relative URLs
        img_registry: 可选的图片尺寸登记簿。若提供，则对带 width/height
            的 <img> 标签注入 sentinel 占位符，由调用方在 Markdown 后处理
            阶段还原为内嵌 HTML <img>，从而保留源页面尺寸信息。

    Returns:
        Preprocessed HTML content
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")

        # 收集 <pre>/<code>/<samp> 元素及其所有后代的引用，
        # 确保代码内容在清理阶段不被意外删除
        protected_ids: set = set()
        for pre in soup.find_all(["pre", "code", "samp"]):
            protected_ids.add(id(pre))
            for descendant in pre.descendants:
                protected_ids.add(id(descendant))

        # Remove comments
        comments = soup.find_all(string=lambda text: isinstance(text, Comment))
        for comment in comments:
            comment.extract()

        # Preserve math elements (MathJax, KaTeX, MathML) BEFORE removing scripts
        _preserve_math_elements(soup)

        # 将非 Markdown 友好的媒体元素转换为可转换形式
        # 必须在 unwanted_tags/unwanted_patterns 移除之前执行
        _convert_media_elements(soup, base_url)

        # 登记带尺寸的 <img>：必须在 style 剥离之前执行，否则 style 中的
        # 尺寸信息会丢失。无尺寸的图片保留 <img> 节点走默认 ![alt](src) 路径。
        if img_registry is not None:
            _register_img_placeholders(soup, img_registry)

        # Remove unwanted elements that typically don't contain main content
        unwanted_tags = [
            "script",
            "style",
            "nav",
            "header",
            "footer",
            "aside",
            "advertisement",
            "ads",
        ]
        for tag in unwanted_tags:
            for element in soup.find_all(tag):
                if id(element) not in protected_ids:
                    element.decompose()

        # Remove elements with specific classes/ids commonly used for ads/navigation
        # 使用词边界约束防止误匹配 CSS Module 哈希和复合词（如 reading 中的 ad）
        unwanted_patterns = [
            re.compile(
                r"(?<![a-zA-Z0-9])"
                r"(?:ad(?:s)?|advertisement|sidebar|nav|menu)"
                r"(?![a-zA-Z0-9])",
                re.I,
            ),
            re.compile(
                r".*(newsletter|subscribe|subscription|signup|sign-up|mailing-list).*",
                re.I,
            ),
            re.compile(r".*(social|share|sharing-widget|share-buttons).*", re.I),
            re.compile(r".*(cookie|consent|gdpr|cookie-banner).*", re.I),
            re.compile(r".*(copy-button|copy-btn|clipboard|code-toolbar).*", re.I),
            re.compile(r".*(carousel|slider|gallery|swiper|slick).*", re.I),
            re.compile(r".*(tooltip|popover|modal|dialog|overlay|toast).*", re.I),
        ]

        # 含正文媒体的容器（carousel/gallery 等常被文章用作媒体展示）需
        # 被保护，不能整个移除——否则会丢失图片/视频等内容元素。
        def _has_content_media(el) -> bool:
            try:
                return bool(el.find(["img", "figure", "picture", "video", "audio"]))
            except Exception:
                return False

        for pattern in unwanted_patterns:
            for element in soup.find_all(class_=pattern):
                if id(element) in protected_ids:
                    continue
                if _has_content_media(element):
                    continue
                element.decompose()
            for element in soup.find_all(id=pattern):
                if id(element) in protected_ids:
                    continue
                if _has_content_media(element):
                    continue
                element.decompose()

        # 移除无内容价值的交互元素
        for element in soup.find_all(["button", "noscript"]):
            if id(element) not in protected_ids:
                element.decompose()

        # 移除不含 <text> 的内联 SVG 图标（保留含文字的 SVG 图表）
        for svg in soup.find_all("svg"):
            if id(svg) not in protected_ids and not svg.find("text"):
                svg.decompose()

        # 剥离所有剩余元素的 class 和 style 属性（对 Markdown 输出无语义价值）
        for element in soup.find_all(True):
            if id(element) not in protected_ids:
                element.attrs.pop("class", None)
                element.attrs.pop("style", None)

        # 确保块级元素之间有换行，以便 MarkItDown 正确识别段落边界。
        # MarkItDown 在无空白分隔的连续 <p> 标签间会将内容合并为同一行。
        _ensure_block_whitespace(soup)

        # Convert relative URLs to absolute if base_url is provided
        if base_url:
            # Convert relative links
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                if isinstance(href, str) and not href.startswith(
                    ("http://", "https://")
                ):
                    link["href"] = urljoin(base_url, href)

            # Convert relative image sources
            for img in soup.find_all("img", src=True):
                src = img.get("src", "")
                if isinstance(src, str) and not src.startswith(("http://", "https://")):
                    img["src"] = urljoin(base_url, src)

        return str(soup)

    except Exception as e:
        logger.warning(f"Error preprocessing HTML: {str(e)}")
        return html_content


_BLOCK_TAGS = frozenset(
    [
        "p",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "blockquote",
        "pre",
        "ul",
        "ol",
        "table",
        "hr",
        "section",
        "article",
        "figure",
        "figcaption",
        "details",
    ]
)


def _ensure_block_whitespace(soup: BeautifulSoup) -> None:
    """在块级元素之间插入换行符，确保 MarkItDown 能正确识别段落边界。

    MarkItDown 在处理 ``<p>A</p><p>B</p>`` 这种无空白分隔的 HTML 时，
    会将内容合并为 ``A B``（单行）。通过在块级闭合标签后插入 ``\\n``，
    使其输出为独立段落。
    """
    for tag_name in _BLOCK_TAGS:
        for element in soup.find_all(tag_name):
            # 在元素后插入换行（如果后继不是已有空白）
            next_sib = element.next_sibling
            if next_sib is None:
                continue
            if isinstance(next_sib, str) and next_sib.strip() == "":
                continue
            element.insert_after("\n")


def extract_content_area(html_content: str) -> str:
    """
    Extract the main content area from HTML, removing navigation, ads, etc.

    Args:
        html_content: HTML content

    Returns:
        HTML content with main content area only
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")

        # Try to find main content area using common selectors
        content_selectors = [
            "main",
            '[role="main"]',
            "article",
            ".content",
            ".post",
            ".entry",
            ".article",
            "#content",
            "#main",
            ".main-content",
            ".post-content",
            ".entry-content",
            ".article-content",
        ]

        main_content = None
        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
                for element in elements:
                    text_length = len(element.get_text(strip=True))
                    if text_length > 10:
                        main_content = element
                        break
                if main_content:
                    break

        # If no main content area found, use the body
        if not main_content:
            main_content = soup.find("body") or soup

        return str(main_content)

    except Exception as e:
        logger.warning(f"Error extracting content area: {str(e)}")
        return html_content


def fallback_html_conversion(html_content: str) -> str:
    """Fallback HTML conversion when MarkItDown fails.

    Preserves table structures by converting them to markdown before
    stripping HTML tags.
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")

        # Remove unwanted elements
        for tag in soup.find_all(["script", "style", "nav", "header", "footer"]):
            tag.decompose()

        # Convert <table> elements to markdown BEFORE stripping HTML
        for table_tag in soup.find_all("table"):
            md_table = _html_table_to_markdown(table_tag)
            if md_table:
                table_tag.replace_with(f"\n\n{md_table}\n\n")

        # Simple conversion logic
        text_content = soup.get_text()

        # Basic markdown formatting
        lines = text_content.split("\n")
        markdown_lines = []

        for line in lines:
            line = line.strip()
            if line:
                markdown_lines.append(line)

        return "\n\n".join(markdown_lines)

    except Exception as e:
        logger.warning(f"Fallback conversion failed: {str(e)}")
        return f"Conversion failed: {str(e)}"


def _html_table_to_markdown(table_tag) -> Optional[str]:
    """Convert a BeautifulSoup <table> element to markdown table format.

    Args:
        table_tag: BeautifulSoup Tag for <table>

    Returns:
        Markdown table string, or None if table has no meaningful content
    """
    try:
        rows = []
        for tr in table_tag.find_all("tr"):
            cells = []
            for cell in tr.find_all(["th", "td"]):
                cell_text = cell.get_text(strip=True).replace("|", "\\|")
                cells.append(cell_text)
            if cells:
                rows.append(cells)

        if len(rows) < 2:
            return None

        # Normalize column count
        max_cols = max(len(row) for row in rows)
        for row in rows:
            while len(row) < max_cols:
                row.append("")

        # Build markdown
        md_lines = []
        # Header row
        md_lines.append("| " + " | ".join(rows[0]) + " |")
        # Separator
        md_lines.append("| " + " | ".join(["---"] * max_cols) + " |")
        # Data rows
        for row in rows[1:]:
            md_lines.append("| " + " | ".join(row) + " |")

        return "\n".join(md_lines)

    except Exception:
        return None


def _heuristic_split_paragraphs(text: str) -> list:
    """Split text into paragraphs using heuristics when double-newlines are absent."""
    lines = text.split("\n")
    paragraphs = []
    current: list[str] = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            # Empty line = explicit paragraph break
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue

        current.append(stripped)

        # Check if this line ends a paragraph
        if i < len(lines) - 1:
            next_stripped = lines[i + 1].strip()
            if next_stripped and stripped[-1] in ".?!:" and next_stripped[0].isupper():
                paragraphs.append(" ".join(current))
                current = []

    if current:
        paragraphs.append(" ".join(current))

    return paragraphs if len(paragraphs) > 1 else [text.strip()]


def _match_image_to_paragraph(paragraph: str, img_alt: str) -> bool:
    """Check if an image is contextually related to a paragraph via alt text."""
    if not img_alt or not paragraph:
        return False
    # Normalize for comparison
    alt_lower = img_alt.lower().strip()
    para_lower = paragraph.lower()
    # Skip generic alt texts
    if alt_lower in ("", "image", "img", "photo", "picture", "icon", "logo"):
        return False
    return alt_lower in para_lower


def build_html_from_text(text_content: str, title: str, content_data: Dict) -> str:
    """Build basic HTML structure from text content.

    Images are distributed proportionally among paragraphs to approximate
    the original document layout, rather than being appended at the end.
    """
    try:
        html_parts = ["<html><head>"]
        if title:
            html_parts.append(f"<title>{title}</title>")
        html_parts.append("</head><body>")

        # Add main text content
        html_parts.append("<div class='main-content'>")

        # Split text into paragraphs
        paragraphs = [p.strip() for p in text_content.split("\n\n") if p.strip()]

        # Fallback: if text has no double-newlines, use heuristics
        if len(paragraphs) <= 1 and len(text_content) > 200:
            paragraphs = _heuristic_split_paragraphs(text_content)

        images = content_data.get("images", [])[:20]
        num_images = len(images)
        num_paragraphs = len(paragraphs)

        # First pass: try to match images to paragraphs by alt text
        alt_matched: dict = {}  # img_index -> paragraph_index
        matched_img_indices: set = set()
        if images and paragraphs:
            for img_idx, img in enumerate(images):
                img_alt = img.get("alt", "")
                for para_idx, paragraph in enumerate(paragraphs):
                    if _match_image_to_paragraph(paragraph, img_alt):
                        alt_matched[img_idx] = para_idx
                        matched_img_indices.add(img_idx)
                        break

        # Second pass: distribute remaining images proportionally
        unmatched_images = [
            i for i in range(num_images) if i not in matched_img_indices
        ]
        proportional: dict = {}  # paragraph_index -> [img_indices]
        if unmatched_images and num_paragraphs > 0:
            for seq, img_idx in enumerate(unmatched_images):
                # Distribute evenly: place after paragraph at proportional position
                para_idx = min(
                    (seq + 1) * num_paragraphs // (len(unmatched_images) + 1),
                    num_paragraphs - 1,
                )
                proportional.setdefault(para_idx, []).append(img_idx)

        # Build a combined schedule: paragraph_index -> [img_indices to place after]
        placement: dict = {}
        for img_idx, para_idx in alt_matched.items():
            placement.setdefault(para_idx, []).append(img_idx)
        for para_idx, img_indices in proportional.items():
            placement.setdefault(para_idx, []).extend(img_indices)

        # Emit paragraphs with interleaved images
        for i, paragraph in enumerate(paragraphs):
            if paragraph:
                html_parts.append(f"<p>{paragraph}</p>")
            # Place images scheduled for after this paragraph
            if i in placement:
                for img_idx in placement[i]:
                    img = images[img_idx]
                    img_src = img.get("src", "")
                    img_alt = img.get("alt", "")
                    html_parts.append(f"<img src='{img_src}' alt='{img_alt}'>")

        # Handle edge case: images without any paragraphs
        if images and not paragraphs:
            for img in images:
                img_src = img.get("src", "")
                img_alt = img.get("alt", "")
                html_parts.append(f"<img src='{img_src}' alt='{img_alt}'>")

        html_parts.append("</div>")

        # Add links if available
        links = content_data.get("links", [])
        if links:
            html_parts.append("<div class='links'>")
            for link in links[:50]:
                link_url = link.get("url", "")
                link_text = link.get("text", link_url)
                html_parts.append(f"<a href='{link_url}'>{link_text}</a><br>")
            html_parts.append("</div>")

        html_parts.append("</body></html>")
        return "\n".join(html_parts)

    except Exception as e:
        logger.warning(f"Error building HTML from text: {str(e)}")
        return f"<html><body><p>{text_content}</p></body></html>"


def _preserve_math_elements(soup: BeautifulSoup) -> None:
    """保护 HTML 中的数学元素，将其转换为 LaTeX 文本以避免被清理掉。

    支持：
    - MathJax: ``<script type="math/tex">`` → 提取 LaTeX 源码
    - MathJax 渲染输出: ``.MathJax`` 容器 → 从 annotation 提取 LaTeX
    - KaTeX: ``.katex`` 容器 → 从 annotation 提取 LaTeX
    - MathML: ``<math>`` 标签 → 从 annotation 提取 LaTeX，否则保留
    """
    # 1. MathJax <script type="math/tex"> 或 <script type="math/tex; mode=display">
    for script in soup.find_all("script", type=re.compile(r"math/tex")):
        latex = script.string or ""
        latex = latex.strip()
        if not latex:
            continue
        script_type = script.get("type", "")
        if "display" in script_type:  # type: ignore[operator]
            replacement = soup.new_tag("span")
            replacement.string = f"$${latex}$$"
        else:
            replacement = soup.new_tag("span")
            replacement.string = f"${latex}$"
        script.replace_with(replacement)

    # 2. MathJax 渲染容器 (.MathJax, .MathJax_Display, .MathJax_Preview)
    for container in soup.find_all(class_=re.compile(r"MathJax")):
        latex = _extract_latex_from_annotation(container)  # type: ignore[assignment]
        if latex:
            replacement = soup.new_tag("span")
            # 判断是否为 display 模式
            classes = container.get("class", [])  # type: ignore[arg-type]
            is_display = any("Display" in c or "display" in c for c in classes)  # type: ignore[union-attr]
            if is_display:
                replacement.string = f"$${latex}$$"
            else:
                replacement.string = f"${latex}$"
            container.replace_with(replacement)

    # 3. KaTeX 容器 (.katex, .katex-display)
    for container in soup.find_all(class_=re.compile(r"katex")):
        latex = _extract_latex_from_annotation(container)  # type: ignore[assignment]
        if latex:
            replacement = soup.new_tag("span")
            classes = container.get("class", [])  # type: ignore[arg-type]
            is_display = any("display" in c for c in classes)  # type: ignore[union-attr]
            if is_display:
                replacement.string = f"$${latex}$$"
            else:
                replacement.string = f"${latex}$"
            container.replace_with(replacement)

    # 4. MathML <math> 标签
    for math_elem in soup.find_all("math"):
        latex = _extract_latex_from_annotation(math_elem)  # type: ignore[assignment]
        if latex:
            replacement = soup.new_tag("span")
            display = math_elem.get("display", "")  # type: ignore[assignment]
            if display == "block":
                replacement.string = f"$${latex}$$"
            else:
                replacement.string = f"${latex}$"
            math_elem.replace_with(replacement)


def _extract_latex_from_annotation(element) -> Optional[str]:  # noqa: ANN001
    """从 MathML/MathJax/KaTeX 容器中提取 LaTeX annotation。

    查找 ``<annotation encoding="application/x-tex">`` 或
    ``<annotation encoding="application/x-latex">`` 元素。
    """
    if element is None:
        return None

    # 查找 annotation 元素
    for annotation in element.find_all("annotation"):
        encoding = annotation.get("encoding", "")
        if "tex" in encoding.lower() or "latex" in encoding.lower():
            latex = annotation.string
            if latex:
                return latex.strip()

    return None


# ---------------------------------------------------------------------------
# 媒体元素转换（Phase 2）
# ---------------------------------------------------------------------------

# iframe 嵌入视频平台 URL 匹配模式
_IFRAME_VIDEO_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # YouTube: youtube.com/embed/VIDEO_ID
    (
        re.compile(r"https?://(?:www\.)?youtube\.com/embed/([A-Za-z0-9_-]{11})", re.I),
        "https://www.youtube.com/watch?v={id}",
    ),
    # YouTube Shorts: youtube.com/shorts/VIDEO_ID
    (
        re.compile(r"https?://(?:www\.)?youtube\.com/shorts/([A-Za-z0-9_-]{11})", re.I),
        "https://www.youtube.com/watch?v={id}",
    ),
    # youtu.be 短链接
    (
        re.compile(r"https?://youtu\.be/([A-Za-z0-9_-]{11})", re.I),
        "https://www.youtube.com/watch?v={id}",
    ),
    # Vimeo: player.vimeo.com/video/VIDEO_ID
    (
        re.compile(r"https?://player\.vimeo\.com/video/(\d+)", re.I),
        "https://vimeo.com/{id}",
    ),
    # Bilibili: player.bilibili.com/player.html?bvid=BV...
    (
        re.compile(
            r"https?://player\.bilibili\.com/player\.html\?.*bvid=(BV[A-Za-z0-9]+)",
            re.I,
        ),
        "https://www.bilibili.com/video/{id}",
    ),
    # Bilibili: player.bilibili.com/player.html?aid=...
    (
        re.compile(
            r"https?://player\.bilibili\.com/player\.html\?.*aid=(\d+)",
            re.I,
        ),
        "https://www.bilibili.com/video/av{id}",
    ),
    # Bilibili: www.bilibili.com/video/BV...
    (
        re.compile(r"https?://(?:www\.)?bilibili\.com/video/(BV[A-Za-z0-9]+)", re.I),
        "https://www.bilibili.com/video/{id}",
    ),
    # Bilibili: www.bilibili.com/video/av...
    (
        re.compile(r"https?://(?:www\.)?bilibili\.com/video/av(\d+)", re.I),
        "https://www.bilibili.com/video/av{id}",
    ),
]

# Next.js 图片优化代理 URL 匹配
_NEXTJS_IMAGE_RE = re.compile(r"/_next/image\b")

# 常见占位符 src（透明 gif / 占位 svg / about:blank）
_PLACEHOLDER_SRC_RE = re.compile(
    r"^(data:image/(?:gif|svg\+xml);base64,|data:image/svg\+xml,|about:blank)",
    re.IGNORECASE,
)


def _is_placeholder_src(src: object) -> bool:
    """判断 img src 是否为占位符/缺失（触发懒加载属性兜底）。

    未设置（``None``）与空字符串均视为占位，以覆盖 ``srcset-only`` 写法。
    """
    if src is None:
        return True
    if not isinstance(src, str):
        return False
    s = src.strip()
    if not s:
        return True
    return bool(_PLACEHOLDER_SRC_RE.match(s))


def _resolve_iframe_video_url(src: str) -> Optional[str]:
    """识别 iframe 嵌入的视频平台 URL，返回可访问的播放页链接。"""
    for pattern, template in _IFRAME_VIDEO_PATTERNS:
        match = pattern.search(src)
        if match:
            return template.format(id=match.group(1))
    return None


def _resolve_nextjs_image_url(url: str, base_url: Optional[str] = None) -> str:
    """将 Next.js 图片优化代理 URL 解析为真实 CDN URL。

    ``/_next/image?url=<encoded_url>&w=<width>&q=<quality>`` → 真实 CDN URL。
    相对路径代理 URL 会使用 base_url 解析。
    """
    if not _NEXTJS_IMAGE_RE.search(url):
        return url

    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    real_url = qs.get("url", [None])[0]
    if not real_url:
        return url

    real_url = unquote(real_url)

    if base_url and not real_url.startswith(("http://", "https://", "data:")):
        real_url = urljoin(base_url, real_url)

    return real_url


def _pick_best_srcset_url(srcset: str) -> Optional[str]:
    """从 srcset 属性值中选取最高分辨率的图片 URL。

    srcset 格式：``url1 1x, url2 2x, url3 3x`` 或 ``url1 100w, url2 200w``。
    选取描述符数值最大的 URL。
    """
    if not srcset:
        return None

    best_url: Optional[str] = None
    best_density: float = 0

    for entry in srcset.split(","):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split()
        if not parts:
            continue

        url = parts[0]
        descriptor = parts[1] if len(parts) > 1 else "1x"

        try:
            if descriptor.endswith("x"):
                density = float(descriptor.rstrip("x"))
            elif descriptor.endswith("w"):
                density = float(descriptor.rstrip("w")) / 1000.0  # 归一化
            else:
                density = 1.0
        except (ValueError, TypeError):
            density = 1.0

        if density >= best_density:
            best_density = density
            best_url = url

    return best_url


def _convert_media_elements(
    soup: BeautifulSoup, base_url: Optional[str] = None
) -> None:
    """将非 Markdown 友好的媒体元素转换为可转换的等价形式。

    必须在 unwanted_tags/unwanted_patterns 移除之前调用，
    否则媒体元素可能因父容器被删除而丢失。
    """
    # ── 1. <video> → <a> 链接 ──────────────────────────────────────
    for video in soup.find_all("video"):
        video_url: Optional[str] = video.get("src")  # type: ignore[assignment]
        if not video_url:
            source_tag = video.find("source")
            if source_tag:
                video_url = source_tag.get("src")  # type: ignore[assignment]
        if not video_url or not isinstance(video_url, str):
            video.decompose()
            continue

        if base_url and not video_url.startswith(("http://", "https://")):
            video_url = urljoin(base_url, video_url)

        parts: list[str] = []
        poster = video.get("poster")  # type: ignore[assignment]
        if (
            poster
            and isinstance(poster, str)
            and base_url
            and not poster.startswith(("http://", "https://", "data:"))
        ):
            poster = urljoin(base_url, poster)
        if poster and isinstance(poster, str):
            poster_img = soup.new_tag("img", src=poster, alt="[视频封面]")
            parts.append(str(poster_img))

        link = soup.new_tag("a", href=video_url)
        link.string = "[视频]"
        parts.append(str(link))

        video.replace_with(BeautifulSoup(" ".join(parts), "html.parser"))

    # ── 2. <audio> → <a> 链接 ──────────────────────────────────────
    for audio in soup.find_all("audio"):
        audio_url = audio.get("src")  # type: ignore[assignment]
        if not audio_url:
            source_tag = audio.find("source")
            if source_tag:
                audio_url = source_tag.get("src")  # type: ignore[assignment]
        if not audio_url or not isinstance(audio_url, str):
            audio.decompose()
            continue

        if base_url and not audio_url.startswith(("http://", "https://")):
            audio_url = urljoin(base_url, audio_url)

        link = soup.new_tag("a", href=audio_url)
        link.string = "[音频]"
        audio.replace_with(link)

    # ── 3. <iframe> 视频 → <a> 链接 ────────────────────────────────
    for iframe in soup.find_all("iframe"):
        src = iframe.get("src", "")  # type: ignore[assignment]
        if not src or not isinstance(src, str):
            iframe.decompose()
            continue

        watch_url = _resolve_iframe_video_url(src)
        if watch_url:
            link = soup.new_tag("a", href=watch_url)
            link.string = "[视频]"
            iframe.replace_with(link)
        # 非视频 iframe（如地图、表单等）保留原样，由后续流程处理

    # ── 4. <embed> 视频 → <a> 链接 ────────────────────────────────
    for embed in soup.find_all("embed"):
        embed_src = embed.get("src", "")  # type: ignore[assignment]
        embed_type = embed.get("type", "")  # type: ignore[assignment]
        if not embed_src or not isinstance(embed_src, str):
            embed.decompose()
            continue
        etype = embed_type.lower() if isinstance(embed_type, str) else ""
        if "video/" in etype or embed_src.endswith(
            (".mp4", ".webm", ".ogg", ".avi", ".mov")
        ):
            if base_url and not embed_src.startswith(("http://", "https://")):
                embed_src = urljoin(base_url, embed_src)
            link = soup.new_tag("a", href=embed_src)
            link.string = "[视频]"
            embed.replace_with(link)
        # 非视频 embed（如 PDF）保留原样

    # ── 5. <object> 视频 → <a> 链接 ───────────────────────────────
    for obj in soup.find_all("object"):
        data_url = obj.get("data", "")  # type: ignore[assignment]
        obj_type = obj.get("type", "")  # type: ignore[assignment]
        if not data_url or not isinstance(data_url, str):
            obj.decompose()
            continue
        otype = obj_type.lower() if isinstance(obj_type, str) else ""
        if "video/" in otype or data_url.endswith(
            (".mp4", ".webm", ".ogg", ".avi", ".mov")
        ):
            if base_url and not data_url.startswith(("http://", "https://")):
                data_url = urljoin(base_url, data_url)
            link = soup.new_tag("a", href=data_url)
            link.string = "[视频]"
            obj.replace_with(link)
        # 非视频 object 保留原样

    # ── 6. <img> 归一化：懒加载 + srcset + Next.js 代理解析 ───────
    _LAZY_SRC_ATTRS = (
        "data-src",
        "data-original",
        "data-lazy-src",
        "data-url",
        "data-srcset",
    )
    for img in soup.find_all("img"):
        # 6a. 懒加载兜底：src 为空/占位符时迁移 data-* 真实 URL
        if _is_placeholder_src(img.get("src")):
            for attr in _LAZY_SRC_ATTRS:
                lazy = img.get(attr)
                if isinstance(lazy, str) and lazy.strip():
                    if attr == "data-srcset":
                        best_lazy = _pick_best_srcset_url(lazy)
                        if best_lazy:
                            img["src"] = best_lazy
                            break
                    else:
                        img["src"] = lazy.strip()
                        break

        # 6b. 仍无 src 但有 srcset：从 srcset 选最佳回填
        if _is_placeholder_src(img.get("src")):
            srcset_val = img.get("srcset", "")
            if isinstance(srcset_val, str) and srcset_val:
                best = _pick_best_srcset_url(srcset_val)
                if best:
                    img["src"] = best

        # 6c. src 中的 Next.js 代理 → 真实 CDN URL
        src = img.get("src", "")  # type: ignore[assignment]
        if src and isinstance(src, str) and _NEXTJS_IMAGE_RE.search(src):
            img["src"] = _resolve_nextjs_image_url(src, base_url)

        # 6d. srcset 中的 Next.js 代理：选最佳 URL 解析后回写到 src
        srcset = img.get("srcset", "")  # type: ignore[assignment]
        if srcset and isinstance(srcset, str) and _NEXTJS_IMAGE_RE.search(srcset):
            best = _pick_best_srcset_url(srcset)
            if best:
                img["src"] = _resolve_nextjs_image_url(best, base_url)

    # ── 7. <picture> 元素展平 ─────────────────────────────────────
    for picture in soup.find_all("picture"):
        best_url: Optional[str] = None

        for source in picture.find_all("source"):
            srcset = source.get("srcset", "")  # type: ignore[assignment]
            if srcset and isinstance(srcset, str):
                best_url = _pick_best_srcset_url(srcset)
                if best_url:
                    break
            src = source.get("src", "")  # type: ignore[assignment]
            if src and isinstance(src, str) and not best_url:
                best_url = src

        child_img = picture.find("img")
        if child_img:
            if best_url:
                child_img["src"] = best_url
            picture.replace_with(child_img)
        elif best_url:
            replacement = soup.new_tag("img", src=best_url)
            picture.replace_with(replacement)
        # else: 无子 img 也无可用 URL，保留原 picture（后续由 _basic_cleanup 清除）
