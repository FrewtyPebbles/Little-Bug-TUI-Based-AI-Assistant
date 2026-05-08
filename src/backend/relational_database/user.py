# SQLAlchemy model for storing user accounts
# This stores the user, their email, and acts as a primary key for their settings
import asyncio
from dataclasses import dataclass
import re

from backend.auth import Role
from backend.relational_database.contact import Contact
from tui_client.database.engine import SQLBase, SQLiteVector, Session
from sqlalchemy import ForeignKey
from sqlalchemy.orm import validates, Mapped, mapped_column, relationship, object_session, Session as SessionType
from backend.relational_database.sanitize import EMAIL_REGEX
from sqlalchemy import event
from backend.mongo_database.ai_chat_session import AISession, AIMessage
from backend.mongo_database.user_chat_session import UserSession, UserMessage
from beanie.operators import In

class UserRole(SQLBase):
    __tablename__ = "user_role"
    id:Mapped[int] = mapped_column(primary_key=True, nullable=False)
    user_id:Mapped[int] = mapped_column(ForeignKey("user.id"))
    user:Mapped["User"] = relationship(back_populates="roles")
    role:Mapped[str] =  mapped_column(nullable=False)

    @validates('role')
    def validate_role(self, key, role):
        if role not in Role.roles.keys():
            raise ValueError(f"Invalid role: {role}")
            
        return role


class User(SQLBase):
    __tablename__ = "user"
    id:Mapped[int] = mapped_column(primary_key=True, nullable=False)
    # This info is so the assistant knows who it's talking to
    email:Mapped[str] = mapped_column(nullable=False)
    first_name:Mapped[str] = mapped_column(nullable=False)
    last_name:Mapped[str] = mapped_column(nullable=False)
    roles:Mapped[list[UserRole]] = relationship(back_populates="user")
    contacts:Mapped[list[Contact]] = relationship(back_populates="user")
    
    @validates('email')
    def validate_email(self, key, address):
        address = address.strip().lower()

        if not re.match(EMAIL_REGEX, address):
            raise ValueError(f"Invalid email address: {address}")
            
        return address
    


@event.listens_for(User, "after_delete")
def mark_for_cleanup(mapper, connection, target: User):
    session = object_session(target)
    # Just store the ID. The session is implied because we are in session.info
    session.info.setdefault("user_ids_to_clean", set()).add(target.id)

@event.listens_for(Session, "after_rollback")
def cleanup_on_failure(session: SessionType):
    session.info["user_ids_to_clean"] = set()

@event.listens_for(Session, "after_commit")
def clean_up_after_commit(session: SessionType):
    user_ids = list(session.info.get("user_ids_to_clean", []))
    if not user_ids:
        return

    async def async_cleanup(ids):
        await UserSession.find(In(UserSession.user_id, ids)).delete()
        await AISession.find(In(UserSession.user_id, ids)).delete()

    try:
        loop = asyncio.get_running_loop()
        # Fire and forget in the background
        loop.create_task(async_cleanup(user_ids))
    except RuntimeError:
        # Fallback for sync environments (like management scripts)
        asyncio.run(async_cleanup(user_ids))
    
    # Final wipe of the info dictionary
    session.info["user_ids_to_clean"] = set()

    
