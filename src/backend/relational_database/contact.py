# SQLAlchemy model for storing contacts
import re
import uuid

from backend.relational_database.engine import SQLBase, SQLiteVector
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import validates, Mapped, mapped_column, relationship
from backend.relational_database.sanitize import EMAIL_REGEX, PHONE_NUMBER_REGEX
from pgvector.sqlalchemy import VECTOR

class Contact(SQLBase):
    # TODO: Add retrieval counter, to keep track of which contacts are used most.
    # This is so we can tell who is the most used contacts. Then we can list the top 50 of these at the beginning of every chat
    __tablename__ = "contact"
    id:Mapped[int] = mapped_column(primary_key=True, nullable=False)
    user_id:Mapped[uuid.UUID] = mapped_column(nullable=False)
    first_name:Mapped[str] = mapped_column(nullable=False)
    last_name:Mapped[str] = mapped_column(nullable=True, default='')
    email:Mapped[str] = mapped_column(nullable=True)
    phone_number:Mapped[str] = mapped_column(String(16), nullable=True)
    notes:Mapped[str] = mapped_column(nullable=True)
    embedding:Mapped[list[float]] = mapped_column(VECTOR(2048), nullable=False)

    @classmethod
    def format_contact_embedding_string(first_name:str, last_name:str | None = None, email:str | None = None, phone_number:str | None = None, notes:str | None = None):
        return f"First Name: {first_name}\nLast Name: {last_name or ''}\nEmail: {email or ''}\nPhone Number: {phone_number or ''}\nNotes:\n{notes or ''}"

    def display_str(self) -> str:
        return self.format_contact_embedding_string(self.first_name, self.last_name, self.email, self.phone_number, self.notes)

    @validates('email')
    def validate_email(self, key, address):
        address = address.strip().lower()

        if not re.match(EMAIL_REGEX, address):
            raise ValueError(f"Invalid email address: {address}")
            
        return address
    
    @validates('phone_number')
    def validate_phone_number(self, key, number):
        if not number:
            return None
        
        # Remove all non-digit characters except '+'
        # This cleans up inputs like "(555) 123-4567"
        cleaned = re.sub(r'[^\d+]', '', number)
        
        # Prepend '+' if the user forgot it
        if not cleaned.startswith('+'):
            cleaned = '+' + cleaned
            
        # Final check against regex
        if not re.match(PHONE_NUMBER_REGEX, cleaned):
            raise ValueError(f"Invalid E.164 phone format: {number}")
            
        return cleaned