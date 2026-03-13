from typing import Any, Dict, List, Optional

from src.llm_service.models.schemas import MenuItem, AddItems, UpdateItems, RemoveItems, create_dish_order_items

def get_decision_tools() -> List[Dict]:
    """
    Return the list of tool definitions to be provided to the LLM before chat starts.
    These define the available functions/actions the LLM can invoke during the chat.
    """
    add_items_schema = {"type": "object"}
    add_items_schema.update(AddItems.model_json_schema()) 
    update_items_schema = {"type": "object"}
    update_items_schema.update(UpdateItems.model_json_schema()) 
    remove_items_schema = {"type": "object"}
    remove_items_schema.update(RemoveItems.model_json_schema()) 
    decision_tools = [
            {
                "type": "function",
                "function": {
                    "name": "add_items",
                    "description": "Adds one or multiple items to the current order. Only use this if the items to add are not in the current order.",
                    "parameters": add_items_schema  
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "update_items",
                    "description": "Update one or multiple existing items from the current order. Always use this if the items to update are in the current order",
                    "parameters": update_items_schema  
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "remove_items",
                    "description": "Remove one or multiple existing items from the current order.",
                    "parameters": remove_items_schema  
                }
            },
        ]
    return decision_tools

def build_response_schema(schema_mode: str, items_list = []) -> Dict[str, Any]:
    """
    Define the JSON schema that the LLM should conform to.
    This matches the OrderSuggestion model from schemas.py

    Returns:
        JSON Schema object suitable for OpenAI-style response_format parameter
    """
    schema_dispatch = {
        "chat": None,
        "add_item": create_dish_order_items(items_list).model_json_schema(),
        "update_item": create_dish_order_items(items_list).model_json_schema(),
    }
    return schema_dispatch[schema_mode]

# def build_menu_block(menu_snapshot: Optional[List[MenuItem]]) -> str:
#     """
#     Render a compact menu block for prompt injection. Menu items are rendered as:
#       - id: name ($price)
#     """
#     if not menu_snapshot:
#         return ""
#     lines = ["Menu:"]
#     for m in menu_snapshot:
#         # MenuItem may be pydantic model or dict
#         item_id = m.id if hasattr(m, "id") else m.get("id")
#         name = m.name if hasattr(m, "name") else m.get("name")
#         price = float(m.price) if hasattr(m, "price") else float(m.get("price", 0.0))
#         lines.append(f"- {item_id}: {name} (${price:.2f})")
#     return "\n".join(lines)