"""单元测试：``_table_quality_score`` 启发式过滤。

动机：PyMuPDF ``find_tables`` 会把对齐列表、菜单、页眉等非表格结构也
误识别为 table。`_table_quality_score` 在 ``row_count>=2 & col_count>=2``
的原始门控之上补一层启发式，依据三项指标（占用率、弱列比、去重单元格数）
剔除伪表格。

测试覆盖：

1. 真实稀疏但有效的表格 → 通过；
2. 空白率过高 → ``reason=low_occupancy`` 拒绝；
3. 过半列几乎为空 → ``reason=too_many_weak_cols`` 拒绝；
4. 所有单元格只有 ≤2 种不同值（典型页眉重复）→ ``reason=low_uniqueness`` 拒绝；
5. 行/列数过少 → ``too_few_rows`` / ``too_few_cols`` 拒绝；
6. ``_QF_ENABLED=False`` → 任何输入均通过（回退原行为）。
"""

from __future__ import annotations

from typing import Any, List

import pytest

from negentropy.perceives.pdf.extraction import table as table_mod
from negentropy.perceives.pdf.extraction.table import _table_quality_score


@pytest.fixture(autouse=True)
def _restore_thresholds(monkeypatch):
    """每个用例独立还原模块级阈值，避免串扰。"""
    monkeypatch.setattr(table_mod, "_QF_ENABLED", True, raising=True)
    monkeypatch.setattr(table_mod, "_QF_MIN_OCCUPANCY", 0.40, raising=True)
    monkeypatch.setattr(table_mod, "_QF_MAX_WEAK_COLS_RATIO", 0.5, raising=True)
    monkeypatch.setattr(table_mod, "_QF_MIN_UNIQUE_CELLS", 3, raising=True)
    yield


class TestAcceptance:
    def test_real_table_passes(self) -> None:
        data: List[List[Any]] = [
            ["Name", "Age", "City"],
            ["Alice", "30", "NYC"],
            ["Bob", "25", "SF"],
            ["Charlie", "35", "LA"],
        ]
        passed, diag = _table_quality_score(data)
        assert passed is True, diag
        assert diag["reason"] == "pass"
        assert diag["occupancy"] == 1.0

    def test_sparse_but_valid_table_passes(self) -> None:
        """稀疏（部分空白）但结构化的表格应被保留。"""
        data: List[List[Any]] = [
            ["Product", "Q1", "Q2", "Q3", "Q4"],
            ["A", "10", "", "30", "40"],
            ["B", "", "20", "", "45"],
            ["C", "15", "25", "35", ""],
        ]
        # 4 行 5 列 = 20 单元；非空 15 → 0.75；每列非空率 100/50/50/50/75% → 无弱列
        passed, diag = _table_quality_score(data)
        assert passed is True, diag
        assert diag["reason"] == "pass"


class TestRejection:
    def test_low_occupancy_rejected(self) -> None:
        """非空密度 < 0.4 → low_occupancy。"""
        data: List[List[Any]] = [
            ["a", "", "", ""],
            ["", "", "", ""],
            ["", "b", "", ""],
            ["", "", "c", ""],
        ]
        # 4*4=16 单元，仅 3 非空 → occupancy≈0.19
        passed, diag = _table_quality_score(data)
        assert passed is False
        assert diag["reason"] == "low_occupancy"

    def test_too_many_weak_cols_rejected(self) -> None:
        """超过半数列的非空率 < 40% → too_many_weak_cols。

        构造 5 列 5 行：仅第 1/2 列填满（强列），其余 3 列仅首行有值（非空率 0.2 → 弱列）。
        非空率 = (5+5+1+1+1)/25 = 0.52（> 0.40 过 occupancy 门），
        弱列数 3 > 5*0.5=2 → 命中。
        """
        data: List[List[Any]] = [
            ["x", "y", "z", "w", "v"],
            ["x", "y", "", "", ""],
            ["x", "y", "", "", ""],
            ["x", "y", "", "", ""],
            ["x", "y", "", "", ""],
        ]
        passed, diag = _table_quality_score(data)
        assert passed is False, diag
        assert diag["reason"] == "too_many_weak_cols"
        assert diag["weak_cols"] == 3
        assert diag["cols"] == 5

    def test_low_uniqueness_rejected_header_repetition(self) -> None:
        """所有单元格仅 1~2 种取值 → low_uniqueness（典型页眉复制）。"""
        data: List[List[Any]] = [
            ["Header", "Header"],
            ["Header", "Header"],
            ["Header", "Header"],
        ]
        passed, diag = _table_quality_score(data)
        assert passed is False
        assert diag["reason"] == "low_uniqueness"
        assert diag["unique_cells"] == 1

    def test_two_unique_values_rejected(self) -> None:
        data: List[List[Any]] = [
            ["Y", "N"],
            ["Y", "N"],
            ["Y", "N"],
            ["Y", "N"],
        ]
        # 占用率 1.0，弱列 0，但 unique_cells=2 ≤ 2
        passed, diag = _table_quality_score(data)
        assert passed is False
        assert diag["reason"] == "low_uniqueness"


class TestShapeGuards:
    def test_empty_data(self) -> None:
        passed, diag = _table_quality_score([])
        assert passed is False
        assert diag["reason"] == "empty"

    def test_single_row_rejected(self) -> None:
        passed, diag = _table_quality_score([["a", "b", "c"]])
        assert passed is False
        assert diag["reason"] == "too_few_rows"

    def test_single_col_rejected(self) -> None:
        passed, diag = _table_quality_score([["a"], ["b"], ["c"]])
        assert passed is False
        assert diag["reason"] == "too_few_cols"


class TestDisabledFallback:
    def test_disabled_passes_everything(self, monkeypatch) -> None:
        """_QF_ENABLED=False → 只要行列满足即通过（回退到原 row_count>=2 门控语义）。"""
        monkeypatch.setattr(table_mod, "_QF_ENABLED", False)
        # 非空率极低且单值 → 原本被拒，但关闭后应通过
        data: List[List[Any]] = [
            ["a", "", ""],
            ["", "", ""],
            ["", "", ""],
        ]
        passed, diag = _table_quality_score(data)
        assert passed is True
        assert diag["reason"] == "disabled"


class TestThresholdOverride:
    def test_relaxed_occupancy_admits_sparse(self, monkeypatch) -> None:
        """把 min_occupancy 放宽到 0.05 → 原本 low_occupancy 的稀疏表通过。"""
        monkeypatch.setattr(table_mod, "_QF_MIN_OCCUPANCY", 0.05)
        # 需要同时放宽弱列比和唯一值数阈值以隔离单个维度
        monkeypatch.setattr(table_mod, "_QF_MAX_WEAK_COLS_RATIO", 1.0)
        monkeypatch.setattr(table_mod, "_QF_MIN_UNIQUE_CELLS", 1)
        data: List[List[Any]] = [
            ["a", "", "", ""],
            ["", "", "", ""],
            ["", "b", "", ""],
            ["", "", "c", ""],
        ]
        passed, diag = _table_quality_score(data)
        assert passed is True
        assert diag["reason"] == "pass"
