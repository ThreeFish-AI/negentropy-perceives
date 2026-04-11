"""图片嵌入模块：将 Markdown 中引用的远程图片转换为 data URI。"""

import base64
import logging
import mimetypes
import re
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)


def embed_images_in_markdown(
    markdown_content: str,
    *,
    max_images: int = 50,
    max_bytes_per_image: int = 2_000_000,
    timeout_seconds: int = 10,
) -> Dict[str, Any]:
    """Embed remote images referenced in Markdown as data URIs."""
    try:
        pattern = re.compile(r"!\[(.*?)\]\((.*?)\)")

        embedded_count = 0
        attempted = 0
        skipped_large = 0
        skipped_errors = 0

        def replacer(match: re.Match) -> str:
            nonlocal embedded_count, attempted, skipped_large, skipped_errors
            if embedded_count >= max_images:
                return match.group(0)

            alt_text = match.group(1)
            image_url = match.group(2)

            attempted += 1

            try:
                resp = requests.get(image_url, timeout=timeout_seconds, stream=True)
                resp.raise_for_status()

                content_type = resp.headers.get("Content-Type", "")
                if not content_type.startswith("image/"):
                    guessed, _ = mimetypes.guess_type(image_url)
                    if not (guessed and guessed.startswith("image/")):
                        return match.group(0)
                    content_type = guessed

                # Guard by Content-Length if present
                length_header = resp.headers.get("Content-Length")
                if length_header is not None:
                    try:
                        content_length = int(length_header)
                        if content_length > max_bytes_per_image:
                            skipped_large += 1
                            return match.group(0)
                    except (ValueError, TypeError):
                        # Invalid Content-Length header, continue processing
                        pass

                content = resp.content
                if len(content) > max_bytes_per_image:
                    skipped_large += 1
                    return match.group(0)

                b64 = base64.b64encode(content).decode("ascii")
                data_uri = f"data:{content_type};base64,{b64}"
                embedded_count += 1
                return f"![{alt_text}]({data_uri})"
            except Exception:
                skipped_errors += 1
                return match.group(0)

        new_md = pattern.sub(replacer, markdown_content)

        return {
            "markdown": new_md,
            "stats": {
                "attempted": attempted,
                "embedded": embedded_count,
                "skipped_large": skipped_large,
                "skipped_errors": skipped_errors,
                "max_images": max_images,
                "max_bytes_per_image": max_bytes_per_image,
            },
        }
    except Exception as e:
        logger.warning(f"Error embedding images: {str(e)}")
        return {
            "markdown": markdown_content,
            "stats": {
                "attempted": 0,
                "embedded": 0,
                "skipped_large": 0,
                "skipped_errors": 1,
            },
        }
