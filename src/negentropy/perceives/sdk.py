"""Python SDK facade for the Negentropy Perceives MCP service."""

from __future__ import annotations

from typing import Any

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


class NegentropyPerceivesError(Exception):
    """Base exception for Python SDK failures."""


class NegentropyPerceivesConnectionError(NegentropyPerceivesError):
    """Raised when the SDK cannot establish or maintain a client session."""


class NegentropyPerceivesToolError(NegentropyPerceivesError):
    """Raised when a tool invocation fails."""


# 默认端点地址（与服务端配置默认值一致：http_host=localhost, http_port=8081, http_path=/mcp）
DEFAULT_BASE_URL = "http://localhost:8081/mcp"


class NegentropyPerceivesClient:
    """High-level async SDK for calling the negentropy-perceives MCP service."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        headers: dict[str, str] | None = None,
        auth: Any = None,
        timeout: float | int | None = None,
        client_name: str = "negentropy-perceives-sdk",
    ) -> None:
        self.base_url = base_url
        self._transport = StreamableHttpTransport(
            url=base_url,
            headers=headers,
            auth=auth,
        )
        self._client = Client(
            self._transport,
            name=client_name,
            timeout=timeout,
        )
        self._connected = False

    async def __aenter__(self) -> "NegentropyPerceivesClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def connect(self) -> None:
        """Connect to the remote MCP service."""
        if self._connected:
            return
        try:
            await self._client.__aenter__()
            self._connected = True
        except Exception as exc:  # pragma: no cover - delegated to FastMCP
            raise NegentropyPerceivesConnectionError(
                f"Failed to connect to negentropy-perceives service at {self.base_url}"
            ) from exc

    async def close(self) -> None:
        """Close the underlying FastMCP client."""
        if not self._connected:
            return
        try:
            await self._client.__aexit__(None, None, None)
        finally:
            self._connected = False

    async def list_tools(self) -> list[Any]:
        """List server tools after ensuring the client session is active."""
        await self.connect()
        try:
            return await self._client.list_tools()
        except Exception as exc:  # pragma: no cover - delegated to FastMCP
            raise NegentropyPerceivesConnectionError(
                "Failed to list tools from negentropy-perceives service"
            ) from exc

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        *,
        timeout: float | int | None = None,
        raise_on_error: bool = True,
        meta: dict[str, Any] | None = None,
    ) -> Any:
        """Call an arbitrary MCP tool through the project SDK."""
        await self.connect()
        try:
            return await self._client.call_tool(
                name,
                arguments or {},
                timeout=timeout,
                raise_on_error=raise_on_error,
                meta=meta,
            )
        except Exception as exc:  # pragma: no cover - delegated to FastMCP
            raise NegentropyPerceivesToolError(
                f"Tool '{name}' failed on negentropy-perceives service"
            ) from exc

    async def scrape_webpage(
        self,
        *,
        url: str,
        method: str = "auto",
        extract_config: dict[str, Any] | None = None,
        wait_for_element: str | None = None,
    ) -> Any:
        """Typed convenience wrapper for scrape_webpage."""
        return await self.call_tool(
            "scrape_webpage",
            {
                "url": url,
                "method": method,
                "extract_config": extract_config,
                "wait_for_element": wait_for_element,
            },
        )

    async def convert_webpage_to_markdown(
        self,
        *,
        url: str,
        method: str = "auto",
        extract_main_content: bool = True,
        embed_images: bool = False,
    ) -> Any:
        """Typed convenience wrapper for convert_webpage_to_markdown."""
        return await self.call_tool(
            "convert_webpage_to_markdown",
            {
                "url": url,
                "method": method,
                "extract_main_content": extract_main_content,
                "embed_images": embed_images,
            },
        )
