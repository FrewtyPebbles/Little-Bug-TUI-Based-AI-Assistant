from __future__ import annotations
from fastmcp.server.auth import AuthContext

from backend.auth.keycloak import KEYCLOAK_AUTH_MANAGER

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
        self.description = description

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
    def add(cls, role:Role) -> Role: # THIS SHOULD ONLY BE CALLED ONCE ON SERVER BOOT
        cls.roles[role.name] = role
        return role

    @classmethod
    def has_role(cls, user_roles_names:list[str], target_roles_names:list[str]) -> bool:
        target_roles_set = set([Role.roles[role] for role in target_roles_names])
        for user_role in user_roles_names:
            if user_role in target_roles_set or any([
                target_role.is_subordinate(user_role)
                for target_role
                in target_roles_set
            ]):
                return True
        return False
    
    @classmethod
    def mcp_has_role(cls, *roles: str):
        def check(ctx: AuthContext) -> bool:
            if ctx.token is None:
                return False
            user_roles:list[str] = ctx.token.claims.get("roles", [])
            return cls.has_role(user_roles, roles)
        return check
