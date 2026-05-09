from typing import Literal
from enum import Enum
from pydantic_settings import BaseSettings, SettingsConfigDict

class EnvironmentType(str, Enum):
    DEV = "DEV"
    PROD = "PROD"
    @classmethod
    def _missing_(cls, value):
        # This allows case-insensitive matching for the values
        for member in cls:
            if member.value.lower() == value.lower():
                return member
        return None

class Environment(BaseSettings):
    ENVIRONMENT_TYPE:EnvironmentType = EnvironmentType.DEV

    # KEYCLOAK
    KEYCLOAK_API_CLIENT_ID:str = "little-bug-api-client"
    KEYCLOAK_CLI_CLIENT_ID:str = "little-bug-cli-client"
    KEYCLOAK_API_CLIENT_SECRET:str
    KEYCLOAK_REALM:str = "little-bug-realm"
    KEYCLOAK_ADMIN_USERNAME:str
    KEYCLOAK_ADMIN_PASSWORD:str
    KEYCLOAK_URL:str = "http://localhost:8080/"
    

    # DATABASE
    AUTH_DB_USERNAME:str
    AUTH_DB_PASSWORD:str
    MONGO_DB_USERNAME:str
    MONGO_DB_PASSWORD:str
    REDIS_PASSWORD:str
    APP_DB_USERNAME:str
    APP_DB_PASSWORD:str
    APP_DB:str = "application"

    # BACKEND
    BACKEND_PORT:int = 8000

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"  # Ignores extra variables in .env not defined here
    )

ENVIRONMENT = Environment()