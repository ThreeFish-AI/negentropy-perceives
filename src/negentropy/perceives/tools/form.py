"""Form interaction MCP tools."""

import logging
from typing import Annotated, Any, Dict, Optional

from pydantic import Field

import time

from ..infra import rate_limiter
from ..schemas import ScrapeResponse
from ..scraping import FormHandler, playwright_session, selenium_session
from ._registry import BrowserMethod, app, validate_url

logger = logging.getLogger(__name__)


@app.tool()
async def fill_and_submit_form(
    url: Annotated[
        str,
        Field(
            ...,
            description="包含表单的网页 URL，必须包含协议前缀（http:// 或 https://）",
        ),
    ],
    form_data: Annotated[
        Dict[str, Any],
        Field(
            ...,
            description="""表单字段数据，格式为{"选择器": "值"}，支持各种表单元素。
                示例：{"#username": "admin", "input[name=password]": "secret", "select[name=country]": "US", "input[type=checkbox]": True}""",
        ),
    ],
    submit: Annotated[bool, Field(default=False, description="是否提交表单")],
    submit_button_selector: Annotated[
        Optional[str],
        Field(
            default=None,
            description="""提交按钮的CSS选择器，如未指定则尝试自动查找。
                示例："button[type=submit]"、"#submit-btn\"""",
        ),
    ],
    method: Annotated[
        BrowserMethod,
        Field(
            default="selenium",
            description="""自动化方法选择，可选值：
                "selenium"（使用Selenium WebDriver）、
                "playwright"（使用Playwright浏览器自动化）""",
        ),
    ],
    wait_for_element: Annotated[
        Optional[str],
        Field(
            default=None,
            description="""表单填写前等待加载的元素CSS选择器。
                示例：".form-container"、"#login-form\"""",
        ),
    ],
) -> ScrapeResponse:
    """
    Fill and optionally submit a form on a webpage.

    This tool can handle various form elements including:
    - Text inputs
    - Checkboxes and radio buttons
    - Dropdown selects
    - File uploads
    - Form submission

    Useful for interacting with search forms, contact forms, login forms, etc.

    Returns:
        ScrapeResponse object containing success status, form interaction results, and optional submission response.
        Supports complex form automation workflows.
    """
    method_key = f"form_{method}"
    _start = time.time()
    try:
        # Validate inputs
        url_error = validate_url(url)
        if url_error:
            return ScrapeResponse(
                success=False,
                url=url,
                method=method,
                error=url_error,
            )

        logger.info(f"Form interaction for: {url}")

        # Apply rate limiting
        await rate_limiter.wait()

        # Setup browser based on method
        if method == "selenium":
            with selenium_session(url, wait_for_element=wait_for_element) as driver:
                form_handler = FormHandler(driver)
                result = await form_handler.fill_form(
                    form_data=form_data,
                    submit=submit,
                    submit_button_selector=submit_button_selector,
                )
                final_url = driver.current_url
                final_title = driver.title

        elif method == "playwright":
            async with playwright_session(
                url, wait_for_element=wait_for_element
            ) as page:
                form_handler = FormHandler(page)
                result = await form_handler.fill_form(
                    form_data=form_data,
                    submit=submit,
                    submit_button_selector=submit_button_selector,
                )
                final_url = page.url
                final_title = await page.title()

        if result.get("success"):
            return ScrapeResponse(
                success=True,
                url=url,
                method=method_key,
                data={
                    "form_results": result,
                    "final_url": final_url,
                    "final_title": final_title,
                    "original_url": url,
                },
            )
        else:
            return ScrapeResponse(
                success=False,
                url=url,
                method=method_key,
                error=result.get("error", "Form interaction failed"),
            )

    except Exception as e:
        logger.error(f"Error in form interaction for {url}: {str(e)}")
        return ScrapeResponse(
            success=False,
            url=url,
            method=method_key,
            error=str(e),
        )
