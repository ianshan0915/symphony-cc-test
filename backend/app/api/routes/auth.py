"""Authentication endpoints — register, login, refresh, and me."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    create_access_token,
    get_current_user,
    get_db_session,
    hash_password,
    verify_password,
)
from app.models.user import TokenResponse, User, UserCreate, UserOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    body: UserCreate,
    session: AsyncSession = Depends(get_db_session),
) -> UserOut:
    """Create a new user account and return the user profile with a JWT."""
    # Check if the email is already registered
    result = await session.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    logger.info("New user registered: %s", user.email)
    return UserOut.model_validate(user)


@router.post("/register/token", response_model=TokenResponse)
async def register_with_token(
    body: UserCreate,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """Create a new user account and return a JWT directly."""
    result = await session.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    token = create_access_token(user.id)
    logger.info("New user registered (with token): %s", user.email)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: UserCreate,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """Authenticate with email + password and return a JWT."""
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(user.id)
    logger.info("User logged in: %s", user.email)
    return TokenResponse(access_token=token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    current_user: User = Depends(get_current_user),
) -> TokenResponse:
    """Return a fresh JWT for an already-authenticated user."""
    token = create_access_token(current_user.id)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
async def me(
    current_user: User = Depends(get_current_user),
) -> UserOut:
    """Return the profile of the currently authenticated user."""
    return UserOut.model_validate(current_user)
