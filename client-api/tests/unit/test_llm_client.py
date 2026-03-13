import httpx
import pytest
from pydantic import BaseModel
from src.llm_service.llm.client import LLMClient
from src.llm_service.config import Settings
from src.llm_service.models.schemas import MenuItem, OrderItem, OrderSuggestion
from src.llm_service.custom_exceptions import LLMServiceException, OrderBuildingException


class DummyResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data
    
class DummyFunction(BaseModel):
    name: str
    arguments: str

class DummyToolCall(BaseModel):
    id: str = "1"
    function: DummyFunction

def sample_menu():
    return [
        MenuItem(id=104, dish_name="Baozi", price=8.0, description="", category="entrée"),
        MenuItem(id=101, dish_name="Nems porc", price=5.0, description="", category="entrée"),
        MenuItem(id=2, dish_name="Wok thaï", price=13.0, spiciness=["fort"], dish_base=["riz"], dish_meat=["boeuf"], description="", category="plat"),
    ]

def sample_order_suggestion():
    return OrderSuggestion(
        items=[
            OrderItem(item_id=104, qty=2, price=8.0, spiciness="None", dish_base="None", dish_meat="None"),
            OrderItem(item_id=2, qty=1, price=13.0, spiciness="fort", dish_base="riz", dish_meat="boeuf"),
        ],
        total=29.0,
        raw_text="2 Baozi, 1 Wok thaï"
    )   

@pytest.mark.asyncio
async def test_chat_returns_text(monkeypatch):
    settings = Settings()
    client = LLMClient(settings)
    client._started = True

    # stub out prompt builder to avoid dependency on real logic
    monkeypatch.setattr(client, "_prompt_builder", type("P", (), {"build_chat_prompt": lambda *args, **kwargs: []})())

    class DummyClient:
        async def post(self, endpoint, json, headers):
            return DummyResponse({"choices": [{"message": {"content": "Hello world"}}]})

    client._client = DummyClient()
    result = await client.chat({"user_message": "hi", "user_id": "u", "user_history": [], "menu_listing": []}, max_tokens=10)
    assert "Hello world" in result

@pytest.mark.asyncio
async def test_handle_api_error(monkeypatch):
    settings = Settings()
    client = LLMClient(settings)
    client._started = True

    monkeypatch.setattr(client, "_prompt_builder", type("P", (), {"build_chat_prompt": lambda *args, **kwargs: []})())

    class DummyClient:
        async def post(self, endpoint, json, headers):
            raise httpx.HTTPError("API error")

    client._client = DummyClient()
    with pytest.raises(httpx.HTTPError):
        await client.chat({"user_message": "hi", "user_id": "u", "user_history": [], "menu_listing": []}, max_tokens=10)

@pytest.mark.asyncio
async def test_handle_llm_service_error(monkeypatch):
    # error adding item while building order draft
    settings = Settings()
    client = LLMClient(settings)
    client._started = True

    async def mock_openai_api_call(*args, **kwargs):
        return [DummyToolCall(function=DummyFunction(name="update_items", arguments='{"items": [{"order_item_index": 0, "item_id": 2, "qty": 1}]}'))]
    monkeypatch.setattr(client, "openai_api_call", mock_openai_api_call)
    
    class DummyClient:
        async def post(self, endpoint, json, headers):
            return DummyResponse({"choices": [{"message": {"content": "Hello world"}}]})
    client._client = DummyClient()
    async def mock_update_items(payload, function_response, max_tokens):
        raise OrderBuildingException("Failed to update items in order draft")
    monkeypatch.setattr(client, "chat_update_order", mock_update_items)
    with pytest.raises(LLMServiceException):
        await client.chat_initial({"user_message": "hi", "user_history": [], "user_order": sample_order_suggestion(), "menu_listing": sample_menu()}, max_tokens=10)

@pytest.mark.asyncio
async def test_chat_initial(monkeypatch):
    settings = Settings()
    client = LLMClient(settings)
    client._started = True

    async def mock_openai_api_call(*args, **kwargs):
        return [DummyToolCall(function=DummyFunction(name="add_items", arguments='{"items": [{"item_id": 104, "qty": 2}]}'))]
    monkeypatch.setattr(client, "openai_api_call", mock_openai_api_call)

    class DummyClient:
        async def post(self, endpoint, json, headers):
            return DummyResponse({"choices": [{"message": {"content": "Hello world"}}]})

    client._client = DummyClient()
    result, user_history, tools_details = await client.chat_initial({"user_message": "hi", "user_history": [], "user_order": sample_order_suggestion(), "menu_listing": sample_menu()}, max_tokens=10)
    assert "Avec ceci" in result.raw_text
    assert len(user_history) == 2
    assert tools_details["tools_called"] == ["add_items"]

@pytest.mark.asyncio
async def test_chat_raises_if_not_started():
    settings = Settings()
    client = LLMClient(settings)
    with pytest.raises(RuntimeError):
        await client.chat({})
