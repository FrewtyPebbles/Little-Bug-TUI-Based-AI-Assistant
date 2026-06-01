import struct
from types import CoroutineType
from sqlalchemy import text
from sqlalchemy.orm import declarative_base, sessionmaker
import sqlite_vec
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.engine import URL
from backend.config import ENVIRONMENT
import asyncio

SQL_URL = URL.create(
    drivername="postgresql+asyncpg",
    username=ENVIRONMENT.APP_DB_USERNAME,
    password=ENVIRONMENT.APP_DB_PASSWORD,
    host=ENVIRONMENT.APP_DB_HOST,
    port=5432,
    database=ENVIRONMENT.APP_DB
)
SQL_URL
SQL_ENGINE = create_async_engine(SQL_URL, echo=True)

SQLBase = declarative_base()

async def setup_database():
    async with SQL_ENGINE.begin() as conn:
        # Create extensions
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS fuzzystrmatch"))
        
        # Optionally create your tables
        await conn.run_sync(SQLBase.metadata.create_all)

Session = async_sessionmaker(
    bind=SQL_ENGINE,
    class_=AsyncSession,
    expire_on_commit=False
)

class _SQLJobManager:
    """
    A singleton for managing sql jobs.
    """
    def __init__(self):
        self.jobs_by_model:dict[str, list[CoroutineType]] = {}

    def add(self, model:str, job:CoroutineType):
        if model not in self.jobs_by_model:
            self.jobs_by_model[model] = []
        self.jobs_by_model[model].append(job)

    async def wait(self, *model_dependencies:str):
        dependencies:list[CoroutineType] = []
        for jobs in (self.jobs_by_model[model] for model in model_dependencies):
            dependencies.extend(jobs)
        await asyncio.gather(*dependencies)

SQL_JOB_MANAGER = _SQLJobManager()
