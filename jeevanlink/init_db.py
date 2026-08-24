"""Create the JeevanLink database tables.

Usage:
    python -m jeevanlink.init_db

Safe to run more than once: every table and index uses ``IF NOT EXISTS``,
so re-running will not destroy existing data.

Picks the right schema file automatically: ``schema.sql`` for SQLite,
``schema_postgres.sql`` when ``DATABASE_URL`` points at PostgreSQL.
"""

from .database import backend_name
from .database import describe_database
from .database import get_db_connection
from .database import schema_path


def initialise_database() -> None:
    connection = get_db_connection()
    try:
        with open(schema_path(), "r", encoding="utf-8") as file:
            connection.executescript(file.read())
        connection.commit()
    finally:
        connection.close()

    print(f"Database created successfully ({backend_name()})")
    print(f"  location: {describe_database()}")


if __name__ == "__main__":
    initialise_database()
