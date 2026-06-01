# SQLAlchemy model acts as a proxy for keycloak accounts with an embedding for vector search.
import asyncio
import uuid

from tui_client.database.engine import SQLBase, Session
from sqlalchemy.orm import Mapped, mapped_column, relationship, object_session, Session as SessionType
from sqlalchemy import Column, ForeignKey, Table, event
from beanie.operators import In
from pgvector.sqlalchemy import VECTOR
from backend.auth import KeycloakUserInfo, KEYCLOAK_AUTH_MANAGER

user_group_association = Table(
    "user_group_association",
    SQLBase.metadata,
    Column("access_group_id", ForeignKey("access_group.id"), primary_key=True),
    Column("user_proxy_id", ForeignKey("user_proxy.id"), primary_key=True),
)

sub_access_group_association = Table(
    "sub_access_group_association",
    SQLBase.metadata,
    Column("parent_access_group_id", ForeignKey("access_group.id"), primary_key=True),
    Column("sub_access_group_id", ForeignKey("access_group.id"), primary_key=True),
)

class AccessGroup(SQLBase):
    """
    For controlling access to documents.  Also supports vector search and heirarchal ownership.
    """
    __tablename__ = "access_group"
    id:Mapped[int] = mapped_column(primary_key=True, nullable=False)
    owner_id:Mapped[int] = mapped_column(nullable=False) # from keycloak
    name:Mapped[str] = mapped_column(nullable=False)
    description:Mapped[str] = mapped_column(nullable=True, default="No description.")
    group_members:Mapped[list["UserProxy"]] = relationship(
        secondary=user_group_association, 
        back_populates="access_groups"
    )
    # Sub access groups
    # These are groups that users in the parent access group also have access to.
    sub_access_groups:Mapped[list["AccessGroup"]] = relationship(
        secondary=sub_access_group_association,
        primaryjoin=(id == sub_access_group_association.c.parent_access_group_id),
        secondaryjoin=(id == sub_access_group_association.c.sub_access_group_id),
        back_populates="parent_access_groups",
        overlaps="parent_access_groups"
    )
    parent_access_groups:Mapped[list["AccessGroup"]] = relationship(
        secondary=sub_access_group_association,
        primaryjoin=(id == sub_access_group_association.c.sub_access_group_id),
        secondaryjoin=(id == sub_access_group_association.c.parent_access_group_id),
        back_populates="sub_access_groups",
        overlaps="sub_access_groups"
    )

    embedding:Mapped[list[float]] = mapped_column(VECTOR(2048), nullable=False)
    # ^ This embedding is for vector search.

    def get_embedding_string(self, with_members:bool = True) -> str:
        group_text = ""
        no_members = len(self.group_members) == 0
        no_sub_groups = len(self.sub_access_groups) == 0
        if with_members:
            if no_members and no_sub_groups:
                group_text = "\n\nThis group doesn't have any members or sub access groups."
            elif no_members:
                group_text = "\n\nThis group doesn't have any members."
                group_text += "\n\nSub Access Groups:\n\n" + "\n\n---\n\n".join([sub_access_group.get_embedding_string(False) for sub_access_group in self.sub_access_groups])
            elif no_sub_groups:
                group_text = "\n\nThis group doesn't have any sub access groups."
                group_text += "\n\nMembers:\n\n" + "\n\n---\n\n".join([member.get_embedding_string(False) for member in self.group_members])
            else:
                group_text = "\n\nMembers:\n\n" + "\n\n---\n\n".join([member.get_embedding_string(False) for member in self.group_members])
                group_text += "\n\nSub Access Groups:\n\n" + "\n\n---\n\n".join([sub_access_group.get_embedding_string(False) for sub_access_group in self.sub_access_groups])
        
        return (
            f"Name: {self.name}\n"
            f"Description:\n\n{self.description}"
        ) + group_text
    
    def __contains__(self, user_or_access_group, _visited: set | None =None):
        if _visited is None:
            _visited = set()
        if self.id in _visited:
            return False
        _visited.add(self.id)
        if isinstance(user_or_access_group, UserProxy):
            return user_or_access_group in self.group_members or any(
                pg.__contains__(user_or_access_group, _visited) for pg in self.parent_access_groups
            )
        elif isinstance(user_or_access_group, AccessGroup):
            return user_or_access_group in self.sub_access_groups
        raise Exception("The `in` operator for AccessGroups only work between a UserProxy and an AccessGroup or an AccessGroup and an AccessGroup.")

class UserProxy(SQLBase):
    """
    Used for vector RAG user lookup. Also as a proxy for adding users to groups.
    """
    __tablename__ = "user_proxy"
    id:Mapped[int] = mapped_column(primary_key=True, nullable=False)
    user_id:Mapped[uuid.UUID] = mapped_column(nullable=False) # from keycloak
    access_groups:Mapped[list["AccessGroup"]] = relationship(
        secondary=user_group_association, 
        back_populates="group_members"
    )
    embedding:Mapped[list[float]] = mapped_column(VECTOR(2048), nullable=False)
    # ^ an embedding of all of the user's information.
    
    
    def get_userinfo(self) -> KeycloakUserInfo:
        return KEYCLOAK_AUTH_MANAGER.get_user(self.user_id)
    
    def get_embedding_string(self, with_group:bool = True) -> str:
        userinfo = self.get_userinfo()
        access_groups_str = "\n\nAccess Groups:\n\n" if len(self.access_groups) else "\n\nThis user isn't a part of any groups."
        access_groups_str += "\n\n---\n\n".join([group.get_embedding_string(False) for group in self.access_groups])
        return (
            f"Username: {userinfo.username}\n"
            f"Email: {userinfo.email}\n"
            f"First Name: {userinfo.first_name}\n"
            f"Last Name: {userinfo.last_name}"
        ) + (access_groups_str if with_group else "")
    


# @event.listens_for(UserProxy, "after_delete")
# def mark_for_cleanup(mapper, connection, target: UserProxy):
#     session = object_session(target)
#     # Just store the ID. The session is implied because we are in session.info
#     session.info.setdefault("user_ids_to_clean", set()).add(target.user_id)

# @event.listens_for(Session, "after_rollback")
# def cleanup_on_failure(session: SessionType):
#     session.info["user_ids_to_clean"] = set()

# @event.listens_for(Session, "after_commit")
# def clean_up_after_commit(session: SessionType):
#     user_ids = list(session.info.get("user_ids_to_clean", []))
#     if not user_ids:
#         return

#     async def async_cleanup(ids):
#         await UserSession.find(In(UserSession.user_id, ids)).delete()

#     try:
#         loop = asyncio.get_running_loop()
#         # Fire and forget in the background
#         loop.create_task(async_cleanup(user_ids))
#     except RuntimeError:
#         # Fallback for sync environments (like management scripts)
#         asyncio.run(async_cleanup(user_ids))
    
#     # Final wipe of the info dictionary
#     session.info["user_ids_to_clean"] = set()

    
