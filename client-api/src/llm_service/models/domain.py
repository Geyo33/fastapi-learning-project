from typing import List, Dict, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from uuid import uuid4

from src.llm_service.models.schemas import MenuItem, OrderItem, OrderSuggestion


@dataclass
class ItemsDraft:
    """
    Ephemeral, authoritative items draft used in OrderDraft.
    """
    item_id: int =field(default_factory=int)
    qty: int = field(default_factory=int)
    spiciness: str = "None"
    dish_meat: str = "None"
    dish_base: str = "None"
    price: float = 0

@dataclass
class OrderDraft:
    """
    Ephemeral, authoritative order draft.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    items: Dict[str, ItemsDraft] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, str] = field(default_factory=dict)
    item_draft = ItemsDraft()

    def build_items_draft(self, item_id: int, qty: int, spiciness: str = "None", dish_meat: str = "None", dish_base: str = "None") -> None:
        """Builds the item draft with the given parameters."""
        self.item_draft = ItemsDraft(item_id, qty, spiciness, dish_meat, dish_base)

    def extra_id(self, item_id: int) -> str:
        """Generates a unique id for the item based on its id and options."""
        full_id = f"{item_id}|{self.item_draft.spiciness}-{self.item_draft.dish_base}-{self.item_draft.dish_meat}"
        return full_id

    def add_item(self, item_id: int) -> None:
        """Adds item to draft, if item with same id and options already exists, it updates the qty."""
        if self.item_draft.qty <= 0:
            raise ValueError("qty must be positive")
        full_id = self.extra_id(item_id) #generate full id based on item id and options
        if self.items.get(full_id):
            self.item_draft.qty = self.items.get(full_id).qty+self.item_draft.qty

        self.items[full_id] = self.item_draft #add item draft to items dict with full id as key
        self.updated_at = datetime.now()

    def remove_item(self, item_index: int, qty: Optional[int] = None) -> ItemsDraft:
        """Removes item from draft, if qty is provided, it updates the qty, otherwise it removes the item."""
        if len(list(self.items)) < item_index:
            raise KeyError(f"item not in draft: {item_index}")
        item_to_remove = list(self.items)[item_index]
        removed_item = self.items[item_to_remove]
        if qty is None:
            self.items.pop(item_to_remove) 
        else:
            if qty <= 0:
                raise ValueError("qty must be positive")
            new_qty = self.items[item_to_remove].qty - qty
            if new_qty > 0:
                self.items[item_to_remove].qty = new_qty
            else:
                self.items.pop(item_to_remove) 
        self.updated_at = datetime.now()
        return asdict(removed_item)

    def update_item(self, item_index: int, item: OrderItem) -> None:
        """Updates item in draft based on item index and new item data."""
        if item.qty <= 0:
            raise ValueError("qty must be positive")
        item_to_update = list(self.items)[item_index]
        self.items[item_to_update] = ItemsDraft(item.item_id, item.qty, item.spiciness, item.dish_meat, item.dish_base, item.price)
        self.updated_at = datetime.now()

    def update_qty(self, item_index: int, qty: int) -> None:
        """Updates item qty in draft based on item index and new qty."""
        if qty <= 0:
            raise ValueError("qty must be positive")
        item_to_update = list(self.items)[item_index]
        self.items[item_to_update].qty = qty
        self.updated_at = datetime.now()

    def compute_total(self, menu: List[MenuItem]) -> float:
        """Computes total price of the order draft based on the menu prices."""
        menu_map = {m.id: m for m in menu}
        total = 0.0
        for full_id, item_draft in self.items.items():
            menu_item = menu_map.get(item_draft.item_id)
            if menu_item is None:
                raise KeyError(f"item not found in menu: {full_id}")
            item_draft.price = float(menu_item.price)
            total += float(menu_item.price) * item_draft.qty
        return round(total, 2)
    
    def to_suggestion(self, menu: List[MenuItem], raw_text: Optional[str] = None) -> OrderSuggestion:
        """From OrderDraft to OrderSuggestion."""
        total = self.compute_total(menu)
        items = []
        is_complete = True
        for full_id, item_draft in self.items.items():
            items.append(OrderItem(item_id=item_draft.item_id, qty=item_draft.qty, price=item_draft.price, spiciness=item_draft.spiciness, dish_meat=item_draft.dish_meat, dish_base=item_draft.dish_base))
            if item_draft.spiciness == 'indéfini' or item_draft.dish_base == 'indéfini' or item_draft.dish_meat == 'indéfini':
                is_complete = False
        if not is_complete:
            raw_text = "incomplete_order"
        return OrderSuggestion(items=items, total=total, raw_text=raw_text or "")
    
    def to_draft(self, order_suggestion: OrderSuggestion):
        """From OrderSuggestion to OrderDraft."""
        self.items = {}
        for item in order_suggestion.items:
            if item.qty <= 0:
                raise ValueError("qty must be positive")
            self.build_items_draft(item.item_id, item.qty, item.spiciness, item.dish_meat, item.dish_base)
            full_id = self.extra_id(item.item_id)
            self.items[full_id] = self.item_draft
        self.updated_at = datetime.now()
    
    def order_draft_to_str(self, menu: list[MenuItem]) -> str:
        """Converts the order draft to a human-readable string format, including a markdown table of items and the total price."""
        menu_map = {m.id: m for m in menu}
        total = self.compute_total(menu)
        if not self.items:
            self.current_order = "Aucun article dans la commande"
            return "Aucun article dans la commande"

        # Markdown table header
        headers = [
            "Index",
            "Dish Name",
            "Spiciness",
            "Base",
            "Meat",
            "Quantity",
            "Price (€)"
        ]
        separator = "| " + " | ".join(["---"] * len(headers)) + " |"
        # Prepare table rows
        rows = []
        for order_item_index, (full_id, item_draft) in enumerate(self.items.items()):
            menu_item = menu_map.get(item_draft.item_id)
            if menu_item is None:
                raise KeyError(f"Item not found in menu: {full_id}")

            spiciness = item_draft.spiciness if item_draft.spiciness != "None" else ""
            base = item_draft.dish_base if item_draft.dish_base != "None" else ""
            meat = item_draft.dish_meat if item_draft.dish_meat != "None" else ""
            qty = item_draft.qty
            price = f"{item_draft.price:.2f}"

            rows.append(f"| {order_item_index} | {menu_item.dish_name} | {spiciness} | {base} | {meat} | {qty} | {price} |")
        # Combine everything
        table = (
            f"| {' | '.join(headers)} |\n"
            f"{separator}\n"
            + "\n".join(rows)
        )

        # Add total
        order_str = f"{table}\n\n**Prix de la commande = {total:.2f} €**"
        self.current_order = order_str
        return order_str



@dataclass
class MenuSnapshot:
    """
    Lightweight snapshot of menu items used for validation and LLM context.
    """
    items: Dict[str, MenuItem] = field(default_factory=dict)
    taken_at: datetime = field(default_factory=datetime.now())

    @classmethod
    def from_list(cls, menu_list: List[MenuItem]) -> "MenuSnapshot":
        return cls(items={m.id: m for m in menu_list}, taken_at=datetime.now())

    def to_list(self) -> List[MenuItem]:
        return list(self.items.values())