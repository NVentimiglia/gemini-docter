"""Configuration loading for user overrides.

Reads from ~/.gemini-docter/config.json if it exists.
"""

from __future__ import annotations

import json
from pathlib import Path

CONFIG_PATH = Path.home() / ".gemini-docter" / "config.json"

_DEFAULTS: dict = {
    "providers": ["gemini", "claude", "cursor", "copilot"],  # Which providers to enable: "gemini", "claude", "cursor", "copilot"
    "max_line_length": 80,
    "enable_rfc2119": True,
    "split_long_rules": False,  # Move rules >5 lines to references/
    "thresholds": {},           # Override individual constants, e.g. {"THRASHING_EDIT_THRESHOLD": 3}
}


def load_config() -> dict:
    """Load user configuration, falling back to defaults."""
    config = dict(_DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            with CONFIG_PATH.open(encoding="utf-8") as fh:
                user_config = json.load(fh)
            config.update(user_config)
        except (json.JSONDecodeError, OSError):
            pass
    return config


def get_enabled_providers(config: dict | None = None) -> list[str]:
    if config is None:
        config = load_config()
    return config.get("providers", _DEFAULTS["providers"])
