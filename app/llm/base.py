from __future__ import annotations

from abc import ABC, abstractmethod

from app.inventory.models import InventoryRecord


class LLMError(Exception):
    """Base class for LLM adapter failures."""


class LLMTimeoutError(LLMError):
    pass


class LLMProviderError(LLMError):
    pass


class LLMClient(ABC):
    """Provider adapters implement this. Business logic must not import an SDK."""

    provider_name: str

    @abstractmethod
    def generate_analysis(
        self,
        field_update: str,
        inventory: list[InventoryRecord],
    ) -> str:
        """Return a JSON string for AnalyzeResponse. Raise LLMError on failure."""
        raise NotImplementedError
