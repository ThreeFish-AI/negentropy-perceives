"""``perceives prefetch-models`` CLI 单元测试。

覆盖：
1. 引擎子集选择（monkeypatch 真实下载函数，断言仅触发所选引擎）；
2. 未安装引擎走 ``_SkipEngine`` 分支，输出 ``skipped`` 且不抛异常；
3. ``--hf-home`` 正确设置 ``os.environ["HF_HOME"]``；
4. 任一引擎失败 → 退出码 1；全部 ok/skipped → 退出码 0；
5. ``--engines`` 解析（``all`` / 逗号 / 非法值）。
"""

from __future__ import annotations

import os

import pytest
from typer.testing import CliRunner

from negentropy.perceives.cli.app import app
from negentropy.perceives.cli.commands import prefetch_models as pm


runner = CliRunner()


@pytest.fixture(autouse=True)
def _restore_hf_home():
    """隔离 HF_HOME 环境变量污染。"""
    saved = os.environ.get("HF_HOME")
    yield
    if saved is None:
        os.environ.pop("HF_HOME", None)
    else:
        os.environ["HF_HOME"] = saved


# ---------------------------------------------------------------------------
# _parse_engines
# ---------------------------------------------------------------------------


def test_parse_engines_all():
    assert pm._parse_engines("all") == ["docling", "marker", "mineru"]
    assert pm._parse_engines("") == ["docling", "marker", "mineru"]


def test_parse_engines_subset_and_dedup():
    assert pm._parse_engines("docling,marker") == ["docling", "marker"]
    assert pm._parse_engines("marker,marker,docling") == ["marker", "docling"]


def test_parse_engines_rejects_unknown():
    import typer

    with pytest.raises(typer.BadParameter):
        pm._parse_engines("docling,foobar")


# ---------------------------------------------------------------------------
# CLI 行为
# ---------------------------------------------------------------------------


def _patch_all_ok(monkeypatch: pytest.MonkeyPatch, called: list[str]):
    def _docling() -> str:
        called.append("docling")
        return "docling-note"

    def _marker() -> str:
        called.append("marker")
        return "marker-note"

    def _mineru() -> str:
        called.append("mineru")
        return "mineru-note"

    monkeypatch.setattr(pm, "_prefetch_docling", _docling)
    monkeypatch.setattr(pm, "_prefetch_marker", _marker)
    monkeypatch.setattr(pm, "_prefetch_mineru", _mineru)


def test_cli_all_engines_ok(monkeypatch: pytest.MonkeyPatch):
    called: list[str] = []
    _patch_all_ok(monkeypatch, called)

    result = runner.invoke(app, ["prefetch-models"])
    assert result.exit_code == 0, result.output
    assert called == ["docling", "marker", "mineru"]
    assert "ok" in result.output


def test_cli_engines_subset_only_calls_selected(monkeypatch: pytest.MonkeyPatch):
    called: list[str] = []
    _patch_all_ok(monkeypatch, called)

    result = runner.invoke(app, ["prefetch-models", "--engines", "docling,marker"])
    assert result.exit_code == 0, result.output
    assert called == ["docling", "marker"]
    assert "mineru" not in called


def test_cli_skipped_engine_still_exits_zero(monkeypatch: pytest.MonkeyPatch):
    """未安装引擎 → skipped，不影响退出码。"""

    def _skip() -> str:
        raise pm._SkipEngine("not installed")

    def _ok() -> str:
        return "ok-note"

    monkeypatch.setattr(pm, "_prefetch_docling", _ok)
    monkeypatch.setattr(pm, "_prefetch_marker", _skip)
    monkeypatch.setattr(pm, "_prefetch_mineru", _ok)

    result = runner.invoke(app, ["prefetch-models"])
    assert result.exit_code == 0, result.output
    assert "skipped" in result.output
    assert "not installed" in result.output


def test_cli_error_engine_exits_nonzero(monkeypatch: pytest.MonkeyPatch):
    def _boom() -> str:
        raise RuntimeError("kaboom")

    def _ok() -> str:
        return "ok"

    monkeypatch.setattr(pm, "_prefetch_docling", _ok)
    monkeypatch.setattr(pm, "_prefetch_marker", _boom)
    monkeypatch.setattr(pm, "_prefetch_mineru", _ok)

    result = runner.invoke(app, ["prefetch-models"])
    assert result.exit_code == 1
    assert "error" in result.output
    assert "kaboom" in result.output


def test_cli_hf_home_sets_env(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """--hf-home 应当把环境变量传导给底层下载栈。"""
    called: list[str] = []

    def _check() -> str:
        called.append(os.environ.get("HF_HOME", ""))
        return "ok"

    monkeypatch.setattr(pm, "_prefetch_docling", _check)
    monkeypatch.setattr(pm, "_prefetch_marker", _check)
    monkeypatch.setattr(pm, "_prefetch_mineru", _check)

    custom = str(tmp_path / "hf_cache")
    result = runner.invoke(app, ["prefetch-models", "--hf-home", custom])
    assert result.exit_code == 0, result.output
    # 每个引擎都应看到已设置的 HF_HOME
    assert all(env == custom for env in called), called


def test_cli_unknown_engine_returns_error(monkeypatch: pytest.MonkeyPatch):
    _patch_all_ok(monkeypatch, [])
    result = runner.invoke(app, ["prefetch-models", "--engines", "nope"])
    assert result.exit_code != 0
    # Typer BadParameter 的输出
    assert "nope" in result.output or "Usage" in result.output


# ---------------------------------------------------------------------------
# 触发下载的守门逻辑（不触网）
# ---------------------------------------------------------------------------


def test_prefetch_docling_missing_module_skips(monkeypatch: pytest.MonkeyPatch):
    """docling 未安装 → _SkipEngine。"""
    import builtins

    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name.startswith("docling"):
            raise ImportError(f"no module {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    with pytest.raises(pm._SkipEngine):
        pm._prefetch_docling()


def test_prefetch_mineru_missing_binary_skips(monkeypatch: pytest.MonkeyPatch):
    """mineru 导入成功但 CLI 缺失 → _SkipEngine。"""
    import sys
    import types

    fake = types.ModuleType("mineru")
    monkeypatch.setitem(sys.modules, "mineru", fake)
    monkeypatch.setattr(pm.shutil, "which", lambda name: None)

    with pytest.raises(pm._SkipEngine):
        pm._prefetch_mineru()


def test_prefetch_mineru_subprocess_failure_raises(monkeypatch: pytest.MonkeyPatch):
    """子进程非零退出 → RuntimeError（被 _dispatch 上报为 error）。"""
    import subprocess as _sp
    import sys
    import types

    fake = types.ModuleType("mineru")
    monkeypatch.setitem(sys.modules, "mineru", fake)
    monkeypatch.setattr(pm.shutil, "which", lambda name: "/tmp/fake-mineru")

    class _R:
        returncode = 2
        stdout = ""
        stderr = "something broke"

    def _run(cmd, **kw):  # noqa: ANN001
        return _R()

    monkeypatch.setattr(_sp, "run", _run)
    monkeypatch.setattr(pm.subprocess, "run", _run)

    with pytest.raises(RuntimeError) as ei:
        pm._prefetch_mineru()
    assert "2" in str(ei.value)
