from typing import List, Dict, Optional, Any
import logging

from src.llm_service.models.schemas import MenuItem
from src.llm_service.models.domain import OrderDraft

logger = logging.getLogger("llm_prompts")


class PromptTemplates:
    """
    Collection of prompt templates.
    """

    # System role definition
    SYSTEM_ROLE = """You are a friendly and professional restaurant order assistant. Your role is to:
1. Help customers browse the menu and understand dishes
2. Guide customers through the ordering process
3. Handle misunderstandings and mistakes customers might make
4. Suggest items based on preferences
5. Be helpful, concise, and polite

Always respond in the same language as the customer and provide clear, actionable suggestions.

Menu available:
{menu_listing}"""

    SYSTEM_ROLE_DECISION = """You are a rigorous and professional restaurant order assistant. Your role is to:
1. Understand the customer request
2. Assess what is the best course of action to fulfill this request
3. Decide if tool calls are necessary
4. Always call a tool when the current order need a modification

Always generate a precise and rigorous output, filling the relevant fields accurately when calling tools.

Menu available:
{menu_listing}"""

    # Main prompts
    ADD_ITEM_PROMPT = """You are taking a restaurant order from a customer. Your task is to:
1. Understand what the customer wants to order
2. Extract menu items, quantities, prices as well as spiciness, dish base and dish meat(proteins), when needed, from user message.
3. If user didn't provide spiciness, dish base or dish meat(proteins), fill the concerned field with 'indéfini'.

Menu available:
{menu_listing}"""

    UPDATE_ITEM_PROMPT = """You are updating a restaurant order from a customer. Your task is to:
1. Understand what the customer wants to upate in the order
2. Extract menu items, quantities, prices as well as spiciness, dish base and dish meat(proteins), when needed, from user message.
3. If user didn't provide spiciness, dish base or dish meat(proteins), fill the concerned field with 'indéfini'.

Menu available:
{menu_listing}"""


class PromptBuilder:
    """
    Helper class to build and format prompts with dynamic content.
    Handles menu formatting, context injection, and template rendering.
    """

    def __init__(self, logger_instance: Optional[logging.Logger] = None):
        self.logger = logger_instance or logger
        self.user_history = []

    def format_menu_listing(
        self,
        menu_items: List[MenuItem],
        include_description: bool = True,
        categories: Optional[List[str]] = None,
    ) -> str:
        """
        Format menu items for inclusion in prompts.
        
        Args:
            menu_items: List of menu item dicts
            include_description: Whether to include dish descriptions
            categories: If provided, filter menu to only these categories
            
        Returns:
            Formatted menu string suitable for LLM context
        """
        menu_items: list[dict] = [m.model_dump() for m in menu_items]
        lines = []
        current_category = None

        # Filter by category if specified
        items_to_show = menu_items
        if categories:
            items_to_show = [m for m in menu_items if m.get("category") in categories]

        for item in items_to_show:
            category = item.get("category", "general")

            # Add category header if it changed
            if category != current_category:
                current_category = category
                lines.append(f"\n--- {category.upper()} ---")

            # Format item with ID, name, and price
            item_id = item.get("id") or item.get("item_id", "?")
            name = item.get("name") or item.get("dish_name", "Unknown")
            price = float(item.get("price", 0))
            
            line = f"[{item_id}] {name} - ${price:.2f}"
            lines.append(line)

            # Add description
            if include_description:
                description = item.get("description", "")
                if description:
                    lines.append(f"    {description}")

            # Add options if present
            options_text = self._format_item_options(item)
            if options_text:
                lines.append(f"    Options: {options_text}")

        return "\n".join(lines) if lines else "No menu items available"

    def _format_item_options(self, item: Dict[str, Any]) -> str:
        """Format optional choices for a menu item (spice, protein, etc)."""
        options = []

        if "spiciness" in item and item["spiciness"]:
            spice_opts = ", ".join(item["spiciness"])
            options.append(f"Spice: {spice_opts}")

        if "dish_meat" in item and item["dish_meat"]:
            meat_opts = ", ".join(item["dish_meat"])
            options.append(f"Protein: {meat_opts}")

        if "dish_base" in item and item["dish_base"]:
            base_opts = ", ".join(item["dish_base"])
            options.append(f"Base: {base_opts}")

        return " | ".join(options) if options else ""

    def build_prompt_decision(
        self,
        user_message: str,
        order: OrderDraft,
        menu: list[MenuItem],
    ) -> list[dict]:
        """
        Build the main tool decision prompt with menu context.
        
        Args:
            user_message: Customer's message
            order: OrderDraft
            menu_items: Available menu items
            
        Returns:
            Formatted dict prompt ready for LLM
        """
        menu_listing = self.format_menu_listing(menu, include_description=False)
        system_prompt = PromptTemplates.SYSTEM_ROLE_DECISION.format(
            menu_listing=menu_listing,
        )

        system_prompt = {"role": "system", "content": system_prompt}

        prompt = [system_prompt]
        if self.user_history:
            for e in self.user_history:
                prompt.append(e)
        prompt.append({"role": "user", "content": f"""User message is : {user_message}
                       
-----
                       
Current order :                        
{order.order_draft_to_str(menu)}

-----

Final instructions : 
- You have access to 3 tools that can be used to : add items, update items and remove items                  
- Decide if you need to call a tool(answer with 'tool called') or not(answer with "Reply directly to the user").
- Never call the same tool multiple times.
- A single tool can add, remove or update multiple items at once.
- A tool call is mandatory to perform any operation on the current order !!!"""})
        
        return prompt

    def build_chat_prompt(
        self,
        user_message: str,
        order: OrderDraft,
        menu_items: List[Dict[str, Any]],
        mode = None,
        extra = None
    ) -> list[dict]:
        """
        Build the simple chat prompt with menu context.
        
        Args:
            user_message: Customer's message/order request
            order: OrderDraft
            menu_items: Available menu items
            mode: used for specific usage of simple chat
            extra: additional context for some modes
            
        Returns:
            Formatted dict prompt ready for LLM
        """
        menu_listing = self.format_menu_listing(menu_items, include_description=True)
        system_prompt = PromptTemplates.SYSTEM_ROLE.format(
            menu_listing=menu_listing,
        )

        extra_instruct = ""
        if mode:
            extra_instruct_dispatch = {
                "incomplete_order": "Some fields in the current order are undefined('indéfini'), inform the user and invite them to provides what's missing.",
                "chat": "",
                "clarify": f"Ask the user to clarify or provide further information about this missing data for the order : {extra}"
            }
            extra_instruct = extra_instruct_dispatch[mode]
        system_prompt = {"role": "system", "content": system_prompt}

        prompt = [system_prompt]
        if self.user_history:
            for e in self.user_history:
                prompt.append(e)
        prompt.append({"role": "user", "content": f"""User message is : {user_message}
                       
-----
                       
Current order :                        
{order.order_draft_to_str(menu_items)}

-----

You cannot modify the current order now, just answers, guide or clarify things for the customer.
Customer can consult the menu by clicking on the menu tab. 
{extra_instruct}
if any fields is filed with 'indéfini' invite the user to provide relevant data to fill the field with a valid entry.
"""})
        

        return prompt

    def build_order_prompt(
        self,
        user_message: str,
        order: OrderDraft,
        menu_items: List[Dict[str, Any]],
        items_list: List[Dict[str, Any]],
    ) -> list[dict]:
        """
        Build the add item to order prompt with menu context.
        
        Args:
            user_message: Customer's message/order request
            order: OrderDraft
            menu_items: Available menu items
            items_list: List of items to add
            
        Returns:
            Formatted prompt ready for LLM
        """
        menu_listing = self.format_menu_listing(menu_items, include_description=False)
        system_prompt = PromptTemplates.ADD_ITEM_PROMPT.format(
            menu_listing=menu_listing,
        )
        
        system_prompt = {"role": "system", "content": system_prompt}

        prompt = [system_prompt]
        if self.user_history:
            for e in self.user_history:
                prompt.append(e)
        prompt.append({"role": "user", "content": f"""User message is : {user_message}
                       
-----
                       
Current order :                        
{order.order_draft_to_str(menu_items)} 

-----
                       
Dish(es) user seemingly wishes to add to the order : {[f"{e["dish_name"]}(id: {e["item_id"]}) x{e["qty"]}" for e in items_list]}.
- Only generate the items to add in the list just above.
- Each wok has to be added individually so the 'qty' field should always be 1."""})

        
        return prompt
    
    def build_update_order_prompt(
        self,
        user_message: str,
        order: OrderDraft,
        menu_items: List[Dict[str, Any]],
        items_list: List[Dict[str, Any]],
    ) -> list[dict]:
        """
        Build the update item from order prompt with menu context.
        
        Args:
            user_message: Customer's message/order request
            order: OrderDraft
            menu_items: Available menu items
            items_list: List of items to update
            
        Returns:
            Formatted prompt ready for LLM
        """
        menu_listing = self.format_menu_listing(menu_items, include_description=False)
        system_prompt = PromptTemplates.UPDATE_ITEM_PROMPT.format(
            menu_listing=menu_listing,
        )
        
        system_prompt = {"role": "system", "content": system_prompt}

        prompt = [system_prompt]
        if self.user_history:
            for e in self.user_history:
                prompt.append(e)
        prompt.append({"role": "user", "content": f"""User message is : {user_message}
                       
-----
                       
Current order :                        
{order.order_draft_to_str(menu_items)} 

-----

Dish(es) user seemingly wishes to update from the order : {[f"{e["dish_name"]}(id: {e["item_id"]}) x{e["qty"]}" for e in items_list]}.
- Only generate the items requiring an update mentioned in the list just above."""})
        
        return prompt


def get_prompt_builder() -> PromptBuilder:
    """Factory function to get a PromptBuilder instance."""
    return PromptBuilder()
