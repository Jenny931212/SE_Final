# routes/auth.py
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from db import getDB

router = APIRouter()
#指定了模板檔案在您的專案中存放的位置
templates = Jinja2Templates(directory="templates")



@router.get("/login")
#訪問/login網址 伺服器載入模板 完整html回傳給瀏覽器
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})



# 登入動作（使用 Session）
#post 發送敏感資訊如密碼
@router.post("/login")

async def login_action(
    #直接傳入
    request: Request,
    #從使用者提交的 HTML 表單 中獲取值
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    #建立和管理資料庫連線 在登入驗證時可以查詢資料庫
    conn=Depends(getDB) 
    
):
    print("📥 收到登入請求：", username, password, role)

    # 查詢使用者
    async with conn.cursor() as cur: #建立游標
        await cur.execute( #執行 SQL 查詢語句
            "SELECT id, name, password, role FROM users WHERE name=%s AND password=%s;",
            (username, password),
        )
        user = await cur.fetchone()
        print("🔍 查詢結果：", user)

    # 沒找到
    if not user:
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "帳號或密碼錯誤"}
        )

    # 角色錯誤
    if user["role"] != role:
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "角色錯誤或無法登入"}
        )

    #  登入成功 → 寫入 Session
    response = RedirectResponse(url="/dashboard", status_code=302)
    request.session["user_id"] = user["id"]
    request.session["username"] = user["name"]
    request.session["role"] = user["role"]
    print(f"✅ 登入成功，user_id={user['id']} role={user['role']}")
    return response  # ← 這行現在正確地在函式內

#  註冊頁面

@router.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


#  註冊動作

@router.post("/register")
async def register_action(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    conn=Depends(getDB)
):
    async with conn.cursor() as cur:
        #開啟游標查詢
        await cur.execute("SELECT id FROM users WHERE name=%s;", (username,))
        exists = await cur.fetchone()
        if exists:
            return templates.TemplateResponse(
                "register.html", {"request": request, "error": "使用者名稱已存在"}
            )
        await cur.execute( #執行新的使用者插入
            "INSERT INTO users (name, password, role) VALUES (%s, %s, %s);",
            (username, password, role)
        )
    await conn.commit()
    print(f"🆕 註冊成功：{username} ({role})")
    return RedirectResponse(url="/login", status_code=302)


#  Dashboard 導向（依角色）

@router.get("/dashboard")
async def dashboard(request: Request):
    role = request.session.get("role")
    if not role:
        return RedirectResponse(url="/login")

    if role == "client":
        return RedirectResponse(url="/jobs/")
    elif role == "contractor":
        return RedirectResponse(url="/bid/available")
    else:
        return RedirectResponse(url="/login")


#  登出功能

@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    print("👋 使用者已登出")
    return RedirectResponse(url="/login", status_code=302)
