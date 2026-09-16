import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_redis
from app.core.redis import RedisClient
from app.db.session import get_db
from app.models.user import User
from app.schemas.tag import (
    AttachTagRequest,
    TagCreate,
    TagListResponse,
    TagResponse,
    TagUpdate,
)
from app.services.tag_service import (
    attach_tag_to_todo,
    create_tag,
    delete_tag,
    detach_tag_from_todo,
    get_tag_by_id,
    get_tag_by_name,
    get_tags_by_user,
    update_tag,
)
from app.services.todo_service import get_todo_by_id

router = APIRouter()


# ── Helper ──────────────────────────────────────────────────────────────────

async def _get_user_tag_or_404(
    db: AsyncSession, tag_id: uuid.UUID, current_user: User
):
    """Fetch a tag and verify it belongs to the current user."""
    tag = await get_tag_by_id(db, tag_id)
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    if tag.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return tag


async def _invalidate_todo_cache(redis: RedisClient, user_id: uuid.UUID) -> None:
    pattern = f"todos:{user_id}:*"
    cursor = 0
    while True:
        cursor, keys = await redis.client.scan(cursor, match=pattern, count=100)
        if keys:
            await redis.client.delete(*keys)
        if cursor == 0:
            break


# ── Tag CRUD ─────────────────────────────────────────────────────────────────

@router.get("", response_model=TagListResponse)
async def list_tags(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all tags of the authenticated user."""
    tags, total = await get_tags_by_user(db, current_user.id)
    return TagListResponse(items=tags, total=total)


@router.post("", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
async def create_new_tag(
    tag_data: TagCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new tag.

    Tag names are unique per user (case-insensitive).
    """
    existing = await get_tag_by_name(db, current_user.id, tag_data.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tag '{tag_data.name}' already exists (case-insensitive)",
        )

    tag = await create_tag(db, tag_data, current_user.id)
    return tag


@router.patch("/{tag_id}", response_model=TagResponse)
async def update_existing_tag(
    tag_id: uuid.UUID,
    tag_data: TagUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rename or update a tag."""
    tag = await _get_user_tag_or_404(db, tag_id, current_user)

    # Check for duplicate name if name is being changed
    if tag_data.name and tag_data.name.lower() != tag.name.lower():
        existing = await get_tag_by_name(db, current_user.id, tag_data.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Tag '{tag_data.name}' already exists",
            )

    updated = await update_tag(db, tag, tag_data)
    return updated


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_tag(
    tag_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Delete a tag and remove it from all todos."""
    tag = await _get_user_tag_or_404(db, tag_id, current_user)
    await delete_tag(db, tag)
    # Invalidate todo cache because todos may have had this tag attached
    await _invalidate_todo_cache(redis, current_user.id)
    return None


# ── Tag-Todo Attachment ───────────────────────────────────────────────────────

@router.post("/{tag_id}/todos/{todo_id}", status_code=status.HTTP_200_OK)
async def attach_tag(
    tag_id: uuid.UUID,
    todo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Attach a tag to a todo.

    Both the tag and the todo must belong to the current user.
    """
    tag = await _get_user_tag_or_404(db, tag_id, current_user)

    todo = await get_todo_by_id(db, todo_id)
    if not todo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")
    if todo.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    await attach_tag_to_todo(db, todo, tag)
    await _invalidate_todo_cache(redis, current_user.id)
    return {"message": "Tag attached successfully"}


@router.delete("/{tag_id}/todos/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def detach_tag(
    tag_id: uuid.UUID,
    todo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Detach a tag from a todo."""
    tag = await _get_user_tag_or_404(db, tag_id, current_user)

    todo = await get_todo_by_id(db, todo_id)
    if not todo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")
    if todo.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    await detach_tag_from_todo(db, todo, tag)
    await _invalidate_todo_cache(redis, current_user.id)
    return None
