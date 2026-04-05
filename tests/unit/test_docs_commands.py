"""docs/commands.md 文档完整性测试。"""

import re

import pytest
from tests.unit.doc_contracts import (
    assert_doc_exists,
    assert_relative_links_resolve,
    assert_required_frontmatter,
    iter_relative_links,
    read_doc,
)

COMMANDS_DOC = "commands.md"


@pytest.fixture(scope="module")
def doc_content() -> str:
    """读取命令文档内容。"""
    return read_doc(COMMANDS_DOC)


def _extract_bash_blocks(content: str) -> list[str]:
    """提取文档中所有 bash 代码块内容。"""
    return re.findall(r"```bash\n(.*?)```", content, re.DOTALL)


class TestDocExists:
    """文档文件存在性验证。"""

    def test_commands_doc_exists(self):
        """commands.md 文件存在。"""
        assert_doc_exists(COMMANDS_DOC)


class TestFrontmatter:
    """Frontmatter 完整性验证。"""

    def test_has_frontmatter(self, doc_content: str):
        """文档包含 YAML frontmatter。"""
        assert_required_frontmatter(doc_content)


class TestRelativeLinks:
    """文档内相对路径链接有效性验证。"""

    LINK_PATTERN = re.compile(r"\[.*?\]\((\.\.?/[^)#]+?)(?:#[^)]*)?\)")

    def test_has_relative_links(self, doc_content: str):
        """文档包含指向权威文档的相对路径链接。"""
        links = iter_relative_links(doc_content)
        assert len(links) > 0, "未找到任何相对路径链接（文档应包含权威文档引用）"

    def test_all_relative_links_resolve(self, doc_content: str):
        """所有相对路径链接指向的文件存在。"""
        assert_relative_links_resolve(doc_content)


class TestEnvVarAccuracy:
    """文档中环境变量与 config.py 一致性验证。"""

    ENV_VAR_PATTERN = re.compile(r"NEGENTROPY_PERCEIVES_(\w+)")

    def test_no_nonexistent_env_vars(self, doc_content: str):
        """文档 bash 代码块中引用的 NEGENTROPY_PERCEIVES_ 变量在 config.py 中有对应字段。"""
        from negentropy.perceives.config import NegentropyPerceivesSettings

        valid_fields = {name.upper() for name in NegentropyPerceivesSettings.model_fields}

        bash_blocks = _extract_bash_blocks(doc_content)
        doc_vars: set[str] = set()
        for block in bash_blocks:
            doc_vars.update(self.ENV_VAR_PATTERN.findall(block))

        invalid = [
            f"NEGENTROPY_PERCEIVES_{var}" for var in doc_vars if var not in valid_fields
        ]

        assert invalid == [], f"以下环境变量在 config.py 中不存在: {invalid}"


class TestNoRedundancy:
    """验证文档不包含应由权威文档覆盖的冗余命令。"""

    def test_no_setup_sh_execution(self, doc_content: str):
        """环境设置命令应由 Development.md 覆盖。"""
        for block in _extract_bash_blocks(doc_content):
            assert "./scripts/dev/setup.sh" not in block, (
                "文档不应包含 ./scripts/dev/setup.sh 执行命令（已由 development.md 覆盖）"
            )

    def test_no_pytest_commands(self, doc_content: str):
        """pytest 命令应由 Testing.md 覆盖。"""
        for block in _extract_bash_blocks(doc_content):
            assert "uv run pytest" not in block, (
                "文档不应包含 pytest 命令（已由 testing.md 覆盖）"
            )

    def test_no_uv_sync_commands(self, doc_content: str):
        """uv sync 命令应由 Development.md 覆盖。"""
        for block in _extract_bash_blocks(doc_content):
            assert "uv sync" not in block, (
                "文档不应包含 uv sync 命令（已由 development.md 覆盖）"
            )

    def test_no_uv_build_command(self, doc_content: str):
        """构建命令应由 Development.md 覆盖。"""
        for block in _extract_bash_blocks(doc_content):
            assert "uv build" not in block, (
                "文档不应包含 uv build 命令（已由 development.md 覆盖）"
            )


class TestRequiredSections:
    """验证文档包含预期的独有价值章节。"""

    EXPECTED_HEADINGS = [
        "服务器启动",
        "项目依赖管理",
        "系统调试与诊断",
    ]

    @pytest.mark.parametrize("heading", EXPECTED_HEADINGS)
    def test_has_required_section(self, doc_content: str, heading: str):
        """文档包含必需章节: {heading}。"""
        assert heading in doc_content, f"文档缺少必需章节: '{heading}'"

    AUTHORITY_DOCS = ["development.md", "testing.md"]

    @pytest.mark.parametrize("doc_name", AUTHORITY_DOCS)
    def test_has_authority_link(self, doc_content: str, doc_name: str):
        """文档包含指向权威文档的链接: {doc_name}。"""
        assert doc_name in doc_content, f"文档缺少指向权威文档 {doc_name} 的链接"
