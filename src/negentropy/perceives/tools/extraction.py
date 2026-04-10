"""Data extraction MCP tools (links, page info, structured data)."""

import logging
from typing import Annotated, List, Optional
from urllib.parse import urlparse

from pydantic import Field

from ..schemas import (
    LinkItem,
    LinksResponse,
    PageInfoResponse,
)
from ._registry import app, validate_url, web_scraper

logger = logging.getLogger(__name__)


@app.tool()
async def extract_links(
    url: Annotated[
        str,
        Field(
            ...,
            description="""目标网页 URL，必须包含协议前缀（http://或https://），将从此页面提取所有链接。
                支持 http 和 https 协议的有效 URL 格式""",
        ),
    ],
    filter_domains: Annotated[
        Optional[List[str]],
        Field(
            default=None,
            description="""白名单域名列表，仅包含这些域名的链接。设置后只返回指定域名的链接。
                示例：["example.com", "subdomain.example.com", "blog.example.org"]""",
        ),
    ],
    exclude_domains: Annotated[
        Optional[List[str]],
        Field(
            default=None,
            description="""黑名单域名列表，排除这些域名的链接。用于过滤广告、跟踪器等不需要的外部链接。
                示例：["ads.com", "tracker.net", "analytics.google.com"]""",
        ),
    ],
    internal_only: Annotated[
        bool,
        Field(
            default=False,
            description="是否仅提取内部链接（同域名链接）。设为 True 时只返回与源页面相同域名的链接，忽略所有外部链接",
        ),
    ],
) -> LinksResponse:
    """
    Extract all links from a webpage.

    This tool is specialized for link extraction and can filter links by domain,
    extract only internal links, or exclude specific domains.

    Returns:
        LinksResponse object containing success status, extracted links list, and optional filtering statistics.
        Each link includes url, text, and additional attributes if available.
    """
    try:
        # Validate inputs
        url_error = validate_url(url)
        if url_error:
            raise ValueError(url_error)

        logger.info(f"Extracting links from: {url}")

        # Scrape the page to get links
        scrape_result = await web_scraper.scrape_url(
            url=url,
            method="simple",
        )

        if "error" in scrape_result:
            return LinksResponse(
                success=False,
                url=url,
                total_links=0,
                links=[],
                internal_links_count=0,
                external_links_count=0,
                error=scrape_result["error"],
            )

        # Extract and filter links
        all_links = scrape_result.get("content", {}).get("links", [])
        base_domain = urlparse(url).netloc

        filtered_links = []
        for link in all_links:
            link_url = link.get("url", "")
            if not link_url:
                continue

            link_domain = urlparse(link_url).netloc

            # Apply filters
            if internal_only and link_domain != base_domain:
                continue

            if filter_domains and link_domain not in filter_domains:
                continue

            if exclude_domains and link_domain in exclude_domains:
                continue

            filtered_links.append(
                LinkItem(
                    url=link_url,
                    text=link.get("text", "").strip(),
                    is_internal=link_domain == base_domain,
                )
            )

        internal_count = sum(1 for link in filtered_links if link.is_internal)
        external_count = len(filtered_links) - internal_count

        return LinksResponse(
            success=True,
            url=url,
            total_links=len(filtered_links),
            links=filtered_links,
            internal_links_count=internal_count,
            external_links_count=external_count,
        )

    except Exception as e:
        logger.error(f"Error extracting links from {url}: {str(e)}")
        return LinksResponse(
            success=False,
            url=url,
            total_links=0,
            links=[],
            internal_links_count=0,
            external_links_count=0,
            error=str(e),
        )


@app.tool()
async def get_page_info(
    url: Annotated[
        str,
        Field(
            ...,
            description="""目标网页 URL，必须包含协议前缀（http://或https://），用于获取页面基础信息和元数据。
                这是一个轻量级工具，不会提取完整页面内容""",
        ),
    ],
) -> PageInfoResponse:
    """
    Get basic information about a webpage (title, description, status).

    This is a lightweight tool for quickly checking page accessibility and
    getting basic metadata without full content extraction.

    Returns:
        PageInfoResponse object containing success status, URL, status_code, title, meta_description, and domain.
        Useful for quick page validation and metadata extraction.
    """
    try:
        # Validate inputs
        url_error = validate_url(url)
        if url_error:
            raise ValueError(url_error)

        logger.info(f"Getting page info for: {url}")

        # Use simple scraper for quick info
        result = await web_scraper.http_scraper.scrape(url, extract_config={})

        if "error" in result:
            return PageInfoResponse(
                success=False, url=url, status_code=0, error=result["error"]
            )

        return PageInfoResponse(
            success=True,
            url=result.get("url", url),
            title=result.get("title"),
            description=result.get("meta_description"),
            status_code=result.get("status_code", 200),
            content_type=result.get("content_type"),
            content_length=result.get("content_length"),
        )

    except Exception as e:
        logger.error(f"Error getting page info for {url}: {str(e)}")
        return PageInfoResponse(success=False, url=url, status_code=0, error=str(e))
