from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

ANALYZE_RESPONSE_FIELDS = (
    "issue_category",
    "urgency",
    "evidence",
    "recommended_next_action",
    "missing_information",
    "needs_human_review",
    "review_reason",
)


class StrictModel(BaseModel):
    # extra="forbid" rejects unknown JSON keys.
    # Enums stay closed (only documented values). JSON strings like
    # "stockout" are accepted because FastAPI receives text, not Enum objects.
    model_config = ConfigDict(extra="forbid")


class IssueCategory(str, Enum):
    STOCKOUT = "stockout"
    DAMAGED_PRODUCT = "damaged_product"
    PRICING = "pricing"
    DELIVERY = "delivery"
    CUSTOMER_SAFETY = "customer_safety"
    OTHER = "other"
    NONE = "none"


class Urgency(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EvidenceSource(str, Enum):
    FIELD_UPDATE = "field_update"
    VERIFIED_TABLE = "verified_table"


class EvidenceStatus(str, Enum):
    REPORTED = "reported"
    VERIFIED = "verified"
    CONFLICTING = "conflicting"
    UNVERIFIED = "unverified"


class Evidence(StrictModel):
    source: EvidenceSource
    claim: str = Field(min_length=1, max_length=1000)
    status: EvidenceStatus
    record_id: str | None = None

    @model_validator(mode="after")
    def validate_record_id(self) -> "Evidence":
        if self.source == EvidenceSource.FIELD_UPDATE and self.record_id is not None:
            raise ValueError("field_update evidence must not include a record_id")
        if self.source == EvidenceSource.VERIFIED_TABLE and not self.record_id:
            raise ValueError("verified_table evidence requires a record_id")
        return self


class AnalyzeRequest(StrictModel):
    field_update: str = Field(min_length=1, max_length=5000)


class AnalyzeResponse(StrictModel):
    issue_category: IssueCategory
    urgency: Urgency
    evidence: list[Evidence]
    recommended_next_action: str = Field(min_length=1, max_length=2000)
    missing_information: list[str]
    needs_human_review: bool
    review_reason: str | None = None

    @model_validator(mode="after")
    def validate_review_reason(self) -> "AnalyzeResponse":
        if self.needs_human_review and not self.review_reason:
            raise ValueError("review_reason is required when human review is needed")
        if not self.needs_human_review and self.review_reason is not None:
            raise ValueError("review_reason must be null when human review is not needed")
        return self
