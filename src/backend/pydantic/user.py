from pydantic import BaseModel

class CreateUserModel:
    username:str
    password:str
    email:str
    first_name:str
    last_name:str