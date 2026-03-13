from typing import List, Optional, Literal, Dict, Any, Annotated, Type
from pydantic import BaseModel, create_model, Field
from pydantic.types import StringConstraints, PositiveInt, NonNegativeFloat


NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]

ItemID = int # used to determine if item is customizable(DIY) or not; if <100 then DIY, else simple menu item
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

class ChatRequest(BaseModel):
    user_message: NonEmptyStr
    context: UserContext
    order: OrderSuggestion
    menu_listing: Optional[List[MenuItem]] = None
    max_tokens: int = Field(8192, gt=0)

class AddItem(BaseModel):
    item_id: ItemID
    qty: Qty
    
class RemoveItem(BaseModel):
    order_item_index: int
    qty: Qty

class UpdateItem(BaseModel):
    order_item_index: int
    item_id: ItemID
    qty: Qty

class OrderSuggestionDIY(BaseModel):
    items: List[OrderItem]

class ValidateOrderRequest(BaseModel):
    suggested_order: OrderSuggestion
    user_context: UserContext
    menu_snapshot: Optional[List[MenuItem]] = None

class ValidateOrderResponse(BaseModel):
    is_valid: bool
    response: str

class OrderRequest(BaseModel):
    order: OrderSuggestion
    user_context: UserContext
    items_to_remove: Optional[list[dict]] = None

class FullOrderRequest(BaseModel):
    order_request: OrderRequest
    tools_details: dict

class CustomerOrder(BaseModel):
    customer_info: UserContext
    customer_order: OrderSuggestion
    status: str

class AddItems(BaseModel):
    items: List[AddItem] = Field(..., description="A list of menu items to add to the order.")

class RemoveItems(BaseModel):
    items_to_remove: List[RemoveItem] = Field(..., description="A list of menu items to remove from the current order.")

class UpdateItems(BaseModel):
    items: List[UpdateItem] = Field(..., description="A list of menu items to update from the current order.")


def create_dish_order_items(
    menus: List[Dict[str, Any]]
) -> Type[OrderSuggestionDIY]:
    """
    Create dish-specific OrderItem subclasses and return OrderSuggestionDIY model.
    
    Returns:
        OrderSuggestionDIY model with all dish-specific OrderItem types unioned in items list
    """
    dish_models: Dict[str, Type[OrderItem]] = {}
    
    for menu in menus:
        dish_name = menu["dish_name"]
        
        sp_vals = menu.get("spiciness")
        base_vals = menu.get("dish_base")
        meat_vals = menu.get("dish_meat")
        
        SpType = Literal[tuple(sp_vals)]
        BaseType = Literal[tuple(base_vals)]
        MeatType = Literal[tuple(meat_vals)]
        
        # Create dish-specific OrderItem
        dish_model = create_model(
            f"OrderItem_{dish_name.title()}",
            __base__=OrderItem,
            spiciness=(SpType, None),
            dish_base=(BaseType, None),
            dish_meat=(MeatType, None),
        )
        dish_models[dish_name] = dish_model
    
    # Create Union type of all dish models for the items list
    if not dish_models:
        ItemsUnion = OrderItem
    else:
        import typing
        ItemsUnion = typing.Union[tuple(dish_models.values())]
    
    # Create customized OrderSuggestionDIY with dish-specific items union
    OrderSuggestionDynamic = create_model(
        "OrderSuggestion", 
        items=(List[ItemsUnion], []),
        __base__=OrderSuggestionDIY
    )
    
    return OrderSuggestionDynamic