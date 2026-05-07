import struct
from sqlalchemy.orm import declarative_base, sessionmaker
import sqlite_vec
from sqlalchemy import LargeBinary, TypeDecorator, create_engine, event
from rapidfuzz.distance import Levenshtein

SQL_ENGINE = create_engine("sqlite:///database.db")

@event.listens_for(SQL_ENGINE, "connect")
def load_extension(dbapi_con, con_record):
    dbapi_con.enable_load_extension(True)
    sqlite_vec.load(dbapi_con)
    dbapi_con.enable_load_extension(False)

@event.listens_for(SQL_ENGINE, "connect")
def add_custom_functions(dbapi_connection, connection_record):
    # Register the Python function 'Levenshtein.distance' as 'levenshtein' in SQL
    # The '2' indicates it takes two arguments
    dbapi_connection.create_function("levenshtein", 2, Levenshtein.distance)

Session = sessionmaker(bind=SQL_ENGINE)

SQLBase = declarative_base()

class SQLiteVector(TypeDecorator):
    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value, dialect) -> bytes | None:
        if value is not None:
            return sqlite_vec.serialize_float32(value)
        return None

    def process_result_value(self, value, dialect) -> list[float] | None:
        if value is None:
            return None
        # Convert binary blob back to list [0.1, 0.2...]
        num_floats = len(value) // 4
        return list(struct.unpack(f'{num_floats}f', value))