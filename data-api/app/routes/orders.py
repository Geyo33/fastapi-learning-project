from fastapi import APIRouter, HTTPException, status
from app.schemas import CustomerOrder, CreateOrderRequest, UpdateOrderRequest, DeleteOrderRequest
from app.storage import load_ci, save_ci, load_ci_validated, save_ci_validated
from app.sql_requests.requests import *

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])

@router.get("/is_open/{order_id}", response_model=bool)
async def is_order_open(order_id: str):
    """Check if order exists and is open"""     
    is_open = order_exist(order_id)
    return is_open

@router.post("/create_order", response_model=CustomerOrder, status_code=status.HTTP_201_CREATED)
async def create_order(req: CreateOrderRequest) -> CustomerOrder:
    """Create a new order or add items to an existing order"""
    customers_info = load_ci()
    current_order = CustomerOrder(**{"customer_info": req.user_context, "customer_order": req.order, "status": "open"})
    if order_exist(req.user_context.user_id):
        add_item_db(current_order.customer_info.user_id, current_order.customer_order.model_dump(), current_order.status)
    else:
        create_order_db(current_order.customer_info.user_id, current_order.customer_order.model_dump(), current_order.status)
    customers_info[current_order.customer_info.user_id] = req.user_context.model_dump()
    save_ci(customers_info)

    return current_order

@router.put("/validate_order/{order_id}", response_model=CustomerOrder, status_code=status.HTTP_201_CREATED)
async def validate_order(order_id: str, req: UpdateOrderRequest) -> CustomerOrder:
    """Validate an order"""
    if order_exist(order_id):
        if order_complete(order_id):
            customers_info = load_ci()
            customers_info_validated = load_ci_validated()
            current_order = CustomerOrder(**{"customer_info": req.user_context, "customer_order": req.order, "status": "validated"})
            update_order_db(current_order.customer_info.user_id, current_order.customer_order.model_dump(), current_order.status)
            customers_info_validated[current_order.customer_info.user_id] = req.user_context.model_dump()
            customers_info.pop(current_order.customer_info.user_id)
            save_ci_validated(customers_info_validated)
            save_ci(customers_info)


            return current_order 
        else:
            return CustomerOrder(**{"customer_info": req.user_context, "customer_order": req.order, "status": "open"})
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

@router.get("/{order_id}", response_model=CustomerOrder)
async def get_order(order_id: str):
    """retrieve a specific order"""    
    if order_exist(order_id):
        order = get_order_db(order_id)
        return order
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

@router.put("/{order_id}", response_model=CustomerOrder)
async def update_order(order_id: str, req: UpdateOrderRequest):
    """Update order""" 
    if order_exist(order_id):
        customers_info = load_ci()
        current_order = CustomerOrder(**{"customer_info": req.user_context, "customer_order": req.order, "status": "open"})
        update_order_db(current_order.customer_info.user_id, current_order.customer_order.model_dump(), current_order.status)
        customers_info[current_order.customer_info.user_id] = req.user_context.model_dump()
        save_ci(customers_info)

        return current_order 

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

@router.put("/delete_from_order/{order_id}", response_model=CustomerOrder)
async def delete_from_order(order_id: str, req: DeleteOrderRequest):
    """delete items from order"""  
    if order_exist(order_id):
        customers_info = load_ci()
        current_order = CustomerOrder(**{"customer_info": req.user_context, "customer_order": req.order, "status": "open"})
        delete_items_db(current_order.customer_info.user_id, current_order.customer_order.model_dump(), req.items_to_remove, current_order.status)
        customers_info[current_order.customer_info.user_id] = req.user_context.model_dump()
        save_ci(customers_info)

        return current_order 

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order(order_id: str):
    """Delete an open order"""
    if order_exist(order_id):
        customers_info = load_ci()
        delete_order_db(order_id)
        customers_info.pop(order_id)
        save_ci(customers_info)
        return
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")