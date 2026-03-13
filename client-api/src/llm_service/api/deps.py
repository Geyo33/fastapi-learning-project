from fastapi import Depends, HTTPException, Request
from typing import Any

from src.llm_service.services.orchestrator import OrderOrchestrator
from src.llm_service.llm.infrastructure.orders_client import OrdersClient, get_orders_client


def get_settings(request: Request) -> Any:
    return request.app.state.settings


def get_logger(request: Request) -> Any:
    return request.app.state.logger


def get_llm_client(request: Request) -> Any:
    client = getattr(request.app.state, "llm_client", None)
    if client is None:
        raise HTTPException(status_code=500, detail="LLM client not initialized")
    return client


def get_orchestrator(request: Request) -> Any:
    orch = getattr(request.app.state, "orchestrator", None)
    if orch is None:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")
    return orch

async def get_order_orchestrator(orders_client: OrdersClient = Depends(get_orders_client)):
    return OrderOrchestrator(orders_client)
