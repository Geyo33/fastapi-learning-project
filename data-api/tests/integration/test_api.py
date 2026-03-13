import pytest
import json
from main import app
from app.schemas import CreateOrderRequest, UpdateOrderRequest, DeleteOrderRequest, OrderSuggestion, OrderItem


# ===== Orders API Integration Tests =====
class TestOrdersAPI:
    def test_is_order_open_nonexistent_order(self, client, mock_data_paths):
        """Test checking if a non-existent order is open."""
        response = client.get("/api/v1/orders/is_open/nonexistent_user")
        assert response.status_code == 200
        assert response.json() is False

    def test_create_order_success(self, client, mock_data_paths, sample_user_context, sample_order_suggestion):
        """Test creating a new order successfully."""
        request_data = CreateOrderRequest(
            order=sample_order_suggestion,
            user_context=sample_user_context
        )

        response = client.post("/api/v1/orders/create_order", json=request_data.model_dump())
        assert response.status_code == 201

        response_data = response.json()
        assert response_data["customer_info"]["user_id"] == sample_user_context.user_id
        assert response_data["customer_order"]["total"] == sample_order_suggestion.total
        assert response_data["status"] == "open"
        assert len(response_data["customer_order"]["items"]) == 2

    def test_is_order_open_after_creation(self, client, mock_data_paths, sample_user_context, sample_order_suggestion):
        """Test that order is open after creation."""
        # Create order first
        request_data = CreateOrderRequest(
            order=sample_order_suggestion,
            user_context=sample_user_context
        )
        client.post("/api/v1/orders/create_order", json=request_data.model_dump())

        # Check if order is open
        response = client.get(f"/api/v1/orders/is_open/{sample_user_context.user_id}")
        assert response.status_code == 200
        assert response.json() is True

    def test_get_order_after_creation(self, client, mock_data_paths, sample_user_context, sample_order_suggestion):
        """Test retrieving an order after creation."""
        # Create order first
        request_data = CreateOrderRequest(
            order=sample_order_suggestion,
            user_context=sample_user_context
        )
        client.post("/api/v1/orders/create_order", json=request_data.model_dump())

        # Get the order
        response = client.get(f"/api/v1/orders/{sample_user_context.user_id}")
        assert response.status_code == 200

        response_data = response.json()
        assert response_data["customer_info"]["user_id"] == sample_user_context.user_id
        assert response_data["customer_order"]["total"] == sample_order_suggestion.total
        assert len(response_data["customer_order"]["items"]) == 2

    def test_get_nonexistent_order(self, client, mock_data_paths):
        """Test retrieving a non-existent order returns 404."""
        response = client.get("/api/v1/orders/nonexistent_user")
        assert response.status_code == 404
        assert response.json()["detail"] == "Order not found"

    def test_add_items_to_existing_order(self, client, mock_data_paths, sample_user_context, sample_order_suggestion):
        """Test adding items to an existing order."""
        # Create initial order
        initial_order = OrderSuggestion(
            items=[sample_order_suggestion.items[0]],  # Only first item
            total=13,
            raw_text="One item"
        )
        request_data = CreateOrderRequest(
            order=initial_order,
            user_context=sample_user_context
        )
        client.post("/api/v1/orders/create_order", json=request_data.model_dump())

        # Add more items
        updated_order = OrderSuggestion(
            items=sample_order_suggestion.items,  # Both items
            total=26,
            raw_text="Two items"
        )
        add_request = CreateOrderRequest(
            order=updated_order,
            user_context=sample_user_context
        )
        response = client.post("/api/v1/orders/create_order", json=add_request.model_dump())
        assert response.status_code == 201

        # Verify total was updated
        response_data = response.json()
        assert response_data["customer_order"]["total"] == 26

    def test_update_order(self, client, mock_data_paths, sample_user_context, sample_order_suggestion):
        """Test updating an existing order."""
        # Create order first
        request_data = CreateOrderRequest(
            order=sample_order_suggestion,
            user_context=sample_user_context
        )
        client.post("/api/v1/orders/create_order", json=request_data.model_dump())

        # Update order
        updated_order = OrderSuggestion(
            items=[
                OrderItem(
                    item_id=1,
                    qty=3,  # Changed quantity
                    price=13,
                    spiciness=json.dumps(["moyen"]),
                    dish_base=json.dumps(["riz"]),
                    dish_meat=json.dumps(["boeuf"])
                )
            ],
            total=39,
            raw_text="Three items"
        )
        update_request = UpdateOrderRequest(
            order=updated_order,
            user_context=sample_user_context
        )

        response = client.put(f"/api/v1/orders/{sample_user_context.user_id}", json=update_request.model_dump())
        assert response.status_code == 200

        response_data = response.json()
        assert response_data["customer_order"]["total"] == 39
        assert response_data["customer_order"]["items"][0]["qty"] == 3

    def test_update_nonexistent_order(self, client, mock_data_paths, sample_user_context, sample_order_suggestion):
        """Test updating a non-existent order returns 404."""
        update_request = UpdateOrderRequest(
            order=sample_order_suggestion,
            user_context=sample_user_context
        )

        response = client.put("/api/v1/orders/nonexistent_user", json=update_request.model_dump())
        assert response.status_code == 404
        assert response.json()["detail"] == "Order not found"

    def test_delete_items_from_order(self, client, mock_data_paths, sample_user_context, sample_order_suggestion):
        """Test deleting items from an order."""
        # Create order first
        request_data = CreateOrderRequest(
            order=sample_order_suggestion,
            user_context=sample_user_context
        )
        client.post("/api/v1/orders/create_order", json=request_data.model_dump())

        # Delete one item
        remaining_items = [sample_order_suggestion.items[0]]  # Keep only first item
        updated_order = OrderSuggestion(
            items=remaining_items,
            total=13,
            raw_text="One item remaining"
        )

        items_to_remove = [
            {
                "item_id": 2,
                "spiciness": json.dumps(["fort"]),
                "dish_base": json.dumps(["nouilles fines"]),
                "dish_meat": json.dumps(["poulet"])
            }
        ]

        delete_request = DeleteOrderRequest(
            order=updated_order,
            user_context=sample_user_context,
            items_to_remove=items_to_remove
        )

        response = client.put(f"/api/v1/orders/delete_from_order/{sample_user_context.user_id}", json=delete_request.model_dump())
        assert response.status_code == 200

        response_data = response.json()
        assert response_data["customer_order"]["total"] == 13
        assert len(response_data["customer_order"]["items"]) == 1

    def test_delete_items_from_nonexistent_order(self, client, mock_data_paths, sample_user_context, sample_order_suggestion):
        """Test deleting items from non-existent order returns 404."""
        delete_request = DeleteOrderRequest(
            order=sample_order_suggestion,
            user_context=sample_user_context,
            items_to_remove=[]
        )

        response = client.put("/api/v1/orders/delete_from_order/nonexistent_user", json=delete_request.model_dump())
        assert response.status_code == 404
        assert response.json()["detail"] == "Order not found"

    def test_validate_order_success(self, client, mock_data_paths, sample_user_context, sample_order_suggestion):
        """Test validating an order successfully."""
        # Create order first
        request_data = CreateOrderRequest(
            order=sample_order_suggestion,
            user_context=sample_user_context
        )
        client.post("/api/v1/orders/create_order", json=request_data.model_dump())

        # Validate order
        validate_request = UpdateOrderRequest(
            order=sample_order_suggestion,
            user_context=sample_user_context
        )

        response = client.put(f"/api/v1/orders/validate_order/{sample_user_context.user_id}", json=validate_request.model_dump())
        assert response.status_code == 201

        response_data = response.json()
        assert response_data["status"] == "validated"

    def test_validate_nonexistent_order(self, client, mock_data_paths, sample_user_context, sample_order_suggestion):
        """Test validating a non-existent order returns 404."""
        validate_request = UpdateOrderRequest(
            order=sample_order_suggestion,
            user_context=sample_user_context
        )

        response = client.put("/api/v1/orders/validate_order/nonexistent_user", json=validate_request.model_dump())
        assert response.status_code == 404
        assert response.json()["detail"] == "Order not found"

    def test_delete_order_success(self, client, mock_data_paths, sample_user_context, sample_order_suggestion):
        """Test deleting an order successfully."""
        # Create order first
        request_data = CreateOrderRequest(
            order=sample_order_suggestion,
            user_context=sample_user_context
        )
        client.post("/api/v1/orders/create_order", json=request_data.model_dump())

        # Delete order
        response = client.delete(f"/api/v1/orders/{sample_user_context.user_id}")
        assert response.status_code == 204

        # Verify order is gone
        response = client.get(f"/api/v1/orders/is_open/{sample_user_context.user_id}")
        assert response.status_code == 200
        assert response.json() is False

    def test_delete_nonexistent_order(self, client, mock_data_paths):
        """Test deleting a non-existent order returns 404."""
        response = client.delete("/api/v1/orders/nonexistent_user")
        assert response.status_code == 404
        assert response.json()["detail"] == "Order not found"


# ===== Restaurants API Integration Tests =====
class TestRestaurantsAPI:
    def test_get_menu_success(self, client, mock_data_paths, sample_menu_data):
        """Test retrieving a restaurant menu successfully."""
        response = client.get("/api/v1/restaurants/MTW/menu")
        assert response.status_code == 200

        menu_data = response.json()
        assert isinstance(menu_data, list)
        assert len(menu_data) == 2
        assert menu_data[0]["dish_name"] == "Wok saté"
        assert menu_data[1]["dish_name"] == "Wok thaï"

    def test_get_menu_nonexistent_restaurant(self, client, mock_data_paths):
        """Test retrieving menu for non-existent restaurant returns 404."""
        response = client.get("/api/v1/restaurants/NONEXISTENT/menu")
        assert response.status_code == 404
        assert response.json()["detail"] == "Menu not found"

    def test_get_menu_empty_menu(self, client, mock_data_paths, temp_data_dir):
        """Test retrieving menu when menu file exists but is empty."""
        # Create empty menu file
        menu_file = temp_data_dir / "menus" / "EMPTY_menu.json"
        menu_file.parent.mkdir(parents=True, exist_ok=True)
        with open(menu_file, 'w') as f:
            json.dump([], f)

        response = client.get("/api/v1/restaurants/EMPTY/menu")
        assert response.status_code == 404
        assert response.json()["detail"] == "Menu not found"


# ===== End-to-End Workflow Tests =====
class TestEndToEndWorkflow:
    def test_complete_order_workflow(self, client, mock_data_paths, sample_user_context, sample_order_suggestion, revert_order_status):
        """Test complete order workflow: create -> update -> validate -> delete."""
        # 1. Create order
        create_request = CreateOrderRequest(
            order=sample_order_suggestion,
            user_context=sample_user_context
        )
        response = client.post("/api/v1/orders/create_order", json=create_request.model_dump())
        assert response.status_code == 201

        # 2. Check order exists and is open
        response = client.get(f"/api/v1/orders/is_open/{sample_user_context.user_id}")
        assert response.json() is True

        # 3. Get order details
        response = client.get(f"/api/v1/orders/{sample_user_context.user_id}")
        assert response.status_code == 200
        order_data = response.json()
        assert order_data["status"] == "open"

        # 4. Update order
        updated_order = OrderSuggestion(
            items=[sample_order_suggestion.items[0]],  # Remove one item
            total=13,
            raw_text="Updated order"
        )
        update_request = UpdateOrderRequest(
            order=updated_order,
            user_context=sample_user_context
        )
        response = client.put(f"/api/v1/orders/{sample_user_context.user_id}", json=update_request.model_dump())
        assert response.status_code == 200

        # 5. Validate order
        validate_request = UpdateOrderRequest(
            order=updated_order,
            user_context=sample_user_context
        )
        response = client.put(f"/api/v1/orders/validate_order/{sample_user_context.user_id}", json=validate_request.model_dump())
        assert response.status_code == 201
        assert response.json()["status"] == "validated"

        # 6. Delete order
        # Deletion of validated order not implemented, revert status first using helper
        revert_order_status(sample_user_context.user_id, sample_user_context)
        response = client.delete(f"/api/v1/orders/{sample_user_context.user_id}")
        assert response.status_code == 204

        # 7. Verify order is gone
        response = client.get(f"/api/v1/orders/is_open/{sample_user_context.user_id}")
        assert response.json() is False