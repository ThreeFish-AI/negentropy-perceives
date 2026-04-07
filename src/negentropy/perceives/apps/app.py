"""FastMCP application entry point for Negentropy Perceives."""

import argparse
import logging
import sys
from pathlib import Path

import yaml

from ..config import (
    _get_user_config_path,
    _load_bundled_yaml,
    describe_config_sources,
    reload_settings,
    settings,
)
from .._logging import build_uvicorn_log_config, setup_logging

logger = logging.getLogger(__name__)


def _active_cli_name() -> str:
    """Return the current CLI executable name for user-facing diagnostics."""
    argv0 = sys.argv[0] if sys.argv else "negentropy-perceives"
    return Path(argv0).name or "negentropy-perceives"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。

    Args:
        argv: 参数列表，默认使用 sys.argv[1:]

    Returns:
        解析后的参数命名空间
    """
    parser = argparse.ArgumentParser(
        prog="negentropy-perceives",
        description="Negentropy Perceives MCP Server — 商业级 Web 内容与 PDF 提取服务",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=None,
        metavar="PATH",
        help="指定自定义 YAML 配置文件路径（优先级高于用户配置）",
    )
    parser.add_argument(
        "--init-config",
        action="store_true",
        default=False,
        help="将默认配置复制到用户配置目录后退出",
    )
    return parser.parse_args(argv)


def _ensure_user_config() -> None:
    """确保用户配置文件存在，首次运行时从内置默认复制。

    若 ~/.negentropy/perceives.config.yaml 不存在，则从内置默认配置
    生成一份副本供用户修改。
    """
    user_path = _get_user_config_path()
    if user_path.exists():
        return

    try:
        bundled_dict = _load_bundled_yaml()
        user_path.parent.mkdir(parents=True, exist_ok=True)
        with user_path.open("w", encoding="utf-8") as f:
            yaml.dump(
                bundled_dict,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
        logger.info("已生成用户配置文件: %s", user_path)
    except OSError as exc:
        logger.warning("无法创建用户配置文件 %s: %s", user_path, exc)


def main(argv: list[str] | None = None) -> None:
    """Run the MCP server."""
    # ── 步骤 0：解析 CLI 参数 ──
    args = _parse_args(argv)

    # --init-config 模式：生成配置文件后退出
    if args.init_config:
        _ensure_user_config()
        print(f"用户配置已生成至: {_get_user_config_path()}")
        sys.exit(0)

    # ── 步骤 1：构建配置（必须在其他操作之前） ──
    reload_settings(config_path=args.config)
    _ensure_user_config()

    # ── 步骤 2：初始化日志体系（必须在导入 tools 之前） ──
    setup_logging(settings.log_level)

    # ── 步骤 3：延迟导入 tools（触发 @app.tool 注册，此时 logger 已就绪） ──
    from ..tools import app  # noqa: E402

    cli_name = _active_cli_name()
    logger.info("Starting %s v%s", settings.server_name, settings.server_version)
    logger.info("CLI entrypoint: %s", cli_name)
    logger.info("Transport mode: %s", settings.transport_mode)
    logger.info(
        "JavaScript support: %s",
        "Enabled" if settings.enable_javascript else "Disabled",
    )
    logger.info(
        "Random User-Agent: %s",
        "Enabled" if settings.use_random_user_agent else "Disabled",
    )
    logger.info("Proxy: %s", "Enabled" if settings.use_proxy else "Disabled")
    logger.info(
        "Resolved settings: server_name=%s, host=%s, port=%s, path=%s",
        settings.server_name,
        settings.http_host,
        settings.http_port,
        settings.http_path,
    )
    logger.info("Config sources: %s", describe_config_sources())

    if settings.transport_mode in ["http", "sse"]:
        transport_type = "HTTP" if settings.transport_mode == "http" else "SSE"
        binding_host = settings.http_host
        binding_port = settings.http_port
        binding_path = settings.http_path

        if binding_host == "0.0.0.0":  # nosec B104
            logger.info(
                "Starting %s server on %s:%s",
                transport_type,
                binding_host,
                binding_port,
            )
            logger.info(
                "Local endpoint: http://localhost:%s%s", binding_port, binding_path
            )
            logger.info(
                "Network endpoint: http://%s:%s%s",
                binding_host,
                binding_port,
                binding_path,
            )
        else:
            logger.info(
                "Starting %s server on %s:%s",
                transport_type,
                binding_host,
                binding_port,
            )
            endpoint_url = f"http://{binding_host}:{binding_port}{binding_path}"
            logger.info("%s endpoint: %s", transport_type, endpoint_url)

        logger.info("CORS origins: %s", settings.http_cors_origins)

        # ── 步骤 4：构建 Uvicorn 日志配置并启动 ──
        uvicorn_log_config = build_uvicorn_log_config(settings.log_level)

        app.run(
            transport=settings.transport_mode,
            host=binding_host,
            port=binding_port,
            path=binding_path,
            uvicorn_config={
                "log_config": uvicorn_log_config,
                "timeout_graceful_shutdown": 5,
            },
        )
    else:
        logger.info("Starting STDIO server")
        app.run()


if __name__ == "__main__":
    main()
