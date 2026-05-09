from fastapi import APIRouter

ROUTE = APIRouter(prefix="/account")

@ROUTE.get("info")
async def get_account_info():
    pass