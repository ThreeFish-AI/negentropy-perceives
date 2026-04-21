"""HTML 预处理模块：清理、内容区域提取、URL 归一化。"""

import logging
import re
from typing import Dict, Optional

from bs4 import BeautifulSoup, Comment
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


def preprocess_html(html_content: str, base_url: Optional[str] = None) -> str:
    """
    Preprocess HTML content before MarkItDown conversion.

    Args:
        html_content: Raw HTML content
        base_url: Base URL for resolving relative URLs

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

        for pattern in unwanted_patterns:
            for element in soup.find_all(class_=pattern):
                if id(element) not in protected_ids:
                    element.decompose()
            for element in soup.find_all(id=pattern):
                if id(element) not in protected_ids:
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
