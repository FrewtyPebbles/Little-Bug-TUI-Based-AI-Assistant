from fastapi import APIRouter, Depends
from backend.auth import fastapi_get_user_with_roles

ROUTE = APIRouter(prefix="/account")

@ROUTE.get("info")
async def get_account_info(user: dict = Depends(fastapi_get_user_with_roles("user"))):
    pass