from __future__ import annotations

import re

# Short phrase lists for the mock + safety policy. Not NLU.
_STOCKOUT = ("out of stock", "unavailable", "all gone", "nothing left")
_ILLNESS = ("unwell", "feeling ill")
_PRICING = re.compile(
    r"price match|competitor.{0,60}(discount|cheaper|price)",
    re.IGNORECASE,
)
_INJECTION = re.compile(
    r"ignore .{0,40}instructions|mark .{0,30}resolved",
    re.IGNORECASE,
)
_IMPACT = re.compile(r"lost sales|major (loss|impact)", re.IGNORECASE)


def normalize(text: str) -> str:
    return text.casefold()


def is_stockout(text: str) -> bool:
    lowered = normalize(text)
    return any(token in lowered for token in _STOCKOUT)


def is_illness(text: str) -> bool:
    return any(token in normalize(text) for token in _ILLNESS)


def is_damaged(text: str) -> bool:
    return "damag" in normalize(text)


def is_pricing(text: str) -> bool:
    return bool(_PRICING.search(normalize(text)))


def is_injection(text: str) -> bool:
    return bool(_INJECTION.search(normalize(text)))


def is_impact_claim(text: str) -> bool:
    return bool(_IMPACT.search(normalize(text)))
