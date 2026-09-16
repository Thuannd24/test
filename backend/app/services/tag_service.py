import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tag import Tag, todo_tags_table
from app.models.todo import Todo
from app.schemas.tag import TagCreate, TagUpdate


async def get_tags_by_user(
    db: AsyncSession, user_id: uuid.UUID
) -> tuple[list[Tag], int]:
    """Get all tags for a specific user."""
    query = select(Tag).where(Tag.user_id == user_id).order_by(Tag.name)
    result = await db.execute(query)
    tags = list(result.scalars().all())

    count_query = select(func.count()).select_from(Tag).where(Tag.user_id == user_id)
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    return tags, total


async def get_tag_by_id(
    db: AsyncSession, tag_id: uuid.UUID
) -> Tag | None:
    """Get tag by ID."""
    result = await db.execute(select(Tag).where(Tag.id == tag_id))
    return result.scalar_one_or_none()


async def get_tag_by_name(
    db: AsyncSession, user_id: uuid.UUID, name: str
) -> Tag | None:
    """Get tag by name for a user (case-insensitive)."""
    result = await db.execute(
        select(Tag).where(
            Tag.user_id == user_id,
            func.lower(Tag.name) == name.lower(),
        )
    )
    return result.scalar_one_or_none()


async def create_tag(
    db: AsyncSession, tag_data: TagCreate, user_id: uuid.UUID
) -> Tag:
    """Create a new tag for the given user."""
    tag = Tag(
        user_id=user_id,
        name=tag_data.name,
        color=tag_data.color,
    )
    db.add(tag)
    await db.flush()
    await db.refresh(tag)
    return tag


async def update_tag(
    db: AsyncSession, tag: Tag, tag_data: TagUpdate
) -> Tag:
    """Update tag fields (partial update)."""
    update_data = tag_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(tag, key, value)
    await db.flush()
    await db.refresh(tag)
    return tag


async def delete_tag(db: AsyncSession, tag: Tag) -> None:
    """Delete a tag and all its todo-tag associations (cascade)."""
    await db.delete(tag)
    await db.flush()


async def attach_tag_to_todo(
    db: AsyncSession, todo: Todo, tag: Tag
) -> None:
    """Attach a tag to a todo (idempotent – safe to call if already attached)."""
    # Check if already attached
    existing = await db.execute(
        select(todo_tags_table).where(
            todo_tags_table.c.todo_id == todo.id,
            todo_tags_table.c.tag_id == tag.id,
        )
    )
    if existing.first() is None:
        await db.execute(
            todo_tags_table.insert().values(todo_id=todo.id, tag_id=tag.id)
        )
        await db.flush()


async def detach_tag_from_todo(
    db: AsyncSession, todo: Todo, tag: Tag
) -> None:
    """Remove a tag from a todo."""
    await db.execute(
        todo_tags_table.delete().where(
            todo_tags_table.c.todo_id == todo.id,
            todo_tags_table.c.tag_id == tag.id,
        )
    )
    await db.flush()
