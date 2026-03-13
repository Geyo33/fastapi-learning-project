from fastapi import APIRouter, HTTPException, status
from app.storage import load_menu

router = APIRouter(prefix="/api/v1/restaurants", tags=["restaurants"])


@router.get("/{restaurant_id}/menu", response_model=list[dict])
async def get_menu(restaurant_id: str):
    """retrieve a menu"""
    menu: list[dict] = load_menu(restaurant_id)
    if menu:
        return menu
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu not found")
