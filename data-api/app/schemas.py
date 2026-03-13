from enum import Enum
from typing import List, Optional, Annotated
from pydantic import BaseModel
from pydantic.types import StringConstraints, PositiveInt, NonNegativeFloat

NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]
ItemID = int
Qty = PositiveInt
Price = NonNegativeFloat
Total = NonNegativeFloat

class OrderStatus(str, Enum):
    open = "open"
    in_progress = "validated"
    closed = "closed"

class UserContext(BaseModel):
    user_id: NonEmptyStr
    user_history: Optional[list[dict[str, str]]] = []
    language: Optional[NonEmptyStr] = "fr"

class OrderItem(BaseModel):
    item_id: ItemID
    qty: Qty
    price: Price
    spiciness: str
    dish_base: str
    dish_meat: str

class OrderSuggestion(BaseModel):
    items: List[OrderItem]
    total: Total
    raw_text: Optional[str] = None

class CreateOrderRequest(BaseModel):
    order: OrderSuggestion
    user_context: UserContext
    items_to_remove: Optional[list[dict]] = None

class UpdateOrderRequest(BaseModel):
    order: OrderSuggestion
    user_context: UserContext
    items_to_remove: Optional[list[dict]] = None

class DeleteOrderRequest(BaseModel):
    order: OrderSuggestion
    user_context: UserContext
    items_to_remove: list[dict] = None

class CustomerOrder(BaseModel):
    customer_info: UserContext
    customer_order: OrderSuggestion
    status: OrderStatus