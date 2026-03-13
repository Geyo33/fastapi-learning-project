import pytest
import logging
from fastapi import FastAPI
from httpx import AsyncClient
import pytest_asyncio
from collections.abc import AsyncGenerator
from starlette.testclient import TestClient

from src.llm_service.custom_exceptions import LLMServiceException, OrderBuildingException
from src.llm_service.main import create_app
from src.llm_service.api.deps import get_orchestrator, get_order_orchestrator
from src.llm_service.models.schemas import FullOrderRequest, OrderRequest, OrderSuggestion, OrderItem, CustomerOrder, UserContext


@pytest.fixture
def logger():
    return logging.getLogger("tests")


@pytest.fixture
def app(logger) -> FastAPI:
    app = create_app(logger)
    return app

@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest_asyncio.fixture
async def async_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    sync_client = TestClient(app)
    async with AsyncClient() as ac:
        ac.app = sync_client.app # set the app for the async client to use the same app instance
        yield ac

def sample_raw_menu():
    return [
        {"id": 104, "dish_name": "Baozi", "price": 8.0, "description": "", "category": "entrée"},
        {"id": 101, "dish_name": "Nems porc", "price": 5.0, "description": "", "category": "entrée"},
        {"id": 2, "dish_name": "Wok thaï", "price": 13.0, "description": "", "category": "plat"}
    ]

# Helper override that returns a dummy orchestrator
class DummyOrch:
    async def handle_chat(self, req):
        if req.context.user_id == "fail_test_api":
            raise LLMServiceException("Simulated LLM error")
        elif req.context.user_id == "fail_test_order":
            raise OrderBuildingException("Simulated order building error")
        # return a minimal FullOrderRequest
        item = OrderItem(item_id=1, qty=1, price=1.0, spiciness="", dish_base="", dish_meat="")
        suggestion = OrderSuggestion(items=[item], total=1.0, raw_text="ok")
        order_req = OrderRequest(order=suggestion, user_context=req.context)
        return FullOrderRequest(order_request=order_req, tools_details={})

    async def validate_order(self, req):
        # simply echo back the suggested order, mimicking the real orchestration logic
        return req.suggested_order


class DummyOrderOrch:
    async def validate_order(self, req):
        return True
    async def create_order(self, req):
        return "created"
    async def update_order(self, req):
        return "updated"
    async def remove_from_order(self, req):
        return "removed"
    async def remove_order(self, req):
        return True
    async def order_exists(self, user_id):
        return False
    async def get_order(self, user_id):
        return CustomerOrder(
            customer_info=UserContext(user_id="u1", user_history=[]), 
            customer_order=OrderSuggestion(items=[], total=0.0, raw_text=""), 
            status="open"
        )
    async def get_menu(self, restaurant_id):
        return sample_raw_menu()


@pytest.fixture(autouse=True)
def override_dependencies(app: FastAPI):
    app.dependency_overrides[get_orchestrator] = lambda: DummyOrch()
    app.dependency_overrides[get_order_orchestrator] = lambda: DummyOrderOrch()
    yield
    app.dependency_overrides.clear()
