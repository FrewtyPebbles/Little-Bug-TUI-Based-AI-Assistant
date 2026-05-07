# SQLAlchemy model for storing contacts
import re

from sqlalchemy import Column, Integer, String

from tui_client.database.engine import SQLBase, SQLiteVector
from sqlalchemy.orm import validates

EMAIL_REGEX = r"\A[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\Z"
PHONE_NUMBER_REGEX = r"^\+[1-9]\d{1,14}$"

class Contact(SQLBase):
    # TODO: Add retrieval counter, to keep track of which contacts are used most.
    # This is so we can tell who is the most used contacts. Then we can list the top 50 of these at the beginning of every chat
    __tablename__ = "contacts"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    email = Column(String, nullable=True)
    phone_number = Column(String(16), nullable=True)
    notes = Column(String, nullable=True)
    embedding = Column(SQLiteVector, nullable=True)

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