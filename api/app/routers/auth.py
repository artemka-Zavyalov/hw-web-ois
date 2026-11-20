from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, status, HTTPException, Response, Request
from sqlalchemy import select, func, delete
from sqlalchemy.exc import IntegrityError

from app.auth import CurrentUser
from app.schemas import ChangePasswordRequest, ErrorResponse, UserRead, RegisterRequest, LoginRequest
from app.db import SessionDep, violated_constraint
from app.models import User, AuthSession, LoginAttempt
from app.security import (
    hash_password,
    verify_password,
    new_session_token,
    token_digest,
    SESSION_TTL, SESSION_COOKIE, COOKIE_SECURE
)

router = APIRouter(prefix="/api/auth", tags=["Вход"])

UNAUTHORIZED = {401: {"model": ErrorResponse, "description": "Не выполнен вход"}}
LOGIN_WINDOW = timedelta(minutes=15)
MAX_FAILED_LOGINS = 5

@router.post(
    "/resister",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse, "description": "Email уже зарегистрирован"}},
    summary="Регистрация студента",
)
def register(payload: RegisterRequest, session: SessionDep):
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if violated_constraint(exc) == "users_email_key":
            raise HTTPException(status.HTTP_409_CONFLICT, "Этот email уже зарегистрирован") from exc
        raise
    return user

@router.post(
    "/login",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    responses={401: {"model": ErrorResponse, "description": "Неверный логин или пароль"}},
    summary="Вход",
)
def login(payload: LoginRequest, response: Response, session: SessionDep):
    email = payload.email.strip().lower()
    window_start = datetime.now(timezone.utc) - LOGIN_WINDOW
    failed_count = session.scalar(
        select(func.count(LoginAttempt.id)).where(
            LoginAttempt.email == email,
            LoginAttempt.attempted_at >= window_start,
        )
    ) or 0
    if failed_count >= MAX_FAILED_LOGINS:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Слишком много попыток, попробуйте через N минут",
        )

    user = session.scalars(
        select(User).where(func.lower(User.email) == email)
    ).first()
    if not verify_password(user.password_hash if user else None, payload.password) or not user or not user.is_active:
        session.add(LoginAttempt(email=email))
        session.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный email или пароль")

    token = new_session_token()
    session.add(
        AuthSession(
            token_hash=token_digest(token),
            user=user,
            expires_at=datetime.now(timezone.utc) + SESSION_TTL,
        )
    )
    session.commit()

    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax"
    )

    return user

@router.post(
    "/loguot",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=UNAUTHORIZED,
    summary="Выход"
)
def logout(request: Request, response: Response, user: CurrentUser, session: SessionDep):
    token = request.cookies.get(SESSION_COOKIE, "")
    session.execute(delete(AuthSession).where(AuthSession.token_hash == token_digest(token)))
    session.commit()
    response.delete_cookie(SESSION_COOKIE, httponly=True, secure=COOKIE_SECURE, samesite="lax")

@router.get("/me", response_model=UserRead, responses=UNAUTHORIZED, summary="Кто я")
def me(user: CurrentUser):
    return user


@router.post(
    "/password",
    response_model=UserRead,
    responses={
        **UNAUTHORIZED,
        400: {"model": ErrorResponse, "description": "Старый пароль неверен"},
    },
    summary="Сменить пароль",
)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    user: CurrentUser,
    session: SessionDep,
):
    if not verify_password(user.password_hash, payload.old_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Старый пароль неверен")

    current_token = request.cookies.get(SESSION_COOKIE, "")
    current_hash = token_digest(current_token)
    user.password_hash = hash_password(payload.new_password)
    session.execute(
        delete(AuthSession).where(
            AuthSession.user_id == user.id,
            AuthSession.token_hash != current_hash,
        )
    )
    session.commit()
    return user
