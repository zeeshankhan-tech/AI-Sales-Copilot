from __future__ import annotations

import json
from pathlib import Path

from app.inventory.models import InventoryRecord


class InventoryRepository:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._records = self._load()
        self._by_id = {record.id: record for record in self._records}

    def _load(self) -> list[InventoryRecord]:
        if not self._path.exists():
            raise FileNotFoundError(f"Inventory file not found: {self._path}")

        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Inventory JSON is malformed: {self._path}") from exc
        if not isinstance(raw, list):
            raise ValueError("Inventory JSON must be a list of records")

        records = [InventoryRecord.model_validate(item) for item in raw]
        ids = [record.id for record in records]
        duplicates = {record_id for record_id in ids if ids.count(record_id) > 1}
        if duplicates:
            raise ValueError(f"Duplicate inventory ids: {', '.join(sorted(duplicates))}")
        return records

    def all(self) -> list[InventoryRecord]:
        return list(self._records)

    def get(self, record_id: str) -> InventoryRecord | None:
        return self._by_id.get(record_id)

    def find_by_store(self, store: str) -> list[InventoryRecord]:
        needle = store.casefold()
        return [record for record in self._records if record.store.casefold() == needle]

    def find_by_product(self, product: str) -> list[InventoryRecord]:
        needle = product.casefold()
        return [record for record in self._records if record.product.casefold() == needle]

    def find(self, store: str, product: str) -> InventoryRecord | None:
        matches = self.find_by_store(store)
        needle = product.casefold()
        for record in matches:
            if record.product.casefold() == needle:
                return record
        return None
