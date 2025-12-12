from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware  # ← 新增這行
from routes import jobs, upload, dbQuery, bid, auth
import traceback

app = FastAPI()

# 啟用 SessionMiddleware 
#在處理客戶端請求和發送回應的過程中，夾在中間執行一些操作

app.add_middleware(
    SessionMiddleware,
    secret_key="supersecretkey123", #金鑰
    same_site="lax",       # 允許同源表單傳 cookie
    https_only=False,      # 本地測試不要強制 HTTPS
    max_age=60 * 60 * 24,  # cookie 保留 1 天
)


# 全域例外處理

@app.exception_handler(Exception)
#記錄錯誤和回傳
#發出這個請求的上下文資訊，錯誤的具體內容

async def global_exception_handler(request: Request, exc: Exception):
    print("🚨 發生未處理的例外！")
    traceback.print_exc()
    #把字典資料 ({"detail": "...", "error": "..."}) 
    #自動轉換為標準的 JSON 格式字串。
    
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "error": str(exc)}
    )


# 模組路由

app.include_router(jobs.router, prefix="/jobs")
app.include_router(upload.router, prefix="/api")
app.include_router(dbQuery.router, prefix="/api")
app.include_router(bid.router, prefix="/bid")
app.include_router(auth.router)
app.include_router(upload.router, prefix="/upload")


# ============================
# 首頁
# ============================
@app.get("/")
async def home():
    return {"message": "前往 /jobs 查看委託案列表"}

# ============================
# 靜態檔案
# ============================
app.mount("/static", StaticFiles(directory="static"), name="static")
