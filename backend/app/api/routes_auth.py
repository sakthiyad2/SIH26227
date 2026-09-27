import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.db.database import get_connection

router = APIRouter(prefix="/auth")


class SignUpPayload(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=160)
    organization: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=10, max_length=128)
    role: str = "ANALYST"


class SignInPayload(BaseModel):
    email: str
    password: str


class AccountDecision(BaseModel):
    status: str


class AdminCreateUser(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=160)
    organization: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=10, max_length=128)
    role: str = "ANALYST"
    status: str = "ACTIVE"


def _public_user(row) -> dict:
    return {key: row[key] for key in ("id", "full_name", "email", "organization", "role", "status", "created_at", "last_login")}


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    token = authorization.split(" ", 1)[1].strip()
    conn = get_connection()
    row = conn.execute(
        "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ? AND s.expires_at > ?",
        (_token_hash(token), datetime.now(timezone.utc).isoformat()),
    ).fetchone()
    conn.close()
    if row is None or row["status"] != "ACTIVE":
        raise HTTPException(status_code=401, detail="Session expired or account inactive")
    return dict(row)


def require_roles(*roles: str):
    def dependency(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="This role is not authorized for the operation")
        return user

    return dependency


@router.post("/signup")
def signup(payload: SignUpPayload) -> dict:
    role = payload.role.upper()
    email = payload.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    if role not in {"ANALYST", "RESEARCHER"}:
        raise HTTPException(status_code=400, detail="Self-registration is limited to analyst and researcher roles")
    conn = get_connection()
    try:
        if conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
            raise HTTPException(status_code=409, detail="An account with this email already exists")
        conn.execute(
            "INSERT INTO users (id, full_name, email, organization, password_hash, role, status) VALUES (?, ?, ?, ?, ?, ?, 'PENDING')",
            (secrets.token_hex(16), payload.full_name.strip(), email, payload.organization.strip(), bcrypt.hashpw(payload.password.encode(), bcrypt.gensalt()).decode(), role),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "status": "PENDING", "message": "Account created. An administrator must approve access."}


@router.post("/signin")
def signin(payload: SignInPayload) -> dict:
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (payload.email.strip().lower(),)).fetchone()
    if row is None or not bcrypt.checkpw(payload.password.encode(), row["password_hash"].encode()):
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if row["status"] != "ACTIVE":
        conn.close()
        raise HTTPException(status_code=403, detail=f"Account status: {row['status'].lower()}")
    token = secrets.token_urlsafe(36)
    expires_at = datetime.now(timezone.utc) + timedelta(days=1)
    conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (datetime.now(timezone.utc).isoformat(), row["id"]))
    conn.execute("INSERT INTO sessions (id, user_id, token_hash, expires_at) VALUES (?, ?, ?, ?)", (secrets.token_hex(16), row["id"], _token_hash(token), expires_at.isoformat()))
    conn.commit()
    conn.close()
    return {"ok": True, "token": token, "user": _public_user(row), "expires_at": expires_at.isoformat()}


@router.get("/me")
def me(user: dict = Depends(get_current_user)) -> dict:
    return {"ok": True, "user": _public_user(user)}


@router.post("/logout")
def logout(authorization: str | None = Header(default=None)) -> dict:
    if authorization and authorization.lower().startswith("bearer "):
        conn = get_connection()
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(authorization.split(" ", 1)[1].strip()),))
        conn.commit()
        conn.close()
    return {"ok": True}


@router.get("/admin/users")
def users(user: dict = Depends(require_roles("ADMIN"))) -> dict:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return {"ok": True, "users": [_public_user(row) for row in rows]}


@router.post("/admin/users")
def create_user(payload: AdminCreateUser, admin: dict = Depends(require_roles("ADMIN"))) -> dict:
    email = payload.email.strip().lower()
    role = payload.role.upper()
    status = payload.status.upper()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    if role not in {"ADMIN", "ANALYST", "RESEARCHER"}:
        raise HTTPException(status_code=400, detail="Unsupported role")
    if status not in {"ACTIVE", "PENDING", "SUSPENDED"}:
        raise HTTPException(status_code=400, detail="Unsupported account status")
    conn = get_connection()
    try:
        if conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
            raise HTTPException(status_code=409, detail="An account with this email already exists")
        user_id = secrets.token_hex(16)
        conn.execute(
            "INSERT INTO users (id, full_name, email, organization, password_hash, role, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, payload.full_name.strip(), email, payload.organization.strip(), bcrypt.hashpw(payload.password.encode(), bcrypt.gensalt()).decode(), role, status),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    finally:
        conn.close()
    return {"ok": True, "user": _public_user(row), "created_by": admin["id"]}


@router.patch("/admin/users/{user_id}")
def update_user(user_id: str, payload: AccountDecision, admin: dict = Depends(require_roles("ADMIN"))) -> dict:
    status = payload.status.upper()
    if status not in {"ACTIVE", "SUSPENDED", "REJECTED"}:
        raise HTTPException(status_code=400, detail="Unsupported account status")
    if user_id == admin["id"] and status != "ACTIVE":
        raise HTTPException(status_code=400, detail="The active administrator cannot suspend or reject their own account")
    conn = get_connection()
    conn.execute("UPDATE users SET status = ? WHERE id = ?", (status, user_id))
    conn.commit()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True, "user": _public_user(row)}
