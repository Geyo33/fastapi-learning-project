import gradio as gr
import requests
import uuid
import pandas as pd
from schemas import OrderSuggestion, OrderRequest, UserContext, CustomerOrder, ChatRequest

# --- API Configuration ---
BASE_URL = "http://localhost:8001/api/v1"
RESTAURANT_ID = "MTW"

def get_restaurant_menu():
    """Retrieve menu from backend."""
    try:
        resp = requests.get(f'{BASE_URL}/get-menu/{RESTAURANT_ID}')
        resp.raise_for_status()
        menu = resp.json()
        return menu
    except Exception as e:
        print(f"Menu error: {e}")
        return []
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    

def get_customer_order(user_id: str) -> CustomerOrder:
    """Retrieve customer order from backend."""
    try:
        resp = requests.get(f"{BASE_URL}/order-exists/{user_id}")
        resp.raise_for_status()
        order_exists: bool = resp.json()
        if order_exists:
            resp = requests.get(f"{BASE_URL}/get-order/{user_id}")
            resp.raise_for_status()
            order = resp.json()
            return CustomerOrder(**order)
        else:
            return None
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        return None


def remove_order(user_id: str) -> bool:
    """Delete customer open order from backend."""
    try:
        resp = requests.post(f"{BASE_URL}/remove-order/{user_id}")
        resp.raise_for_status()
        order_deleted: bool = resp.json()
        return order_deleted
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        return False
    

def load_menu():
    """Formats menu items into a Pandas DataFrame for the UI."""
    menu = menu_snapshot
    if not menu:
        return pd.DataFrame(columns=["Dish", "Price", "Category"])
    df = pd.DataFrame(menu)
    return df[["dish_name", "price", "category", "description"]]
    

def format_order_for_display(order_suggestion: OrderSuggestion):
    """Formats OrderSuggestion items into a Pandas DataFrame for the UI."""
    items = order_suggestion.items
    if not items:
        return pd.DataFrame(columns=["Qty", "Item", "Price"])
    
    id_to_name = {}
    for item in items:
        for menu_item in menu_snapshot:
            if item.item_id == menu_item["id"]:
                id_to_name[str(item.item_id)] = menu_item["dish_name"]

    data = [
        [item.qty, id_to_name[str(item.item_id)], f"{item.price}€"] 
        for item in items
    ]
    return pd.DataFrame(data, columns=["Qty", "Item", "Price"])

# --- Main App ---

def build_app():
    with gr.Blocks() as demo:
        
        # Internal state for UserContext and UserSuggestion
        user_context_state = gr.State(UserContext(**{
            "user_id": str(uuid.uuid4()),
            "user_history": [],
            "language": "fr"
        }))
        user_order_state = gr.State(OrderSuggestion(items=[], total=0.0))
        
        gr.Markdown("# 🍜 Automated wAIter")
        
        with gr.Tabs():
            # --- TAB 1: CHAT & ORDER ---
            with gr.Tab("Chat"):
                with gr.Row(equal_height=True):

                    # Left Column: Chat
                    with gr.Column(scale=3):
                        chatbot = gr.Chatbot(label=user_context_state.value.user_id, height=550)
                        
                        with gr.Row():
                            msg_input = gr.Textbox(
                                show_label=False, 
                                placeholder="J'aimerais commander...",
                                container=False,
                                scale=7
                            )
                            submit_btn = gr.Button("Send", variant="primary", scale=1)
                    
                    # Right Column: Order View
                    with gr.Column(scale=1, variant="panel"):
                        gr.Markdown("### 🛒 Current Order")
                        order_table = gr.Dataframe(
                            headers=["Qty", "Item", "Price"],
                            interactive=False,
                            datatype=["number", "str", "str"]
                        )
                        total_display = gr.Markdown("## Total: 0.00€")
                        
                        with gr.Row():
                            btn_cancel = gr.Button("Annuler", variant="stop")
                            btn_confirm = gr.Button("Valider la commande", variant="primary")
                        
                        status_msg = gr.Markdown("")

            # --- TAB 2: MENU VIEW ---
            with gr.Tab("Menu"):
                menu_display = gr.Dataframe(value=load_menu(), label="Our Menu", interactive=False)


        # --- Logic Functions ---

        def load_user_order(context: UserContext):
            customer_order = get_customer_order(context.user_id)
            if customer_order:
                context.user_history = customer_order.customer_info.user_history
                order_suggestion = OrderSuggestion(items=customer_order.customer_order.items, total=customer_order.customer_order.total)
                df_order = format_order_for_display(order_suggestion)
                return gr.update(value=context.user_history), context, order_suggestion, df_order, f"## Total: {order_suggestion.total}€"
            else:
                return gr.update(value=[]), context, OrderSuggestion(items=[], total=0.0), pd.DataFrame(columns=["Qty", "Item", "Price"]), "## Total: 0.00€"

        def handle_chat(message, history, context: UserContext, order_suggestion: OrderSuggestion):
            if not message.strip():
                return "", history, context, order_suggestion, gr.skip(), gr.skip()

            if context.user_history:
                try:
                    context.user_history[-1]["content"] = context.user_history[-1]["content"].split("-----", 1)[1].strip()
                except:
                    print("No markdown table")
                    pass
            history = context.user_history
            
            payload = ChatRequest(
                user_message=message,
                context=context,
                order=order_suggestion,
                menu_listing=menu_snapshot
            )
            try:
                # Call Backend - LLM
                resp = requests.post(f'{BASE_URL}/chat', json=payload.model_dump())
                resp.raise_for_status()
                output = resp.json()
                response = OrderRequest(**output["order_request"])
                tools_details = output["tools_details"]

                new_context = response.user_context
                new_suggestion = response.order

                history = new_context.user_history

                # Update Order Table
                df_order = format_order_for_display(new_suggestion)
                total_val = new_suggestion.total
                
                # Call Backend - DB storage
                available_tools = {
                    "add_items": {"url": f"{BASE_URL}/create-order", "args": response.model_dump()},
                    "update_items": {"url": f"{BASE_URL}/update-order/{context.user_id}", "args": response.model_dump()},
                    "remove_items": {"url": f"{BASE_URL}/remove-from-order/{context.user_id}", "args": response.model_dump()},
                }

                if tools_details["tools_called"] and tools_details["tools_called"] != "clarify_order":
                    for tool in tools_details["tools_called"]:
                        if tools_details["removed_items"] and tool == "update_items":
                            req_args = available_tools["remove_items"]
                            resp = requests.post(req_args["url"], json=req_args["args"])
                            resp.raise_for_status()
                            req_args = available_tools["add_items"]
                            resp = requests.post(req_args["url"], json=req_args["args"])
                            resp.raise_for_status()

                        else:
                            req_args = available_tools[tool]
                            resp = requests.post(req_args["url"], json=req_args["args"])
                            resp.raise_for_status()
                            
                
                return (
                    "", 
                    history, 
                    new_context, 
                    new_suggestion,
                    df_order, 
                    f"## Total: {total_val}€"
                )
            except requests.exceptions.HTTPError as http_err:
                print(f"HTTP error occurred: {http_err}")
            except Exception as e:
                history.append({"role": "assistant", "content": f"Error: {str(e)}"})
                return "", history, context, order_suggestion, gr.skip(), "Error"
            return "", history, context, order_suggestion, gr.skip(), "Error"

        def cancel_order(chatbot, context: UserContext):
            is_removed = remove_order(context.user_id)
            if not is_removed:
                print("No order to remove or error occurred.")
            empty_df = pd.DataFrame(columns=["Qty", "Item", "Price"])
            empty_context = UserContext(user_id=str(uuid.uuid4()), user_history=[])
            empty_order = OrderSuggestion(items=[], total=0.0)
            chatbot = gr.Chatbot(label=empty_context.user_id, value=[])
            return "", chatbot, empty_context, empty_order, empty_df, "## Total: 0.00€", gr.update(visible=True), gr.update(value="Cancel"), gr.update(visible=True), gr.update(visible=True)

        def pre_confirm_order(history):
            history.append({"role": "user", "content": "Je souhaite valider ma commande."})
            return history

        def confirm_order(history, context: UserContext, table: pd.DataFrame):
            try:
                resp = requests.get(f'{BASE_URL}/get-order/{context.user_id}')
                resp.raise_for_status()
                order = resp.json()
                if context.user_history:
                    try:
                        split_last_msg = context.user_history[-1]["content"].split("-----", 1)
                        context.user_history[-1]["content"] = split_last_msg[1].strip()
                        str_markdown_order = split_last_msg[0].strip()
                    except:
                        print("No markdown table")
                        str_markdown_order = table.to_markdown()
                        pass
                history = context.user_history
                payload = {
                    "suggested_order": order["customer_order"],
                    "user_context": context.model_dump(),
                    "menu_snapshot": menu_snapshot
                }
                resp = requests.post(f'{BASE_URL}/validate-order', json=payload)
                resp.raise_for_status()
                validate_response = resp.json()
                is_valid = validate_response.get("is_valid")
                response = validate_response.get("response")
                status_msg = "Order Sent to Kitchen! 🚀" if is_valid else ""
                context.user_history.append({"role": "user", "content": "Je souhaite valider ma commande."})
                history.append({"role": "assistant", "content": f"{str_markdown_order}\n\n---\n{response}"})
                return status_msg, history, gr.update(visible=False), gr.update(value="Démarrer une nouvelle commande"), gr.update(visible=False), gr.update(visible=False)
            except requests.exceptions.HTTPError as http_err:
                print(f"HTTP error occurred: {http_err}")
            except requests.exceptions.ConnectionError as conn_err:
                print(f"Connection error occurred: {conn_err}")
            except requests.exceptions.Timeout as timeout_err:
                print(f"Timeout error occurred: {timeout_err}")
            except requests.exceptions.RequestException as err:
                print(f"An error occurred: {err}")
            history.append({"role": "assistant", "content": "⚠️ Aucune commande à valider ⚠️"})
            return "", history, gr.skip(), gr.skip(), gr.skip(), gr.skip()

        # --- Event Listeners ---

        msg_input.submit(
            handle_chat, 
            inputs=[msg_input, chatbot, user_context_state, user_order_state], 
            outputs=[msg_input, chatbot, user_context_state, user_order_state, order_table, total_display]
        )
        
        submit_btn.click(
            handle_chat, 
            inputs=[msg_input, chatbot, user_context_state, user_order_state], 
            outputs=[msg_input, chatbot, user_context_state, user_order_state, order_table, total_display]
        )

        btn_cancel.click(cancel_order, inputs=[chatbot, user_context_state], outputs=[status_msg, chatbot, user_context_state, user_order_state, order_table, total_display, btn_confirm, btn_cancel, msg_input, submit_btn])
        btn_confirm.click(pre_confirm_order, inputs=[chatbot], outputs=[chatbot]).then(confirm_order, inputs=[chatbot, user_context_state, order_table], outputs=[status_msg, chatbot, btn_confirm, btn_cancel, msg_input, submit_btn])

        demo.load(load_user_order, inputs=[user_context_state], outputs=[chatbot, user_context_state, user_order_state, order_table, total_display])

    return demo

if __name__ == "__main__":
    menu_snapshot = get_restaurant_menu()
    app = build_app()
    app.launch(
        theme=gr.themes.Soft(primary_hue="orange"), 
        debug=True
    )