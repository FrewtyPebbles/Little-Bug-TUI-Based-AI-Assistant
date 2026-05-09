from __future__ import annotations
import uuid
from fastapi import Depends, HTTPException, status
from fastmcp.server.auth.oidc_proxy import OIDCProxy
from fastmcp.server.dependencies import get_access_token
from backend.config import ENVIRONMENT
from fastapi.security import OAuth2PasswordBearer
from keycloak import KeycloakOpenID

# FastAPI

keycloak_openid = KeycloakOpenID(
    server_url=ENVIRONMENT.KEYCLOAK_URL,
    client_id=ENVIRONMENT.KEYCLOAK_API_CLIENT_ID,
    realm_name=ENVIRONMENT.KEYCLOAK_REALM,
    client_secret_key=ENVIRONMENT.KEYCLOAK_API_CLIENT_SECRET # Required since client is confidential
)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{ENVIRONMENT.KEYCLOAK_URL}realms/{ENVIRONMENT.KEYCLOAK_REALM}/protocol/openid-connect/token"
)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        # Fetch Keycloak Public Key
        public_key = "-----BEGIN PUBLIC KEY-----\n" + \
                     keycloak_openid.public_key() + \
                     "\n-----END PUBLIC KEY-----"

        # Decode and Verify Token
        token_info = keycloak_openid.decode_token(
            token,
            key=public_key,
            algorithms=["RS256"]
        )
        return token_info
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(e)}"
        )

# MCP

MCP_VERIFIER = OIDCProxy(
    config_url=f"{ENVIRONMENT.KEYCLOAK_URL}realms/{ENVIRONMENT.KEYCLOAK_REALM}/.well-known/openid-configuration",
    client_id=ENVIRONMENT.KEYCLOAK_API_CLIENT_ID,
    client_secret=ENVIRONMENT.KEYCLOAK_API_CLIENT_SECRET,
    base_url=ENVIRONMENT.KEYCLOAK_URL,
    redirect_path="callback"
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