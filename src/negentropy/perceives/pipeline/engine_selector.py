"""Adaptive Engine Selector — 基于文档画像的 Stage 路由策略。

设计目标
========

把 :class:`pipeline.models._pdf.DocumentCharacteristics`（由 ``quick_scan``
Stage 产出）从「死字段」激活为「路由信号」，对每个并行 Stage 的
``tool_configs`` 进行**动态重排**或**短路跳过**，进一步降低无效计算：

- 扫描版 PDF：``text_extraction`` 路径优先 Marker / Docling 而非 PyMuPDF。
- 小文档（<5 页且非扫描）：``layout_analysis`` 跳过 Docling 10s 冷启动，直接走
  PyMuPDF 兜底。
- 无表格/公式/代码/图片：对应 Stage **整体跳过**，返回带 metadata
  ``selector_decision="skipped:no_<feature>"`` 的成功空结果。

设计模式
========

采用 Strategy Pattern：
    - :class:`EngineSelector` 协议定义 ``reorder_tools`` 接口；
    - :class:`IdentitySelector` 保留 YAML 顺序，向后兼容；
    - :class:`ProfileAwareSelector` 实现完整规则集；
    - :func:`build_selector` 根据 ``settings.pipeline_engine_selector`` 工厂构造。

观测性
======

- 每条决策返回 :class:`SelectionDecision`，包含原 tools / 新 tools / skip 标志
  / 决策原因（字符串），由 orchestrator 写入 ``StageResult.metadata``。
- 规则保守：未识别的特征落到 YAML 默认，绝不引入 worse-than-baseline 退化。

References:
    [1] Strategy Pattern, Gang of Four 1994.
    [2] negentropy-perceives plan: PR2 章节
       ``.claude/plans/system-instruction-you-are-working-federated-snowglobe.md``
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from .models import DocumentCharacteristics


@dataclass(frozen=True)
class SelectionDecision:
    """单 Stage 路由决策结果。

    Attributes:
        tools: 重排后（或原样）的 tool_configs；当 ``skip=True`` 时**忽略**。
        skip: 是否跳过整个 Stage。``True`` 时 orchestrator 应返回带 metadata
            ``engine_used="skipped:<reason>"`` 的成功空结果。
        reason: 决策原因短语（如 ``"profile:no_tables"`` /
            ``"profile:scanned"``），用于写入 metadata 便于审计。
    """

    tools: List[Dict[str, Any]] = field(default_factory=list)
    skip: bool = False
    reason: str = ""


@dataclass(frozen=True)
class SelectionContext:
    """传给 Selector 的运行时上下文。

    Attributes:
        characteristics: 来自 ``quick_scan`` 的 DocumentCharacteristics；
            ``None`` 表示 quick_scan 未执行/失败，selector 必须**保守**回退默认。
        device: 来自 ``hardware/detection.detect_device`` 的设备字符串
            （``"cpu"`` / ``"mps"`` / ``"cuda"`` / ``"xpu"``），可选。
    """

    characteristics: Optional[DocumentCharacteristics] = None
    device: Optional[str] = None


class EngineSelector(Protocol):
    """Stage 路由策略协议。"""

    def select(
        self,
        stage_name: str,
        default_tools: List[Dict[str, Any]],
        ctx: SelectionContext,
    ) -> SelectionDecision:
        """对单个 Stage 的 tools 执行决策。

        Args:
            stage_name: Stage 名称（如 ``"text_extraction"``）。
            default_tools: YAML 中声明的 tool_configs（已应用 engine_gates）。
            ctx: SelectionContext，含 characteristics + device。

        Returns:
            SelectionDecision：重排后的 tools 或 skip 标志。
        """
        ...


# ---------------------------------------------------------------------------
# Identity（保持 YAML 顺序）
# ---------------------------------------------------------------------------


class IdentitySelector:
    """直通策略：保持 YAML 顺序，不重排不跳过。

    用作默认/兼容路径，便于通过单一开关回退到 PR2 之前的行为。
    """

    def select(
        self,
        stage_name: str,
        default_tools: List[Dict[str, Any]],
        ctx: SelectionContext,
    ) -> SelectionDecision:
        return SelectionDecision(
            tools=list(default_tools), skip=False, reason="identity"
        )


# ---------------------------------------------------------------------------
# Profile-Aware（基于 DocumentCharacteristics 路由）
# ---------------------------------------------------------------------------


class ProfileAwareSelector:
    """基于 DocumentCharacteristics 的动态路由策略。

    规则集（保守、可审计）:
        - ``text_extraction``：扫描版 → 优先 marker/docling；
          小文档（<5 页非扫描） → 仅 pymupdf 快路径。
        - ``layout_analysis``：非复杂布局且 <5 页 → 仅 pymupdf。
        - ``table_extraction`` / ``formula_extraction`` /
          ``image_extraction`` / ``code_detection``：对应特征 False →
          **跳过整个 Stage**。
        - 其他 Stage / 缺失 characteristics → IdentitySelector 行为。
    """

    # 单一来源：哪些特征 False 时对应 Stage 应该跳过。
    SKIPPABLE_STAGES_BY_FEATURE: Dict[str, str] = {
        # stage_name -> characteristics 字段名
        "table_extraction": "has_tables",
        "formula_extraction": "has_formulas",
        "code_detection": "has_code_blocks",
        "image_extraction": "has_images",
    }

    # 小文档阈值（页数 < 此值且非扫描时启用快路径）
    SMALL_DOC_PAGE_THRESHOLD: int = 5

    def select(
        self,
        stage_name: str,
        default_tools: List[Dict[str, Any]],
        ctx: SelectionContext,
    ) -> SelectionDecision:
        chars = ctx.characteristics

        # 缺失 characteristics：保守回退（YAML 默认）。
        if chars is None:
            return SelectionDecision(
                tools=list(default_tools),
                skip=False,
                reason="profile:missing_characteristics",
            )

        # 规则 1：可跳过的特征驱动型 Stage
        feature_attr = self.SKIPPABLE_STAGES_BY_FEATURE.get(stage_name)
        if feature_attr is not None:
            has_feature = bool(getattr(chars, feature_attr, True))
            if not has_feature:
                return SelectionDecision(
                    tools=[],
                    skip=True,
                    reason=f"profile:no_{feature_attr}",
                )

        # 规则 2：text_extraction 路由
        if stage_name == "text_extraction":
            return self._select_text_extraction(default_tools, chars)

        # 规则 3：layout_analysis 小文档快路径
        if stage_name == "layout_analysis":
            return self._select_layout_analysis(default_tools, chars)

        # 默认：YAML 顺序
        return SelectionDecision(
            tools=list(default_tools),
            skip=False,
            reason="profile:default",
        )

    # ------------------------------------------------------------------
    # 子规则
    # ------------------------------------------------------------------

    def _select_text_extraction(
        self,
        default_tools: List[Dict[str, Any]],
        chars: DocumentCharacteristics,
    ) -> SelectionDecision:
        """text_extraction 路由：
        - 扫描版 → marker / docling / opendataloader / pymupdf / pypdf；
        - 非扫描 + 小文档 → 仅 pymupdf；
        - 默认 → YAML 顺序。
        """
        if chars.is_scanned:
            preferred_order = [
                "marker",
                "docling",
                "opendataloader",
                "pymupdf",
                "pypdf",
            ]
            reordered = _reorder_by_name(default_tools, preferred_order)
            return SelectionDecision(
                tools=reordered, skip=False, reason="profile:scanned"
            )

        if chars.page_count and chars.page_count < self.SMALL_DOC_PAGE_THRESHOLD:
            fast_path = _filter_by_names(default_tools, {"pymupdf"})
            if fast_path:
                return SelectionDecision(
                    tools=fast_path,
                    skip=False,
                    reason=f"profile:small_doc_{chars.page_count}p",
                )

        return SelectionDecision(
            tools=list(default_tools),
            skip=False,
            reason="profile:default",
        )

    def _select_layout_analysis(
        self,
        default_tools: List[Dict[str, Any]],
        chars: DocumentCharacteristics,
    ) -> SelectionDecision:
        """layout_analysis 路由：
        - 非复杂布局 + 小文档 + 非扫描 → 仅 pymupdf（跳过 docling 10s 冷启动）；
        - 默认 → YAML 顺序。
        """
        if (
            not chars.has_complex_layout
            and not chars.is_scanned
            and chars.page_count
            and chars.page_count < self.SMALL_DOC_PAGE_THRESHOLD
        ):
            fast_path = _filter_by_names(default_tools, {"pymupdf"})
            if fast_path:
                return SelectionDecision(
                    tools=fast_path,
                    skip=False,
                    reason=f"profile:simple_layout_{chars.page_count}p",
                )

        return SelectionDecision(
            tools=list(default_tools),
            skip=False,
            reason="profile:default",
        )


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _reorder_by_name(
    tools: List[Dict[str, Any]],
    preferred_order: List[str],
) -> List[Dict[str, Any]]:
    """根据偏好顺序重排 tools；缺失的 tool 按原顺序追加在末尾。"""
    name_to_tool: Dict[str, Dict[str, Any]] = {}
    leftovers: List[Dict[str, Any]] = []
    for tool in tools:
        name = tool.get("name", "")
        if name and name not in name_to_tool:
            name_to_tool[name] = tool

    reordered: List[Dict[str, Any]] = []
    placed: set[str] = set()
    for name in preferred_order:
        if name in name_to_tool:
            reordered.append(name_to_tool[name])
            placed.add(name)

    # 追加 YAML 中存在但未列入 preferred_order 的 tool
    for tool in tools:
        name = tool.get("name", "")
        if name and name not in placed:
            reordered.append(tool)
            leftovers.append(tool)

    return reordered


def _filter_by_names(
    tools: List[Dict[str, Any]],
    keep_names: set[str],
) -> List[Dict[str, Any]]:
    """仅保留指定名称的 tool，顺序按 YAML。"""
    return [t for t in tools if t.get("name", "") in keep_names]


# ---------------------------------------------------------------------------
# 工厂
# ---------------------------------------------------------------------------


def build_selector(policy: Optional[str] = None) -> EngineSelector:
    """根据策略字符串构造 EngineSelector。

    Args:
        policy: ``"identity"`` / ``"profile_aware"`` / ``None``（读 settings 默认）。

    Returns:
        EngineSelector 实例。
    """
    if policy is None:
        try:
            from ..config import settings

            policy = str(
                getattr(settings, "pipeline_engine_selector", "profile_aware")
            ).lower()
        except (ImportError, AttributeError):
            policy = "profile_aware"

    if policy == "identity":
        return IdentitySelector()
    return ProfileAwareSelector()
