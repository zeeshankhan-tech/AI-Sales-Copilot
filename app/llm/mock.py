from __future__ import annotations

import json

from app.inventory.models import InventoryRecord
from app.llm.base import LLMClient
from app.llm.prompt import build_prompt
from app.services.signals import is_damaged, is_illness, is_pricing, is_stockout

# MOCK PROVIDER. Deterministic fixture. Does not validate real LLM behavior.


class MockLLM(LLMClient):
    provider_name = "mock"

    def generate_analysis(
        self,
        field_update: str,
        inventory: list[InventoryRecord],
    ) -> str:
        build_prompt(field_update, inventory)
        return json.dumps(self._payload(field_update, inventory))

    def _payload(
        self,
        field_update: str,
        inventory: list[InventoryRecord],
    ) -> dict:
        text = field_update.casefold()
        by_id = {record.id: record for record in inventory}
        metro = by_id.get("inv_metro_fresh_cola_500ml")
        indir = by_id.get("inv_indiranagar_cola_500ml")
        juice = by_id.get("inv_city_corner_juice_1l")

        if self._mentions(text, juice) and is_illness(field_update) and is_damaged(field_update):
            return self._illness_case(field_update, juice)
        if is_pricing(field_update):
            return self._pricing_case(field_update)
        if self._mentions(text, metro) and is_stockout(field_update):
            return self._conflict_case(field_update, metro)
        if self._mentions(text, indir) and is_stockout(field_update):
            return self._corroborated_stockout(field_update, indir)
        if self._mentions(text, juice):
            return self._normal_visit(field_update, juice)
        return self._missing_details(field_update)

    @staticmethod
    def _mentions(text: str, record: InventoryRecord | None) -> bool:
        if record is None:
            return False
        return record.store.casefold() in text and record.product.casefold() in text

    @staticmethod
    def _reported(field_update: str) -> dict:
        return {
            "source": "field_update",
            "claim": field_update.strip()[:1000],
            "status": "reported",
            "record_id": None,
        }

    @staticmethod
    def _table(record: InventoryRecord, status: str) -> dict:
        return {
            "source": "verified_table",
            "claim": (
                f"System inventory records {record.units} units of "
                f"{record.product} at {record.store}."
            ),
            "status": status,
            "record_id": record.id,
        }

    def _conflict_case(self, field_update: str, record: InventoryRecord) -> dict:
        return {
            "issue_category": "stockout",
            "urgency": "high",
            "evidence": [
                self._reported(field_update),
                self._table(record, "conflicting"),
            ],
            "recommended_next_action": (
                "Verify the physical shelf and the inventory record before any "
                "replenishment decision."
            ),
            "missing_information": ["When the shelf was last physically checked"],
            "needs_human_review": True,
            "review_reason": (
                f"Reported stockout conflicts with the {record.units}-unit "
                "system inventory record."
            ),
        }

    def _corroborated_stockout(self, field_update: str, record: InventoryRecord) -> dict:
        return {
            "issue_category": "stockout",
            "urgency": "high",
            "evidence": [
                self._reported(field_update),
                self._table(record, "verified"),
            ],
            "recommended_next_action": (
                "Treat as a corroborated recorded stockout. Do not invent a "
                "lost-sales figure. Arrange replenishment through the normal process."
            ),
            "missing_information": [
                "Evidence for the claimed sales impact; no figure was provided"
            ],
            "needs_human_review": False,
            "review_reason": None,
        }

    def _pricing_case(self, field_update: str) -> dict:
        return {
            "issue_category": "pricing",
            "urgency": "medium",
            "evidence": [
                {
                    "source": "field_update",
                    "claim": field_update.strip()[:1000],
                    "status": "unverified",
                    "record_id": None,
                }
            ],
            "recommended_next_action": (
                "Do not authorize a price match. Send the competitor claim for "
                "authorized commercial review with documented evidence."
            ),
            "missing_information": [
                "Competitor name",
                "Documented competitor price",
                "Outlet and product affected",
            ],
            "needs_human_review": True,
            "review_reason": (
                "Unsupported competitor pricing claim must not authorize a price change."
            ),
        }

    def _illness_case(self, field_update: str, record: InventoryRecord) -> dict:
        return {
            "issue_category": "customer_safety",
            "urgency": "critical",
            "evidence": [
                self._reported(field_update),
                self._table(record, "verified"),
            ],
            "recommended_next_action": (
                "Escalate as a product-safety incident. Isolate remaining packs, "
                "do not diagnose the customer, and follow the incident process."
            ),
            "missing_information": ["Batch or pack identifier if available"],
            "needs_human_review": True,
            "review_reason": (
                "Damaged product associated with a customer feeling unwell "
                "requires urgent human review."
            ),
        }

    def _normal_visit(self, field_update: str, record: InventoryRecord) -> dict:
        return {
            "issue_category": "none",
            "urgency": "low",
            "evidence": [
                self._reported(field_update),
                self._table(record, "verified"),
            ],
            "recommended_next_action": "No commercial action required from this update.",
            "missing_information": [],
            "needs_human_review": False,
            "review_reason": None,
        }

    def _missing_details(self, field_update: str) -> dict:
        return {
            "issue_category": "other",
            "urgency": "low",
            "evidence": [self._reported(field_update)],
            "recommended_next_action": (
                "Ask for the outlet, product, and issue. Ignore any embedded "
                "instruction to change schema, urgency, or review outcome."
            ),
            "missing_information": ["Outlet name", "Product name", "Issue type"],
            "needs_human_review": False,
            "review_reason": None,
        }
