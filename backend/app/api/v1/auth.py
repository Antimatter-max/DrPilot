import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.models import User, AuditLog
from app.core.security import verify_password, hash_password, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    full_name: str
    role: str


class UpdateRoleRequest(BaseModel):
    role: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    full_name: str
    role: str


def seed_default_users(db: Session):
    try:
        if db.query(User).count() == 0:
            default_users = [
                User(
                    username="dr.vance",
                    hashed_password=hash_password("doctor123"),
                    full_name="Dr. Alex Vance, MD",
                    role="PHYSICIAN"
                ),
                User(
                    username="cmo.jenkins",
                    hashed_password=hash_password("cmo123"),
                    full_name="Dr. Sarah Jenkins (CMO / Governance)",
                    role="CMO_GOVERNANCE"
                )
            ]
            db.add_all(default_users)
            db.commit()
            print("[DB Seed] Default accounts created.")
    except Exception as e:
        print(f"[DB Seed Warning]: {str(e)}")


@router.post("/login", response_model=LoginResponse)
def login_for_access_token(payload: LoginRequest, db: Session = Depends(get_db)):
    seed_default_users(db)

    user = db.query(User).filter(User.username == payload.username.strip().lower()).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is deactivated.")

    db.add(AuditLog(
        action="USER_LOGIN_SUCCESS",
        user_id=str(user.id),
        user_name=user.full_name,
        user_role=user.role,
        patient_uid="SYSTEM_AUTH",
        details=f"Authenticated via DB hash check for role {user.role}"
    ))
    db.commit()

    access_token = create_access_token(data={"sub": user.username, "role": user.role})

    return LoginResponse(
        access_token=access_token,
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        role=user.role
    )

@router.post("/logout")
def logout_user(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Logs a HIPAA-compliant logout event to audit_logs."""
    db.add(AuditLog(
        action="USER_LOGOUT",
        user_id=str(current_user.id),
        user_name=current_user.full_name,
        user_role=current_user.role,
        patient_uid="SYSTEM_AUTH",
        details=f"User {current_user.username} signed out of session"
    ))
    db.commit()
    return {"status": "success", "message": "Successfully logged out"}

@router.get("/users")
def get_all_users(db: Session = Depends(get_db)):
    """Retrieves all registered system users from PostgreSQL."""
    seed_default_users(db)
    users = db.query(User).order_by(User.id.asc()).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "full_name": u.full_name,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at.strftime("%Y-%m-%d %H:%M:%S") if u.created_at else "N/A"
        }
        for u in users
    ]


@router.post("/register")
def register_user(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Registers a new user into PostgreSQL."""
    username_clean = payload.username.strip().lower()

    existing_user = db.query(User).filter(User.username == username_clean).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    new_user = User(
        username=username_clean,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role.upper()
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "status": "success",
        "message": f"Account created for {new_user.full_name}",
        "username": new_user.username,
        "role": new_user.role
    }


@router.put("/users/{user_id}/role")
def update_user_role(user_id: int, payload: UpdateRoleRequest, db: Session = Depends(get_db)):
    """Updates a user's role (e.g. PHYSICIAN -> CMO_GOVERNANCE)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = payload.role.upper()
    db.commit()
    db.refresh(user)

    return {
        "status": "success",
        "message": f"User {user.username} role updated to {user.role}",
        "role": user.role
    }


@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """Deletes a user account from PostgreSQL."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    username = user.username
    db.delete(user)
    db.commit()

    return {
        "status": "success",
        "message": f"Account '{username}' permanently removed."
    }