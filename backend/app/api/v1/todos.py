import json
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_redis
from app.core.redis import RedisClient
from app.db.session import get_db
from app.models.tag import todo_tags_table
from app.models.todo import Todo
from app.models.user import User
from app.schemas.tag import BulkStatusUpdate
from app.schemas.todo import TodoCreate, TodoListResponse, TodoResponse, TodoUpdate
from app.services.todo_service import (
    create_todo,
    delete_todo,
    get_todo_by_id,
    get_todos,
    update_todo,
)

router = APIRouter()

CACHE_TTL = 300  # 5 minutes


def _cache_key(
    user_id: uuid.UUID,
    page: int,
    size: int,
    status_filter: str | None,
    tag_id: str | None,
    keyword: str | None,
    date_from: str | None,
    date_to: str | None,
) -> str:
    """Build a per-user, per-filter cache key."""
    return (
        f"todos:{user_id}:{page}:{size}:"
        f"{status_filter or ''}:{tag_id or ''}:{keyword or ''}:"
        f"{date_from or ''}:{date_to or ''}"
    )


async def _invalidate_user_todo_cache(
    redis: RedisClient, user_id: uuid.UUID
) -> None:
    """Invalidate all cached todo pages for a given user."""
    pattern = f"todos:{user_id}:*"
    cursor = 0
    while True:
        cursor, keys = await redis.client.scan(cursor, match=pattern, count=100)
        if keys:
            await redis.client.delete(*keys)
        if cursor == 0:
            break


def _todo_to_response(todo: Todo, user_email: str) -> TodoResponse:
    return TodoResponse(
        id=todo.id,
        title=todo.title,
        description=todo.description,
        completed=todo.completed,
        user_id=todo.user_id,
        created_at=todo.created_at,
        updated_at=todo.updated_at,
        user_email=user_email,
    )


@router.get("", response_model=TodoListResponse)
async def list_todos(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1),
    # Tier 4: filter params
    status: str | None = Query(None, description="'completed' or 'active'"),
    tag_id: uuid.UUID | None = Query(None, description="Filter by tag UUID"),
    keyword: str | None = Query(None, description="Search in title/description"),
    date_from: date | None = Query(None, description="Filter by created_at >= date"),
    date_to: date | None = Query(None, description="Filter by created_at <= date"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Get paginated list of todos for the current user with optional filters."""
    skip = (page - 1) * size

    cache_key = _cache_key(
        current_user.id, page, size,
        status, str(tag_id) if tag_id else None,
        keyword, str(date_from) if date_from else None,
        str(date_to) if date_to else None,
    )

    cached = await redis.get(cache_key)
    if cached:
        return TodoListResponse(**json.loads(cached))

    # Build dynamic filter
    filters = [Todo.user_id == current_user.id]

    if status == "completed":
        filters.append(Todo.completed.is_(True))
    elif status == "active":
        filters.append(Todo.completed.is_(False))

    if keyword:
        like_expr = f"%{keyword}%"
        filters.append(
            (Todo.title.ilike(like_expr)) | (Todo.description.ilike(like_expr))
        )

    if date_from:
        filters.append(func.date(Todo.created_at) >= date_from)
    if date_to:
        filters.append(func.date(Todo.created_at) <= date_to)

    query = (
        select(Todo)
        .where(and_(*filters))
        .order_by(Todo.created_at.desc(), Todo.id.desc())
        .offset(skip)
        .limit(size)
    )

    if tag_id:
        query = query.join(
            todo_tags_table,
            and_(
                todo_tags_table.c.todo_id == Todo.id,
                todo_tags_table.c.tag_id == tag_id,
            ),
        )

    result = await db.execute(query)
    todos = list(result.scalars().unique().all())

    # Count query
    count_filters = filters.copy()
    count_query = select(func.count()).select_from(Todo).where(and_(*count_filters))
    if tag_id:
        count_query = count_query.join(
            todo_tags_table,
            and_(
                todo_tags_table.c.todo_id == Todo.id,
                todo_tags_table.c.tag_id == tag_id,
            ),
        )
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    items = [_todo_to_response(todo, current_user.email) for todo in todos]
    response = TodoListResponse(items=items, total=total, page=page, size=size)

    await redis.set(cache_key, response.model_dump_json(), ex=CACHE_TTL)
    return response


@router.post("", response_model=TodoResponse, status_code=status.HTTP_201_CREATED)
async def create_new_todo(
    todo_data: TodoCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Create a new todo item."""
    todo = await create_todo(db, todo_data, current_user.id)
    await _invalidate_user_todo_cache(redis, current_user.id)
    return _todo_to_response(todo, current_user.email)


@router.patch("/bulk-status", response_model=dict)
async def bulk_update_status(
    body: BulkStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Bulk update completion status for multiple todos.

    All todo_ids must belong to the current user.
    Runs in a single database transaction.
    """
    # Fetch all requested todos in one query
    result = await db.execute(
        select(Todo).where(
            Todo.id.in_(body.todo_ids),
        )
    )
    todos = list(result.scalars().all())

    # Verify ownership for all todos
    unauthorized = [str(t.id) for t in todos if t.user_id != current_user.id]
    if unauthorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Not authorized to modify todos: {unauthorized}",
        )

    # Verify all requested IDs were found
    found_ids = {t.id for t in todos}
    missing = [str(tid) for tid in body.todo_ids if tid not in found_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Todos not found: {missing}",
        )

    # Bulk update in the same transaction
    for todo in todos:
        todo.completed = body.completed

    await db.flush()
    await _invalidate_user_todo_cache(redis, current_user.id)

    return {"updated": len(todos), "completed": body.completed}


@router.get("/{todo_id}", response_model=TodoResponse)
async def get_todo(
    todo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific todo by ID."""
    todo = await get_todo_by_id(db, todo_id)
    if not todo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")
    if todo.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this todo")
    return _todo_to_response(todo, current_user.email)


@router.put("/{todo_id}", response_model=TodoResponse)
async def update_existing_todo(
    todo_id: uuid.UUID,
    todo_data: TodoUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Update a todo item."""
    todo = await get_todo_by_id(db, todo_id)
    if not todo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")
    if todo.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to modify this todo")

    update_data = todo_data.model_dump(exclude_unset=True)

    if "title" in update_data:
        todo.title = update_data["title"]
    if "description" in update_data:
        todo.description = update_data["description"]
    if "completed" in update_data and update_data["completed"] is not None:
        todo.completed = update_data["completed"]

    updated_todo = await update_todo(db, todo, {})
    await _invalidate_user_todo_cache(redis, current_user.id)
    return _todo_to_response(updated_todo, current_user.email)


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_todo(
    todo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Delete a todo item."""
    todo = await get_todo_by_id(db, todo_id)
    if not todo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")
    if todo.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this todo")

    await delete_todo(db, todo)
    await _invalidate_user_todo_cache(redis, current_user.id)
    return None
