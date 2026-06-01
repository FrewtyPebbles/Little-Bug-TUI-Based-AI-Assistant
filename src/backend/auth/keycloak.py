import uuid

from keycloak import KeycloakAdmin
from backend.config import ENVIRONMENT
from typing import TYPE_CHECKING
from shared.config import SHARED_ENVIRONMENT
from backend.relational_database.user import User
import uuid
if TYPE_CHECKING:
    from backend.auth.rbac import Role

class KeycloakUserInfo:
    def __init__(self, raw_keycloak_user:dict):
        self.id:uuid.UUID = uuid.UUID(raw_keycloak_user["id"])
        self.username:str = raw_keycloak_user["username"]
        self.email:str = raw_keycloak_user["email"]
        self.first_name:str = raw_keycloak_user["firstName"]
        self.last_name:str = raw_keycloak_user["lastName"]
        self.enabled:bool = raw_keycloak_user["enabled"]
        self.email_verified:bool = raw_keycloak_user["emailVerified"]

class KeycloakAuthManager:
    def __init__(self, api_client_uuid:str, cli_client_uuid:str):
        self.api_client_uuid = api_client_uuid
        self.cli_client_uuid = cli_client_uuid

        #We create a scoped keycloak client admin to adhere to least privledge
        self.keycloak_admin = KeycloakAdmin(
            server_url=ENVIRONMENT.KEYCLOAK_URL,
            realm_name=ENVIRONMENT.KEYCLOAK_REALM,
            client_id=ENVIRONMENT.KEYCLOAK_API_CLIENT_ID,
            client_secret_key=ENVIRONMENT.KEYCLOAK_API_CLIENT_SECRET
        )
    def get_user(self, user_id:uuid.UUID):
        return KeycloakUserInfo(self.keycloak_admin.get_user(user_id, True))

    def add_user(self, user:User, password:str):
        user_payload = {
            "username": user.username,
            "email": user.email,
            "firstName": user.first_name,
            "lastName": user.last_name,
            "emailVerified":not ENVIRONMENT.REQUIRE_EMAIL_VERIFICATION,
            "enabled": True,
            "credentials": [{"type": "password", "value": password, "temporary": False}]
        }
        user_id = self.keycloak_admin.create_user(payload=user_payload)
        
        kc_roles = []
        
        for user_role in user.roles:
            kc_roles.append(self.keycloak_admin.get_realm_role(user_role.role))
        
        self.keycloak_admin.assign_realm_roles(user_id, kc_roles)

# THIS KEYCLOAK ADMIN IS NOT TO BE USED ELSEWARE
# This creates the realm and clients.

__ABSOLUTE_KEYCLOAK_ADMIN = KeycloakAdmin(
    server_url=ENVIRONMENT.KEYCLOAK_URL,
    username=ENVIRONMENT.KEYCLOAK_ADMIN_USERNAME,
    password=ENVIRONMENT.KEYCLOAK_ADMIN_USERNAME,
    realm_name=ENVIRONMENT.KEYCLOAK_REALM,
    user_realm_name="master",
    verify=True
)

# CREATES ROLES
def __create_role(keycloak_admin:KeycloakAdmin, role:Role):
        role_payload = {
            "name": role.name,
            "description": role.description
        }
        keycloak_admin.create_realm_role(payload=role_payload, skip_exists=True)
        realm_role = keycloak_admin.get_realm_role(
            role_name=role.name
        )
        roles = []
        for subordinate in role.subordinate_roles:
            roles.append(keycloak_admin.get_realm_role(subordinate.name))
            
        keycloak_admin.add_composite_realm_roles_to_role(realm_role, roles)

# Create a realm for the app
__realm_payload = {
    "realm": ENVIRONMENT.KEYCLOAK_REALM,
    "enabled": True,
    "displayName": "Little Bug Realm"
}

__ABSOLUTE_KEYCLOAK_ADMIN.create_realm(payload=__realm_payload, skip_exists=True)

# Create API Client

__api_client_payload = {
    "clientId": ENVIRONMENT.KEYCLOAK_API_CLIENT_ID,
    "name": "Little Bug API Client",
    "enabled": True,
    "publicClient": False,              # Confidential (needs secret)
    "serviceAccountsEnabled": True,      # Allow backend-to-Keycloak calls
    "standardFlowEnabled": False,        # APIs don't use browser redirects
    "directAccessGrantsEnabled": False,
    "bearerOnly": True,                  # Older Keycloak: Only verifies tokens
    "attributes": {
        "access.token.lifespan": "3600"  # Optional: specific token timeout
    }
}

__ABSOLUTE_KEYCLOAK_ADMIN.create_client(payload=__api_client_payload, skip_exists=True)

# Add CRUD users permissions
__api_client_uuid = __ABSOLUTE_KEYCLOAK_ADMIN.get_client_id(ENVIRONMENT.KEYCLOAK_API_CLIENT_ID)
__service_user = __ABSOLUTE_KEYCLOAK_ADMIN.get_client_service_account_user(__api_client_uuid)
__realm_mgmt_uuid = __ABSOLUTE_KEYCLOAK_ADMIN.get_client_id("realm-management")
__mgmt_roles = __ABSOLUTE_KEYCLOAK_ADMIN.get_client_roles(__realm_mgmt_uuid)
__manage_users_role = [r for r in __mgmt_roles if r['name'] == 'manage-users']

__ABSOLUTE_KEYCLOAK_ADMIN.assign_client_role(
    user_id=__service_user['id'],
    client_id=__realm_mgmt_uuid,
    roles=__manage_users_role
)


# Create CLI Client

__cli_client_payload = {
    "clientId": ENVIRONMENT.KEYCLOAK_API_CLIENT_ID,
    "name": "Little Bug CLI Client",
    "enabled": True,
    "publicClient": True,         # This is going to be on the end user's pc
    "redirectUris": [SHARED_ENVIRONMENT.CLI_AUTH_LOOPBACK_URI],
    "standardFlowEnabled": True,    # Enables Authorization Code Flow
    "directAccessGrantsEnabled": False,
    "attributes": {
        "pkce.code.challenge.method": "RS256" # Enforce PKCE
    }
}

__ABSOLUTE_KEYCLOAK_ADMIN.create_client(payload=__cli_client_payload, skip_exists=True)

__cli_client_uuid = __ABSOLUTE_KEYCLOAK_ADMIN.get_client_id(ENVIRONMENT.KEYCLOAK_CLI_CLIENT_ID)

# create roles

# Basic user account
__create_role(__ABSOLUTE_KEYCLOAK_ADMIN,
    Role.add(Role(
        "user",
        description="This is the default role for all authenticated users."
    ))
)
# Admin account
__create_role(__ABSOLUTE_KEYCLOAK_ADMIN,
    Role.add(Role(
        "admin",
        {"user"},
        description="This role has access to server consoles."
    ))
)

# CREATE CLIENT SCOPE FOR TOKEN ROLE CLAIMS
__api_access_client_scope_payload = {
    "name": "api-access-scope",
    "protocol": "openid-connect",
    "attributes": {
        "display.on.consent.screen": "false" # Hide from user during login
    }
}
__ABSOLUTE_KEYCLOAK_ADMIN.create_client_scope(payload=__api_access_client_scope_payload)
__api_access_client_scope = __ABSOLUTE_KEYCLOAK_ADMIN.get_client_scope_by_name("api-access-scope")
## CREATE TOKEN CLAIMS MAPPING
__api_access_client_scope_role_mapper = {
    "name": "realm-role-mapper",
    "protocol": "openid-connect",
    "protocolMapper": "oidc-usermodel-realm-role-mapper",
    "config": {
        "claim.name": "roles", 
        "multivalued": "true",
        "jsonType.label": "String",
        "access.token.claim": "true",
        "userinfo.token.claim": "true",
        "id.token.claim": "true",
    }
}

__ABSOLUTE_KEYCLOAK_ADMIN.add_mapper_to_client_scope(
    client_id=__api_access_client_scope["id"], 
    payload=__api_access_client_scope_role_mapper
)

# ATTACH SCOPE TO FRONTEND CLIENT(S)
__ABSOLUTE_KEYCLOAK_ADMIN.add_client_default_client_scope(
    client_id=__cli_client_uuid, 
    client_scope_id=__api_access_client_scope["id"],
    payload={
        "realm":ENVIRONMENT.KEYCLOAK_REALM,
        "client":__cli_client_uuid,
        "clientScopeId":__api_access_client_scope["id"]
    }
)

KEYCLOAK_AUTH_MANAGER = KeycloakAuthManager(__api_client_uuid, __cli_client_uuid)