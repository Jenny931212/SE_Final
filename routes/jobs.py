from fastapi import APIRouter, Request, Depends, Form, UploadFile, File
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import os
from db import getDB
from psycopg import Error as PsycopgError 

router = APIRouter()
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# =================================================================
# 🟢 接受報價 (使用 /actions/ 前綴，解決 Not Found 衝突)
# =================================================================
@router.get("/actions/accept_bid/{job_id}/{bid_id}")
async def accept_bid(request: Request, job_id: int, bid_id: int, conn=Depends(getDB)):
    print(f"DEBUG_HIT: /jobs/actions/accept_bid hit. Job ID: {job_id}, Bid ID: {bid_id}")

    owner_id = request.session.get("user_id")

    if not owner_id or request.session.get("role") != "client":
        return RedirectResponse(url="/login", status_code=302)

    try:
        async with conn.cursor() as cur:
            # 1. 取得案子狀態和擁有者ID
            await cur.execute(
                "SELECT status, owner_id FROM jobs WHERE id = %s;", (job_id,)
            )
            job = await cur.fetchone()
            
            if not job or job["owner_id"] != owner_id:
                return RedirectResponse(url="/error?msg=權限錯誤或案子不存在", status_code=302)
            
            # 狀態檢查：案子必須在 'bidding' 或 'pending_review' 才能接受報價
            if job["status"] not in ("pending_review", "bidding"):
                print(f"DEBUG_STATUS_FAIL: Job {job_id} status is {job['status']}, not eligible for acceptance.")
                return RedirectResponse(url=f"/error?msg=案子狀態為 {job['status']}，無法接受報價", status_code=302)

            # 2. 更新 Job 狀態為執行中 (in_progress) 並設定選擇的報價
            await cur.execute(
                "UPDATE jobs SET status = 'in_progress', accepted_bid_id = %s WHERE id = %s;",
                (bid_id, job_id),
            )

            # 3. 更新被接受的 Bid 狀態為 'accepted'
            await cur.execute(
                "UPDATE bids SET status = 'accepted' WHERE id = %s AND job_id = %s AND status = 'pending';",
                (bid_id, job_id),
            )
            
            # 4. 更新該案子下其他 Bid 狀態為 'rejected'
            await cur.execute(
                "UPDATE bids SET status = 'rejected' WHERE job_id = %s AND id != %s AND status = 'pending';",
                (job_id, bid_id),
            )
            
        await conn.commit()
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)

    except Exception as e:
        print(f"❌ 接受報價時發生內部錯誤: {e}") 
        return RedirectResponse(url=f"/error?msg=接受報價發生內部錯誤: {e}", status_code=302)


# =================================================================
# 🔴 拒絕報價 (使用 /actions/ 前綴，解決 Not Found 衝突)
# =================================================================
@router.get("/actions/reject_bid/{job_id}/{bid_id}")
async def reject_bid(request: Request, job_id: int, bid_id: int, conn=Depends(getDB)):
    owner_id = request.session.get("user_id")

    if not owner_id or request.session.get("role") != "client":
        return RedirectResponse(url="/login", status_code=302)
        
    try:
        async with conn.cursor() as cur:
            # 1. 檢查案子權限
            await cur.execute(
                "SELECT owner_id FROM jobs WHERE id = %s;", (job_id,)
            )
            job = await cur.fetchone()

            if not job or job["owner_id"] != owner_id:
                return RedirectResponse(url="/error?msg=權限錯誤或案子不存在", status_code=302)

            # 2. 拒絕單一報價（必須是 pending 狀態）
            await cur.execute(
                "UPDATE bids SET status = 'rejected' WHERE id = %s AND job_id = %s AND status = 'pending';",
                (bid_id, job_id),
            )
            
        await conn.commit()
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)

    except Exception as e:
        print(f"❌ 拒絕報價時發生錯誤: {e}")
        return RedirectResponse(url=f"/error?msg=拒絕報價發生內部錯誤", status_code=302)


# =================================================================
# 📦 標記為完成 (驗收結案)
# =================================================================
@router.get("/complete/{job_id}")
async def complete_job(request: Request, job_id: int, conn=Depends(getDB)):
    if "user_id" not in request.session or request.session.get("role") != "client":
        return RedirectResponse(url="/login", status_code=302)
    
    owner_id = request.session["user_id"]

    try:
        async with conn.cursor() as cur:
            # 只有案主可以將案子結案 (從 in_progress, reviewing, in_revision 轉為 completed)
            await cur.execute("""
                UPDATE jobs SET status = 'completed'
                WHERE id = %s AND owner_id = %s AND status IN ('in_progress', 'reviewing', 'in_revision');
            """, (job_id, owner_id))

        await conn.commit()
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)
    except Exception as e:
        print(f"❌ MANUAL COMPLETE ERROR: {e}")
        await conn.rollback()
        return templates.TemplateResponse("error.html", {"request": request, "message": f"手動結案失敗：{e}"})


# =================================================================
# 🔴 甲方退件/要求修改 (reviewing -> in_revision) 【新增功能】
# =================================================================
@router.get("/reject_work/{job_id}")
async def reject_work(request: Request, job_id: int, conn=Depends(getDB)):
    if "user_id" not in request.session or request.session.get("role") != "client":
        return RedirectResponse(url="/login", status_code=302)
    
    owner_id = request.session["user_id"]

    try:
        async with conn.cursor() as cur:
            # 1. 檢查權限並確認案子狀態必須是 'reviewing'
            await cur.execute("""
                SELECT owner_id, status FROM jobs WHERE id = %s;
            """, (job_id,))
            job = await cur.fetchone()

            if not job or job["owner_id"] != owner_id:
                return RedirectResponse(url="/error?msg=權限錯誤或案子不存在", status_code=302)
            
            # 必須是 reviewing 狀態才能退件
            if job["status"] != "reviewing":
                return RedirectResponse(url=f"/error?msg=案子目前狀態為 {job['status']}，無法執行退件", status_code=302)

            # 2. 關鍵修正：將狀態更新為 'in_revision' (待修改)，允許乙方重新提交
            await cur.execute("""
                UPDATE jobs SET status = 'in_revision'
                WHERE id = %s;
            """, (job_id,))
            
        await conn.commit()
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)
        
    except Exception as e:
        print(f"❌ REJECT WORK ERROR: {e}")
        await conn.rollback()
        return RedirectResponse(url=f"/error?msg=退件操作失敗: {e}", status_code=302)


# ============================
# ❌ 刪除委託案
# ============================
@router.get("/delete/{id}")
async def delete_job(request: Request, id: int, conn=Depends(getDB)):
    if "user_id" not in request.session or request.session.get("role") != "client":
        return RedirectResponse(url="/login", status_code=302)

    owner_id = request.session["user_id"]

    async with conn.cursor() as cur:
        await cur.execute("DELETE FROM jobs WHERE id = %s AND owner_id = %s;", (id, owner_id))

    await conn.commit()
    return RedirectResponse(url="/jobs/", status_code=302)


# ============================
# 📋 委託案列表（甲方）
# ============================
@router.get("/")
async def job_list(request: Request, conn=Depends(getDB)):
    if "user_id" not in request.session or request.session.get("role") != "client":
        return RedirectResponse(url="/login", status_code=302)

    owner_id = request.session["user_id"]

    async with conn.cursor() as cur:
        await cur.execute("""
            SELECT j.id, j.title, j.description, j.budget, j.status,
                   j.bidding_deadline,
                   u.name AS owner_name
            FROM jobs j
            JOIN users u ON j.owner_id = u.id
            WHERE j.owner_id = %s
            ORDER BY j.id DESC;
        """, (owner_id,))
        rows = await cur.fetchall()

    return templates.TemplateResponse("postList.html", {"request": request, "items": rows})


# ============================
# ➕ 新增案子（表單）
# ============================
@router.get("/add/form")
async def add_form(request: Request):
    if "user_id" not in request.session or request.session.get("role") != "client":
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("addForm.html", {"request": request})


# ============================
# 📝 新增案子（POST）
# ============================
@router.post("/add")
async def add_job(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    budget: int = Form(...),
    bidding_deadline: str = Form(...),
    conn=Depends(getDB)
):
    if "user_id" not in request.session or request.session.get("role") != "client":
        return RedirectResponse(url="/login", status_code=302)

    owner_id = request.session["user_id"]

    async with conn.cursor() as cur:
        await cur.execute("""
            INSERT INTO jobs (title, description, budget, status, owner_id, bidding_deadline)
            VALUES (%s, %s, %s, %s, %s, %s);
        """, (title, description, budget, "bidding", owner_id, bidding_deadline))

    await conn.commit()
    return RedirectResponse(url="/jobs/", status_code=302)


# ============================
# ✏️ 編輯案子（表單）
# ============================
@router.get("/edit/{id}")
async def edit_job(request: Request, id: int, conn=Depends(getDB)):
    if "user_id" not in request.session or request.session.get("role") != "client":
        return RedirectResponse(url="/login", status_code=302)

    owner_id = request.session["user_id"]

    async with conn.cursor() as cur:
        await cur.execute("""
            SELECT id, title, description, budget, status
            FROM jobs
            WHERE id = %s AND owner_id = %s;
        """, (id, owner_id))
        job = await cur.fetchone()

    if not job:
        return templates.TemplateResponse("error.html",
            {"request": request, "message": "找不到該案子或無權限編輯"})
    
    if job["status"] != "bidding":
        return templates.TemplateResponse("error.html",
            {"request": request, "message": "此案已被報價或執行，無法修改"})

    return templates.TemplateResponse("editForm.html", {"request": request, "job": job})


# ============================
# 💾 更新案子
# ============================
@router.post("/update/{id}")
async def update_job(
    request: Request,
    id: int,
    title: str = Form(...),
    description: str = Form(...),
    budget: int = Form(...),
    conn=Depends(getDB)
):
    if "user_id" not in request.session or request.session.get("role") != "client":
        return RedirectResponse(url="/login", status_code=302)

    owner_id = request.session["user_id"]

    async with conn.cursor() as cur:
        await cur.execute("""
            UPDATE jobs
            SET title = %s, description = %s, budget = %s
            WHERE id = %s AND owner_id = %s AND status = 'bidding';
        """, (title, description, budget, id, owner_id))

    await conn.commit()
    return RedirectResponse(url="/jobs/", status_code=302)


# ============================
# 🔍 案子詳情（含附件、報價）
# ============================
@router.get("/{id}")
async def job_detail(request: Request, id: int, conn=Depends(getDB)):
    user_id = request.session.get("user_id")
    role = request.session.get("role")

    if not user_id:
        return RedirectResponse(url="/login", status_code=302)

    async with conn.cursor() as cur:
        # 案子資料
        await cur.execute("""
            SELECT j.id, j.title, j.description, j.budget, j.status,
                   j.owner_id, j.bidding_deadline, j.accepted_bid_id,
                   u.name AS owner_name
            FROM jobs j
            JOIN users u ON j.owner_id = u.id
            WHERE j.id = %s;
        """, (id,))
        job = await cur.fetchone()

        # 報價列表
        await cur.execute("""
            SELECT b.id, b.bidder_id, v.name AS bidder_name,
                   b.price, b.message, b.status
            FROM bids b
            JOIN users v ON b.bidder_id = v.id
            WHERE b.job_id = %s;
        """, (id,))
        bids = await cur.fetchall()

        # 附件列表
        await cur.execute("""
            SELECT f.filename, f.role, f.upload_time, f.original_name, u.name AS uploader_name,
                   f.kind, f.version /* 確保撈出 kind 和 version 用於前端顯示或 debug */
            FROM files f
            JOIN users u ON f.uploader_id = u.id
            WHERE f.job_id = %s
            ORDER BY f.upload_time DESC;
        """, (id,))
        files = await cur.fetchall()

    if not job:
        return templates.TemplateResponse("error.html",
            {"request": request, "message": "找不到該案子"})

    # --- 權限判斷邏輯 ---
    can_upload = False
    accepted_contractor_id = None
    
    # 找出被接受的報價者 ID
    for b in bids:
        if b["status"] == 'accepted':
            accepted_contractor_id = b["bidder_id"]
            break

    # 權限判斷
    if role == "client" and user_id == job["owner_id"]:
        # 甲方隨時可以上傳資料
        can_upload = True
    elif role == "contractor" and user_id == accepted_contractor_id:
        # 乙方（被接受者）在執行中、審核中或待修改時可以上傳成果
        if job["status"] in ["in_progress", "reviewing", "in_revision"]:
            can_upload = True
        
    # 報價者在 'bidding' 階段可上傳報價附件
    elif role == "contractor" and job["status"] == "bidding":
        for b in bids:
            if b["bidder_id"] == user_id and b["status"] == 'pending':
                can_upload = True
                break
    # --- 權限判斷邏輯 END ---


    return templates.TemplateResponse(
        "postDetail.html",
        {
            "request": request,
            "job": job,
            "bids": bids,
            "files": files,
            "can_upload": can_upload,
            "current_user_id": user_id, 
            "role": role 
        }
    )


# ============================
# 📎 上傳附件（乙方上傳成果會觸發狀態轉換）
# ============================
@router.post("/upload")
async def upload_file(
    request: Request,
    job_id: int = Form(...),
    file: UploadFile = File(...),
    conn=Depends(getDB)
):
    user_id = request.session.get("user_id")
    role = request.session.get("role")
    if not user_id:
        return RedirectResponse(url="/login", status_code=302)

    original_name = file.filename
    name, ext = os.path.splitext(original_name)
    safe_filename = original_name
    file_kind = 'general' # 假設 kind 預設為 'general'

    upload_dir = UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)

    try:
        async with conn.cursor() as cur:
            
            # --- 1. 計算版本號 (VERSIONING) ---
            # 查詢當前用戶/案子組合的最大版本號 (用於解決 unique constraint error)
            await cur.execute("""
                SELECT MAX(version) AS max_version
                FROM files
                WHERE job_id = %s AND uploader_id = %s AND kind = %s;
            """, (job_id, user_id, file_kind))
            
            max_version_row = await cur.fetchone()
            # 版本號遞增，如果為空則從 1 開始
            current_version = (max_version_row['max_version'] or 0) + 1 
            
            # --- 2. 檔名重複處理邏輯 (確保檔名在文件系統中唯一) ---
            counter = 1
            temp_filename = safe_filename
            while True:
                await cur.execute("SELECT id FROM files WHERE filename = %s;", (temp_filename,))
                exists = await cur.fetchone()
                if not exists:
                    safe_filename = temp_filename # 確定最終使用的檔名
                    break
                temp_filename = f"{name} ({counter}){ext}"
                counter += 1
            
            # 實際儲存檔案
            save_path = os.path.join(upload_dir, safe_filename)
            with open(save_path, "wb") as f:
                f.write(await file.read())

            # --- 3. 寫入 DB (包含新的版本號) ---
            await cur.execute("""
                INSERT INTO files (job_id, uploader_id, filename, original_name, role, kind, version)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
            """, (job_id, user_id, safe_filename, original_name, role, file_kind, current_version))
            
            # --- 4. 狀態轉換邏輯 ---
            # 只有在 'in_progress' 或 'in_revision' 狀態下才推到 'reviewing'
            if role == "contractor":
                await cur.execute("""
                    UPDATE jobs
                    SET status = 'reviewing'
                    WHERE id = %s AND status IN ('in_progress', 'in_revision') 
                    AND EXISTS (SELECT 1 FROM bids WHERE job_id = %s AND bidder_id = %s AND status = 'accepted');
                """, (job_id, job_id, user_id))

        await conn.commit()
    except Exception as e:
        print(f"❌ UPLOAD ERROR: {e}")
        await conn.rollback()
        # 導向錯誤頁面，傳遞詳細錯誤訊息 (這是唯一不 RedirectResponse 到 /error 的情況)
        return RedirectResponse(url=f"/jobs/error?msg=檔案上傳失敗：{e}", status_code=302)

    return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)


# ============================
# ⚠️ 錯誤頁面處理 
# ============================
@router.get("/error")
async def error_page(request: Request, msg: str = "發生未知錯誤"):
    print(f"ERROR REDIRECT: Received error message: {msg}")
    
    return templates.TemplateResponse(
        "error.html", 
        {"request": request, "message": msg},
        status_code=400 
    )