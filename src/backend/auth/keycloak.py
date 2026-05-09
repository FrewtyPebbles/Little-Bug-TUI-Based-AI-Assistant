import uuid

from keycloak import KeycloakAdmin
from backend.config import ENVIRONMENT
from typing import TYPE_CHECKING
from shared.config import SHARED_ENVIRONMENT

from backend.relational_database.user import User
if TYPE_CHECKING:
    from backend.auth.rbac import Role

class KeycloakAuthManager:
    def __init__(self):
        
        self.keycloak_admin = KeycloakAdmin(
            server_url=ENVIRONMENT.KEYCLOAK_URL,
            username=ENVIRONMENT.KEYCLOAK_ADMIN_USERNAME,
            password=ENVIRONMENT.KEYCLOAK_ADMIN_USERNAME,
            realm_name=ENVIRONMENT.KEYCLOAK_REALM,
            user_realm_name="master",
            verify=True
        )

        # Create a realm for the app
        realm_payload = {
            "realm": ENVIRONMENT.KEYCLOAK_REALM,
            "enabled": True,
            "displayName": "Little Bug Realm"
        }

        self.keycloak_admin.create_realm(payload=realm_payload, skip_exists=True)

        # Create API Client
        
        api_client_payload = {
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

        self.keycloak_admin.create_client(payload=api_client_payload, skip_exists=True)
        
        self.api_client_uuid = self.keycloak_admin.get_client_id(ENVIRONMENT.KEYCLOAK_API_CLIENT_ID)

        # Create CLI Client
        
        cli_client_payload = {
            "clientId": ENVIRONMENT.KEYCLOAK_API_CLIENT_ID,
            "name": "Little Bug CLI Client",
            "enabled": True,
            "publicClient": True,         # This is going to be on the end user's pc
            "redirectUris": [SHARED_ENVIRONMENT.CLI_AUTH_LOOPBACK_URI],
            "standardFlowEnabled": True,    # Enables Authorization Code Flow
            "directAccessGrantsEnabled": False,
            "attributes": {
                "pkce.code.challenge.method": "S256" # Enforce PKCE
            }
        }

        self.keycloak_admin.create_client(payload=cli_client_payload, skip_exists=True)
        
        self.cli_client_uuid = self.keycloak_admin.get_client_id(ENVIRONMENT.KEYCLOAK_CLI_CLIENT_ID)

        realm_role_mapper = {
            "name": "realm-role-mapper",
            "protocol": "openid-connect",
            "protocolMapper": "oidc-usermodel-realm-role-mapper",
            "config": {
                "claim.name": "roles", 
                "jsonType.label": "String",
                "multivalued": "true",
                "access.token.claim": "true",
                "id.token.claim": "true",
                "userinfo.token.claim": "true",
                "usermodel.clientRoleMapping.rolePrefix": "",
                "usermodel.clientRoleMapping.clientId": ENVIRONMENT.KEYCLOAK_API_CLIENT_ID
            }
        }

        self.keycloak_admin.add_mapper_to_client(
            client_id=self.api_client_uuid, 
            payload=realm_role_mapper
        )

    def create_role(self, role:Role):
        role_payload = {
            "name": role.name,
            "description": role.description
        }
        self.keycloak_admin.create_realm_role(payload=role_payload, skip_exists=True)
        realm_role = self.keycloak_admin.get_realm_role(
            role_name=role.name
        )
        roles = []
        for subordinate in role.subordinate_roles:
            roles.append(self.keycloak_admin.get_realm_role(subordinate.name))
            
        self.keycloak_admin.add_composite_realm_roles_to_role(realm_role, roles)

    def add_user(self, user:User, password:str):
        user_payload = {
            "username": user.username,
            "email": user.email,
            "firstName": user.first_name,
            "lastName": user.last_name,
            "database_id":user.id,
            "enabled": True,
            "credentials": [{"type": "password", "value": password, "temporary": False}]
        }
        user_id = self.keycloak_admin.create_user(payload=user_payload)
        
        kc_roles = []
        
        for user_role in user.roles:
            kc_roles.append(self.keycloak_admin.get_realm_role(user_role.role))
        
        self.keycloak_admin.assign_realm_roles(user_id, kc_roles)

KEYCLOAK_AUTH_MANAGER = KeycloakAuthManager()