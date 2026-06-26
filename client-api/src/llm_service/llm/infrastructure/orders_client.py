import httpx
from typing import Optional, Any, Dict, List
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import logging
from src.llm_service.config import settings
from src.llm_service.models.schemas import OrderSuggestion, UserContext, CustomerOrder

logger = logging.getLogger(__name__)

class OrdersClient:
    _instance: Optional['OrdersClient'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):  # Singleton pattern - only init once
            return
        self.base_url = str(settings.orders_api_base_url)
        self.restaurants_url = str(settings.restaurants_api_base_url)
        self.timeout = httpx.Timeout(settings.orders_api_timeout, connect=settings.orders_api_timeout_connect)
        self.auth_header = {"Authorization": f"Bearer {settings.orders_api_token}"} if settings.orders_api_token else {}
        self._client: Optional[httpx.AsyncClient] = None
        self._initialized = True
    
    async def startup(self):
        """Called on FastAPI startup."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self.auth_header,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
        logger.info(f"OrdersClient connected to {self.base_url}")
    
    async def shutdown(self):
        """Called on FastAPI shutdown."""
        if self._client:
            await self._client.aclose()
            logger.info("OrdersClient connection closed")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), retry=retry_if_exception_type(httpx.RequestError))
    async def order_exists(self, order_id: str) -> bool:
        if not self._client:
            raise RuntimeError("Client not started")
        url = f"{self.base_url}/is_open/{order_id}"
        resp = await self._client.get(url)
        resp.raise_for_status()
        exists: bool = resp.json()
        return exists

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), retry=retry_if_exception_type(httpx.RequestError))
    async def create_order(self, order_draft: OrderSuggestion, user_context: UserContext) -> str:
        if not self._client:
            raise RuntimeError("Client not started")
        url = f"{self.base_url}/create_order"
        data = {
            "order": order_draft.model_dump(exclude_unset=True),
            "user_context": user_context.model_dump(exclude_unset=True),
        }
        resp = await self._client.post(url, json=data)
        resp.raise_for_status()
        order_data = resp.json()
        logger.info(f"Appended to order {order_data['customer_info']['user_id']}")
        return f"Appended to order : {user_context.user_id}"
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), retry=retry_if_exception_type(httpx.RequestError))
    async def get_order(self, order_id: str) -> CustomerOrder:
        if not self._client:
            raise RuntimeError("Client not started")
        url = f"{self.base_url}/{order_id}"
        resp = await self._client.get(url)
        resp.raise_for_status()
        return CustomerOrder(**resp.json())
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), retry=retry_if_exception_type(httpx.RequestError))
    async def update_order(self, order_id: str, order_draft: OrderSuggestion, user_context: UserContext) -> str:
        if not self._client:
            raise RuntimeError("Client not started")
        url = f"{self.base_url}/{order_id}"
        updates = {
            "order": order_draft.model_dump(exclude_unset=True),
            "user_context": user_context.model_dump(exclude_unset=True),
        }
        resp = await self._client.put(url, json=updates)
        resp.raise_for_status()
        order_data = resp.json()
        logger.info(f"Updated order {order_data['customer_info']['user_id']}")
        return f"Updated order : {user_context.user_id}"
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), retry=retry_if_exception_type(httpx.RequestError))
    async def remove_from_order(self, order_id: str, order_draft: OrderSuggestion, user_context: UserContext, items_to_remove: list[dict]) -> str:
        if not self._client:
            raise RuntimeError("Client not started")
        url = f"{self.base_url}/delete_from_order/{order_id}"
        remove_update = {
            "order": order_draft.model_dump(exclude_unset=True),
            "user_context": user_context.model_dump(exclude_unset=True),
            "items_to_remove": items_to_remove,
        }
        resp = await self._client.put(url, json=remove_update)
        resp.raise_for_status()
        order_data = resp.json()
        logger.info(f"Updated order {order_data['customer_info']['user_id']}")
        return f"Updated order : {user_context.user_id}"
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), retry=retry_if_exception_type(httpx.RequestError))
    async def remove_order(self, order_id: str) -> bool:
        if not self._client:
            raise RuntimeError("Client not started")
        try:
            url = f"{self.base_url}/{order_id}"
            resp = await self._client.delete(url)
            resp.raise_for_status()
            if resp.status_code == 204:
                deleted = True
            else:
                deleted = False
            if deleted:
                logger.info(f"Removed order {order_id}")
                return deleted
            else:
                logger.info(f"Order {order_id} not found")
                return deleted
        except httpx.HTTPError as e:
            logger.error("HTTP error from LLM API: %s", e)
            return False
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), retry=retry_if_exception_type(httpx.RequestError))
    async def validate_order(self, order_id: str, order_draft: OrderSuggestion, user_context: UserContext) -> bool:
        if not self._client:
            raise RuntimeError("Client not started")
        url = f"{self.base_url}/validate_order/{order_id}"
        updates = {
            "order": order_draft.model_dump(exclude_unset=True),
            "user_context": user_context.model_dump(exclude_unset=True),
        }
        resp = await self._client.put(url, json=updates)
        resp.raise_for_status()
        order_data = resp.json()
        if order_data["customer_order"]["raw_text"] == "incomplete_order":
            return False
        else:
            logger.info(f"Validated order {order_data['customer_info']['user_id']}")
            return True
    
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5), retry=retry_if_exception_type(httpx.RequestError))
    async def get_menu(self, restaurant_id: str) -> List[Dict[str, Any]]:
        if not self._client:
            raise RuntimeError("Client not started")
        url = f"{self.restaurants_url}/{restaurant_id}/menu"
        resp = await self._client.get(url)
        resp.raise_for_status()
        return resp.json()
    
# Dependency injection factory - RETURNS OrdersClient directly
async def get_orders_client() -> OrdersClient:
    client = OrdersClient()
    if not client._client:
        await client.startup()
        # Quick health check
        try:
            resp = await client._client.get(f"{client.base_url}/health", timeout=httpx.Timeout(2.0))
            if resp.status_code != 200:
                raise ValueError("Orders service unhealthy")
        except:
            raise ValueError("Orders service unreachable")
    return client
