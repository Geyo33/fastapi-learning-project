from fastapi import APIRouter, Depends, HTTPException, status
from src.llm_service.models.schemas import ChatRequest, OrderSuggestion, ValidateOrderRequest, ValidateOrderResponse, OrderRequest, FullOrderRequest, CustomerOrder
from src.llm_service.api.deps import get_orchestrator, get_order_orchestrator
from src.llm_service.custom_exceptions import LLMServiceException

router = APIRouter()


# Simple health endpoint
@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# Wrapper endpoint: LLM service
@router.post("/chat", response_model=FullOrderRequest, status_code=status.HTTP_200_OK)
async def chat_endpoint(req: ChatRequest, orchestrator=Depends(get_orchestrator)):
    """
    Accepts user message + user context + menu list, forwards to orchestrator which
    calls the LLM client, parses output, and returns a FullOrderRequest.
    """
    try:
        response: FullOrderRequest = await orchestrator.handle_chat(req)
    except LLMServiceException as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return response

@router.post("/validate-order", response_model=ValidateOrderResponse, status_code=status.HTTP_200_OK)
async def validate_order_endpoint(req: ValidateOrderRequest, orchestrator=Depends(get_orchestrator), order_orchestrator=Depends(get_order_orchestrator)):
    """
    Validates an OrderSuggestion against provided menu_snapshot (or internal rules) and check if the order is complete(forwards to LLM if not).
    Returns ValidateOrderRequest.
    """
    try:
        validated: OrderSuggestion = await orchestrator.validate_order(req)
        is_valid: bool = await order_orchestrator.validate_order(OrderRequest(order=validated, user_context=req.user_context))
        if is_valid:
            response: str = f"Votre commande a été validée !"
        else:
            payload = {"user_message": "Je souhaite valider ma commande.", "user_id": req.user_context.user_id, "user_history": req.user_context.user_history, "menu_listing": req.menu_snapshot}
            response: str = await orchestrator.simple_chat(payload, mode = "clarify", extra = "Some fields are undefined('indéfini')")
    except LLMServiceException as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return ValidateOrderResponse(is_valid=is_valid, response=response)



# Wrapper endpoint: DB storage
@router.post("/create-order", status_code=status.HTTP_200_OK)
async def create_order_endpoint(req: OrderRequest, orchestrator=Depends(get_order_orchestrator)) -> str:
    """
    Creates/Appends and stores an OrderRequest.
    Returns confirmation str.
    """
    try:
        stored: str = await orchestrator.create_order(req)
    except LLMServiceException as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return stored

@router.post("/update-order/{order_id}", status_code=status.HTTP_200_OK)
async def update_order_endpoint(req: OrderRequest, orchestrator=Depends(get_order_orchestrator)) -> str:
    """
    Updates and stores an OrderRequest.
    Returns confirmation str.
    """
    try:
        updated: str = await orchestrator.update_order(req)
    except LLMServiceException as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return updated

@router.post("/remove-from-order/{order_id}", status_code=status.HTTP_200_OK)
async def remove_from_order_endpoint(req: OrderRequest, orchestrator=Depends(get_order_orchestrator)):
    """
    Removes item(s) from an order.
    Returns confirmation str.
    """
    try:
        removed: str = await orchestrator.remove_from_order(req)
    except LLMServiceException as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return removed

@router.post("/remove-order/{user_id}", status_code=status.HTTP_200_OK)
async def remove_order_endpoint(user_id: str, orchestrator=Depends(get_order_orchestrator)):
    """
    Delete an open order if it exists.
    Returns bool.
    """
    try:
        deleted: bool = await orchestrator.remove_order(user_id)
    except LLMServiceException as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return deleted

@router.get("/order-exists/{user_id}", status_code=status.HTTP_200_OK)
async def order_exists_endpoint(user_id: str, orchestrator=Depends(get_order_orchestrator)):
    """
    Checks if an order exists for a given user_id.
    Returns bool.
    """
    try:
        exists: bool = await orchestrator.order_exists(user_id)
    except LLMServiceException as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return exists

@router.get("/get-order/{user_id}", response_model=CustomerOrder, status_code=status.HTTP_200_OK)
async def get_order_endpoint(user_id: str, orchestrator=Depends(get_order_orchestrator)):
    """
    Returns a specific CustomerOrder.
    """
    try:
        validated: CustomerOrder = await orchestrator.get_order(user_id)
    except LLMServiceException as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return validated

@router.get("/get-menu/{restaurant_id}", response_model=list[dict], status_code=status.HTTP_200_OK)
async def get_menu_endpoint(restaurant_id: str, orchestrator=Depends(get_order_orchestrator)):
    """
    Returns the relevant menu list.
    """
    try:
        menu: list[dict] = await orchestrator.get_menu(restaurant_id)
    except LLMServiceException as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return menu
