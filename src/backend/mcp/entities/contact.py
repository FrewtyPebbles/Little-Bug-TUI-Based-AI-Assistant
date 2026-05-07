from sqlalchemy import func
import sqlite_vec

from backend.database.contact import Contact
from backend.mcp.app import EMBEDDINGS_MODEL, MCP
from backend.database.engine import Session, SQL_ENGINE
from backend.utility import format_contact_embedding_string
from backend.mcp.verifier import Role
from fastmcp.server.dependencies import get_access_token

@MCP.tool(auth=Role.has_role("user"))
def add_contact(
    name:str, email:str | None = None, phone_number:str | None = None, notes:str | None = None
):
    """
    Adds a contact to the user's contact book.
    Args:
        name(Required, type:str): The name of the contact.
        email(Optional, type:str): The email of the contact.
        phone_number(Optional, type:str): The phone number of the contact, must follow the regex format "^\+[1-9]\d{1,14}$".
        notes(Optional, type:str): Notes about the contact.
    """
    token = get_access_token()

    if token is None:
        return "Not authenticated"
    user_id = token.claims.get("user_id") or token.claims.get("sub")
    with Session(bind=SQL_ENGINE) as session:
        embedding_string = format_contact_embedding_string(name, email, phone_number, notes)
        embedding = EMBEDDINGS_MODEL.encode(embedding_string).tolist()
        contact = Contact(
            name=name,
            email=email,
            phone_number=phone_number,
            notes=notes,
            embedding=embedding
        )
        try:
            session.add(contact)
            session.commit()
            return f"Successfully added contact: \"{name}\""
        except Exception as e:
            session.rollback()
            error_message = str(e)
            return f"Failed to add contact: {error_message}"

@MCP.tool(auth=Role.has_role("user"))
def delete_contact(name:str):
    """
    Deletes a contact from the user's contact book.
    Args:
        name(Required, type:str): The name of the contact. This must be exact.
    """
    with Session(bind=SQL_ENGINE) as session:
        contact = session.query(Contact).filter(Contact.name == name).first()

        if contact:
            session.delete(contact)
    
            # 3. Commit the change to the file
            try:
                session.commit()
                return f"Successfully deleted contact: \"{name}\""
            except Exception as e:
                session.rollback()
                return f"Error deleting contact: {str(e)}"
        else:
            return f"Failed to find contact with name: \"{name}\"\nTry searching for the contact first."

@MCP.tool(auth=Role.has_role("user"))
def edit_contact(self, name:str, email:str | None = None, phone_number:str | None = None, notes:str | None = None):
    """
    Edits a contact in the user's contact book. If one of the optional arguments is not included, it will not be changed in the contact.
    Whenever you learn something new about an existing contact, you should add it to that contact's notes.
    
    IMPORTANT: make sure you always read a contact with search_contacts before you edit that contact.
    
    Args:
        name(Required, type:str): The name of the contact. This tool will do an edit-distance fuzzy lookup of the name when searching for the contact to edit.
        email(Optional, type:str): The email of the contact.
        phone_number(Optional, type:str): The phone number of the contact, must follow the regex format "^\+[1-9]\d{1,14}$".
        notes(Optional, type:str): Notes about the contact.
    """
    with Session(bind=SQL_ENGINE) as session:
        contact = session.query(Contact).filter(
            func.levenshtein(Contact.name, name) <= 3
        ).order_by(
            func.levenshtein(Contact.name, name).asc()
        ).first()
        # Edit the contact
        if email is not None:
            contact.email = email
        if phone_number is not None:
            contact.phone_number = phone_number
        if notes is not None:
            contact.notes = notes

        # Regenerate the vector embedding since the data changed
        embedding_string = format_contact_embedding_string(contact.name, contact.email, contact.phone_number, contact.notes)
        contact.embedding = self.embeddings_model.encode(embedding_string).tolist()
        try:
            session.commit()
            return f"Successfully edited contact: \"{contact.name}\""
        except Exception as e:
            # Extract the message
            session.rollback()
            error_message = str(e)
            return f"Failed to edit contact: {error_message}"

@MCP.resource("contacts://{query_text}/{limit}/contacts", auth=Role.has_role("user"))
def search_contacts(query_text: str, limit: int = 5):
    """
    Searches the user's contact book for contacts based on a search prompt and returns a specified amount of results in order from most to least similar.
    Contacts always include a name and usually include an email, phone number, and notes about the person.
    This tool encodes the query_text into an embedding and compares it with existing contacts using cosine similarity.
    Args:
        query_text(Required, type:str): A search prompt to find contacts with.
        limit(Optional, type:int): The amount of contacts to return. The default value for this is 5.
    """
    query_vector = EMBEDDINGS_MODEL.encode(query_text).tolist()
    query_vector_bytes = sqlite_vec.serialize_float32(query_vector)

    with Session(bind=SQL_ENGINE) as session:
        # use cosine similarity to look up contact
        contacts:list[tuple[Contact, float]] = session.query(
            Contact, 
            func.vec_distance_cosine(Contact.embedding, query_vector_bytes).label("distance")
        ).order_by(
            "distance"
        ).limit(limit).all()

        return_value = f"Found {len(contacts)} Contacts" + (":" if len(contacts) > 0 else ".")
        for i, (contact, similarity_score) in enumerate(contacts, 1):
            return_value += f"\n --- Result {i} --- \nName: {contact.name}\nEmail: {contact.email}\nPhone Number: {contact.phone_number}\nNotes:\n{contact.notes}\n"

        return return_value