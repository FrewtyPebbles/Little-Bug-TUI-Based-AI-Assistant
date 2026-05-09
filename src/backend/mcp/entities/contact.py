from typing import Iterable

from sqlalchemy import Row, and_, or_, select, func
import sqlite_vec

from backend.relational_database.contact import Contact
from backend.relational_database.user import User
from backend.mcp.app import EMBEDDINGS_MODEL, MCP
from backend.relational_database.engine import Session, SQL_ENGINE, SQL_JOB_MANAGER
from backend.auth import Role
from fastmcp.server.dependencies import get_access_token
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.verification import mcp_get_user_id

@MCP.tool(auth=Role.mcp_has_role("user"))
async def add_contact(
    first_name:str, last_name:str, email:str | None = None, phone_number:str | None = None, notes:str | None = None
):
    """
    Adds a contact to the user's contact book.
    Args:
        first_name(Required, type:str): The first name of the contact.
        last_name(Optional, type:str): The last name of the contact.
        email(Optional, type:str): The email of the contact.
        phone_number(Optional, type:str): The phone number of the contact, must follow the regex format "^\+[1-9]\d{1,14}$".
        notes(Optional, type:str): Notes about the contact.
    """
    user_id = mcp_get_user_id()
    async with Session(bind=SQL_ENGINE) as session:
        await SQL_JOB_MANAGER.wait("user")
        user = await session.get(User, user_id)
        if not user:
            raise Exception(f"User with id {user_id} does not exist")
        embedding_string = Contact.format_contact_embedding_string(first_name, last_name, email, phone_number, notes)
        embedding = EMBEDDINGS_MODEL.encode(embedding_string).tolist()
        contact = Contact(
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone_number,
            notes=notes,
            embedding=embedding
        )

        user.contacts.append(contact)

        try:
            SQL_JOB_MANAGER.add("contact", session.commit())
            return f"Successfully added contact: \"{first_name}\""
        except Exception as e:
            SQL_JOB_MANAGER.add("contact", session.rollback())
            error_message = str(e)
            return f"Failed to add contact: {error_message}"

@MCP.tool(auth=Role.mcp_has_role("user"))
async def delete_contact(first_name:str, last_name:str):
    """
    Deletes a contact from the user's contact book.
    Args:
        first_name(Required, type:str): The first name of the contact. This must be the contact's exact last name. If it is not, this tool will do an edit-distance fuzzy lookup of the full name and offer contact full name suggestions.
        last_name(Sometimes Required, type:str): The last name of the contact. This is only required if a last name exists on the person's contact. This must be the contact's exact last name. If it is not, this tool will do an edit-distance fuzzy lookup of the full name and offer contact full name suggestions.
    """
    user_id = mcp_get_user_id()
    async with Session(bind=SQL_ENGINE) as session:
        await SQL_JOB_MANAGER.wait("user", "contact")
        user = await session.get(User, user_id)
        if not user:
            raise Exception(f"User with id {user_id} does not exist")
        contact = next((c for c in user.contacts if c.first_name == first_name and last_name), None)

        if not contact:
            return await contact_suggestion(session, user_id, first_name, last_name)

        if contact:
            user.contacts.remove(contact)
    
            # 3. Commit the change to the file
            try:
                SQL_JOB_MANAGER.add("contact", session.commit())
                return f"Successfully deleted contact: \"{first_name}\""
            except Exception as e:
                SQL_JOB_MANAGER.add("contact", session.rollback())
                return f"Error deleting contact: {str(e)}"
        else:
            return f"Failed to find contact with name: \"{first_name}\"\nTry searching for the contact first."

@MCP.tool(auth=Role.mcp_has_role("user"))
async def edit_contact(first_name:str, last_name:str = '', email:str | None = None, phone_number:str | None = None, notes:str | None = None):
    """
    Edits a contact in the user's contact book. If one of the optional arguments is not included, it will not be changed in the contact.
    Whenever you learn something new about an existing contact, you should add it to that contact's notes.
    
    IMPORTANT: make sure you always read a contact with search_contacts before you edit that contact.
    
    Args:
        first_name(Required, type:str): The first name of the contact. This must be the contact's exact first name. If it is not, this tool will do an edit-distance fuzzy lookup of the full name and offer contact full name suggestions.
        last_name(Sometimes Required, type:str): The last name of the contact. This is only required if a last name exists on the person's contact. This must be the contact's exact last name. If it is not, this tool will do an edit-distance fuzzy lookup of the full name and offer contact full name suggestions.
        email(Optional, type:str): The email of the contact.
        phone_number(Optional, type:str): The phone number of the contact, must follow the regex format "^\+[1-9]\d{1,14}$".
        notes(Optional, type:str): Notes about the contact.
    """
    user_id = mcp_get_user_id()
    async with Session(bind=SQL_ENGINE) as session:
        await SQL_JOB_MANAGER.wait("user", "contact")

        stmt = (
            select(Contact)
            .where(
                Contact.user_id == user_id,
                Contact.first_name == first_name,
                Contact.last_name == last_name,
            ).limit(1)
        )

        contact = await session.scalar(stmt)

        if not contact:
            return await contact_suggestion(session, user_id, first_name, last_name)


        # Edit the contact
        if email is not None:
            contact.email = email
        if phone_number is not None:
            contact.phone_number = phone_number
        if notes is not None:
            contact.notes = notes

        # Regenerate the vector embedding since the data changed
        embedding_string = Contact.format_contact_embedding_string(contact.first_name, contact.last_name, contact.email, contact.phone_number, contact.notes)
        contact.embedding = EMBEDDINGS_MODEL.encode(embedding_string).tolist()
        try:
            SQL_JOB_MANAGER.add("contact", session.commit())
            return f"Successfully edited contact: \"{contact.first_name}\""
        except Exception as e:
            # Extract the message
            SQL_JOB_MANAGER.add("contact", session.rollback())
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
        distance_expr = func.vec_distance_cosine(Contact.embedding, query_vector_bytes).label("distance")

        stmt = (
            select(Contact, distance_expr)
            .order_by(distance_expr.asc())
            .limit(limit)
        )

        results = session.execute(stmt).all()
        contacts: list[tuple[Contact, float]] = [(row.Contact, row.distance) for row in results]

        return_value = f"Found {len(results)} Contacts" + (":" if len(results) > 0 else ".")
        for i, (contact, distance) in enumerate(contacts, 1):
            return_value += f"\n --- Result {i} --- \n{contact.display_str()}\n"

        return return_value
    

async def contact_suggestion(session:AsyncSession, user_id:int, first_name:str, last_name:str) -> str:
    await SQL_JOB_MANAGER.wait("contact")
    # Make suggestions on failure to find contact
    stmt_suggestions = (
        select(Contact.first_name, Contact.last_name)
        .where(
            and_(
                Contact.user_id == user_id,
                or_(
                    func.levenshtein_less_equal(Contact.first_name, first_name) <= 3,
                    func.levenshtein_less_equal(Contact.last_name, last_name) <= 3
                )
            )
        )
        .order_by(
            func.least(
                func.levenshtein(Contact.first_name, first_name),
                func.levenshtein(Contact.last_name, last_name)
            ).asc()
        )
        .limit(10)
    )

    suggestions_result = await session.execute(stmt_suggestions)

    contact_suggestions:list[Contact] = suggestions_result.all()

    tool_response = f"No contact was found with the name \"{first_name}{f' {last_name}' if last_name.strip() != '' else ''}\". Perhaps you meant "

    for i in range(len(contact_suggestions)-1):
        contact = contact_suggestions[i]
        tool_response += f"\"{contact.first_name}{f' {contact.last_name}' if contact.last_name.strip() != '' else ''}\", "
    contact = contact_suggestions[i]
    tool_response += f"or \"{contact.first_name}{f' {contact.last_name}' if contact.last_name.strip() != '' else ''}\"."

    SQL_JOB_MANAGER.add("contact", session.rollback())
    return tool_response