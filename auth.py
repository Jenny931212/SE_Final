# auth.py
from fastapi import Request
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv
from psycopg.rows import dict_row
import os

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")

def setup_session(app):
    app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, session_cookie="jp_session")

def login_user(request: Request, user_id: int):
    request.session["user_id"] = user_id

def logout_user(request: Request):
    request.session.clear()

async def current_user(request: Request, conn) -> dict | None:
    uid = request.session.get("user_id")
    if not uid:
        return None
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute("SELECT id, username, role, created_at FROM users WHERE id=%s;", (uid,))
        return await cur.fetchone()
