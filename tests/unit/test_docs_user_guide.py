"""docs/user-guide.md 文档完整性测试。"""

import re

import pytest
from tests.unit.doc_contracts import (
    assert_doc_exists,
    assert_relative_links_resolve,
    assert_required_frontmatter,
    read_doc,
)

USER_GUIDE_DOC = "user-guide.md"


@pytest.fixture(scope="module")
def doc_content() -> str:
    """读取用户指南文档内容。"""
    return read_doc(USER_GUIDE_DOC)


class TestDocExists:
    """文档文件存在性验证。"""

    def test_user_guide_doc_exists(self):
        """user-guide.md 文件存在。"""
        assert_doc_exists(USER_GUIDE_DOC)


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


class TestSectionStructure:
    """文档章节结构验证。"""

    REQUIRED_H2_SECTIONS = [
        "概述",
        "快速开始",
        "MCP Server 配置",
        "MCP 工具详细",
        "API 编程接口",
        "高级使用场景",
        "常见问题",
    ]

    FORBIDDEN_H2_SECTIONS = [
        "配置详解",
        "最佳实践",
        "使用技巧",
    ]

    H2_PATTERN = re.compile(r"^## (.+)$", re.MULTILINE)

    def test_has_required_sections(self, doc_content: str):
        """文档包含所有必需的二级标题。"""
        h2_titles = self.H2_PATTERN.findall(doc_content)
        for section in self.REQUIRED_H2_SECTIONS:
            assert any(
                section in title for title in h2_titles
            ), f"缺少必需章节: '## {section}'"

    @pytest.mark.parametrize("section", FORBIDDEN_H2_SECTIONS)
    def test_no_redundant_section(self, doc_content: str, section: str):
        """文档不包含冗余章节: {section}。"""
        h2_titles = self.H2_PATTERN.findall(doc_content)
        assert not any(
            section == title.strip() for title in h2_titles
        ), f"文档包含冗余章节 '## {section}'，应链接到对应权威文档"


class TestOrthogonalityConstraints:
    """正交性约束验证 -- 确保 User Guide 不包含属于其他文档的内容。"""

    def test_no_dev_install_commands(self, doc_content: str):
        """文档不包含开发依赖安装命令。"""
        assert "uv sync --group dev" not in doc_content, (
            "User Guide 不应包含开发依赖安装命令，应链接到 development.md"
        )

    def test_no_git_clone_instructions(self, doc_content: str):
        """文档不包含 git clone 安装说明。"""
        assert "git clone" not in doc_content, (
            "User Guide 不应包含从源码克隆的安装说明，应链接到 development.md"
        )

    def test_has_cross_reference_to_development(self, doc_content: str):
        """文档包含到开发指南的交叉引用链接。"""
        assert "development.md" in doc_content, (
            "缺少到 development.md 的交叉引用链接"
        )

    def test_has_cross_reference_to_configuration(self, doc_content: str):
        """文档包含到配置系统的交叉引用链接。"""
        assert "configuration.md" in doc_content, (
            "缺少到 configuration.md 的交叉引用链接"
        )

    def test_has_cross_reference_to_commands(self, doc_content: str):
        """文档包含到常用命令的交叉引用链接。"""
        assert "commands.md" in doc_content, (
            "缺少到 commands.md 的交叉引用链接"
        )


class TestMcpToolCompleteness:
    """MCP 工具文档完整性验证。"""

    EXPECTED_TOOL_COUNT = 12
    TOOL_HEADING_PATTERN = re.compile(r"^### (\d+)\. ", re.MULTILINE)

    def test_all_tools_documented(self, doc_content: str):
        """文档包含所有 14 个 MCP 工具的文档。"""
        tool_numbers = [
            int(n) for n in self.TOOL_HEADING_PATTERN.findall(doc_content)
        ]
        assert len(tool_numbers) >= self.EXPECTED_TOOL_COUNT, (
            f"仅找到 {len(tool_numbers)} 个工具文档，"
            f"期望 {self.EXPECTED_TOOL_COUNT}"
        )

    def test_tool_numbers_continuous(self, doc_content: str):
        """工具编号从 1 到 12 连续无遗漏。"""
        tool_numbers = sorted(
            int(n) for n in self.TOOL_HEADING_PATTERN.findall(doc_content)
        )
        for i in range(1, self.EXPECTED_TOOL_COUNT + 1):
            assert i in tool_numbers, f"缺少工具 #{i} 的文档"
