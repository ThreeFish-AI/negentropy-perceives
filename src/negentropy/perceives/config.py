"""Negentropy Perceives MCP Server 配置管理模块。

基于 pydantic-settings 的分层配置系统，按优先级从低到高：
1. 内置默认配置（config.default.yaml，打包在 wheel 内）
2. 用户 YAML 配置（~/.negentropy/perceives.config.yaml）
3. 环境变量（NEGENTROPY_PERCEIVES_ 前缀）
4. -c/--config 显式配置（最高优先级，通过构造函数传入）

config.default.yaml 为所有配置的单一事实默认值源。
Python Field 定义仅作为安全回退（fallback）。
"""

from __future__ import annotations

import logging
import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, InitSettingsSource, PydanticBaseSettingsSource

from . import __version__

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 项目根目录定位
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


# ---------------------------------------------------------------------------
# Deep Merge 工具函数
# ---------------------------------------------------------------------------


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """递归深度合并两个字典。

    合并规则：
    - 标量值：override 覆盖 base
    - 嵌套字典：递归合并（非整体替换）
    - 列表值：override 完整替换 base
    - override 中值为 None 的键：跳过（保留 base 原值）

    Args:
        base: 底层字典（低优先级）
        override: 覆盖字典（高优先级）

    Returns:
        合并后的新字典
    """
    result = base.copy()
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        elif value is not None:
            result[key] = value
    return result


# ---------------------------------------------------------------------------
# YAML 配置加载
# ---------------------------------------------------------------------------


def _load_bundled_yaml() -> Dict[str, Any]:
    """加载内置默认 YAML 配置（打包在 wheel 内）。

    作为所有配置的基线默认值源，与用户 YAML 进行深度合并后参与运行时解析。
    同时也用于 --init-config 复制和文档参考。

    Returns:
        解析后的配置字典

    Raises:
        FileNotFoundError: 内置配置文件缺失
        yaml.YAMLError: YAML 格式错误
    """
    from importlib import resources

    bundled_path = resources.files(__package__).joinpath("config.default.yaml")
    if not bundled_path.is_file():
        raise FileNotFoundError(
            f"Bundled config not found: {bundled_path}. "
            "Ensure config.default.yaml is included in package_data."
        )
    with bundled_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _get_user_config_path() -> Path:
    """获取用户配置文件的标准路径。

    Returns:
        用户配置文件路径：~/.negentropy/perceives.config.yaml
    """
    return Path.home() / ".negentropy" / "perceives.config.yaml"


def _load_yaml_file(path: Path) -> Optional[Dict[str, Any]]:
    """安全加载 YAML 文件。

    Args:
        path: YAML 文件路径

    Returns:
        解析后的字典，或 None（文件不存在时）
    """
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError) as exc:
        logger.warning("加载配置文件失败 %s: %s", path, exc)
        return None


# ---------------------------------------------------------------------------
# 用户 YAML 配置数据存储（供自定义 SettingsSource 读取）
# ---------------------------------------------------------------------------

# 模块级缓存：用户 YAML 配置数据（不含 bundled 默认值）
_user_yaml_data: Dict[str, Any] = {}

# CLI 覆盖路径缓存（由 reload_settings 设置）
_config_path_override: Optional[str] = None


class _UserYamlConfigSource(PydanticBaseSettingsSource):
    """自定义配置源：将合并后的 YAML 配置数据注入 pydantic-settings 优先级链。

    包含内置默认（config.default.yaml）与用户 YAML 深度合并后的完整配置。
    环境变量可正确覆盖所有 YAML 配置的字段。

    优先级位置（靠前者优先级更高）：init_settings(-c) > env_settings > _UserYamlConfigSource(YAML)
    即：-c 显式配置 > 环境变量 > 合并后的 YAML 配置

    注意：__call__() 返回空字典，实际字段值通过 get_field_value() 逐字段提供。
    这确保 pydantic-settings 会继续查询后续源以获取更低优先级的值（作为回退）。
    """

    def __call__(self) -> Dict[str, Any]:
        """返回空字典，强制 pydantic-settings 使用 get_field_value() 进行逐字段查询。"""
        return {}

    def get_field_value(
        self,
        field: Any,
        field_name: str,
    ) -> tuple[Any, str | None, bool]:
        """从用户 YAML 数据中获取字段值。

        仅当字段在用户 YAML 中显式定义时返回值，
        否则返回 None 以允许后续源（环境变量）提供该字段的值。

        Returns:
            (field_value, field_key_name, is_complex)
        """
        if field_name in _user_yaml_data:
            return _user_yaml_data[field_name], field_name, False
        return None, None, False


# ---------------------------------------------------------------------------
# 配置发现与合并（核心编排逻辑）
# ---------------------------------------------------------------------------


def _prepare_user_yaml(
    *,
    config_path: Optional[str] = None,
) -> Dict[str, Any]:
    """加载并合并配置：内置默认 ← 用户 YAML（深度合并）。

    优先级：config.default.yaml(低) < 用户 YAML(高)
    用户 YAML 中仅声明差异项即可，未指定的字段保留内置默认值。

    Args:
        config_path: 显式指定的配置文件路径（-c/--config 参数）

    Returns:
        合并后的配置字典
    """
    global _user_yaml_data

    # 第 1 层：加载内置默认配置（所有配置的基线）
    bundled_dict = _load_bundled_yaml()

    # 第 2 层：加载用户配置（覆盖内置默认的差异项）
    effective_path = config_path or _config_path_override
    if effective_path:
        user_path = Path(effective_path).expanduser().resolve()
    else:
        user_path = _get_user_config_path()

    user_dict = _load_yaml_file(user_path) or {}

    # 深度合并：用户配置仅覆盖差异项，非全文替换
    merged = deep_merge(bundled_dict, user_dict)
    _user_yaml_data = merged
    return merged


def build_settings(
    *,
    config_path: Optional[str] = None,
) -> NegentropyPerceivesSettings:
    """构建配置实例，执行完整的分层优先级合并。

    策略：
    - 无显式 config_path：加载内置默认 + ~/.negentropy/ 配置（深度合并），
      通过 _UserYamlConfigSource 注入，优先级为 内置默认 < 用户YAML < 环境变量
    - 有显式 config_path(-c)：将合并后的 YAML 作为构造参数传入，
      优先级为 内置默认 < 用户YAML < 环境变量 < -c 显式配置(最高)

    Args:
        config_path: 显式指定的配置文件路径（-c/--config 参数）

    Returns:
        完全初始化的配置实例
    """
    if config_path:
        # 显式指定配置文件：加载合并后的配置，作为构造参数传入（最高优先级）
        user_dict = _prepare_user_yaml(config_path=config_path)
        if user_dict:
            return NegentropyPerceivesSettings(**user_dict)
        return NegentropyPerceivesSettings()
    else:
        # 无显式指定：通过自定义 Source 注入合并后的配置
        _prepare_user_yaml(config_path=None)
        return NegentropyPerceivesSettings()


def reload_settings(
    *,
    config_path: Optional[str] = None,
) -> NegentropyPerceivesSettings:
    """重建全局配置单例。

    必须在任何使用 settings 之前调用（通常在 main() 入口处）。
    用于 CLI --config 覆盖场景，使全局 settings 反映用户指定的配置文件。

    Args:
        config_path: 显式指定的配置文件路径

    Returns:
        新建的全局配置实例
    """
    global settings, _config_path_override
    _config_path_override = config_path
    settings = build_settings(config_path=config_path)
    return settings


# ---------------------------------------------------------------------------
# 配置诊断
# ---------------------------------------------------------------------------


def describe_config_sources(
    *,
    config_path: Optional[str] = None,
) -> str:
    """报告配置来源详情，用于启动诊断。

    Args:
        config_path: 显式指定的配置文件路径

    Returns:
        人类可读的配置来源描述
    """
    sources: list[str] = []

    # 内置默认配置始终生效
    sources.append("bundled-default(config.default.yaml)")

    # User config
    effective_path = config_path or _config_path_override
    if effective_path:
        p = Path(effective_path).expanduser().resolve()
        label = f"custom-config({p})" if p.is_file() else f"custom-config({p}, not found)"
        sources.append(label)
    else:
        standard_path = _get_user_config_path()
        if standard_path.is_file():
            sources.append(f"user-config({standard_path})")

    if len(sources) == 1:  # 仅内置默认，无用户配置
        return "Using bundled defaults (config.default.yaml) and environment variables"

    return f"Loaded: {', '.join(sources)}"


# ---------------------------------------------------------------------------
# 配置模型
# ---------------------------------------------------------------------------


class NegentropyPerceivesSettings(BaseSettings):
    """Negentropy Perceives MCP Server 配置。

    所有字段保持扁平结构，通过 YAML 注释提供层次化视图。
    配置值通过深度合并实现层级覆盖，高优先级源仅覆盖差异项。

    优先级（低 → 高）：
      内置默认(config.default.yaml) < 用户YAML配置(~/.negentropy/) < 环境变量 < -c显式配置(构造函数参数)
    """

    # ── 服务标识 ──────────────────────────────────────────────
    server_name: str = Field(
        default="negentropy-perceives", description="MCP 服务器标识名称"
    )
    server_version: str = Field(
        default=__version__, description="版本号（从 pyproject.toml 自动获取）"
    )

    # ── 传输层 ────────────────────────────────────────────────
    transport_mode: str = Field(
        default="http", description="MCP 传输协议模式：stdio / http / sse"
    )
    http_host: str = Field(default="localhost", description="HTTP 服务器绑定主机")
    http_port: int = Field(default=8081, description="HTTP 服务器监听端口")
    http_path: str = Field(default="/mcp", description="HTTP 端点路径")
    http_cors_origins: Optional[str] = Field(
        default="*", description="CORS 来源白名单（null 禁用）"
    )

    # ── 抓取引擎 ──────────────────────────────────────────────
    concurrent_requests: int = Field(default=16, gt=0, description="并发请求上限")
    download_delay: float = Field(default=1.0, ge=0.0, description="下载间隔（秒）")
    randomize_download_delay: bool = Field(default=True, description="随机化下载间隔")
    autothrottle_enabled: bool = Field(default=True, description="启用自动节流")
    autothrottle_start_delay: float = Field(
        default=1.0, ge=0.0, description="自动节流初始延迟（秒）"
    )
    autothrottle_max_delay: float = Field(
        default=60.0, ge=0.0, description="自动节流最大延迟（秒）"
    )
    autothrottle_target_concurrency: float = Field(
        default=1.0, ge=0.0, description="自动节流目标并发度"
    )

    # ── 速率限制 ──────────────────────────────────────────────
    rate_limit_requests_per_minute: int = Field(
        default=60, ge=1, description="每分钟请求频率上限"
    )

    # ── 重试策略 ──────────────────────────────────────────────
    max_retries: int = Field(default=3, ge=0, description="失败重试最大次数")
    retry_delay: float = Field(default=1.0, ge=0.0, description="重试间隔（秒）")

    # ── 缓存系统 ──────────────────────────────────────────────
    enable_caching: bool = Field(default=True, description="启用响应缓存")
    cache_ttl_hours: int = Field(default=24, gt=0, description="缓存生存时间（小时）")

    # ── 日志系统 ──────────────────────────────────────────────
    log_level: str = Field(
        default="INFO",
        description="日志级别：DEBUG / INFO / WARNING / ERROR / CRITICAL",
    )
    log_requests: Optional[bool] = Field(default=None, description="记录请求详情")
    log_responses: Optional[bool] = Field(default=None, description="记录响应详情")

    # ── 浏览器引擎 ────────────────────────────────────────────
    enable_javascript: bool = Field(default=False, description="启用 JavaScript 执行")
    browser_headless: bool = Field(default=True, description="无头浏览器模式")
    browser_timeout: int = Field(default=30, ge=0, description="浏览器操作超时（秒）")
    browser_window_size: Union[str, tuple] = Field(
        default="1920x1080", description="浏览器窗口尺寸"
    )

    # ── 用户代理 ──────────────────────────────────────────────
    use_random_user_agent: bool = Field(
        default=True, description="启用随机 User-Agent 轮换"
    )
    default_user_agent: str = Field(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        description="默认 User-Agent 字符串",
    )

    # ── 代理服务 ──────────────────────────────────────────────
    use_proxy: bool = Field(default=False, description="启用代理服务器")
    proxy_url: Optional[str] = Field(
        default=None, description="代理服务器 URL（启用代理时必填）"
    )

    # ── 请求设置 ──────────────────────────────────────────────
    request_timeout: float = Field(
        default=30.0, gt=0.0, description="HTTP 请求超时（秒）"
    )

    # ── LLM 编排 ──────────────────────────────────────────────
    llm_api_key: Optional[str] = Field(
        default=None, description="LLM API Key（ZhipuAI）"
    )
    llm_model: str = Field(
        default="zhipu/glm-5-plus-250414",
        description="LiteLLM 模型标识（如 zhipu/glm-5-plus-250414）",
    )
    llm_temperature: float = Field(
        default=0.1, ge=0.0, le=2.0, description="LLM 温度参数"
    )
    llm_max_tokens: int = Field(default=4096, gt=0, description="LLM 最大输出 token")
    llm_timeout: float = Field(default=60.0, gt=0.0, description="LLM API 超时（秒）")
    llm_max_retries: int = Field(default=2, ge=0, description="LLM API 重试次数")

    # ── 硬件加速 ──────────────────────────────────────────────
    accelerator_device: str = Field(
        default="auto",
        description="推理设备：auto / cpu / cuda (NVIDIA) / mps (Apple Silicon) / xpu (Intel)",
    )
    accelerator_num_threads: int = Field(default=4, ge=1, description="CPU 推理线程数")
    accelerator_ocr_batch_size: int = Field(
        default=0,
        ge=0,
        description="OCR 推理 batch size（0 = 根据设备显存自动推断）",
    )
    accelerator_layout_batch_size: int = Field(
        default=0,
        ge=0,
        description="Layout 推理 batch size（0 = 根据设备显存自动推断）",
    )
    accelerator_table_batch_size: int = Field(
        default=0,
        ge=0,
        description="Table 推理 batch size（0 = 根据设备显存自动推断）",
    )

    # ── Docling PDF 引擎 ──────────────────────────────────────
    docling_enabled: bool = Field(
        default=False,
        description="启用 Docling 作为可选 PDF 提取引擎（需安装 docling 可选依赖）",
    )
    docling_ocr_enabled: bool = Field(default=True, description="为扫描版 PDF 启用 OCR")
    docling_table_extraction_enabled: bool = Field(
        default=True, description="启用 Docling 高级表格提取"
    )
    docling_formula_extraction_enabled: bool = Field(
        default=True, description="启用 Docling 数学公式提取"
    )

    # ── MinerU PDF 引擎 ──────────────────────────────────────
    mineru_enabled: bool = Field(
        default=False,
        description="启用 MinerU 作为 PDF 提取引擎（Apache 2.0，最佳 LaTeX 公式提取，CDM 90.85）",
    )
    mineru_device: str = Field(
        default="auto",
        description="MinerU 推理设备：auto / cpu / mlx (Apple Silicon) / cuda",
    )
    mineru_backend: str = Field(
        default="auto",
        description="MinerU 后端：auto（优先 MLX on Apple Silicon）/ pipeline / vlm",
    )

    # ── Marker PDF 引擎 ──────────────────────────────────────
    marker_enabled: bool = Field(
        default=False,
        description="启用 Marker 作为 PDF 提取引擎（GPL-3.0，最佳整体准确率 95.67）",
    )
    marker_llm_enhanced: bool = Field(
        default=False,
        description="启用 Marker LLM 增强模式（需额外 LLM 配置）",
    )
    marker_license_acknowledged: bool = Field(
        default=False,
        description="确认 Marker GPL-3.0 许可证条款（商业使用需评估）",
    )

    model_config = {
        "extra": "ignore",
        "env_prefix": "NEGENTROPY_PERCEIVES_",
        "env_ignore_empty": True,
        "frozen": True,
    }

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: InitSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """自定义配置源优先级链。

        返回元组中从左到右优先级递减（靠前者优先级更高）：
          init_settings(-c显式配置) > env_settings(环境变量) > _UserYamlConfigSource(合并后YAML)

        注意：dotenv_settings 参数保留在签名中以符合 pydantic-settings 协议，
        但不再加入返回元组（.env 支持已移除）。
        """
        return (
            init_settings,                        # -c 显式配置（最高优先级，靠前）
            env_settings,                         # 环境变量（中优先级）
            _UserYamlConfigSource(settings_cls),  # 内置默认+用户YAML（低优先级，靠后）
        )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level is one of the standard logging levels."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of: {valid_levels}")
        return v.upper()

    @field_validator("transport_mode")
    @classmethod
    def validate_transport_mode(cls, v):
        """Validate transport mode is one of the supported modes."""
        valid_modes = ["stdio", "http", "sse"]
        if v.lower() not in valid_modes:
            raise ValueError(f"transport_mode must be one of: {valid_modes}")
        return v.lower()

    @field_validator("accelerator_device")
    @classmethod
    def validate_accelerator_device(cls, v):
        """Validate accelerator device is one of the supported devices."""
        valid_devices = ["auto", "cpu", "cuda", "mps", "xpu"]
        if v.lower() not in valid_devices:
            raise ValueError(f"accelerator_device must be one of: {valid_devices}")
        return v.lower()

    def get_scrapy_settings(self) -> Dict[str, Any]:
        """Get Scrapy-specific settings as a dictionary."""
        return {
            "CONCURRENT_REQUESTS": self.concurrent_requests,
            "DOWNLOAD_DELAY": self.download_delay,
            "RANDOMIZE_DOWNLOAD_DELAY": self.randomize_download_delay,
            "AUTOTHROTTLE_ENABLED": self.autothrottle_enabled,
            "AUTOTHROTTLE_START_DELAY": self.autothrottle_start_delay,
            "AUTOTHROTTLE_MAX_DELAY": self.autothrottle_max_delay,
            "AUTOTHROTTLE_TARGET_CONCURRENCY": self.autothrottle_target_concurrency,
            "RETRY_TIMES": self.max_retries,
            "DOWNLOAD_TIMEOUT": self.request_timeout,
            "USER_AGENT": self.default_user_agent,
        }

    def get_docling_settings(self) -> Dict[str, Any]:
        """Get Docling-specific settings as a dictionary.

        Returns settings compatible with Docling's AcceleratorOptions and
        pipeline configuration.

        Example:
            >>> settings.get_docling_settings()
            {'device': 'auto', 'num_threads': 4, 'enable_ocr': True, ...}
        """
        return {
            "device": self.accelerator_device,
            "num_threads": self.accelerator_num_threads,
            "enable_ocr": self.docling_ocr_enabled,
            "enable_table_extraction": self.docling_table_extraction_enabled,
            "enable_formula_extraction": self.docling_formula_extraction_enabled,
            "ocr_batch_size": self.accelerator_ocr_batch_size,
            "layout_batch_size": self.accelerator_layout_batch_size,
            "table_batch_size": self.accelerator_table_batch_size,
        }


# ---------------------------------------------------------------------------
# 全局设置实例（模块级惰性初始化）
# ---------------------------------------------------------------------------

settings = build_settings()
