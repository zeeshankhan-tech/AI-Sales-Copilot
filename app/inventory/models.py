from pydantic import BaseModel, ConfigDict, Field


class InventoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    id: str = Field(min_length=1)
    store: str = Field(min_length=1)
    product: str = Field(min_length=1)
    units: int = Field(ge=0)
