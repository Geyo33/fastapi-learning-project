from ..schemas import CustomerOrder
from ..storage import load_ci

def parse_customer_order(payload: list[dict]) -> dict:
    customer_info_dict: dict = load_ci()
    customer_info = customer_info_dict[payload["order"]["user_id"]]

    customer_order = CustomerOrder(**{
        "customer_info": {
        "user_id": payload["order"]["user_id"],
        "user_history": customer_info["user_history"],
        "language": customer_info["language"]
      },
        "customer_order": {
        "items": payload["order_items"],
        "total": payload["order"]["total"],
        "raw_text": payload["order"]["raw_text"]
      },
        "status": payload["order"]["status"]
    })

    return customer_order.model_dump()