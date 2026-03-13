"""
LLMClient: Unified interface for communicating with LLM providers to process restaurant orders.
Leverages prompt builders, formatters, and parsers for clean separation of concerns.
"""

from openai import AsyncOpenAI
from typing import Any, Dict, Optional
import json
import logging
import httpx
from dataclasses import asdict

from src.llm_service.config import Settings
from src.llm_service.models.schemas import MenuItem, OrderSuggestion
from src.llm_service.llm import prompts, formatters, parser
from src.llm_service.llm.tools import add_items_tool, update_items_tool, remove_items_tool
from src.llm_service.models.domain import OrderDraft
from src.llm_service.custom_exceptions import LLMServiceException, OrderBuildingException


class LLMClient:
    """
    Async HTTP client for LLM API calls with structured JSON response handling.
    """

    def __init__(self, settings: Settings, logger: Optional[logging.Logger] = None):
        """
        Initialize LLMClient with configuration and optional logger.
        
        Args:
            settings: Configuration object (LLM endpoint, model, timeouts, etc)
            logger: Optional logger instance (defaults to module logger)
        """
        self.settings = settings
        self.logger = logger or logging.getLogger("llm_client")
        self._client: Optional[httpx.AsyncClient] = None
        self.active_endpoint = self.settings.local_endpoint if self.settings.llm_provider=="local" else self.settings.other_endpoint
        self.active_endpoint_openai = self.settings.local_endpoint_openai if self.settings.llm_provider=="local" else self.settings.other_endpoint_openai
        self.active_api_key = self.settings.local_api_key if self.settings.llm_provider=="local" else self.settings.other_api_key
        self.active_model = self.settings.local_model if self.settings.llm_provider=="local" else self.settings.other_model
        self.client_active = AsyncOpenAI(
            api_key=self.active_api_key,
            base_url=str(self.active_endpoint_openai)
        )
        self._started = False
        self.current_order = OrderDraft()
        self.menu = []
        
        # Prompt builder for dynamic prompt construction
        self._prompt_builder = prompts.PromptBuilder(logger_instance=self.logger)


    async def startup(self) -> None:
        """Initialize HTTP client and resources."""
        if not self._started:
            self._client = httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds)
            self._started = True
            self.logger.info("LLMClient started with endpoint: %s", self.active_endpoint)

    async def shutdown(self) -> None:
        """Close HTTP client and cleanup resources."""
        if self._client:
            await self._client.aclose()
            self._client = None
            self._started = False
            self.logger.info("LLMClient shutdown")

    async def openai_api_call(self, prompt: list[dict[str, str]], max_tokens: Optional[int] = None, tools: Optional[list] = None):
        self.logger.debug("Decision call %s (model=%s)", self.active_endpoint_openai, self.active_model)
        try:
            response = await self.client_active.chat.completions.create(
                model=self.active_model,
                messages=prompt,
                max_tokens=max_tokens or self.settings.max_tokens,
                temperature=float(self.settings.temperature),
                tools=tools,
                tool_choice="auto",
            )

            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls
            return tool_calls
        except Exception as e:
            self.logger.error("Error during OpenAI API call: %s", e)
            raise httpx.HTTPError(f"Error during OpenAI API call: {e}") from e
        

    def post_tool_action(self, function_name):
        """
        Formats a str response with a markdown table and builds an OrderSuggestion from OrderDraft after a tool call.
        Returns an OrderSuggestion.
        """
        current_order: OrderDraft = self.current_order
        if function_name == "add_items":
            chat_output = f"""{current_order.order_draft_to_str(self.menu)}
-----
Avec ceci ?"""
        elif function_name == "update_items":
            chat_output = f"""{current_order.order_draft_to_str(self.menu)}
-----
J'ai modifié votre commande, cela vous convient-il ?"""
        elif function_name == "remove_items":
            chat_output = f"""{current_order.order_draft_to_str(self.menu)}
-----
J'ai effectué les modifications pour votre commande, cela vous convient-il ?"""
        else:
            chat_output = "No tool used"
        suggestion: OrderSuggestion = current_order.to_suggestion(self.menu, chat_output)
        return suggestion

    async def chat(self, payload: Dict[str, Any], max_tokens: Optional[int] = None, mode = "chat", extra = None) -> str:
        """
        Send a simple chat request to the LLM and return a response.
        
        Args:
            payload: Dict with keys:
                - user_message (str): Customer's order request
                - user_history (list[dict]): Customer's chat history
                - user_order (OrderSuggestion): Customer's current order suggestion for context
                - menu_listing (List[MenuItem]): Available menu items for context
            max_tokens: Optional token limit (defaults to settings.max_tokens)
            mode (str): Mode for prompt formatting (e.g., "chat", "incomplete_order")
            extra(str): Additional context for prompt formatting (e.g., "incomplete_order" to notify LLM of missing info in order)
            
        Returns:
            str: LLM response
            
        Raises:
            RuntimeError: If client not started
            httpx.HTTPError: If API request fails
        """
        if not self._started or self._client is None:
            raise RuntimeError("LLMClient not started. Call startup() first.")

        user_message = payload.get("user_message", "")
        self.menu = payload.get("menu_listing")
        schema_mode = "chat"

        # Build prompt using dedicated prompt builder
        prompt: list[dict[str, str]] = self._prompt_builder.build_chat_prompt(
            user_message=user_message,
            order = self.current_order,
            menu_items=self.menu or [],
            mode=mode,
            extra=extra,
        )

        # Prepare request body
        body = self._build_request_body(prompt, schema_mode, max_tokens)
        headers = self._build_headers()
        endpoint = str(self.active_endpoint)

        # Send request
        self.logger.debug("POST %s (model=%s)", endpoint, self.active_model)
        try:
            response = await self._client.post(endpoint, json=body, headers=headers)
            response.raise_for_status()
            response_data = response.json()
            output: str = self._extract_response_content(response_data)
        except httpx.HTTPError as e:
            self.logger.error("HTTP error from LLM API: %s", e)
            raise
        return output

    async def chat_update_order(self, payload: Dict[str, Any], update_items_tool_data: list[dict,list], max_tokens: Optional[int] = None) -> OrderSuggestion:
        """
        Send a chat request to the LLM and return a validated OrderSuggestion.
        
        Args:
            payload: Dict with keys:
                - user_message (str): Customer's order request
                - user_history (list[dict]): Customer's chat history
                - user_order (OrderSuggestion): Customer's current order suggestion for context
                - menu_listing (List[MenuItem]): Available menu items for context
            update_items_tool_data (list[dict,list]): Tool function response containing items and indices requiring an update
            max_tokens: Optional token limit (defaults to settings.max_tokens)
            
        Returns:
            OrderSuggestion: Parsed and validated order response
            
        Raises:
            RuntimeError: If client not started
            ValueError: If response cannot be parsed into valid OrderSuggestion
            httpx.HTTPError: If API request fails
        """
        if not self._started or self._client is None:
            raise RuntimeError("LLMClient not started. Call startup() first.")

        user_message = payload.get("user_message", "")
        self.menu = payload.get("menu_listing")
        schema_mode = "update_item"


        # Build prompt using dedicated prompt builder
        prompt: list[dict[str, str]] = self._prompt_builder.build_update_order_prompt(
            user_message=user_message,
            order = self.current_order,
            menu_items=self.menu or [],
            items_list = update_items_tool_data["all_items"]["items"]
        )

        # Prepare request body
        body = self._build_request_body(prompt, schema_mode, max_tokens, items_list=update_items_tool_data["template"])
        headers = self._build_headers()
        endpoint = str(self.active_endpoint)

        # Send request
        self.logger.debug("POST %s (model=%s)", endpoint, self.active_model)
        try:
            response = await self._client.post(endpoint, json=body, headers=headers)
            response.raise_for_status()
            response_data = response.json()
            self.logger.debug("Update response_data: %s", str(response_data))
        except httpx.HTTPError as e:
            self.logger.error("HTTP error from LLM API: %s", e)
            raise

        # Extract raw response content (handles multiple provider formats)
        raw_content = self._extract_response_content(response_data)
        self.logger.debug("Raw response (preview): %s", str(raw_content)[:200])
        format_raw_content: dict[str, list[dict]] = json.loads(raw_content)
        total_price = sum([item["price"] for item in format_raw_content["items"]])
        format_raw_content.update({"total": float(total_price)})

        # Parse into OrderSuggestion using dedicated parser
        try:
            suggestion = parser.parse_order_suggestion(format_raw_content)
            self.logger.debug(
                "Successfully parsed order: %d items, total=$%.2f",
                len(suggestion.items),
                suggestion.total
            )
            
            return suggestion
        except (ValueError, Exception) as e:
            self.logger.error("Failed to parse LLM response: %s", e)
            raise ValueError(f"Invalid order response from LLM: {e}") from e

    async def chat_add_order(self, payload: Dict[str, Any], add_items_tool_dict: list[dict,list], max_tokens: Optional[int] = None) -> OrderDraft:
        """
        Send a chat request to the LLM and return a validated OrderDraft.
        
        Args:
            payload: Dict with keys:
                - user_message (str): Customer's order request
                - user_history (list[dict]): Customer's chat history
                - user_order (OrderSuggestion): Customer's current order suggestion for context
                - menu_listing (List[MenuItem]): Available menu items for context
            add_items_tool_dict (list[dict,list]): tool function response containing items to add
            max_tokens: Optional token limit (defaults to settings.max_tokens)
            
        Returns:
            OrderDraft: Parse and validates an OrderSuggestion of items to add then append items to OrderDraft
            
        Raises:
            RuntimeError: If client not started
            ValueError: If response cannot be parsed into valid OrderSuggestion
            httpx.HTTPError: If API request fails
        """
        if not self._started or self._client is None:
            raise RuntimeError("LLMClient not started. Call startup() first.")

        user_message = payload.get("user_message", "")
        self.menu = payload.get("menu_listing")
        schema_mode = "add_item"


        # Build prompt using dedicated prompt builder
        prompt: list[dict[str, str]] = self._prompt_builder.build_order_prompt(
            user_message=user_message,
            order = self.current_order,
            menu_items=self.menu or [],
            items_list = add_items_tool_dict["all_items"]["items"]
        )

        # Prepare request body
        body = self._build_request_body(prompt, schema_mode, max_tokens, items_list=add_items_tool_dict["template"])
        headers = self._build_headers()
        endpoint = str(self.active_endpoint)

        # Send request
        self.logger.debug("POST %s (model=%s)", endpoint, self.active_model)
        try:
            response = await self._client.post(endpoint, json=body, headers=headers)
            response.raise_for_status()
            response_data = response.json()
        except httpx.HTTPError as e:
            self.logger.error("HTTP error from LLM API: %s", e)
            raise

        # Extract raw response content (handles multiple provider formats)
        raw_content = self._extract_response_content(response_data)
        self.logger.debug("Raw response (preview): %s", str(raw_content)[:200])
        format_raw_content: dict[str, list[dict]] = json.loads(raw_content)
        total_price = sum([item["price"] for item in format_raw_content["items"]])
        format_raw_content.update({"total": float(total_price)})

        # Parse into OrderSuggestion using dedicated parser
        try:
            suggestion = parser.parse_order_suggestion(format_raw_content)
            self.logger.debug(
                "Successfully parsed order: %d items, total=$%.2f",
                len(suggestion.items),
                suggestion.total
            )
            # Append parsed items to OrderDraft
            for item in suggestion.items:
                self.current_order.build_items_draft(item.item_id, item.qty, item.spiciness, item.dish_meat, item.dish_base)
                self.current_order.add_item(item.item_id)

            return self.current_order
        except (ValueError, Exception) as e:
            self.logger.error("Failed to parse LLM response: %s", e)
            raise ValueError(f"Invalid order response from LLM: {e}") from e
        
    async def chat_initial(self, payload: Dict[str, Any], max_tokens: Optional[int] = None) -> tuple[OrderSuggestion, list[dict], dict]:
        """
        Initial chat request with decision tools to the LLM and return a validated OrderSuggestion.
        
        Args:
            payload: Dict with keys:
                - user_message (str): Customer's order request
                - user_history (list[dict]): Customer's chat history
                - user_order (OrderSuggestion): Customer's current order suggestion for context
                - menu_listing (List[MenuItem]): Available menu items for context
            max_tokens: Optional token limit (defaults to settings.max_tokens)
            
        Returns:
            OrderSuggestion, user history (list[dict]), tools details (dict)
            
        Raises:
            RuntimeError: If client not started
            ValueError: If response cannot be parsed into valid OrderSuggestion
            OrderBuildingException: If there is an error building the order draft after tool calls
            LLMServiceException: If there is an error during the LLM API call or response processing

        """
        if not self._started or self._client is None:
            raise RuntimeError("LLMClient not started. Call startup() first.")
        user_message: str = payload.get("user_message", "")
        self.menu: list[MenuItem] = payload.get("menu_listing")
        user_history: list = payload.get("user_history", [])
        user_order: OrderSuggestion = payload.get("user_order")
        tools = formatters.get_decision_tools()
        removed_items = []

        # Initialize current order from user order suggestion if exists
        try:
            self.current_order.to_draft(user_order)
        except ValueError as e:
            self.logger.error("Failed to initialize current order: %s", e)
            raise

        # Build prompt using dedicated prompt builder
        self._prompt_builder.user_history = user_history
        prompt: list[dict[str, str]] = self._prompt_builder.build_prompt_decision(
            user_message=user_message,
            order = self.current_order,
            menu=self.menu or [],
        )

        # OpenAi api call
        tool_calls = await self.openai_api_call(prompt, max_tokens, tools)

        try:
            if tool_calls:
                available_functions = {
                    "add_items": add_items_tool,
                    "update_items": update_items_tool,
                    "remove_items": remove_items_tool
                }
                tool_calls_details = []
                last_tools_list = []
                
                for tool_call in tool_calls:
                    self.logger.debug("llm response: %s ", tool_call.function.arguments)

                    # failsafe to avoid same tool call multiple times and prevent some problems with unexpected llm output
                    for tool_used in last_tools_list:
                        if tool_call.function.name == tool_used:
                            self.logger.info("Skipped duplicate tool call: %s", tool_call.function.name)
                            continue
                        else:
                            last_tools_list.append(tool_call.function.name)

                    self.logger.info("Tool call: %s ", tool_call.function.name)
                    function_name = tool_call.function.name
                    function_to_call = available_functions[function_name]
                    function_args = json.loads(tool_call.function.arguments)
                    try:
                        function_response = await function_to_call(self.menu, **function_args)
                    except (ValueError, Exception) as e:
                        self.logger.error("Failed to build tool function response: %s", e)
                        raise OrderBuildingException(f"Failed to build tool function response: {e}") from e
                    tool_calls_details.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": function_response,
                        }
                    )

                    self.logger.debug("llm response: %s ", function_args)
                    self.logger.debug("Tool response: %s ", function_response)
                        
                    if function_name == "add_items":
                        self.logger.debug("Dynamic model: %s ", function_response["template"])
                        try:
                            if function_response["has_diy"]:
                                order_draft = await self.chat_add_order(payload, function_response, max_tokens)
                                self.current_order = order_draft
                            else:
                                for item in function_response["simple_items"]["items"]:
                                    self.current_order.build_items_draft(item_id=item["item_id"], qty=item["qty"])
                                    self.current_order.add_item(item["item_id"])
                                order_draft = self.current_order
                        except (ValueError, Exception) as e:
                            self.logger.error("Failed to add to order draft: %s", e)
                            raise OrderBuildingException(f"Failed to add to order draft: {e}") from e

                    elif function_name == "update_items":
                        self.logger.debug("Dynamic model: %s ", function_response["template"])
                        if max(function_response["indices"]) >= len(self.current_order.items):
                            self.logger.error("LLM returned invalid order_item_index for update: %s", max(function_response["indices"]))
                            raise OrderBuildingException(f"LLM returned invalid order_item_index for update: {max(function_response["indices"])}")
                        if function_response["has_diy"]:
                            order_draft_suggestion = await self.chat_update_order(payload, function_response, max_tokens)
                            try:
                                if len(list(dict.fromkeys(function_response["indices"]))) == len(order_draft_suggestion.items):
                                    items_list = []
                                    for key, item in self.current_order.items.items():
                                        items_list.append(asdict(item))
                                    for i in function_response["indices"]:
                                        removed_items.append(items_list[i])
                                    for index, order_item in enumerate(order_draft_suggestion.items):
                                        self.current_order.update_item(function_response["indices"][index], order_item)
                                else:
                                    for index, index_to_remove in enumerate(function_response["indices"]):
                                        to_remove = self.current_order.remove_item(index_to_remove, function_response["all_items"]["items"][index]["qty"])
                                        removed_items.append(to_remove)
                                    for index, order_item in enumerate(order_draft_suggestion.items):
                                        self.current_order.build_items_draft(order_item.item_id, order_item.qty, order_item.spiciness, order_item.dish_meat, order_item.dish_base)
                                        self.current_order.add_item(order_item.item_id)

                                order_draft = self.current_order
                            except (ValueError, Exception) as e:
                                self.logger.error("Failed to update order draft: %s", e)
                                raise OrderBuildingException(f"Failed to update order draft: {e}") from e
                        else:
                            for index, order_item in enumerate(function_response["simple_items"]["items"]):
                                self.current_order.update_qty(function_response["indices"][index], order_item["qty"])
                            order_draft = self.current_order

                    elif function_name == "remove_items":
                        for order_item in function_response:
                            to_remove = self.current_order.remove_item(order_item["order_item_index"], order_item["qty"])
                            removed_items.append(to_remove)
                        order_draft = self.current_order

                    # Build OrderSuggestion
                    try:
                        suggestion = self.post_tool_action(function_name)
                    except (ValueError, Exception) as e:
                        self.logger.error("Failed to build order suggestion: %s", e)
                        raise OrderBuildingException(f"Failed to build order suggestion: {e}") from e

                    chat_output = suggestion.raw_text

                    # Notify user if missing data in order item(s)
                    if chat_output == "incomplete_order":
                        chat_response = await self.chat(payload, max_tokens, mode=chat_output)
                        chat_output = f"""{self.current_order.order_draft_to_str(self.menu)}
-----
{chat_response}"""
                        
            else:
                # No tool calls
                try:
                    suggestion = self.post_tool_action("chat") 
                except (ValueError, Exception) as e:
                    self.logger.error("Failed to build chat suggestion: %s", e)
                    raise OrderBuildingException(f"Failed to build chat suggestion: {e}") from e
                chat_response = await self.chat(payload, max_tokens)
                chat_output = f"""{self.current_order.order_draft_to_str(self.menu)}
-----
{chat_response}"""
                suggestion.raw_text = chat_output
        
            user_history.append({"role": "user", "content": user_message})
            user_history.append({"role": "assistant", "content": chat_output})
            tools_details = {"tools_called": [e["name"] for e in tool_calls_details] if tool_calls else None, "removed_items": removed_items if removed_items else None}
            self.logger.info("Tools called: %s\n Items to remove: %s", tools_details["tools_called"], tools_details["removed_items"])

        except (ValueError, Exception) as e:
            self.logger.error("HTTP error from LLM API: %s", e)
            raise LLMServiceException(f"HTTP error from LLM API: {e}") from e
        return suggestion, user_history, tools_details

    def _build_request_body(self, prompt: list[dict[str, str]], schema_mode: str, max_tokens: Optional[int], items_list = []) -> Dict[str, Any]:
        """
        Construct the HTTP request body for the LLM API.
        
        Args:
            prompt: The instruction/context prompt
            schema_mode: The mode for response formatting (e.g., "chat", "update_item")
            max_tokens: Token limit for response
            items_list: List of items for response formatting

        Returns:
            Request body dict
        """
        # JSON Schema for structured responses
        response_schema = formatters.build_response_schema(schema_mode, items_list)
        if response_schema:
            return {
                "model": self.active_model,
                "messages": prompt,
                "max_tokens": max_tokens or self.settings.max_tokens,
                "temperature": float(self.settings.temperature),
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "structured_response",
                        "schema": response_schema
                        }
                },
            }
        else:
            return {
                "model": self.active_model,
                "messages": prompt,
                "max_tokens": max_tokens or self.settings.max_tokens,
                "temperature": float(self.settings.temperature),
            }

    def _build_headers(self) -> Dict[str, str]:
        """
        Construct HTTP request headers including authentication if configured.
        
        Returns:
            Headers dict
        """
        headers = {}
        if self.active_api_key:
            headers["Authorization"] = f"Bearer {self.active_api_key}"
        return headers

    def _extract_response_content(self, response_data: Dict[str, Any]) -> Any:
        """
        Extract the actual response content from provider response.
        Handles multiple provider response formats:
        - OpenAI-style: choices[0].message.content
        - Direct parsed: output_parsed, response, parsed fields
        - Custom: output field
        
        Args:
            response_data: Raw response dict from API
            
        Returns:
            Extracted content (dict or string)
            
        Raises:
            ValueError: If content cannot be extracted
        """
        # Try common structured output fields first
        for key in ("output_parsed", "response", "parsed"):
            if key in response_data and isinstance(response_data[key], dict):
                self.logger.debug("Found structured output in '%s' field", key)
                return response_data[key]

        # OpenAI chat completions format: choices[0].message.content
        if "choices" in response_data and isinstance(response_data["choices"], list):
            try:
                choice = response_data["choices"][0]
                message = choice.get("message", {})
                
                # First, check for provider-parsed output
                if "output_parsed" in message and isinstance(message["output_parsed"], dict):
                    self.logger.debug("Found structured output in choices[0].message.output_parsed")
                    return message["output_parsed"]
                
                # Otherwise, return raw content (will be parsed from JSON string)
                content = message.get("content")
                if content:
                    self.logger.debug("Extracting from choices[0].message.content")
                    return content
            except (IndexError, KeyError, TypeError) as e:
                self.logger.debug("Failed to extract from choices: %s", e)

        # Custom "output" field
        if "output" in response_data:
            self.logger.debug("Found output in 'output' field")
            return response_data["output"]

        # Last resort: return the whole response as JSON string for parser to handle
        self.logger.warning("Could not extract structured content, returning raw response")
        return json.dumps(response_data)
