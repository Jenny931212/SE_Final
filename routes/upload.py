from fastapi import APIRouter, Request, Depends, UploadFile, File, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import os
from db import getDB

router = APIRouter()
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = "static/uploads" #定義所有使用者上傳的檔案 要存放在伺服器上的哪個資料夾

# 若資料夾不存在就建立
os.makedirs(UPLOAD_DIR, exist_ok=True) #(如果這個資料夾已經存在了，也不要報錯)


# 上傳表單

@router.get("/form")
async def upload_form(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("uploadForm.html", {"request": request})


#  上傳檔案動作

@router.post("/submit")
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

    # 儲存檔案到 static/uploads
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # 寫入資料庫
    async with conn.cursor() as cur:
        await cur.execute("""
            INSERT INTO files (job_id, uploader_id, filename, role)
            VALUES (%s, %s, %s, %s);
        """, (job_id, user_id, file.filename, role))
    await conn.commit()

    print(f"📁 使用者 {user_id} 上傳檔案 {file.filename}")
    return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)
