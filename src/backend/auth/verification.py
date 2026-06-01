from __future__ import annotations
from functools import lru_cache
from typing import Any
import uuid
from fastapi import Depends, HTTPException, status
from fastmcp.server.auth.oidc_proxy import OIDCProxy
from fastmcp.server.dependencies import get_access_token
from backend.auth.rbac import Role
from backend.config import ENVIRONMENT
from fastapi.security import OAuth2AuthorizationCodeBearer
from keycloak import KeycloakOpenID
import jwt

from shared.config import SHARED_ENVIRONMENT

# FastAPI

keycloak_openid = KeycloakOpenID(
    server_url=ENVIRONMENT.KEYCLOAK_URL,
    client_id=ENVIRONMENT.KEYCLOAK_API_CLIENT_ID,
    realm_name=ENVIRONMENT.KEYCLOAK_REALM,
    client_secret_key=ENVIRONMENT.KEYCLOAK_API_CLIENT_SECRET # Required since client is confidential
)

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"{ENVIRONMENT.KEYCLOAK_URL}realms/{ENVIRONMENT.KEYCLOAK_REALM}/protocol/openid-connect/auth",
    tokenUrl=f"{ENVIRONMENT.KEYCLOAK_URL}realms/{ENVIRONMENT.KEYCLOAK_REALM}/protocol/openid-connect/token",
    refreshUrl=f"{ENVIRONMENT.KEYCLOAK_URL}realms/{ENVIRONMENT.KEYCLOAK_REALM}/protocol/openid-connect/token",
)

@lru_cache(maxsize=1)
def get_public_key() -> str:
    return (
        "-----BEGIN PUBLIC KEY-----\n"
        + keycloak_openid.public_key()
        + "\n-----END PUBLIC KEY-----"
    )

def verify_token(token:str) -> dict[str, Any]:
    # Fetch Keycloak Public Key
    public_key = "-----BEGIN PUBLIC KEY-----\n" + \
                get_public_key() + \
                "\n-----END PUBLIC KEY-----"

    # Decode and Verify Token
    token_info = keycloak_openid.decode_token(
        token,
        key=public_key,
        options={"verify_signature": True, "verify_exp": True}
    )

    return token_info

class FastAPIRoleChecker:
    def __init__(self, *allowed_roles:str):
        self.allowed_roles = allowed_roles

    def __call__(self, token: str = Depends(oauth2_scheme)) -> dict[str, Any]:
        token_info:dict[str, Any] = None
        try:
            token_info = verify_token(token)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid or expired token: {str(e)}"
            )


        user_roles:list[str] = token_info.get("roles", [])
        if Role.has_role(user_roles, self.allowed_roles):
            return token_info
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient Privileges: User does not have the required role(s)"
            )
            

# FastMCP

MCP_VERIFIER = OIDCProxy(
    config_url=f"{ENVIRONMENT.KEYCLOAK_URL}realms/{ENVIRONMENT.KEYCLOAK_REALM}/.well-known/openid-configuration",
    client_id=ENVIRONMENT.KEYCLOAK_API_CLIENT_ID,
    client_secret=ENVIRONMENT.KEYCLOAK_API_CLIENT_SECRET,
    base_url=ENVIRONMENT.KEYCLOAK_URL,
    redirect_path=SHARED_ENVIRONMENT.CLI_AUTH_LOOPBACK_URI
)

def mcp_get_user_id() -> uuid.UUID:
    token = get_access_token()

    if token is None:
        raise Exception("Not authenticated") # Or your AuthError
        
    # 2. Extract and validate user_id
    user_id_raw = token.claims.get("sub")
    
    if not user_id_raw:
        raise Exception("User id not found in token")
        
    try:
        user_id = uuid.UUID(user_id_raw)
    except ValueError:
        raise Exception("Malformed user_id in token")

    # 3. Inject the user_id into the function arguments
    return user_id