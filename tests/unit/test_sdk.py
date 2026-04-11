"""Python SDK tests for the negentropy-perceives facade."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from negentropy.perceives.sdk import (
    NegentropyPerceivesClient,
    NegentropyPerceivesConnectionError,
    NegentropyPerceivesToolError,
)


class TestNegentropyPerceivesClient:
    """测试 negentropy-perceives Python SDK。"""

    @pytest.mark.asyncio
    async def test_connect_and_close(self):
        """connect/close 应委托给底层 FastMCP Client。"""
        with (
            patch("negentropy.perceives.sdk.StreamableHttpTransport") as transport_cls,
            patch("negentropy.perceives.sdk.Client") as client_cls,
        ):
            mock_client = AsyncMock()
            client_cls.return_value = mock_client

            client = NegentropyPerceivesClient("http://localhost:8081/mcp")
            await client.connect()
            await client.close()

            transport_cls.assert_called_once_with(
                url="http://localhost:8081/mcp", headers=None, auth=None
            )
            mock_client.__aenter__.assert_awaited_once()
            mock_client.__aexit__.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_call_tool_delegates(self):
        """call_tool 应透传工具名和参数。"""
        with patch("negentropy.perceives.sdk.StreamableHttpTransport"), patch(
            "negentropy.perceives.sdk.Client"
        ) as client_cls:
            mock_client = AsyncMock()
            mock_client.call_tool = AsyncMock(return_value={"success": True})
            client_cls.return_value = mock_client

            client = NegentropyPerceivesClient()
            result = await client.call_tool("scrape_webpage", {"url": "https://a.com"})

            assert result == {"success": True}
            mock_client.__aenter__.assert_awaited_once()
            mock_client.call_tool.assert_awaited_once_with(
                "scrape_webpage",
                {"url": "https://a.com"},
                timeout=None,
                raise_on_error=True,
                meta=None,
            )

    @pytest.mark.asyncio
    async def test_scrape_webpage_helper(self):
        """快捷方法应调用统一的 call_tool 接口。"""
        with patch.object(
            NegentropyPerceivesClient,
            "call_tool",
            new_callable=AsyncMock,
            return_value={"success": True},
        ) as mock_call_tool:
            client = NegentropyPerceivesClient()
            result = await client.scrape_webpage(
                url="https://example.com",
                method="simple",
                extract_config={"title": "h1"},
                wait_for_element="body",
            )

            assert result == {"success": True}
            mock_call_tool.assert_awaited_once_with(
                "scrape_webpage",
                {
                    "url": "https://example.com",
                    "method": "simple",
                    "extract_config": {"title": "h1"},
                    "wait_for_element": "body",
                },
            )

    @pytest.mark.asyncio
    async def test_list_tools_returns_server_tools(self):
        """list_tools 应返回底层 Client 的结果。"""
        with patch("negentropy.perceives.sdk.StreamableHttpTransport"), patch(
            "negentropy.perceives.sdk.Client"
        ) as client_cls:
            tool = SimpleNamespace(name="scrape_webpage")
            mock_client = AsyncMock()
            mock_client.list_tools = AsyncMock(return_value=[tool])
            client_cls.return_value = mock_client

            client = NegentropyPerceivesClient()
            tools = await client.list_tools()

            assert tools == [tool]

    @pytest.mark.asyncio
    async def test_connect_wraps_connection_errors(self):
        """连接错误应映射为项目异常。"""
        with patch("negentropy.perceives.sdk.StreamableHttpTransport"), patch(
            "negentropy.perceives.sdk.Client"
        ) as client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.side_effect = RuntimeError("boom")
            client_cls.return_value = mock_client

            client = NegentropyPerceivesClient()
            with pytest.raises(NegentropyPerceivesConnectionError):
                await client.connect()

    @pytest.mark.asyncio
    async def test_call_tool_wraps_tool_errors(self):
        """工具调用错误应映射为项目异常。"""
        with patch("negentropy.perceives.sdk.StreamableHttpTransport"), patch(
            "negentropy.perceives.sdk.Client"
        ) as client_cls:
            mock_client = AsyncMock()
            mock_client.call_tool = AsyncMock(side_effect=RuntimeError("boom"))
            client_cls.return_value = mock_client

            client = NegentropyPerceivesClient()
            with pytest.raises(NegentropyPerceivesToolError):
                await client.call_tool("scrape_webpage")
