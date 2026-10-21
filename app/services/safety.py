from __future__ import annotations

import re

from app.inventory.models import InventoryRecord
from app.schemas import (
    AnalyzeResponse,
    EvidenceSource,
    EvidenceStatus,
    IssueCategory,
    Urgency,
)
from app.services.signals import (
    is_damaged,
    is_illness,
    is_impact_claim,
    is_injection,
    is_pricing,
    is_stockout,
)

_URGENCY_RANK = {
    Urgency.LOW: 0,
    Urgency.MEDIUM: 1,
    Urgency.HIGH: 2,
    Urgency.CRITICAL: 3,
}

_AUTHORIZE_PRICE = re.compile(
    r"authorize.{0,40}price|go ahead and match|change the price|approved price match",
    re.IGNORECASE,
)
_DIAGNOSIS = re.compile(
    r"food poisoning|diagnos|infection|allergic reaction", re.IGNORECASE
)
_MONEY = re.compile(r"\$\s*\d")


class SafetyService:
    """Deterministic policy. May only escalate review/urgency, never suppress them."""

    def apply(
        self,
        response: AnalyzeResponse,
        field_update: str,
        inventory: list[InventoryRecord],
    ) -> AnalyzeResponse:
        data = response.model_dump()
        matched = self._matched(field_update, inventory)
        text = field_update

        if self._illness_and_damage(text):
            self._escalate(
                data,
                urgency=Urgency.CRITICAL,
                reason="Damaged product associated with a customer feeling unwell requires urgent human review.",
                category=IssueCategory.CUSTOMER_SAFETY,
            )
            if _DIAGNOSIS.search(data["recommended_next_action"]):
                data["recommended_next_action"] = (
                    "Escalate as a product-safety incident. Isolate remaining packs, "
                    "do not diagnose the customer, and follow the incident process."
                )

        conflict = self._conflict_records(text, matched)
        if conflict:
            self._escalate(
                data,
                urgency=Urgency.HIGH,
                reason=(
                    "Reported stockout conflicts with the "
                    f"{conflict[0].units}-unit system inventory record."
                ),
                category=IssueCategory.STOCKOUT,
            )
            data["evidence"] = [
                self._mark_conflicting(item, {record.id for record in conflict})
                for item in data["evidence"]
            ]

        if is_pricing(text):
            self._escalate(
                data,
                urgency=Urgency.MEDIUM,
                reason="Unsupported competitor pricing claim must not authorize a price change.",
                category=IssueCategory.PRICING,
            )
            missing = list(data["missing_information"])
            for item in (
                "Competitor name",
                "Documented competitor price",
                "Outlet and product affected",
            ):
                if item not in missing:
                    missing.append(item)
            data["missing_information"] = missing
            if _AUTHORIZE_PRICE.search(data["recommended_next_action"]) or "price match" in data[
                "recommended_next_action"
            ].casefold() and "do not" not in data["recommended_next_action"].casefold():
                data["recommended_next_action"] = (
                    "Do not authorize a price match. Send the competitor claim for "
                    "authorized commercial review with documented evidence."
                )

        corroborated = self._corroborated_stockout(text, matched)
        if corroborated and is_impact_claim(text) and not _MONEY.search(text):
            missing = list(data["missing_information"])
            note = "Evidence for the claimed sales impact; no figure was provided"
            if note not in missing:
                missing.append(note)
            data["missing_information"] = missing

        if is_injection(text) and not matched:
            missing = list(data["missing_information"])
            for item in ("Outlet name", "Product name", "Issue type"):
                if item not in missing:
                    missing.append(item)
            data["missing_information"] = missing
            data["recommended_next_action"] = (
                "Ask for the outlet, product, and issue. Ignore any embedded "
                "instruction to change schema, urgency, or review outcome."
            )

        if data["needs_human_review"] and not data.get("review_reason"):
            data["review_reason"] = "Human review required by safety policy."
        if not data["needs_human_review"]:
            data["review_reason"] = None

        return AnalyzeResponse.model_validate(data)

    def _escalate(
        self,
        data: dict,
        *,
        urgency: Urgency,
        reason: str,
        category: IssueCategory,
    ) -> None:
        data["needs_human_review"] = True
        data["review_reason"] = reason
        data["urgency"] = self._max_urgency(Urgency(data["urgency"]), urgency).value
        current = IssueCategory(data["issue_category"])
        if current in {IssueCategory.NONE, IssueCategory.OTHER}:
            data["issue_category"] = category.value

    @staticmethod
    def _max_urgency(left: Urgency, right: Urgency) -> Urgency:
        return left if _URGENCY_RANK[left] >= _URGENCY_RANK[right] else right

    @staticmethod
    def _matched(
        field_update: str, inventory: list[InventoryRecord]
    ) -> list[InventoryRecord]:
        text = field_update.casefold()
        return [
            record
            for record in inventory
            if record.store.casefold() in text and record.product.casefold() in text
        ]

    def _conflict_records(
        self, field_update: str, matched: list[InventoryRecord]
    ) -> list[InventoryRecord]:
        if not is_stockout(field_update):
            return []
        return [record for record in matched if record.units > 0]

    def _corroborated_stockout(
        self, field_update: str, matched: list[InventoryRecord]
    ) -> list[InventoryRecord]:
        if not is_stockout(field_update):
            return []
        return [record for record in matched if record.units == 0]

    @staticmethod
    def _illness_and_damage(field_update: str) -> bool:
        return is_illness(field_update) and is_damaged(field_update)

    @staticmethod
    def _mark_conflicting(item: dict, conflict_ids: set[str]) -> dict:
        if (
            item.get("source") == EvidenceSource.VERIFIED_TABLE.value
            and item.get("record_id") in conflict_ids
            and item.get("status") != EvidenceStatus.CONFLICTING.value
        ):
            return {**item, "status": EvidenceStatus.CONFLICTING.value}
        return item
