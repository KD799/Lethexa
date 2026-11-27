from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.schemas.auth import UserRegister
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)
from app.database import get_app_connection

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_user(user_data: UserRegister):
    hashed_password = hash_password(user_data.password)

    try:
        with get_app_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO users (email, password_hash, role)
                    VALUES (%s, %s, 'user')
                    ON CONFLICT DO NOTHING
                    RETURNING user_id::text, email, role
                    """,
                    (user_data.email, hashed_password),
                )

                user = cursor.fetchone()

                if not user:
                    raise HTTPException(
                        status_code=409,
                        detail="An account with this email already exists",
                    )

        return {
            "message": "Account created successfully",
            "user": user,
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to create account",
        )


@router.post("/login")
def login_user(
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    email = form_data.username.strip().lower()

    with get_app_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT user_id::text, email, password_hash, role, is_active
                FROM users
                WHERE LOWER(email) = LOWER(%s)
                """,
                (email,),
            )
            user = cursor.fetchone()

    if (
        not user
        or not user["is_active"]
        or not verify_password(
            form_data.password,
            user["password_hash"],
        )
    ):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(user["user_id"])

    return {
        "access_token": token,
        "token_type": "bearer",
    }


@router.get("/me")
def get_my_profile(current_user=Depends(get_current_user)):
    return {
        "user_id": current_user["user_id"],
        "email": current_user["email"],
        "role": current_user["role"],
    }