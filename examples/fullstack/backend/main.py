"""FastAPI backend application for TODO management."""

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import asyncpg
from typing import List

from models import TodoCreate, TodoResponse

app = FastAPI(title="TODO API", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection pool (singleton)
_db_pool: asyncpg.Pool | None = None


async def get_db_pool() -> asyncpg.Pool:
    """Get or create database connection pool."""
    global _db_pool
    if _db_pool is None:
        database_url = os.getenv(
            "DATABASE_URL",
            "postgresql://todos_user:todos_password@postgres:5432/todos_db",
        )
        _db_pool = await asyncpg.create_pool(
            database_url,
            min_size=1,
            max_size=10,
        )
    return _db_pool


@app.on_event("startup")
async def startup():
    """Initialize database pool on startup."""
    await get_db_pool()


@app.on_event("shutdown")
async def shutdown():
    """Close database pool on shutdown."""
    global _db_pool
    if _db_pool:
        await _db_pool.close()
        _db_pool = None


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/todos", response_model=List[TodoResponse])
async def get_todos():
    """Get all todos."""
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, title, completed, created_at FROM todos ORDER BY created_at DESC"
            )
            todos = [
                TodoResponse(
                    id=row["id"],
                    title=row["title"],
                    completed=row["completed"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]
            return todos
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/todos", response_model=TodoResponse, status_code=201)
async def create_todo(todo: TodoCreate):
    """Create a new todo."""
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO todos (title, completed) VALUES ($1, $2) RETURNING id, title, completed, created_at",
                todo.title,
                False,
            )
            return TodoResponse(
                id=row["id"],
                title=row["title"],
                completed=row["completed"],
                created_at=row["created_at"],
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/todos/{todo_id}", status_code=204)
async def delete_todo(todo_id: int):
    """Delete a todo by ID."""
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            result = await conn.execute("DELETE FROM todos WHERE id = $1", todo_id)
            if result == "DELETE 0":
                raise HTTPException(status_code=404, detail="Todo not found")
            return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
