from __future__ import annotations

import re

from app.inventory.models import InventoryRecord
from app.inventory.repository import InventoryRepository
from app.schemas import AnalyzeResponse, EvidenceSource

_MONEY = re.compile(r"\$\s*\d")


class EvidenceVerificationError(Exception):
    pass


class EvidenceService:
    """Application-side grounding. LLM output is never trusted as proof."""

    def __init__(self, repo: InventoryRepository) -> None:
        self._repo = repo

    def verify(
        self,
        response: AnalyzeResponse,
        field_update: str,
        inventory: list[InventoryRecord],
    ) -> None:
        trusted_ids = {record.id for record in inventory}
        for item in response.evidence:
            if item.source == EvidenceSource.VERIFIED_TABLE:
                self._verify_table_item(item.record_id, item.claim, trusted_ids)
        dumped = response.model_dump_json()
        if _MONEY.search(dumped) and not _MONEY.search(field_update):
            raise EvidenceVerificationError("invented monetary figure")

    def _verify_table_item(
        self,
        record_id: str | None,
        claim: str,
        trusted_ids: set[str],
    ) -> None:
        if not record_id or record_id not in trusted_ids:
            raise EvidenceVerificationError("unsupported inventory record_id")
        record = self._repo.get(record_id)
        if record is None:
            raise EvidenceVerificationError("inventory record not found")
        lowered = claim.casefold()
        if record.store.casefold() not in lowered:
            raise EvidenceVerificationError("inventory claim missing store")
        if record.product.casefold() not in lowered:
            raise EvidenceVerificationError("inventory claim missing product")
        if str(record.units) not in claim:
            raise EvidenceVerificationError("inventory claim does not match units")
