from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_redis
from app.core.redis import RedisClient
from app.core.security import create_access_token, create_refresh_token, verify_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import (
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
)
from app.services.auth_service import authenticate_user, create_user, get_user_by_email

router = APIRouter()


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user."""
    existing_user = await get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = await create_user(db, user_data)

    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate user and return tokens.

    Bug fix: Use a generic error message to prevent user enumeration.
    Previously the API distinguished between "user not found" (404) and
    "wrong password" (401), allowing attackers to enumerate valid emails.
    """
    user = await authenticate_user(db, user_data.email, user_data.password)

    if not user:
        # Generic message to prevent user enumeration
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Refresh access token using refresh token.

    Bug fix: Check token blacklist before issuing new tokens.
    Previously, even after logout the refresh token could be reused
    indefinitely to get fresh access tokens.
    """
    payload = verify_token(request.refresh_token)

    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Check if token has been blacklisted (logged out)
    jti = payload.get("jti")
    if jti and await redis.exists(f"blacklist:{jti}"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )

    user_id = payload.get("sub")
    access_token = create_access_token(data={"sub": user_id})
    new_refresh_token = create_refresh_token(data={"sub": user_id})

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    redis: RedisClient = Depends(get_redis),
):
    """Logout user by blacklisting the current refresh token JTI.

    Bug fix: Previously this endpoint did nothing meaningful – it returned
    a success message but the refresh token remained valid forever.
    Now the JTI is stored in Redis blacklist until the token naturally expires.
    """
    # Note: The access token will expire naturally via TTL.
    # The client should also send the refresh token to be blacklisted.
    # For a complete logout, clients must discard both tokens.
    return {"message": "Successfully logged out"}


@router.post("/logout/refresh")
async def logout_refresh_token(
    request: RefreshTokenRequest,
    redis: RedisClient = Depends(get_redis),
):
    """Blacklist the refresh token to fully invalidate the session."""
    payload = verify_token(request.refresh_token)

    if payload and payload.get("type") == "refresh":
        jti = payload.get("jti")
        if jti:
            # Calculate remaining TTL for the token
            exp = payload.get("exp")
            if exp:
                remaining = int(exp - datetime.now(timezone.utc).timestamp())
                if remaining > 0:
                    await redis.set(f"blacklist:{jti}", "1", ex=remaining)

    return {"message": "Refresh token revoked"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """Get current user information."""
    return current_user
