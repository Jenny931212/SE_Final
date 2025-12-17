# main.py
from fastapi import FastAPI, Request, Form, UploadFile, File, Depends, HTTPException, status
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from datetime import datetime, timedelta
from passlib.hash import pbkdf2_sha256
from dotenv import load_dotenv
from psycopg.rows import dict_row
import os
import uuid
from typing import Optional
from fastapi import Query

from db import getDB, close_pool
from auth import setup_session, current_user, login_user, logout_user

templates = Jinja2Templates(directory="templates")  #設定HTML位置
RATING_DEADLINE_DAYS = 14  # 評價期限：結案後 14 天內可以評
UPLOAD_DIR = Path("uploads")    #設定上傳的檔案要儲存的資料夾
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)   #建立資料夾

app = FastAPI(title="工作委託平台")   #建立 FastAPI 應用
setup_session(app)  #啟用 session 機制

# ------------ 首頁 / 註冊 / 登入 / 登出 ------------
#顯示平台首頁
@app.get("/", response_class=HTMLResponse)
async def index(request: Request, conn = Depends(getDB)):
    user = await current_user(request, conn)
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

#顯示註冊頁面
@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, conn = Depends(getDB)):
    return templates.TemplateResponse("register.html", {"request": request})
#處理註冊送出
@app.post("/register")
async def register(request: Request,
                   username: str = Form(...),
                   password: str = Form(...),
                   role: str = Form(...),
                   conn = Depends(getDB)):
    if role not in ("client", "contractor"):
        raise HTTPException(400, "無效的角色")
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute("SELECT 1 FROM users WHERE username=%s;", (username,))
        if await cur.fetchone():
            return templates.TemplateResponse("register.html", {"request": request, "error": "使用者名稱已存在"})
        hashed = pbkdf2_sha256.hash(password)   #把密碼加密後存入
        await cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (%s,%s,%s);",
            (username, hashed, role)
        )

        await conn.commit()
    return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)    #回傳到登入畫面

#顯示登入畫面
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, conn = Depends(getDB)):
    return templates.TemplateResponse("login.html", {"request": request})
#處理登入送出
@app.post("/login")
async def login(request: Request,
                username: str = Form(...),
                password: str = Form(...),
                conn = Depends(getDB)):
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute("SELECT id, username, password_hash, role FROM users WHERE username=%s;", (username,))    #從DB找出使用者帳號資訊
        row = await cur.fetchone()
    if not row:
        return templates.TemplateResponse("login.html", {"request": request, "error": "帳號不存在"})
    if not pbkdf2_sha256.verify(password, row["password_hash"]):
        return templates.TemplateResponse("login.html", {"request": request, "error": "帳號或密碼錯誤"})

    login_user(request, row["id"])  #呼叫 auth.py 裡的函式 把使用者的 ID 存進 session
    return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)    #跳到個人首頁的畫面

#登出 清除 session
@app.get("/logout")
async def logout(request: Request):
    logout_user(request)    #呼叫 auth.py 裡的函式，清除 session，登入資訊失效
    return RedirectResponse("/", status_code=status.HTTP_302_FOUND)

# ---------------- 個人首頁 ----------------
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, conn = Depends(getDB)):
    user = await current_user(request, conn)    #呼叫 auth.py 裡的函式 從 session（cookie）取出登入者資訊
    if not user:    #如果還沒登入就跳到登入畫面
        return RedirectResponse("/login")
    #從網址讀取 notice 參數
    notice_key = request.query_params.get("notice")
    notice = None
    if notice_key == "proposal_sent":
        notice = "您的承接意願已送出；若被委託，案件會出現在「我的首頁」。"
    #委託人
    if user["role"] == "client":    
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("""
                SELECT p.*, ur.username AS contractor_username
                FROM projects p
                LEFT JOIN users ur ON ur.id = p.contractor_id
                WHERE p.client_id=%s
                ORDER BY p.created_at DESC;
            """, (user["id"],))
            projects = await cur.fetchall()
        return templates.TemplateResponse("dashboard_client.html", {"request": request, "user": user, "projects": projects})
    #接案人
    else:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("""
                SELECT p.*, uc.username AS client_username, pr.created_at AS accepted_at
                FROM projects p
                JOIN users uc ON uc.id = p.client_id
                LEFT JOIN proposals pr ON pr.project_id = p.id AND pr.contractor_id = p.contractor_id AND pr.accepted = TRUE
                WHERE p.contractor_id=%s
                ORDER BY COALESCE(pr.created_at, p.created_at) DESC;
            """, (user["id"],))
            my_projects = await cur.fetchall()
            await cur.execute("SELECT COUNT(*) AS c FROM projects WHERE status='open';")
            open_count = (await cur.fetchone())["c"]
        return templates.TemplateResponse("dashboard_contractor.html",
            {"request": request, "user": user, "projects": my_projects, "open_count": open_count, "notice": notice})

# ------------- 委託人：建立、編輯、詳情、選人、結案 -------------
#顯示建立畫面
@app.get("/projects/create", response_class=HTMLResponse)
async def project_create_page(request: Request, conn = Depends(getDB)):
    user = await current_user(request, conn)    #從 session 讀取目前登入者的資訊
    if not user or user["role"] != "client":    #檢查身分權限
        return RedirectResponse("/login")
    return templates.TemplateResponse("project_create.html", {"request": request, "user": user})
#接收建立的案件內容
@app.post("/projects/create")
async def project_create(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    bid_deadline: str = Form(...),  # ★ 新增：HTML 會用 datetime-local 傳回來
    conn = Depends(getDB)
):
    user = await current_user(request, conn)    #從 session 讀取目前登入者的資訊
    if not user or user["role"] != "client":
        return RedirectResponse("/login")
    async with conn.cursor(row_factory=dict_row) as cur:
        # ★ 新增：把 datetime-local 的字串轉成 datetime
        deadline_dt = datetime.fromisoformat(bid_deadline)
        #把建立的標題、描述等案件內容寫入資料庫
        await cur.execute("""
            INSERT INTO projects (title, description, status, client_id, bid_deadline)
            VALUES (%s,%s,'open',%s,%s) RETURNING id;
        """, (title, description, user["id"], deadline_dt))
        project_id = (await cur.fetchone())["id"]   #把剛剛 RETURNING 的 ID 拿出來存成變數
        await conn.commit()     #確保資料真的寫進資料庫
    return RedirectResponse(f"/projects/{project_id}", status_code=status.HTTP_302_FOUND)   #會直接跳到案件詳情的畫面

#顯示編輯案件畫面
@app.get("/projects/{project_id}/edit", response_class=HTMLResponse)
async def project_edit_page(request: Request, project_id: int, conn = Depends(getDB)):
    user = await current_user(request, conn)
    if not user or user["role"] != "client":
        return RedirectResponse("/login")
    #從DB查詢要編輯的案件
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute("SELECT * FROM projects WHERE id=%s AND client_id=%s;", (project_id, user["id"]))
        project = await cur.fetchone()  #取出這個案件的資料
    if not project:
        raise HTTPException(404, "找不到案件")
    #委託人只有在公開、承作時和結案被退回時可以編輯案件
    if project["status"] not in ("open", "in_progress","reject"):
        raise HTTPException(400, "此狀態不可編輯")
    return templates.TemplateResponse("project_edit.html", {"request": request, "user": user, "project": project})  #跳到編輯畫面
#接收編輯的案件內容
@app.post("/projects/{project_id}/edit")
async def project_edit(
    request: Request,
    project_id: int,
    title: str = Form(...),
    description: str = Form(...),
    bid_deadline: str = Form(...),  # ★新增
    conn = Depends(getDB)
):
    user = await current_user(request, conn)
    if not user or user["role"] != "client":
        return RedirectResponse("/login")

    deadline_dt = datetime.fromisoformat(bid_deadline)  # ★新增

    async with conn.cursor() as cur:
        await cur.execute("""
            UPDATE projects
            SET title=%s, description=%s, bid_deadline=%s, updated_at=NOW()
            WHERE id=%s AND client_id=%s;
        """, (title, description, deadline_dt, project_id, user["id"]))
        await conn.commit()

    return RedirectResponse(f"/projects/{project_id}", status_code=status.HTTP_302_FOUND)

#查看案件詳情(委託人 & 接案人)
@app.get("/projects/{project_id}", response_class=HTMLResponse)
async def project_detail(request: Request, project_id: int, conn = Depends(getDB)):
    user = await current_user(request, conn)
    notice = request.query_params.get("notice")
    if not user:
        return RedirectResponse("/login")
    async with conn.cursor(row_factory=dict_row) as cur:
        #查詢該案件基本資料
        await cur.execute("""
            SELECT p.*, uc.username AS client_username, ur.username AS contractor_username
            FROM projects p
            JOIN users uc ON uc.id = p.client_id
            LEFT JOIN users ur ON ur.id = p.contractor_id
            WHERE p.id=%s;
        """, (project_id,))
        project = await cur.fetchone()
        if not project:
            raise HTTPException(404, "找不到案件")
        #查詢該案件有誰已經提出意願
        await cur.execute("""
            SELECT pr.*, u.username AS contractor_username
            FROM proposals pr JOIN users u ON u.id = pr.contractor_id
            WHERE pr.project_id=%s
            ORDER BY pr.created_at DESC;
        """, (project_id,))
        proposals = await cur.fetchall()
        #查詢該案的結案檔案
        await cur.execute("""
            SELECT * FROM closure_files WHERE project_id=%s ORDER BY created_at DESC;
        """, (project_id,))
        closures = await cur.fetchall()
        
        # ================== ★ 新增：撈 Issues + 留言 ==================
        await cur.execute("""
            SELECT i.*, u.username AS opener_name
            FROM issues i
            JOIN users u ON u.id = i.opener_id
            WHERE i.project_id=%s
            ORDER BY i.created_at DESC;
        """, (project_id,))
        issues = await cur.fetchall()

        # 把留言整理成：{ issue_id: [comment, comment, ...] }
        issue_comments_by_issue = {}

        if issues:
            issue_ids = [i["id"] for i in issues]  # 取出所有 issue id
            await cur.execute("""
                SELECT ic.*, u.username AS author_name
                FROM issue_comments ic
                JOIN users u ON u.id = ic.author_id
                WHERE ic.issue_id = ANY(%s)
                ORDER BY ic.created_at ASC;
            """, (issue_ids,))
            comments = await cur.fetchall()

            for c in comments:
                issue_comments_by_issue.setdefault(c["issue_id"], []).append(c)
        # ============================================================


        # ⭐⭐ 新增：查詢「目前登入者是否已經評價過對方」⭐⭐
        has_rated_contractor = False
        has_rated_client = False
        if project["contractor_id"]:
            if user["role"] == "client" and project["client_id"] == user["id"]:
                # 我是委託人，看我有沒有評過這個接案人
                await cur.execute(
                    """
                    SELECT 1 FROM ratings
                    WHERE project_id=%s AND rater_id=%s AND target_id=%s;
                    """,
                    (project_id, user["id"], project["contractor_id"])
                )
                has_rated_contractor = bool(await cur.fetchone())
            elif user["role"] == "contractor" and project["contractor_id"] == user["id"]:
                # 我是接案人，看我有沒有評過這個委託人
                await cur.execute(
                    """
                    SELECT 1 FROM ratings
                    WHERE project_id=%s AND rater_id=%s AND target_id=%s;
                    """,
                    (project_id, user["id"], project["client_id"])
                )
                has_rated_client = bool(await cur.fetchone())

    #根據身分決定要跳到哪個畫面
    if user["role"] == "client" and project["client_id"] == user["id"]:
        return templates.TemplateResponse("project_detail_client.html",
            {
                "request": request,
                "user": user,
                "project": project,
                "proposals": proposals,
                "closures": closures,
                "issues": issues,  # ★ 新增
                "issue_comments_by_issue": issue_comments_by_issue,  # ★ 新增
                "has_rated_contractor": has_rated_contractor,  # ⭐ 新增變數
                "notice": notice,
            })
    elif user["role"] == "contractor":
        return templates.TemplateResponse("project_detail_contractor.html",
            {
                "request": request,
                "user": user,
                "project": project,
                "proposals": proposals,
                "closures": closures,
                "issues": issues,  # ★ 新增
                "issue_comments_by_issue": issue_comments_by_issue,  # ★ 新增
                "has_rated_client": has_rated_client,          # ⭐ 新增變數
                "notice": notice,
            })
    else:
        raise HTTPException(403, "無權限")
        
#委託人要能下載「接案人提案書 PDF」
@app.get("/proposals/{proposal_id}/file")
async def download_proposal_file(proposal_id: int, request: Request, conn=Depends(getDB)):
    user = await current_user(request, conn)
    if not user:
        return RedirectResponse("/login")

    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute("""
            SELECT pr.id, pr.proposal_filename, pr.proposal_filepath,
                   p.client_id, p.contractor_id
            FROM proposals pr
            JOIN projects  p ON p.id = pr.project_id
            WHERE pr.id=%s;
        """, (proposal_id,))
        row = await cur.fetchone()

    if not row:
        raise HTTPException(404, "提案書不存在")

    # 只有此案委託人或接案人能下載
    if user["id"] not in (row["client_id"], row["contractor_id"]):
        raise HTTPException(403, "無權限下載")

    path = row["proposal_filepath"]
    if not path or not os.path.exists(path):
        raise HTTPException(404, "檔案已遺失")

    return FileResponse(path, media_type="application/pdf", filename=row["proposal_filename"])

#選擇接案人
@app.post("/projects/{project_id}/select")
async def select_contractor(request: Request, project_id: int, proposal_id: int = Form(...), conn = Depends(getDB)):
    user = await current_user(request, conn)
    if not user:
        return RedirectResponse("/login")
    async with conn.cursor(row_factory=dict_row) as cur:
        #驗證操作權限：必須是此案件的案主
        await cur.execute("SELECT client_id, bid_deadline FROM projects WHERE id=%s;", (project_id,))
        proj = await cur.fetchone()
        if not proj or proj["client_id"] != user["id"]:
            raise HTTPException(403, "無權限")
        # ★ 延伸一：只能在截止後選擇提案者
        if proj["bid_deadline"] and datetime.now(tz=proj["bid_deadline"].tzinfo) < proj["bid_deadline"]:
            return RedirectResponse(
                f"/projects/{project_id}?notice=bid_not_ended",
                status_code=status.HTTP_302_FOUND
            )
        #檢查接案人提出的意願屬於該案：避免跨案誤選
        await cur.execute("SELECT contractor_id FROM proposals WHERE id=%s AND project_id=%s;", (proposal_id, project_id))
        prop = await cur.fetchone()
        if not prop:
            raise HTTPException(404, "提出意願的案件不存在")
        #把接案人提出的意願狀態更新成「已被選中」
        await cur.execute("UPDATE proposals SET accepted=TRUE WHERE id=%s;", (proposal_id,))
        #更新這個案件的接案人、狀態以及最後修改時間
        await cur.execute(
            "UPDATE projects SET contractor_id=%s, status='in_progress', updated_at=NOW() WHERE id=%s;",
            (prop["contractor_id"], project_id)
        )
        await conn.commit()
    return RedirectResponse(f"/projects/{project_id}", status_code=status.HTTP_302_FOUND)   #一樣回到案件詳情畫面

#委託人下載結案檔案來看
@app.get("/files/{closure_id}")
async def download_closure_file(closure_id: int, request: Request, conn = Depends(getDB)):
    user = await current_user(request, conn)
    if not user:
        return RedirectResponse("/login")
    async with conn.cursor(row_factory=dict_row) as cur:
        #把檔案的資料(檔名、路徑等)從DB抓出來
        await cur.execute(
            """
            SELECT cf.id, cf.filename, cf.filepath, p.client_id, p.contractor_id
            FROM closure_files cf
            JOIN projects p ON p.id = cf.project_id
            WHERE cf.id = %s;
            """,
            (closure_id,),
        )
        row = await cur.fetchone()
    #如果找不到就報錯
    if not row:
        raise HTTPException(404, "檔案不存在")
    #只有此專案的委託人或接案人才能下載
    if user["id"] not in (row["client_id"], row["contractor_id"]):
        raise HTTPException(403, "無權限下載")
    #DB有記錄但磁碟上找不到
    path = row["filepath"]
    if not os.path.exists(path):
        raise HTTPException(404, "檔案已遺失")
    #以原檔名下載
    return FileResponse(path, media_type="application/octet-stream", filename=row["filename"])

#決定是否要結案，送出的結果就由這裡接收
@app.post("/projects/{project_id}/decision")
async def close_decision(request: Request, project_id: int, decision: str = Form(...), conn = Depends(getDB)):
    user = await current_user(request, conn)
    if not user:
        return RedirectResponse("/login")
    #結果只會是這兩種，如果不是的話就報錯
    if decision not in ("accept", "reject"):
        raise HTTPException(400, "未知決策")
    async with conn.cursor(row_factory=dict_row) as cur:
        #從DB找出這個案件的委託人是誰
        await cur.execute("SELECT client_id FROM projects WHERE id=%s;", (project_id,))
        row = await cur.fetchone()
        #如果找不到或不是該案的委託人就禁止
        if not row or row["client_id"] != user["id"]:
            raise HTTPException(403, "無權限")
        #設定新狀態並更新DB(如果按的是 接受結案->closed 退回修改->reject)
        new_status = "closed" if decision == "accept" else "reject"
        await cur.execute("UPDATE projects SET status=%s, updated_at=NOW() WHERE id=%s;", (new_status, project_id))
        await conn.commit()
    return RedirectResponse(f"/projects/{project_id}", status_code=status.HTTP_302_FOUND)   #回到案件詳情畫面

# ------------- 接案人：瀏覽/查詢案件與提出意願、上傳結案檔案 -------------
#接案人瀏覽可承接案件
@app.get("/browse", response_class=HTMLResponse)
async def browse_open_projects(
    request: Request,
    q: str | None = Query(default=None, description="搜尋關鍵字"),
    conn = Depends(getDB)
    ):
    #檢查身分
    user = await current_user(request, conn)
    if not user or user["role"] != "contractor":
        return RedirectResponse("/login")
    async with conn.cursor(row_factory=dict_row) as cur:
        #用搜尋的方式
        if q:
            like = f"%{q}%"
            await cur.execute(
                """
                SELECT id, title, description, created_at
                FROM projects
                WHERE status='open'
                  AND (title ILIKE %s OR description ILIKE %s)
                ORDER BY created_at DESC, id DESC;
                """,
                (like, like),
            )
        #直接瀏覽
        else:
            await cur.execute(
                """
                SELECT id, title, description, created_at
                FROM projects
                WHERE status='open'
                ORDER BY created_at DESC, id DESC;
                """
            )
        projects = await cur.fetchall()
    return templates.TemplateResponse(
        "browse_projects.html",
        {"request": request, "user": user, "projects": projects, "q": q or ""}
    )

#開啟提出承包意願的畫面
@app.get("/projects/{project_id}/propose", response_class=HTMLResponse)
async def submit_proposal_page(request: Request, project_id: int, conn = Depends(getDB)):
    user = await current_user(request, conn)
    if not user or user["role"] != "contractor":
        return RedirectResponse("/login")
    #從DB抓出這個案件的資料(id、標題、截止期限和狀態)
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute("SELECT id, title, status, bid_deadline FROM projects WHERE id=%s;", (project_id,))
        project = await cur.fetchone()
    # ★ 延伸一：截止後不能再投標
    if project["bid_deadline"] and datetime.now() > project["bid_deadline"]:
        raise HTTPException(400, "已超過投標截止期限，無法提出意願")
    #如果案件不存在或不是open的狀態就會報錯
    if not project or project["status"] != "open":
        raise HTTPException(404, "案件不可提出意願")
    return templates.TemplateResponse("submit_proposal.html", {"request": request, "user": user, "project": project}) 
#接收接案人送出的提交意願相關資訊（含提案書 PDF）
@app.post("/projects/{project_id}/propose")
async def submit_proposal(
    request: Request,
    project_id: int,
    message: str = Form(...),
    price: float = Form(...),
    proposal_file: UploadFile = File(...),  # ★ 延伸一：提案書（PDF）
    conn = Depends(getDB)
):
    user = await current_user(request, conn)
    if not user or user["role"] != "contractor":
        return RedirectResponse("/login")

    # ★ 延伸一：檔案基本檢查（雙保險：content_type + 副檔名）
    filename = (proposal_file.filename or "").strip()
    if not filename:
        raise HTTPException(400, "請選擇提案書檔案")
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(400, "提案書只允許 PDF 檔")
    if proposal_file.content_type not in ("application/pdf", "application/octet-stream"):
        # 有些瀏覽器會給 octet-stream，所以放寬，但不是 pdf 就擋
        raise HTTPException(400, "提案書格式不正確（請上傳 PDF）")

    async with conn.cursor(row_factory=dict_row) as cur:
        # ★ 延伸一：同時檢查案件狀態 + 投標截止期限
        await cur.execute("SELECT status, bid_deadline FROM projects WHERE id=%s;", (project_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "找不到案件")
        if row["status"] != "open":
            raise HTTPException(400, "案件不可提出意願")

        if row["bid_deadline"] and datetime.now(tz=row["bid_deadline"].tzinfo) > row["bid_deadline"]:
            raise HTTPException(400, "已超過投標截止期限，無法提出意願")

        # ★ 延伸一：把 PDF 存到磁碟（檔名不可覆蓋：timestamp + uuid）
        content = await proposal_file.read()
        safe_uid = uuid.uuid4().hex[:10]
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        dest = UPLOAD_DIR / f"proposal_p{project_id}_u{user['id']}_{ts}_{safe_uid}.pdf"
        with dest.open("wb") as f:
            f.write(content)

        # ★ 延伸一：把提案資料 + 提案書路徑寫進 proposals
        # 需要 proposals 表新增 proposal_filename / proposal_filepath 欄位（下面我有 SQL）
        await cur.execute("""
            INSERT INTO proposals (
                project_id, contractor_id, message, price,
                proposal_filename, proposal_filepath
            )
            VALUES (%s,%s,%s,%s,%s,%s);
        """, (
            project_id, user["id"], message, price,
            filename, str(dest)
        ))
        await conn.commit()

    return RedirectResponse("/dashboard?notice=proposal_sent", status_code=status.HTTP_302_FOUND)   #回到個人首頁畫面並出現已送出意願的通知

#接案人開啟上傳結案檔案畫面
@app.get("/projects/{project_id}/upload", response_class=HTMLResponse)
async def upload_closure_page(request: Request, project_id: int, conn = Depends(getDB)):
    user = await current_user(request, conn)
    if not user or user["role"] != "contractor":
        return RedirectResponse("/login")
    #從DB找出這個案件的標題以及接案人是誰
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute("SELECT title, contractor_id FROM projects WHERE id=%s;", (project_id,))
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "找不到案件")
    title = row["title"]    #在html顯示
    contractor_id = row["contractor_id"]    #用來確認登入者的身分
    if contractor_id != user["id"]:
        raise HTTPException(403, "無權限")
    project = {"id": project_id, "title": title}    #在html顯示
    return templates.TemplateResponse("upload_closure.html", {"request": request, "user": user, "project": project})  #跳到上傳檔案畫面
#接收上傳的結案檔案（版本控管：全版本保留）
@app.post("/projects/{project_id}/upload")
async def upload_closure(
    request: Request,
    project_id: int,
    file: UploadFile = File(...),
    conn = Depends(getDB)
):
    user = await current_user(request, conn)
    if not user or user["role"] != "contractor":
        return RedirectResponse("/login")

    filename = (file.filename or "").strip()
    if not filename:
        raise HTTPException(400, "請選擇要上傳的檔案")

    async with conn.cursor(row_factory=dict_row) as cur:
        # 確認案件存在 + 權限
        await cur.execute("SELECT contractor_id, status FROM projects WHERE id=%s;", (project_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "找不到案件")
        if row["contractor_id"] != user["id"]:
            raise HTTPException(403, "無權限")

        # ★ 延伸一：版本號自動遞增（同一 project 下）
        # 需要 closure_files 表新增 version 欄位（下面我有 SQL）
        await cur.execute("SELECT COALESCE(MAX(version), 0) AS v FROM closure_files WHERE project_id=%s;", (project_id,))
        vrow = await cur.fetchone()
        next_version = int(vrow["v"]) + 1

        # ★ 延伸一：存檔（檔名不可覆蓋：timestamp + uuid）
        content = await file.read()
        safe_uid = uuid.uuid4().hex[:10]
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        dest = UPLOAD_DIR / f"closure_p{project_id}_v{next_version}_{ts}_{safe_uid}_{filename}"

        with dest.open("wb") as f:
            f.write(content)

        # ★ 延伸一：每次上傳都 INSERT 一筆（全版本保留）
        await cur.execute("""
            INSERT INTO closure_files (project_id, contractor_id, version, filename, filepath)
            VALUES (%s,%s,%s,%s,%s);
        """, (project_id, user["id"], next_version, filename, str(dest)))

        # 案件狀態更新：上傳後 → submitted（你原本就這樣）
        await cur.execute(
            "UPDATE projects SET status='submitted', updated_at=NOW() WHERE id=%s;",
            (project_id,)
        )

        await conn.commit()

    return RedirectResponse(f"/projects/{project_id}", status_code=status.HTTP_302_FOUND)   #回到案件詳情畫面

# ================= 評價功能：建立評價 =================

# 顯示評價頁
@app.get("/projects/{project_id}/rate", response_class=HTMLResponse)
async def rate_project_page(
    request: Request,
    project_id: int,
    target: str = Query(..., description="要評價的對象：client 或 contractor"),
    conn = Depends(getDB),
):
    user = await current_user(request, conn)
    if not user:
        return RedirectResponse("/login")

    if target not in ("client", "contractor"):
        raise HTTPException(400, "未知的評價對象")

    async with conn.cursor(row_factory=dict_row) as cur:
        # 抓案件 + 雙方基本資訊
        await cur.execute(
            """
            SELECT p.*, 
                   uc.username AS client_username,
                   ur.username AS contractor_username
            FROM projects p
            JOIN users uc ON uc.id = p.client_id
            LEFT JOIN users ur ON ur.id = p.contractor_id
            WHERE p.id=%s;
            """,
            (project_id,),
        )
        project = await cur.fetchone()

        if not project:
            raise HTTPException(404, "找不到案件")
        if project["status"] != "closed":
            raise HTTPException(400, "案件尚未結案，無法評價")
        if not project["contractor_id"]:
            raise HTTPException(400, "此案件尚未有接案人")

        # 確認 rater / target 是誰
        if target == "contractor":
            # 只有委託人可以評接案人
            if user["id"] != project["client_id"]:
                raise HTTPException(403, "無權限評價")
            target_id = project["contractor_id"]
            target_name = project["contractor_username"]
            dim_labels = ["產出品質", "執行效率", "合作態度"]
            role_label = "接案人"
        else:
            # target == "client"：只有接案人可以評委託人
            if user["id"] != project["contractor_id"]:
                raise HTTPException(403, "無權限評價")
            target_id = project["client_id"]
            target_name = project["client_username"]
            dim_labels = ["需求合理性", "驗收難度", "合作態度"]
            role_label = "委託人"

        # ---------- 評價期限 & 剩餘時間計算（★這一段是新加的） ----------
        remain_days = 0
        remain_hours = 0

        closed_at = project["updated_at"]
        if closed_at and isinstance(closed_at, datetime):
            deadline_at = closed_at + timedelta(days=RATING_DEADLINE_DAYS)
            # 用與 closed_at 相同的時區算現在時間
            now = datetime.now(tz=closed_at.tzinfo)

            # 若已超過評價期限，直接擋掉
            if now > deadline_at:
                raise HTTPException(400, "已超過評價期限")

            diff = deadline_at - now
            total_hours = int(diff.total_seconds() // 3600)
            remain_days = total_hours // 24
            remain_hours = total_hours % 24
        # ---------------------------------------------------------

        # 檢查是否已評過
        await cur.execute(
            """
            SELECT 1 FROM ratings
            WHERE project_id=%s AND rater_id=%s AND target_id=%s;
            """,
            (project_id, user["id"], target_id),
        )
        if await cur.fetchone():
            raise HTTPException(400, "您已經評價過此對象")

    return templates.TemplateResponse(
        "rate_project.html",
        {
            "request": request,
            "user": user,
            "project": project,
            "target_role": target,
            "target_name": target_name,
            "role_label": role_label,
            "dim_labels": dim_labels,
            "deadline_days": RATING_DEADLINE_DAYS,
            "remain_days": remain_days,     # ★ 新增：丟給模板顯示倒數
            "remain_hours": remain_hours,   # ★ 新增：丟給模板顯示倒數
        },
    )

# 接收評價表單
@app.post("/projects/{project_id}/rate")
async def rate_project_submit(
    request: Request,
    project_id: int,
    target: str = Form(...),        # "client" 或 "contractor"
    score_1: str = Form(...),       # 星星選到的分數 (1~5)
    score_2: str = Form(...),
    score_3: str = Form(...),
    comment: str = Form(""),        # 質性評論，可留白
    conn = Depends(getDB),
):
    user = await current_user(request, conn)
    if not user:
        return RedirectResponse("/login")

    if target not in ("client", "contractor"):
        raise HTTPException(400, "未知的評價對象")

    # 1. 把字串分數轉成 int，順便做基本檢查
    try:
        s1 = int(score_1)
        s2 = int(score_2)
        s3 = int(score_3)
    except (TypeError, ValueError):
        raise HTTPException(400, "請完整選擇三個評分（1~5 顆星）")

    if not (1 <= s1 <= 5 and 1 <= s2 <= 5 and 1 <= s3 <= 5):
        raise HTTPException(400, "分數必須介於 1~5 之間")

    async with conn.cursor(row_factory=dict_row) as cur:
        # 2. 抓案件 & 基本檢查
        await cur.execute(
            """
            SELECT p.*,
                   uc.username AS client_username,
                   ur.username AS contractor_username
            FROM projects p
            JOIN users uc ON uc.id = p.client_id
            LEFT JOIN users ur ON ur.id = p.contractor_id
            WHERE p.id = %s;
            """,
            (project_id,),
        )
        project = await cur.fetchone()

        if not project:
            raise HTTPException(404, "找不到案件")
        if project["status"] != "closed":
            raise HTTPException(400, "案件尚未結案，無法評價")
        if not project["contractor_id"]:
            raise HTTPException(400, "此案件尚未有接案人")

        # 3. 判斷這次是誰評誰 → 決定 target_id / rater_id / 角色文字
        if target == "contractor":
            # 委託人評接案人
            if user["id"] != project["client_id"]:
                raise HTTPException(403, "無權限評價")
            target_id = project["contractor_id"]
            target_role = "contractor"
            rater_role = "client"
        else:
            # 接案人評委託人
            if user["id"] != project["contractor_id"]:
                raise HTTPException(403, "無權限評價")
            target_id = project["client_id"]
            target_role = "client"
            rater_role = "contractor"

        # 4. 確認這個人對這個對象是不是已經評過
        await cur.execute(
            """
            SELECT 1 FROM ratings
            WHERE project_id = %s
              AND rater_id   = %s
              AND target_id  = %s;
            """,
            (project_id, user["id"], target_id),
        )
        if await cur.fetchone():
            raise HTTPException(400, "您已經評價過此對象")

        # 5. 寫入 ratings（這裡欄位名要跟你現在的 table 一樣）
        await cur.execute(
            """
            INSERT INTO ratings (
                project_id,
                target_id, target_role,
                rater_id,  rater_role,
                score_1, score_2, score_3,
                comment
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (
                project_id,
                target_id, target_role,
                user["id"], rater_role,
                s1, s2, s3,
                comment,
            ),
        )
        await conn.commit()

    # 6. 評完回案件詳情
    return RedirectResponse(
        f"/projects/{project_id}",
        status_code=status.HTTP_302_FOUND,
    )


# ================= 評價功能：查看歷史評價 =================

# 委託人評價列表
@app.get("/ratings/client/{user_id}", response_class=HTMLResponse)
async def view_client_ratings(request: Request, user_id: int, conn = Depends(getDB)):
    user = await current_user(request, conn)
    if not user:
        return RedirectResponse("/login")

    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute("SELECT id, username FROM users WHERE id=%s;", (user_id,))
        target = await cur.fetchone()
        if not target:
            raise HTTPException(404, "找不到使用者")

        # 平均分數
        await cur.execute(
            """
            SELECT 
                AVG(score_1) AS avg1,
                AVG(score_2) AS avg2,
                AVG(score_3) AS avg3,
                COUNT(*)     AS cnt
            FROM ratings
            WHERE target_id=%s AND target_role='client';
            """,
            (user_id,),
        )
        stats = await cur.fetchone()

        # 各筆評價 + 質性評論
        await cur.execute(
            """
            SELECT r.*, u.username AS rater_username, p.title AS project_title
            FROM ratings r
            JOIN users    u ON u.id = r.rater_id
            JOIN projects p ON p.id = r.project_id
            WHERE r.target_id=%s AND r.target_role='client'
            ORDER BY r.created_at DESC;
            """,
            (user_id,),
        )
        items = await cur.fetchall()

    dim_labels = ["需求合理性", "驗收難度", "合作態度"]
    role_label = "委託人"

    return templates.TemplateResponse(
        "ratings_user.html",
        {
            "request": request,
            "user": user,
            "target": target,
            "role": "client",
            "role_label": role_label,
            "dim_labels": dim_labels,
            "stats": stats,
            "items": items,
        },
    )


# 接案人評價列表
@app.get("/ratings/contractor/{user_id}", response_class=HTMLResponse)
async def view_contractor_ratings(request: Request, user_id: int, conn = Depends(getDB)):
    user = await current_user(request, conn)
    if not user:
        return RedirectResponse("/login")

    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute("SELECT id, username FROM users WHERE id=%s;", (user_id,))
        target = await cur.fetchone()
        if not target:
            raise HTTPException(404, "找不到使用者")

        await cur.execute(
            """
            SELECT 
                AVG(score_1) AS avg1,
                AVG(score_2) AS avg2,
                AVG(score_3) AS avg3,
                COUNT(*)     AS cnt
            FROM ratings
            WHERE target_id=%s AND target_role='contractor';
            """,
            (user_id,),
        )
        stats = await cur.fetchone()

        await cur.execute(
            """
            SELECT r.*, u.username AS rater_username, p.title AS project_title
            FROM ratings r
            JOIN users    u ON u.id = r.rater_id
            JOIN projects p ON p.id = r.project_id
            WHERE r.target_id=%s AND r.target_role='contractor'
            ORDER BY r.created_at DESC;
            """,
            (user_id,),
        )
        items = await cur.fetchall()

    dim_labels = ["產出品質", "執行效率", "合作態度"]
    role_label = "接案人"

    return templates.TemplateResponse(
        "ratings_user.html",
        {
            "request": request,
            "user": user,
            "target": target,
            "role": "contractor",
            "role_label": role_label,
            "dim_labels": dim_labels,
            "stats": stats,
            "items": items,
        },
    )

#==============Issue=================

# ============== Issue ==============


# 顯示新增 Issue 的表單
@app.get("/projects/{project_id}/issues/new", response_class=HTMLResponse)
async def issue_new_page(request: Request, project_id: int, conn=Depends(getDB)):
    user = await current_user(request, conn)
    if not user:
        return RedirectResponse("/login")

    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute("""
            SELECT id, title, client_id, status
            FROM projects
            WHERE id=%s;
        """, (project_id,))
        p = await cur.fetchone()

    if not p:
        raise HTTPException(404, "找不到案件")
    if user["id"] != p["client_id"]:
        raise HTTPException(403, "無權限")
    if p["status"] not in ("submitted", "in_progress", "reject"):
        raise HTTPException(400, "此狀態不可新增 Issue")

    return templates.TemplateResponse(
        "issue_create.html",
        {"request": request, "user": user, "project": p}
    )

# 建立 issue（只有此案件委託人可開）
@app.post("/projects/{project_id}/issues/create")
async def issue_create(
    request: Request,
    project_id: int,
    title: str = Form(...),
    description: str = Form(...),
    conn=Depends(getDB)
):
    user = await current_user(request, conn)
    if not user:
        return RedirectResponse("/login")

    async with conn.cursor(row_factory=dict_row) as cur:
        # ★(2) 權限檢查：必須是此案件的委託人才能開 Issue
        await cur.execute("""
            SELECT client_id, status
            FROM projects
            WHERE id=%s;
        """, (project_id,))
        p = await cur.fetchone()
        if not p:
            raise HTTPException(404, "找不到案件")
        if user["id"] != p["client_id"]:
            raise HTTPException(403, "只有此案件的委託人可以開 Issue")
        if p["status"] not in ("submitted", "in_progress", "reject"):
            raise HTTPException(400, "此專案狀態不可新增 Issue")

        await cur.execute("""
            INSERT INTO issues (project_id, opener_id, title, description)
            VALUES (%s,%s,%s,%s);
        """, (project_id, user["id"], title, description))
        await conn.commit()

    return RedirectResponse(f"/projects/{project_id}?notice=issue_created", status_code=302)


# 回覆 issue（只有此案件委託人或接案人可回覆）
@app.post("/issues/{issue_id}/comment")
async def issue_comment(
    request: Request,
    issue_id: int,
    content: str = Form(...),
    conn=Depends(getDB)
):
    user = await current_user(request, conn)
    if not user:
        return RedirectResponse("/login")

    async with conn.cursor(row_factory=dict_row) as cur:
        # ★ 先確認 issue 存在 + 權限 + 狀態
        await cur.execute("""
            SELECT i.project_id, i.status,
                   p.client_id, p.contractor_id
            FROM issues i
            JOIN projects p ON p.id = i.project_id
            WHERE i.id=%s;
        """, (issue_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "找不到 Issue")

        # resolved 後誰都不能再留言
        if row["status"] == "resolved":
            raise HTTPException(400, "此 Issue 已完成，無法再留言")

        if user["id"] not in (row["client_id"], row["contractor_id"]):
            raise HTTPException(403, "無權限留言")

        await cur.execute("""
            INSERT INTO issue_comments (issue_id, author_id, content)
            VALUES (%s,%s,%s);
        """, (issue_id, user["id"], content))
        await conn.commit()

    return RedirectResponse(request.headers.get("referer", f"/projects/{row['project_id']}"), status_code=302)


# 關閉 issue（只有此案件委託人可關）
@app.post("/issues/{issue_id}/resolve")
async def issue_resolve(issue_id: int, request: Request, conn=Depends(getDB)):
    user = await current_user(request, conn)
    if not user:
        return RedirectResponse("/login")

    async with conn.cursor(row_factory=dict_row) as cur:
        # ★(4) 權限檢查
        await cur.execute("""
            SELECT p.client_id, i.project_id 
            FROM issues i
            JOIN projects p ON p.id = i.project_id
            WHERE i.id=%s;
        """, (issue_id,))
        row = await cur.fetchone()
        
        if not row:
            raise HTTPException(404, "找不到 Issue")

        if user["id"] != row["client_id"]:
            raise HTTPException(403, "只有此案件的委託人可以關閉 Issue")

        # ===========【請加入以下這段程式碼】===========
        # 更新資料庫狀態
        await cur.execute("UPDATE issues SET status='resolved' WHERE id=%s", (issue_id,))
        await conn.commit()
        # ============================================

    # 導回原本的專案頁面
    return RedirectResponse(f"/projects/{row['project_id']}", status_code=302)

@app.on_event("shutdown")
async def _shutdown():

    await close_pool()

