from __future__ import annotations
from fastmcp.server.auth import AuthContext, StaticTokenVerifier

class Permission:
    permissions:dict[str, Permission] = {}
    def __init__(self, name:str, description:str = "No description."):
        self.name = name
        self.description = description
    
    def __hash__(self):
        return hash(self.name)

class Role:
    roles:dict[str, Role] = {}
    def __init__(self, name:str, subordinate_roles:set[str] | None = None, permissions:set[Permission] | None = None, description:str = "No description."):
        self.name = name
        self.permissions:set[Permission] = permissions if permissions else set()
        self.subordinate_roles:set[Role] = set([self.roles[sub] for sub in subordinate_roles]) if subordinate_roles else set()

    def __hash__(self):
        return hash(self.name)
    
    def is_subordinate(self, role:str):
        return role in self.subordinate_roles or any([sub.is_subordinate(role) for sub in self.subordinate_roles])

    def add_permission(self, permission:str) -> Role:
        self.permissions.add(Permission.permissions[permission])
        return self
    
    def has_permission(self, permission:str) -> bool:
        return permission in self.permissions or any([sub.has_permission(permission) for sub in self.subordinate_roles])

    @classmethod
    def add(cls, role:Role):
        cls.roles[role.name] = role

    @classmethod
    def mcp_has_role(cls, *roles: str):
        target_roles_set = set([Role.roles[role] for role in roles])
        def check(ctx: AuthContext) -> bool:
            if ctx.token is None:
                return False
            user_role:str = ctx.token.claims.get("roles", [])
            role = cls.roles[user_role]
            return role in target_roles_set or any([
                target_role.is_subordinate(role)
                for target_role
                in target_roles_set
            ])
        return check
    
Role.add(Role("user", description="This is the default role for all authenticated users."))
Role.add(Role("admin", {"user"}, description="This role has access to server consoles."))

MCP_VERIFIER = StaticTokenVerifier(
    tokens={
        "dev-alice-token": {
            "client_id": "alice@company.com",
            "scopes": ["read:data", "write:data", "admin:users"],
            # add any custom claims here, readable via TokenClaim
        },
        "dev-guest-token": {
            "client_id": "guest-user",
            "scopes": ["read:data"],
        },
    },
    required_scopes=["read:data"]
)