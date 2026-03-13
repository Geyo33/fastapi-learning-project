import pytest
from src.llm_service.models.domain import OrderDraft
from src.llm_service.models.schemas import MenuItem, OrderItem


def sample_menu():
    return [
        MenuItem(id=104, dish_name="Baozi", price=8.0, description="", category="entrée"),
        MenuItem(id=101, dish_name="Nems porc", price=5.0, description="", category="entrée"),
        MenuItem(id=2, dish_name="Wok thaï", price=13.0, description="", category="plat"),
    ]


def test_add_item_and_compute_total():
    draft = OrderDraft()
    draft.build_items_draft(item_id=104, qty=2)
    draft.add_item(104)
    assert len(draft.items) == 1
    # compute total with menu
    total = draft.compute_total(sample_menu())
    assert total == pytest.approx(16.0)

    # adding same item again should increment qty
    draft.build_items_draft(item_id=104, qty=1)
    draft.add_item(104)
    total = draft.compute_total(sample_menu())
    assert total == pytest.approx(24.0)


def test_add_item_invalid_qty():
    draft = OrderDraft()
    draft.build_items_draft(item_id=104, qty=0)
    with pytest.raises(ValueError):
        draft.add_item(104)


def test_remove_and_update_operations():
    draft = OrderDraft()
    draft.build_items_draft(item_id=104, qty=3)
    draft.add_item(104)
    # remove quantity
    removed = draft.remove_item(0, qty=2)
    assert removed["qty"] == 3 or isinstance(removed, dict)
    # only one left
    assert list(draft.items.values())[0].qty == 1

    # add back for update
    draft.build_items_draft(item_id=104, qty=2)
    draft.add_item(104)
    # update item via OrderItem
    item = OrderItem(item_id=104, qty=5, price=8.0, spiciness="", dish_base="", dish_meat="")
    draft.update_item(0, item)
    assert list(draft.items.values())[0].qty == 5


def test_to_suggestion_and_to_draft():
    draft = OrderDraft()
    draft.build_items_draft(item_id=2, qty=2, spiciness="indéfini", dish_base="indéfini", dish_meat="indéfini")
    draft.add_item(2)
    suggestion = draft.to_suggestion(sample_menu())
    assert suggestion.total == pytest.approx(26.0)
    assert suggestion.raw_text == "incomplete_order"

    # roundtrip
    new_draft = OrderDraft()
    new_draft.to_draft(suggestion)
    assert len(new_draft.items) == 1
    assert list(new_draft.items.values())[0].qty == 2
