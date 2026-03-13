from typing import Optional, List
import logging

from src.llm_service.models.schemas import ChatRequest, OrderItem, OrderSuggestion, ValidateOrderRequest, MenuItem, OrderRequest, FullOrderRequest, CustomerOrder
from src.llm_service.models.domain import MenuSnapshot
from src.llm_service.llm.client import LLMClient
from src.llm_service.config import Settings
from src.llm_service.llm.infrastructure.orders_client import OrdersClient
from src.llm_service.custom_exceptions import LLMServiceException, OrderValidationException, OrderCreationException, OrderUpdateException, OrderRemovalException, OrderNotFoundException


class Orchestrator:
    def __init__(self, llm_client: LLMClient, settings: Settings, logger: Optional[logging.Logger] = None):
        self.llm = llm_client
        self.settings = settings
        self.logger = logger or logging.getLogger("orchestrator")

    async def startup(self):
        self.logger.info("Orchestrator startup")

    async def shutdown(self):
        self.logger.info("Orchestrator shutdown")

    # High-level: handle incoming chat request, call LLM, parse and validate suggestion
    async def handle_chat(self, req: ChatRequest) -> FullOrderRequest:
        # call LLM client to get structured response
        prompt_payload = {
            "user_message": req.user_message, 
            "user_history": req.context.user_history, 
            "user_order": req.order,
            "menu_listing": req.menu_listing
            }
        self.logger.debug("Calling LLM with payload: %s", prompt_payload)
        order_suggestion, updated_user_history, tools_details = await self.llm.chat_initial(prompt_payload, max_tokens=self.settings.max_tokens)
        if order_suggestion.items:
            try:
                suggestion = await self._parse_and_validate_suggestion(order_suggestion, req.menu_listing)
            except ValueError as e:
                self.logger.error("Failed to parse and validate suggestion: %s", e)
                raise LLMServiceException(f"Failed to parse and validate LLM suggestion: {e}")
        else:
            suggestion = order_suggestion
        req.context.user_history = updated_user_history

        order_request = OrderRequest(**{"order": suggestion, "user_context": req.context, "items_to_remove": tools_details["removed_items"]})

        return FullOrderRequest(order_request=order_request, tools_details=tools_details)


    async def validate_order(self, req: ValidateOrderRequest) -> OrderSuggestion:
        # compute total from menu_snapshot and correct if needed
        try:
            menu = req.menu_snapshot or []
            menu_snapshot = MenuSnapshot.from_list(menu)
            suggested = req.suggested_order
            computed_total = 0.0
            for it in suggested.items:
                menu_item = menu_snapshot.items.get(it.item_id)
                if not menu_item:
                    self.logger.error("Item not found in menu during validation: %s", it.item_id)
                    raise ValueError(f"Item not found in menu: {it.item_id}")
                computed_total += float(menu_item.price) * int(it.qty)
            computed_total = round(computed_total, 2)
        except (ValueError, Exception) as e:
            self.logger.error("Failed to compute total during order validation: %s", e)
            raise OrderValidationException(f"Failed to compute total during order validation: {e}")
        if abs(computed_total - float(suggested.total)) > 0.5:
            self.logger.warning("Total mismatch: suggested=%s computed=%s", suggested.total, computed_total)
            # return corrected suggestion
            corrected = OrderSuggestion(items=suggested.items, total=computed_total, raw_text=(suggested.raw_text or "") + " (corrected)")
            return corrected
        return suggested

    async def _parse_and_validate_suggestion(self, llm_raw: OrderSuggestion, menu_snapshot: List[MenuItem]) -> OrderSuggestion:
        """
        Validate the OrderSuggestion returned from LLM client against menu.
        """
        # llm_raw is already an OrderSuggestion object from llm.chat()
        parsed = {
            "items": [{"item_id": item.item_id, "qty": item.qty, "price": item.price, "spiciness": item.spiciness, "dish_base": item.dish_base, "dish_meat": item.dish_meat} for item in llm_raw.items],
            "total": llm_raw.total,
            "raw_text": llm_raw.raw_text
        }

        # At this point parsed should be a dict with items & total & raw_text
        if not parsed.get("items"):
            raise ValueError("LLM returned no items")
        # Validate item ids exist in menu_snapshot (if provided)
        menu_map = {m.id: m for m in (menu_snapshot or [])}
        for it in parsed["items"]:
            item_id = it.get("item_id")
            qty = int(it.get("qty", 0))
            if not item_id or qty <= 0:
                self.logger.error("Invalid item in suggestion: %s", it)
                raise ValueError(f"Invalid item in suggestion: {it}")
            if menu_map and item_id not in menu_map:
                self.logger.error("Item not in menu: %s", item_id)
                raise ValueError(f"Item not in menu: {item_id}")
        # compute total from menu if menu provided; else trust LLM total
        total = float(parsed.get("total", 0.0))
        if menu_map:
            computed = 0.0
            for it in parsed["items"]:
                computed += float(menu_map[it["item_id"]].price) * int(it["qty"])
                it = OrderItem(**it)  # convert dict to OrderItem for better structure
            computed = round(computed, 2)
            if abs(computed - total) > 0.5:
                self.logger.info("Adjusting total from %s to %s", total, computed)
                total = computed
        # convert to OrderSuggestion pydantic model via dict
        suggestion = OrderSuggestion(items=[itm for itm in parsed["items"]], total=total, raw_text=parsed.get("raw_text"))
        return suggestion
    
    async def simple_chat(self, payload, mode, extra) -> str:
        # call LLM client to get simple str response
        response: str = await self.llm.chat(payload, self.settings.max_tokens, mode, extra)
        return response


class OrderOrchestrator:
    def __init__(self, orders_client: OrdersClient):
        self.orders_client = orders_client
    
    async def create_order(self, req: OrderRequest) -> str:
        try:
            order: str = await self.orders_client.create_order(req.order, req.user_context)
        except Exception as e:
            raise OrderCreationException(f"Failed to create order: {e}")
        return order
    
    async def update_order(self, req: OrderRequest) -> str:
        try:
            order: str = await self.orders_client.update_order(req.user_context.user_id, req.order, req.user_context)
        except Exception as e:
            raise OrderUpdateException(f"Failed to update order: {e}")
        return order
    
    async def remove_from_order(self, req: OrderRequest) -> str:
        try:
            order: str = await self.orders_client.remove_from_order(req.user_context.user_id, req.order, req.user_context, req.items_to_remove)
        except Exception as e:
            raise OrderRemovalException(f"Failed to remove from order: {e}")
        return order
    
    async def remove_order(self, user_id: str) -> str:
        try:
            deleted: bool = await self.orders_client.remove_order(user_id)
        except Exception as e:
            raise OrderRemovalException(f"Failed to remove order: {e}")
        return deleted
    
    async def order_exists(self, user_id: str) -> bool:
        try:
            exists: bool = await self.orders_client.order_exists(user_id)
        except Exception as e:
            raise LLMServiceException(f"Failed to check order existence: {e}")
        return exists

    async def get_order(self, user_id: str) -> CustomerOrder:
        try:
            order: CustomerOrder = await self.orders_client.get_order(user_id)
        except Exception as e:
            raise OrderNotFoundException(f"Failed to get order: {e}")
        return order
    
    async def validate_order(self, req: OrderRequest) -> bool:
        try:
            is_valid: bool = await self.orders_client.validate_order(req.user_context.user_id, req.order, req.user_context)
        except Exception as e:
            raise OrderValidationException(f"Failed to validate order: {e}")
        return is_valid
    
    async def get_menu(self, restaurant_id: str) -> OrderSuggestion:
        try:
            menu: list[dict] = await self.orders_client.get_menu(restaurant_id)
        except Exception as e:
            raise LLMServiceException(f"Failed to get menu: {e}")
        return menu