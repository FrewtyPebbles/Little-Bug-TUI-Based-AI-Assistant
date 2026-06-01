from typing import Any

from fastapi import APIRouter, Depends
from backend.auth import FastAPIRoleChecker

ROUTE = APIRouter(prefix="/account")

@ROUTE.get("info")
async def get_account_info(user: dict[str, Any] = Depends(FastAPIRoleChecker("user"))):
    pass