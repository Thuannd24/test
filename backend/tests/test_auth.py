"""Auth tests – including security-critical scenarios."""

import time

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, create_refresh_token


# ─────────────────────────── helpers ──────────────────────────────────────────

async def register_user(client: AsyncClient, email: str, password: str = "password123"):
    """Helper to register a user and return response JSON."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    return response


# ─────────────────────────── basic auth flow ──────────────────────────────────

@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """Test successful user registration."""
    response = await register_user(client, "test@example.com")
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    """Registering with an already-used email returns 400."""
    await register_user(client, "dup@example.com")
    response = await register_user(client, "dup@example.com")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """Test successful login after registration."""
    await register_user(client, "login@example.com")

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_get_current_user(client: AsyncClient):
    """Test getting current user info."""
    reg_response = await register_user(client, "me@example.com")
    token = reg_response.json()["access_token"]

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "me@example.com"


@pytest.mark.asyncio
async def test_logout(client: AsyncClient):
    """Test logout endpoint."""
    reg_response = await register_user(client, "logout@example.com")
    token = reg_response.json()["access_token"]

    response = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Successfully logged out"


# ─────────────────────────── security: JWT expiry ─────────────────────────────

@pytest.mark.asyncio
async def test_expired_token_rejected(client: AsyncClient):
    """Bug fix verification: Expired JWT access tokens must be rejected with 401.

    Previously verify_token had options={'verify_exp': False} which allowed
    expired tokens to be accepted forever – a critical security vulnerability.
    """
    from datetime import timedelta

    # Create a token that expired 1 second ago
    expired_token = create_access_token(
        data={"sub": "00000000-0000-0000-0000-000000000001"},
        expires_delta=timedelta(seconds=-1),
    )

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401, (
        "Expired JWT token should be rejected with 401. "
        "If this fails, verify_exp is still disabled in security.py."
    )


@pytest.mark.asyncio
async def test_tampered_token_rejected(client: AsyncClient):
    """Tampered / invalid JWT signature must be rejected with 401."""
    reg_response = await register_user(client, "tamper@example.com")
    valid_token = reg_response.json()["access_token"]

    # Corrupt the signature (last segment)
    parts = valid_token.split(".")
    tampered = parts[0] + "." + parts[1] + ".invalidsignature"

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tampered}"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_wrong_password_returns_401_not_404(client: AsyncClient):
    """Bug fix: Login with wrong password must return 401, not 404.

    Returning 404 for 'email not found' and 401 for 'wrong password'
    allows user enumeration (attackers can discover valid emails).
    Both cases should return the same generic 401 error.
    """
    await register_user(client, "enum@example.com")

    # Wrong password for existing user
    resp_wrong_pass = await client.post(
        "/api/v1/auth/login",
        json={"email": "enum@example.com", "password": "wrongpassword"},
    )
    assert resp_wrong_pass.status_code == 401

    # Non-existent email – must also return 401 (not 404)
    resp_no_user = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "any"},
    )
    assert resp_no_user.status_code == 401, (
        "Login with unknown email should return 401 to prevent user enumeration, "
        "not 404 which reveals whether the email exists."
    )
    # Both errors should have the same message
    assert resp_wrong_pass.json()["detail"] == resp_no_user.json()["detail"]
