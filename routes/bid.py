from fastapi import APIRouter, Request, Depends, Form, UploadFile, File
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import os
import tempfile  # 👈 新增引入
import shutil    # 👈 新增引入
from db import getDB

router = APIRouter()
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ===============================
# 📋 可接案清單（乙方視角）
# ===============================
@router.get("/available")
async def available_jobs(request: Request, conn=Depends(getDB)):

    bidder_id = request.session.get("user_id")
    role = request.session.get("role")

    # 未登入或不是乙方 → 導回登入頁
    if not bidder_id or role != "contractor":
        return RedirectResponse(url="/login", status_code=302)

    async with conn.cursor() as cur:
        # 乙方可以看到：
        #   - 狀態為 'bidding' (報價中)
        #   - 並且尚未過 bidding_deadline
        await cur.execute("""
            SELECT 
                j.id, j.title, j.description, j.budget, j.status,
                j.bidding_deadline,
                u.name AS owner_name,
                CASE WHEN b.id IS NOT NULL THEN TRUE ELSE FALSE END AS already_bid
            FROM jobs j
            JOIN users u ON j.owner_id = u.id
            LEFT JOIN bids b ON j.id = b.job_id AND b.bidder_id = %s
            WHERE j.status = 'bidding'
              AND (j.bidding_deadline IS NULL OR j.bidding_deadline > NOW())
            ORDER BY j.id;
        """, (bidder_id,))
        items = await cur.fetchall()

    print(f"🧾 乙方 {bidder_id} 撈到 {len(items)} 筆可接案")
    return templates.TemplateResponse(
        "availableJobs.html",
        {
            "request": request,
            "items": items,
        }
    )


# ===============================
# 📝 顯示報價表單
# ===============================
@router.get("/bid_form/{job_id}")
async def show_bid_form(request: Request, job_id: int, conn=Depends(getDB)):

    bidder_id = request.session.get("user_id")
    role = request.session.get("role")

    if not bidder_id or role != "contractor":
        return RedirectResponse(url="/login", status_code=302)

    async with conn.cursor() as cur:
        # 只能對「狀態為 bidding + 未過期」的案子報價
        await cur.execute("""
            SELECT 
                j.id, j.title, j.description, j.budget, j.bidding_deadline,
                u.name AS owner_name
            FROM jobs j
            JOIN users u ON j.owner_id = u.id
            WHERE j.id = %s
              AND j.status = 'bidding'
              AND (j.bidding_deadline IS NULL OR j.bidding_deadline > NOW());
        """, (job_id,))
        job = await cur.fetchone()

    if not job:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "message": "此案已截止或不再開放報價",
            }
        )

    return templates.TemplateResponse(
        "addBid.html",
        {"request": request, "job": job, "job_id": job_id}
    )


# ===============================
# 🚀 提交報價 (簡化安全版 - 僅檢查副檔名)
# ===============================
@router.post("/submit")
async def add_bid(
    request: Request,
    job_id: int = Form(...),
    price: int = Form(...),
    message: str = Form(...),
    proposal: UploadFile = File(...), 
    conn=Depends(getDB)
):
    bidder_id = request.session.get("user_id")
    role = request.session.get("role")

    if not bidder_id or role != "contractor":
        return RedirectResponse(url="/login", status_code=302)

    original_name = proposal.filename
    
    # 檢查檔案名稱
    if not original_name:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "message": "請選擇要上傳的計畫書檔案。"}
        )

    # 檢查副檔名 (替換為您想要的 多檔案類型 檢查)
    name, ext = os.path.splitext(original_name)
    ext = ext.lower()
    
    # ⭐ 替換的關鍵：允許副檔名
    ALLOWED_EXTS = [".pdf"]
    if ext not in ALLOWED_EXTS:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "message": f"檔案類型不允許（限 {', '.join(ALLOWED_EXTS)}）"}
        )
    
    # 讀取檔案內容並檢查是否為空
    try:
        # 將上傳檔案的內容一次性讀取到內存 (async read)
        content = await proposal.read()
        if not content:
            raise ValueError("檔案內容不能為空。")
    except Exception as e:
        print(f"❌ 檔案讀取錯誤: {e}")
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "message": "讀取檔案時發生內部錯誤。"}
        )

    # 驗證通過，繼續資料庫和儲存流程
    safe_filename = original_name

    async with conn.cursor() as cur:
        # 1️⃣ 再確認案子是否還能報價 (略)
        # 2️⃣ 檢查是否已報過價 (略)

        # 3️⃣ 文件檔名避免覆蓋 (這裡使用新的檔名邏輯)
        counter = 1
        while True:
            await cur.execute("SELECT id FROM files WHERE filename = %s;", (safe_filename,))
            row = await cur.fetchone()
            if not row:
                break 

            # 如果檔名重複，則加上計數器
            safe_filename = f"{name} ({counter}){ext}"
            counter += 1

        # 4️⃣ 儲存檔案 (直接寫入)
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        save_path = os.path.join(UPLOAD_DIR, safe_filename)
        
        # ⭐ 替換的關鍵：直接將內存中的 content 寫入目標檔案
        with open(save_path, "wb") as f:
            f.write(content)
        
        # 5️⃣ 新增報價 (保持不變)
        await cur.execute("""
            INSERT INTO bids (job_id, bidder_id, price, message, status)
            VALUES (%s, %s, %s, %s, %s);
        """, (job_id, bidder_id, price, message, "pending"))

        # 6️⃣ 把這份計畫書也記錄到 files (保持不變)
        await cur.execute("""
            INSERT INTO files (job_id, uploader_id, filename, original_name, role)
            VALUES (%s, %s, %s, %s, %s);
        """, (job_id, bidder_id, safe_filename, original_name, role))

    await conn.commit()
    print(f"📨 乙方 {bidder_id} 對 job {job_id} 報價成功（含檔案），狀態保持 'bidding'")
    return RedirectResponse(url="/bid/mybids", status_code=302)
# ===============================
# 📦 我的報價清單（歷史紀錄）
# ===============================
@router.get("/mybids")
async def my_bids(request: Request, conn=Depends(getDB)):

    bidder_id = request.session.get("user_id")
    role = request.session.get("role")

    if not bidder_id or role != "contractor":
        return RedirectResponse(url="/login", status_code=302)

    async with conn.cursor() as cur:
        # ⭐ 關鍵：在查詢中加入 job_id
        await cur.execute("""
            SELECT 
                b.id,
                b.job_id, -- 新增 job_id
                j.title,
                j.status AS job_status,
                u.name AS owner_name,
                b.price,
                b.message,
                b.status AS bid_status
            FROM bids b
            JOIN jobs j ON b.job_id = j.id
            JOIN users u ON j.owner_id = u.id
            WHERE b.bidder_id = %s
            ORDER BY b.id DESC;
        """, (bidder_id,))
        items = await cur.fetchall()

    print(f"📚 乙方 {bidder_id} 共 {len(items)} 筆報價紀錄")
    return templates.TemplateResponse("myBids.html", {"request": request, "items": items})

# ===============================
# 🔍 單筆報價詳情 (新增此路由，方便跳轉到案子詳情頁)
# ===============================
@router.get("/mybids/{bid_id}") 
async def bid_detail_view(request: Request, bid_id: int, conn=Depends(getDB)):
    bidder_id = request.session.get("user_id")

    if not bidder_id or request.session.get("role") != "contractor":
        return RedirectResponse(url="/login", status_code=302)

    async with conn.cursor() as cur:
        # ⭐ 關鍵 SQL：獲取 job_id (b.job_id)
        await cur.execute("""
            SELECT 
                b.job_id, j.title, j.description, j.budget, j.status AS job_status, 
                u.name AS owner_name, b.price, b.message, b.status AS bid_status
            FROM bids b
            JOIN jobs j ON b.job_id = j.id
            JOIN users u ON j.owner_id = u.id
            WHERE b.id = %s AND b.bidder_id = %s;
        """, (bid_id, bidder_id))
        bid_data = await cur.fetchone()

    if not bid_data:
        return templates.TemplateResponse("error.html", {"request": request, "message": "找不到該報價"})

    # 確保將包含 job_id 的 bid_data 傳給模板
    return templates.TemplateResponse("bidDetail.html", {"request": request, "bid": bid_data})