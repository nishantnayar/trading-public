"""Launcher service selection — prefect and the cron runner are one unit."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _start():
    name = "quantis_start"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / "start.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _names(only: list[str] | None = None, skip: list[str] | None = None) -> list[str]:
    return [s.name for s in _start().choose_services(only=only, skip=skip)]


def test_default_stack_includes_prefect_and_schedules() -> None:
    assert _names() == ["api", "ui", "prefect", "schedules"]


def test_only_prefect_also_starts_the_runner() -> None:
    assert _names(only=["prefect"]) == ["prefect", "schedules"]


def test_skip_prefect_drops_the_runner() -> None:
    assert _names(skip=["prefect"]) == ["api", "ui"]


def test_skip_schedules_keeps_the_prefect_ui() -> None:
    assert _names(skip=["schedules"]) == ["api", "ui", "prefect"]


def test_only_schedules_does_not_force_the_server() -> None:
    assert _names(only=["schedules"]) == ["schedules"]


def test_prefect_server_turns_off_notification_loop() -> None:
    prefect = next(s for s in _start().services() if s.name == "prefect")
    assert prefect.env["PREFECT_API_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED"] == "false"
