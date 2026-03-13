from typing import List, Optional, Annotated
from pydantic import BaseModel, Field
from pydantic.types import StringConstraints, PositiveInt, NonNegativeFloat

NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]
ItemID = int
Qty = PositiveInt
Price = NonNegativeFloat
Total = NonNegativeFloat


class UserContext(BaseModel):
    user_id: NonEmptyStr
    user_history: Optional[list[dict[str, str]]] = []
    language: Optional[NonEmptyStr] = "fr"


class MenuItem(BaseModel):
    id: ItemID
    dish_name: NonEmptyStr
    price: Price
    description: str
    spiciness: Optional[list] = None
    dish_base: Optional[list] = None
    dish_meat: Optional[list] = None
    category: str

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

class OrderRequest(BaseModel):
    order: OrderSuggestion
    user_context: UserContext
    items_to_remove: Optional[list[dict]] = None

class CustomerOrder(BaseModel):
    customer_info: UserContext
    customer_order: OrderSuggestion
    status: str

class ChatRequest(BaseModel):
    user_message: NonEmptyStr
    context: UserContext
    order: OrderSuggestion
    menu_listing: Optional[List[MenuItem]] = None
    max_tokens: int = Field(8192, gt=0)