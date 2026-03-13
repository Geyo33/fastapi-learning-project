from typing import Any, Dict, Optional
import json
import logging
import re

from src.llm_service.models.schemas import OrderSuggestion, OrderItem, ItemID, Qty, Price, NonNegativeFloat
from pydantic import ValidationError

logger = logging.getLogger("llm_parser")


def _extract_json_blob(text: str) -> Optional[str]:
    """
    Try to extract the most likely JSON object/array substring from text.
    Returns the JSON substring or None.
    """
    if not text:
        return None

    # First, look for a top-level JSON object {...}
    obj_match = re.search(r"\{.*\}", text, re.DOTALL)
    if obj_match:
        return obj_match.group(0)

    # Next, look for a top-level JSON array [...]
    arr_match = re.search(r"\[.*\]", text, re.DOTALL)
    if arr_match:
        return arr_match.group(0)

    return None


def parse_order_suggestion(raw: Any) -> OrderSuggestion:
    """
    Normalize/parse a provider response (could be dict from provider or raw string)
    into an OrderSuggestion (pydantic model). Raises ValueError/ValidationError on failure.
    """
    parsed: Dict[str, Any]

    # If provider already returned a dict-like structure, use it directly
    if isinstance(raw, dict):
        parsed = raw
    elif isinstance(raw, str):
        # try to extract JSON substring
        blob = _extract_json_blob(raw)
        if not blob:
            # last-ditch: try to interpret the whole string as JSON
            blob = raw
        try:
            parsed = json.loads(blob)
        except Exception as exc:
            logger.debug("JSON load failed: %s; raw preview: %s", exc, (raw[:200] if raw else ""))
            raise ValueError("Failed to parse JSON from LLM output") from exc
    else:
        raise ValueError("Unsupported raw type for parsing")

    # At this point parsed should be a dict with keys: items, total, raw_text
    if "items" not in parsed:
        raise ValueError("Parsed response missing 'items'")

    # Normalize items into list of OrderItem-compatible dicts
    items_raw = parsed.get("items")
    if not isinstance(items_raw, list):
        raise ValueError("'items' must be an array")

    items = []
    for it in items_raw:
        if not isinstance(it, dict):
            raise ValueError("Each item must be an object with item_id and qty and price")
        # Accept keys named "item_id" or "id" or "price"
        item_id = it.get("item_id") or it.get("id")
        qty = it.get("qty") or it.get("quantity") or it.get("count")
        price = it.get("price")
        if item_id >= 100:
            spiciniess = it.get("spiciness") if it.get("spiciness") else "None"
            dish_meat = it.get("dish_meat") if it.get("dish_meat") else "None"
            dish_base = it.get("dish_base") if it.get("dish_base") else "None"
        else:
            spiciniess = it.get("spiciness") if it.get("spiciness") else "indéfini"
            dish_meat = it.get("dish_meat") if it.get("dish_meat") else "indéfini"
            dish_base = it.get("dish_base") if it.get("dish_base") else "indéfini"
        if item_id is None or qty is None or price is None:
            raise ValueError(f"Item missing item_id or qty or price: {it}")
        # Coerce types
        try:
            item = OrderItem(item_id=ItemID(item_id), qty=Qty(int(qty)), price=Price(NonNegativeFloat(price)), spiciness=spiciniess, dish_meat=dish_meat, dish_base=dish_base)
        except ValidationError as ve:
            logger.debug("OrderItem validation error: %s", ve)
            raise ValueError(f"Invalid item data: {it}") from ve
        items.append(item)

    # Total
    total_val = parsed.get("total")
    if total_val is None:
        raise ValueError("Parsed response missing 'total'")
    try:
        total_num = float(total_val)
        if total_num < 0:
            raise ValueError("Total must be non-negative")
    except Exception as exc:
        raise ValueError("Invalid total value") from exc

    raw_text = parsed.get("raw_text") or parsed.get("message") or None

    # Build and return OrderSuggestion
    suggestion = OrderSuggestion(items=items, total=round(total_num, 2), raw_text=raw_text)
    return suggestion
