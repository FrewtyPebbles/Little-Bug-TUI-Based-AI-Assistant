from fastmcp.server.dependencies import get_access_token

def mcp_get_user_id() -> int:
    token = get_access_token()

    if token is None:
        raise Exception("Not authenticated") # Or your AuthError
        
    # 2. Extract and validate user_id
    user_id_raw = token.claims.get("user_id") or token.claims.get("sub")
    
    if not user_id_raw:
        raise Exception("User id not found in token")
        
    try:
        user_id = int(user_id_raw)
    except ValueError:
        raise Exception("Malformed user_id in token")

    # 3. Inject the user_id into the function arguments
    return user_id