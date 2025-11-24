"""Database connection and session management."""

import os
from typing import AsyncGenerator
import asyncpg


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://todos_user:todos_password@postgres:5432/todos_db",
)


async def get_db_pool() -> asyncpg.Pool:
    """Create and return a database connection pool."""
    return await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=10,
    )


async def get_db_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """Get a database connection from the pool."""
    pool = await get_db_pool()
    async with pool.acquire() as connection:
        yield connection
    await pool.close()
