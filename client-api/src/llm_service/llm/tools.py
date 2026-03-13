from typing import Any

from src.llm_service.models.domain import MenuSnapshot


async def add_items_tool(menu: list[dict], items: list[dict]) -> dict[str, Any]:
    """Tool function to process items to add to an order draft based on menu and item details."""
    menu_items_simple = {"items": [], "total": float(0)}
    menu_items_all = {"items": [], "total": float(0)}
    menu_items_template = []
    has_diy_dish = False
    menu_snapshot = MenuSnapshot.from_list(menu)

    items_to_add = []

    for item in items:
        if item["item_id"] < 100:
            # divide multiple qty into single ones for customizable menu items
            items_to_add.extend(
                {"item_id": item["item_id"], "qty": 1}
                for _ in range(item["qty"])
            )
        else:
            # keep items >= 100 as they are
            items_to_add.append(item)

    for item in items_to_add:
        menu_item = menu_snapshot.items.get(item["item_id"])
        if menu_item.id == item["item_id"]:
            formatted_item = {
                    "item_id": item["item_id"],
                    "dish_name": menu_item.dish_name,
                    "qty": item["qty"],
                    "price": menu_item.price,
                }
            menu_items_all["items"].append(formatted_item)
            create_model_template = {
                "dish_name": menu_item.dish_name,
                "spiciness": menu_item.spiciness,
                "dish_base": menu_item.dish_base, 
                "dish_meat": menu_item.dish_meat
            }
            menu_items_template.append(create_model_template)
            if item["item_id"] >= 100:
                menu_items_simple["items"].append(formatted_item)
            else:
                has_diy_dish = True

    if menu_items_simple["items"]:
        for item in menu_items_simple["items"]:
            menu_items_simple["total"] += float(item["price"])

    return {"simple_items": menu_items_simple, "all_items": menu_items_all, "template": menu_items_template, "has_diy": has_diy_dish}

async def update_items_tool(menu: list[dict], items: list[dict]) -> dict[str, Any]:
    """Tool function to process items to update in an order draft based on menu and item details."""
    menu_items_simple = {"items": [], "total": float(0)}
    menu_items_all = {"items": [], "total": float(0)}
    menu_items_template = []
    indices = []
    has_diy_dish = False
    menu_snapshot = MenuSnapshot.from_list(menu)

    items_to_update = []

    for item in items:
        if item["item_id"] < 100:
            # divide multiple qty into single ones for customizable menu items
            items_to_update.extend(
                {"order_item_index": item["order_item_index"], "item_id": item["item_id"], "qty": 1}
                for _ in range(item["qty"])
            )
        else:
            # keep items >= 100 as they are
            items_to_update.append(item)

    for item in items_to_update:
        menu_item = menu_snapshot.items.get(item["item_id"])
        if not menu_item:
            raise ValueError(f"Item not found in menu: {item["item_id"]}")
        if menu_item.id == item["item_id"]:
            indices.append(item["order_item_index"])
            formatted_item = {
                    "item_id": item["item_id"],
                    "dish_name": menu_item.dish_name,
                    "qty": item["qty"],
                    "price": menu_item.price,
                }
            menu_items_all["items"].append(formatted_item)
            create_model_template = {
                "dish_name": menu_item.dish_name,
                "spiciness": menu_item.spiciness,
                "dish_base": menu_item.dish_base, 
                "dish_meat": menu_item.dish_meat
            }
            menu_items_template.append(create_model_template)
            if item["item_id"] >= 100:
                menu_items_simple["items"].append(formatted_item)
            else:
                has_diy_dish = True

    if menu_items_simple["items"]:
        for item in menu_items_simple["items"]:
            menu_items_simple["total"] += float(item["price"])

    return {"simple_items": menu_items_simple, "all_items": menu_items_all, "template": menu_items_template, "has_diy": has_diy_dish, "indices": indices}

async def remove_items_tool(menu, items_to_remove: list[dict]) -> list[dict]:
    """Tool function to process items to remove from an order draft based on item details."""
    return items_to_remove
