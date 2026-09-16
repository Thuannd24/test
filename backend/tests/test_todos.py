"""Todo tests – including business logic and authorization boundary tests."""

import pytest
from httpx import AsyncClient


# ─────────────────────────── helpers ──────────────────────────────────────────

async def get_auth_token(client: AsyncClient, email: str = "todo@example.com") -> str:
    """Helper to register and get auth token."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    return response.json()["access_token"]


async def create_todo_helper(
    client: AsyncClient,
    token: str,
    title: str = "Test Todo",
    description: str | None = None,
) -> dict:
    """Helper to create a todo and return its data."""
    payload = {"title": title}
    if description is not None:
        payload["description"] = description

    response = await client.post(
        "/api/v1/todos",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, f"Failed to create todo: {response.text}"
    return response.json()


# ─────────────────────────── basic CRUD ───────────────────────────────────────

@pytest.mark.asyncio
async def test_create_todo(client: AsyncClient):
    """Test creating a new todo."""
    token = await get_auth_token(client, "create@example.com")

    response = await client.post(
        "/api/v1/todos",
        json={"title": "Test Todo", "description": "A test todo item"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Todo"
    assert data["description"] == "A test todo item"
    assert data["completed"] is False


@pytest.mark.asyncio
async def test_get_todos(client: AsyncClient):
    """Test getting todo list."""
    token = await get_auth_token(client, "list@example.com")

    await create_todo_helper(client, token, "List Todo")

    response = await client.get(
        "/api/v1/todos",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_update_todo(client: AsyncClient):
    """Test updating a todo."""
    token = await get_auth_token(client, "update@example.com")

    todo = await create_todo_helper(client, token, "Update Me")
    todo_id = todo["id"]

    response = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"title": "Updated Title", "completed": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"


@pytest.mark.asyncio
async def test_delete_todo(client: AsyncClient):
    """Test deleting a todo."""
    token = await get_auth_token(client, "delete@example.com")

    todo = await create_todo_helper(client, token, "Delete Me")
    todo_id = todo["id"]

    response = await client.delete(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_get_single_todo(client: AsyncClient):
    """Test getting a single todo by ID."""
    token = await get_auth_token(client, "single@example.com")

    todo = await create_todo_helper(client, token, "Single Todo", "Get me")
    todo_id = todo["id"]

    response = await client.get(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Single Todo"


# ─────────────────────────── security: authorization boundary ─────────────────

@pytest.mark.asyncio
async def test_cross_user_cannot_read_todo(client: AsyncClient):
    """Bug fix: User A cannot read User B's todo (IDOR prevention).

    Previously GET /todos/{id} only checked existence, not ownership,
    allowing any authenticated user to read any todo by guessing/knowing the ID.
    """
    token_a = await get_auth_token(client, "userA_read@example.com")
    token_b = await get_auth_token(client, "userB_read@example.com")

    # User A creates a todo
    todo = await create_todo_helper(client, token_a, "User A Private Todo")
    todo_id = todo["id"]

    # User B tries to read User A's todo
    response = await client.get(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code in (403, 404), (
        f"Expected 403 or 404 but got {response.status_code}. "
        "User B should not be able to read User A's todo."
    )


@pytest.mark.asyncio
async def test_cross_user_cannot_update_todo(client: AsyncClient):
    """Bug fix: User A cannot update User B's todo.

    Previously PUT /todos/{id} had no ownership check (IDOR vulnerability).
    """
    token_a = await get_auth_token(client, "userA_update@example.com")
    token_b = await get_auth_token(client, "userB_update@example.com")

    # User A creates a todo
    todo = await create_todo_helper(client, token_a, "User A Todo")
    todo_id = todo["id"]

    # User B tries to update User A's todo
    response = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"title": "Hacked by User B"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code in (403, 404), (
        f"Expected 403 or 404 but got {response.status_code}. "
        "User B should not be able to update User A's todo."
    )

    # Verify the todo was NOT changed
    verify_resp = await client.get(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["title"] == "User A Todo"


@pytest.mark.asyncio
async def test_cross_user_cannot_delete_todo(client: AsyncClient):
    """Bug fix: User A cannot delete User B's todo.

    Previously DELETE /todos/{id} had no ownership check (IDOR vulnerability).
    """
    token_a = await get_auth_token(client, "userA_delete@example.com")
    token_b = await get_auth_token(client, "userB_delete@example.com")

    # User A creates a todo
    todo = await create_todo_helper(client, token_a, "User A Precious Todo")
    todo_id = todo["id"]

    # User B tries to delete User A's todo
    response = await client.delete(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code in (403, 404), (
        f"Expected 403 or 404 but got {response.status_code}. "
        "User B should not be able to delete User A's todo."
    )

    # Verify the todo still exists for User A
    verify_resp = await client.get(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert verify_resp.status_code == 200


# ─────────────────────────── business logic ───────────────────────────────────

@pytest.mark.asyncio
async def test_toggle_completed_false_persists(client: AsyncClient):
    """Bug fix: Setting completed=False must persist correctly.

    Previously the update logic used `if todo_data.completed:` which evaluates
    False as falsy and skips the update, making it impossible to uncheck a todo.
    """
    token = await get_auth_token(client, "toggle@example.com")

    # Create and mark as completed
    todo = await create_todo_helper(client, token, "Toggle Me")
    todo_id = todo["id"]

    await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"completed": True},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Now toggle back to incomplete
    resp_uncheck = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"completed": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_uncheck.status_code == 200

    data = resp_uncheck.json()
    assert data["completed"] is False, (
        "completed should be False after unchecking. "
        "If True, the `if todo_data.completed:` bug is not fixed."
    )


@pytest.mark.asyncio
async def test_partial_update_title_does_not_erase_description(client: AsyncClient):
    """Bug fix: Updating only the title must not erase the description.

    Previously model_dump() (without exclude_unset=True) would set unspecified
    fields to None, causing description to be erased when only title is updated.
    """
    token = await get_auth_token(client, "partial@example.com")

    # Create todo with both title and description
    todo = await create_todo_helper(
        client, token, "Original Title", "Important Description"
    )
    todo_id = todo["id"]
    assert todo["description"] == "Important Description"

    # Update only the title (do NOT send description)
    resp = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"title": "New Title"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["title"] == "New Title"
    assert data["description"] == "Important Description", (
        "Description should be preserved when only title is updated. "
        "If None, model_dump(exclude_unset=True) fix is not applied."
    )


@pytest.mark.asyncio
async def test_cache_invalidated_after_create(client: AsyncClient):
    """Bug fix: Cache must be invalidated after creating a new todo.

    Previously the cache key was global and never invalidated on mutations,
    so newly created todos would not appear until the 5-minute TTL expired.

    In tests, Redis is mocked (always returns None for GET), so this test
    verifies that the DB query returns the new todo correctly after creation.
    """
    token = await get_auth_token(client, "cache_create@example.com")

    # First fetch (empty)
    resp1 = await client.get(
        "/api/v1/todos",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == 200
    initial_count = resp1.json()["total"]

    # Create a todo
    await create_todo_helper(client, token, "New Todo for Cache Test")

    # Second fetch must include the new todo
    resp2 = await client.get(
        "/api/v1/todos",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["total"] == initial_count + 1, (
        "New todo should be visible after creation. "
        "Cache invalidation bug: stale data is being served."
    )


@pytest.mark.asyncio
async def test_cache_invalidated_after_delete(client: AsyncClient):
    """Cache must be invalidated after deleting a todo."""
    token = await get_auth_token(client, "cache_delete@example.com")

    # Create a todo
    todo = await create_todo_helper(client, token, "To Be Deleted")
    todo_id = todo["id"]

    # Confirm it exists
    resp1 = await client.get(
        "/api/v1/todos",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.json()["total"] == 1

    # Delete it
    await client.delete(
        f"/api/v1/todos/{todo_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    # Must not appear after deletion
    resp2 = await client.get(
        "/api/v1/todos",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.json()["total"] == 0, (
        "Deleted todo should not appear in list. "
        "Cache not invalidated after delete."
    )
