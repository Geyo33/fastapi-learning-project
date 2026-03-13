import pytest

from src.llm_service.models.schemas import ChatRequest, UserContext, MenuItem, OrderSuggestion
from src.llm_service.custom_exceptions import LLMServiceException, OrderBuildingException


@pytest.mark.asyncio
async def test_health(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_chat_endpoint(client):
    payload = ChatRequest(
        user_message="Hello",
        context=UserContext(user_id="u1"),
        order=OrderSuggestion(items=[], total=0.0),
        menu_listing=[MenuItem(id=1, dish_name="A", price=1.0, description="", category="x")],
    ).model_dump()
    resp = client.post("/api/v1/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "order_request" in data
    assert data["order_request"]["order"]["items"]

@pytest.mark.asyncio
async def test_chat_endpoint_exceptions(client):
    # Test with missing required fields
    payload = {"user_message": "Hello"}
    resp = client.post("/api/v1/chat", json=payload)
    assert resp.status_code == 422  # Unprocessable Entity due to validation error

    # Test with invalid data types
    payload = {
        "user_message": "Hello",
        "context": {"user_id": 123},  # user_id should be a string
        "order": {"items": [], "total": "not_a_number"},  # total should be a float
    }
    resp = client.post("/api/v1/chat", json=payload)
    assert resp.status_code == 422  # Unprocessable Entity due to validation error

    # Simulated LLM error using the DummyOrch fixture: the DummyOrch raises an LLMServiceException when user_id is "fail_test_api"
    payload = ChatRequest(
        user_message="Hello",
        context=UserContext(user_id="fail_test_api"),
        order=OrderSuggestion(items=[], total=0.0),
        menu_listing=[MenuItem(id=1, dish_name="A", price=1.0, description="", category="x")]
    ).model_dump()
    resp = client.post("/api/v1/chat", json=payload)
    assert resp.status_code == 400  # Error due to simulated LLM error

    # Simulated OrderBuilding error using the DummyOrch fixture: the DummyOrch raises an OrderBuildingException when user_id is "fail_test_order"
    payload = ChatRequest(
        user_message="Hello",
        context=UserContext(user_id="fail_test_order"),
        order=OrderSuggestion(items=[], total=0.0),
        menu_listing=[MenuItem(id=1, dish_name="A", price=1.0, description="", category="x")]
    ).model_dump()
    resp = client.post("/api/v1/chat", json=payload)
    assert resp.status_code == 400  # Error due to simulated OrderBuilding error


@pytest.mark.asyncio
async def test_validate_order_endpoint(client):
    payload = {
        "suggested_order": {
            "items": [{"item_id": 104, "qty": 2, "price": 1.0, "spiciness": "None", "dish_base": "None", "dish_meat": "None"}],
            "total": 2.0,
            "raw_text": "2 A"
        },
        "user_context": {"user_id": "u1"},
        "menu_snapshot": [
            {"id": 104, "dish_name": "A", "price": 1.0, "description": "", "category": "x"}
        ]
    }
    resp = client.post("/api/v1/validate-order", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_valid"] is True
    assert data["response"] == "Votre commande a été validée !"

@pytest.mark.asyncio
async def test_create_order_endpoint(client):
    payload = {
        "order": {
            "items": [{"item_id": 104, "qty": 2, "price": 1.0, "spiciness": "None", "dish_base": "None", "dish_meat": "None"}],
            "total": 2.0,
            "raw_text": "2 A"
        },
        "user_context": {"user_id": "u1"},
        "items_to_remove": []
    }
    resp = client.post("/api/v1/create-order", json=payload)
    assert resp.status_code == 200
    stored = resp.json()
    assert "created" in stored

@pytest.mark.asyncio
async def test_update_order_endpoint(client):
    payload = {
        "order": {
            "items": [{"item_id": 104, "qty": 2, "price": 1.0, "spiciness": "None", "dish_base": "None", "dish_meat": "None"}],
            "total": 2.0,
            "raw_text": "2 A"
        },
        "user_context": {"user_id": "u1"},
        "items_to_remove": []
    }
    resp = client.post("/api/v1/update-order/<order_id>", json=payload)
    assert resp.status_code == 200
    stored = resp.json()
    assert "updated" in stored

@pytest.mark.asyncio
async def test_remove_from_order_endpoint(client):
    payload = {
        "order": {
            "items": [{"item_id": 104, "qty": 2, "price": 1.0, "spiciness": "None", "dish_base": "None", "dish_meat": "None"}],
            "total": 2.0,
            "raw_text": "2 A"
        },
        "user_context": {"user_id": "u1"},
        "items_to_remove": [{"item_id": 104, "qty": 1}]
    }
    resp = client.post("/api/v1/remove-from-order/<order_id>", json=payload)
    assert resp.status_code == 200
    stored = resp.json()
    assert "removed" in stored

@pytest.mark.asyncio
async def test_remove_order_endpoint(client):
    payload = {
        "user_context": {"user_id": "u1"}
    }
    resp = client.post("/api/v1/remove-order/<user_id>", json=payload)
    assert resp.status_code == 200
    removed = resp.json()
    assert removed is True

@pytest.mark.asyncio
async def test_order_exists_endpoint(client):
    resp = client.get("/api/v1/order-exists/<user_id>")
    assert resp.status_code == 200
    exists = resp.json()
    assert exists is False

@pytest.mark.asyncio
async def test_get_order_endpoint(client):
    resp = client.get("/api/v1/get-order/<user_id>")
    assert resp.status_code == 200
    order = resp.json()
    assert order["customer_info"]["user_id"] == "u1"
    assert order["customer_order"]["items"] == []
    assert order["customer_order"]["total"] == 0.0

@pytest.mark.asyncio
async def test_get_menu_endpoint(client):
    resp = client.get("/api/v1/get-menu/<restaurant_id>")
    assert resp.status_code == 200
    menu = resp.json()
    assert len(menu) == 3
    assert menu[0]["id"] == 104
    assert menu[0]["dish_name"] == "Baozi"
    assert menu[0]["price"] == 8.0
    assert menu[1]["id"] == 101
    assert menu[1]["dish_name"] == "Nems porc"
    assert menu[1]["price"] == 5.0
    assert menu[2]["id"] == 2
    assert menu[2]["dish_name"] == "Wok thaï"
    assert menu[2]["price"] == 13.0