from app.config import settings
from app.llm.base import LLMClient, LLMProviderError
from app.llm.mock import MockLLM


def get_llm() -> LLMClient:
    """Return the configured adapter. Only the mock provider is implemented."""
    if settings.llm_provider == "mock":
        return MockLLM()
    raise LLMProviderError("LLM provider is not available")
