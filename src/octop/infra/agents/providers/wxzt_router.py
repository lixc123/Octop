"""Environment-driven OpenAI-compatible provider for the wxzt AI Router."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

WXZT_ROUTER_PROVIDER_NAME = "wxzt-ai-router"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw not in {"0", "false", "no", "off"}


def _models() -> list[dict[str, Any]]:
    raw = (os.environ.get("OCTOP_WXZT_AI_ROUTER_MODELS") or "").strip()
    values = [item.strip() for item in raw.split(",") if item.strip()]
    if not values:
        values = ["geminibalance_main", "gpt5"]
    seen: set[str] = set()
    models: list[dict[str, Any]] = []
    for model_id in values:
        if model_id in seen:
            continue
        seen.add(model_id)
        models.append({"id": model_id, "name": model_id, "enabled": True, "input": ["text"]})
    return models


def sync_wxzt_router_provider(services: Any) -> None:
    """Create/update the managed Provider row without exposing its token.

    The environment is the deployment source of truth. Disabling the feature
    disables an existing managed row, but does not delete it or affect operators'
    other providers.
    """
    enabled = _env_bool("OCTOP_WXZT_AI_ROUTER_ENABLED", False)
    origin = (os.environ.get("OCTOP_WXZT_ORIGIN") or "").strip().rstrip("/")
    base_url = (os.environ.get("OCTOP_WXZT_AI_ROUTER_BASE_URL") or "").strip()
    if not base_url and origin:
        base_url = f"{origin}/v1"
    token = (os.environ.get("OCTOP_WXZT_AI_ROUTER_TOKEN") or "").strip()
    if enabled and (not base_url or not token):
        logger.warning("wxzt AI Router enabled but base URL or token is missing; provider disabled")
        enabled = False

    repo = services.provider_repo
    models_json = json.dumps(_models(), ensure_ascii=False, separators=(",", ":"))
    row = repo.get_by_name(WXZT_ROUTER_PROVIDER_NAME)
    if row is None:
        if not enabled:
            # Keep the disabled state deployment-driven without adding a
            # surprising empty provider to every fresh local installation.
            return
        repo.create(
            name=WXZT_ROUTER_PROVIDER_NAME,
            kind="openai",
            base_url=base_url or None,
            api_key=token or None,
            models_json=models_json,
            note="Managed by OCTOP_WXZT_AI_ROUTER_* environment settings.",
        )
        return

    repo.update(
        row.id,
        kind="openai",
        base_url=base_url or None,
        api_key=token or None,
        models_json=models_json,
        note="Managed by OCTOP_WXZT_AI_ROUTER_* environment settings.",
        enabled=enabled,
    )
