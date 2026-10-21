from __future__ import annotations

import json

from pydantic import ValidationError

from app.inventory.repository import InventoryRepository
from app.llm.base import LLMClient
from app.schemas import AnalyzeResponse
from app.services.evidence import EvidenceService
from app.services.safety import SafetyService


class AnalysisParseError(Exception):
    pass


class AnalysisService:
    def __init__(
        self,
        repo: InventoryRepository,
        llm: LLMClient,
        evidence: EvidenceService | None = None,
        safety: SafetyService | None = None,
    ) -> None:
        self._repo = repo
        self._llm = llm
        self._evidence = evidence or EvidenceService(repo)
        self._safety = safety or SafetyService()

    def analyze(self, field_update: str) -> AnalyzeResponse:
        inventory = self._repo.all()
        raw = self._llm.generate_analysis(field_update, inventory)
        response = self._parse(raw)
        self._evidence.verify(response, field_update, inventory)
        return self._safety.apply(response, field_update, inventory)

    @staticmethod
    def _parse(raw: str) -> AnalyzeResponse:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AnalysisParseError("malformed model output") from exc
        try:
            return AnalyzeResponse.model_validate(data)
        except ValidationError as exc:
            raise AnalysisParseError("invalid model output") from exc
