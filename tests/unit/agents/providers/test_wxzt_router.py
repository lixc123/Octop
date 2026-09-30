from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from octop.infra.agents.providers.wxzt_router import (
    WXZT_ROUTER_PROVIDER_NAME,
    sync_wxzt_router_provider,
)
from octop.infra.db.migrate import run_migrations
from octop.infra.db.pool import SqlitePool
from octop.infra.db.repos.providers import ProviderRepo


def _services(tmp_path: Path) -> tuple[SimpleNamespace, ProviderRepo]:
    db = SqlitePool(tmp_path / "router.db")
    run_migrations(db)
    repo = ProviderRepo(db)
    return SimpleNamespace(provider_repo=repo), repo


def test_sync_creates_managed_router_from_environment(tmp_path: Path, monkeypatch) -> None:
    services, repo = _services(tmp_path)
    monkeypatch.setenv("OCTOP_WXZT_AI_ROUTER_ENABLED", "true")
    monkeypatch.setenv("OCTOP_WXZT_ORIGIN", "https://wxzt.example")
    monkeypatch.setenv("OCTOP_WXZT_AI_ROUTER_TOKEN", "server-secret")
    monkeypatch.setenv("OCTOP_WXZT_AI_ROUTER_MODELS", "geminibalance_main,gpt5,gpt5")

    sync_wxzt_router_provider(services)

    row = repo.get_by_name(WXZT_ROUTER_PROVIDER_NAME)
    assert row is not None
    assert row.kind == "openai"
    assert row.base_url == "https://wxzt.example/v1"
    assert row.api_key == "server-secret"
    assert row.enabled == 1
    assert [m["id"] for m in json.loads(row.models_json or "[]")] == [
        "geminibalance_main",
        "gpt5",
    ]


def test_sync_disables_managed_router_when_not_enabled(tmp_path: Path, monkeypatch) -> None:
    services, repo = _services(tmp_path)
    pid = repo.create(
        name=WXZT_ROUTER_PROVIDER_NAME,
        kind="anthropic",
        base_url="https://old.example/v1",
        api_key="old-secret",
        models_json="[]",
    )
    monkeypatch.delenv("OCTOP_WXZT_AI_ROUTER_ENABLED", raising=False)
    monkeypatch.delenv("OCTOP_WXZT_AI_ROUTER_BASE_URL", raising=False)
    monkeypatch.delenv("OCTOP_WXZT_ORIGIN", raising=False)
    monkeypatch.delenv("OCTOP_WXZT_AI_ROUTER_TOKEN", raising=False)

    sync_wxzt_router_provider(services)

    row = repo.get(pid)
    assert row is not None
    assert row.kind == "openai"
    assert row.enabled == 0
    assert row.api_key == "old-secret"
