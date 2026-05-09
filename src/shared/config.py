from typing import Literal
from enum import Enum
from pydantic_settings import BaseSettings, SettingsConfigDict

class Environment(BaseSettings):
    
    # AUTH
    CLI_AUTH_BROWSER_PORT:int = 8800
    ### This is the port of the localhosted login page on the client's default browser.
    CLI_AUTH_LOOPBACK_URI:str = f"http://localhost:{CLI_AUTH_BROWSER_PORT}/callback"
    ### This is where the key is sent to after the user logs in on the client.

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"  # Ignores extra variables in .env not defined here
    )

SHARED_ENVIRONMENT = Environment()