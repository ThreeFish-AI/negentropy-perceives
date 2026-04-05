"""docs/configuration.md 文档完整性测试。"""

import re

import pytest

from negentropy.perceives.config import NegentropyPerceivesSettings
from tests.unit.doc_contracts import (
    assert_doc_exists,
    assert_relative_links_resolve,
    assert_required_frontmatter,
    read_doc,
)

CONFIG_DOC = "configuration.md"

# NegentropyPerceivesSettings 中非配置元字段（model_config 等不映射为环境变量）
_EXCLUDED_FIELDS = {"model_config"}

# 从 NegentropyPerceivesSettings 的 model_fields 中推导 NEGENTROPY_PERCEIVES_* 环境变量名
_SETTINGS_ENV_VARS: set[str] = {
    f"NEGENTROPY_PERCEIVES_{name.upper()}"
    for name in NegentropyPerceivesSettings.model_fields
    if name not in _EXCLUDED_FIELDS
}


@pytest.fixture(scope="module")
def doc_content() -> str:
    """读取配置文档内容。"""
    return read_doc(CONFIG_DOC)


class TestDocExists:
    """文档文件存在性验证。"""

    def test_configuration_doc_exists(self):
        """configuration.md 文件存在。"""
        assert_doc_exists(CONFIG_DOC)


class TestFrontmatter:
    """Frontmatter 完整性验证。"""

    def test_has_frontmatter(self, doc_content: str):
        """文档包含 YAML frontmatter。"""
        assert_required_frontmatter(doc_content)


class TestRelativeLinks:
    """文档内相对路径链接有效性验证。"""

    LINK_PATTERN = re.compile(r"\[.*?\]\((\.\.?/[^)#]+?)(?:#[^)]*)?\)")

    def test_all_relative_links_resolve(self, doc_content: str):
        """所有相对路径链接指向的文件存在。"""
        assert_relative_links_resolve(doc_content)


class TestEnvVarConsistency:
    """文档中环境变量与代码实现的一致性验证。"""

    ENV_VAR_PATTERN = re.compile(r"`(NEGENTROPY_PERCEIVES_\w+)`")

    def test_doc_covers_all_code_env_vars(self, doc_content: str):
        """文档覆盖 config.py 中所有配置字段对应的环境变量。"""
        doc_vars = set(self.ENV_VAR_PATTERN.findall(doc_content))
        missing = _SETTINGS_ENV_VARS - doc_vars
        assert missing == set(), (
            f"以下环境变量在 config.py 中定义但文档未记录: {sorted(missing)}"
        )

    # 元配置环境变量：用于定位 .env 文件本身，不对应 NegentropyPerceivesSettings 字段
    _META_ENV_VARS = {"NEGENTROPY_PERCEIVES_ENV_FILE"}

    def test_doc_env_vars_exist_in_code(self, doc_content: str):
        """文档中引用的环境变量在 config.py 中有对应字段。"""
        doc_vars = set(self.ENV_VAR_PATTERN.findall(doc_content))
        extra = doc_vars - _SETTINGS_ENV_VARS - self._META_ENV_VARS
        assert extra == set(), (
            f"以下环境变量在文档中出现但 config.py 中无对应字段: {sorted(extra)}"
        )


class TestConfigGroupCompleteness:
    """文档表格对 config.py 字段的覆盖完整性验证。"""

    TABLE_ROW_PATTERN = re.compile(
        r"^\| `NEGENTROPY_PERCEIVES_(\w+)` \|", re.MULTILINE
    )

    def test_all_fields_in_tables(self, doc_content: str):
        """文档表格行覆盖 config.py 中所有配置字段。"""
        table_fields = {
            match.lower() for match in self.TABLE_ROW_PATTERN.findall(doc_content)
        }
        code_fields = {
            name for name in NegentropyPerceivesSettings.model_fields
            if name not in _EXCLUDED_FIELDS
        }
        missing = code_fields - table_fields
        assert missing == set(), (
            f"以下字段在 config.py 中定义但未出现在文档表格中: {sorted(missing)}"
        )
