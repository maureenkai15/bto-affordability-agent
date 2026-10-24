"""Loads policy_2026.yaml. Every calculator reads its numbers from here, never from literals."""
from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

POLICY_PATH = Path(__file__).resolve().parent.parent / "policy_2026.yaml"


@lru_cache(maxsize=1)
def load_policy(path: str | None = None) -> dict[str, Any]:
    with open(path or POLICY_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def value(*keys: str) -> Any:
    """Read a policy value by path, e.g. value("hdb_loan", "ltv") -> 0.75.

    If the node is a dict with a "value" key, the bare value is returned.
    """
    node: Any = load_policy()
    for k in keys:
        node = node[k]
    if isinstance(node, dict) and "value" in node:
        return node["value"]
    return node


def node(*keys: str) -> dict[str, Any]:
    """Return the whole policy node (value + source + verified flag)."""
    n: Any = load_policy()
    for k in keys:
        n = n[k]
    return n


def as_of() -> str:
    return load_policy()["meta"]["as_of"]


def is_stale(today: date | None = None) -> bool:
    meta = load_policy()["meta"]
    age = ((today or date.today()) - date.fromisoformat(meta["as_of"])).days
    return age > meta["stale_after_days"]


def unverified_items() -> list[str]:
    """Paths of every policy node marked verified: false, so the UI can warn about them."""
    out: list[str] = []

    def walk(n: Any, path: list[str]) -> None:
        if isinstance(n, dict):
            if n.get("verified") is False:
                out.append(".".join(path))
            for k, v in n.items():
                walk(v, path + [str(k)])

    walk(load_policy(), [])
    return out


def sourced_items() -> list[dict[str, Any]]:
    """Every policy node that carries a verified flag, with its source, for the UI's sources table."""
    out: list[dict[str, Any]] = []

    def walk(n: Any, path: list[str]) -> None:
        if isinstance(n, dict):
            if "verified" in n:
                out.append({
                    "rule": ".".join(path),
                    "verified": n["verified"],
                    "source_url": n.get("source_url"),
                    "confirmed_by": n.get("confirmed_by"),
                    "note": n.get("note"),
                })
            for k, v in n.items():
                walk(v, path + [str(k)])

    walk(load_policy(), [])
    return out
