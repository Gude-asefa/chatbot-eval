"""Central place to read credentials.

Lookup order for every setting:
  1. real environment variable
  2. a local `.env` file in the project root          (local development)
  3. Streamlit secrets (flat key, e.g. DATABASE_URL)   (Streamlit Community Cloud)

Settings used:
  DATABASE_URL         Neon connection string
  ADMIN_USERNAME       admin login name
  ADMIN_PASSWORD_HASH  output of  python tools/hash_password.py
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent / ".env"


@lru_cache(maxsize=1)
def _dotenv() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_FILE.exists():
        return values
    for raw in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
            val = val[1:-1]
        values[key.strip()] = val
    return values


def get_setting(name: str, default: str | None = None) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    if _dotenv().get(name):
        return _dotenv()[name]
    try:
        import streamlit as st

        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:  # noqa: BLE001 - no secrets file is fine
        pass
    return default
