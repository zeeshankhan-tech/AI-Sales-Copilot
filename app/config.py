from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings:
    """Environment-backed settings. Only the mock LLM provider is implemented."""

    def __init__(self) -> None:
        inventory = Path(os.getenv("INVENTORY_PATH", ROOT_DIR / "data" / "inventory.json"))
        self.inventory_path = inventory if inventory.is_absolute() else ROOT_DIR / inventory
        self.llm_provider = os.getenv("LLM_PROVIDER", "mock").strip().lower()
        self.field_update_max_length = int(os.getenv("FIELD_UPDATE_MAX_LENGTH", "4000"))
        self.rate_limit_per_minute = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))


settings = Settings()
