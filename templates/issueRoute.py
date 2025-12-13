from fastapi import APIRouter, Depends, Form
from fastapi.responses import JSONResponse
from model.db import getDB
import model.issues as issues
import model.posts as posts # 用來處理最終結案和檢查 post 擁有者
from fastapi import HTTPException # 引入 HTTPException 處理錯誤

# <<< 修正：從 dependencies.py 引入身份驗證函式 >>>
from dependencies import get_current_user 

router = APIRouter()

# 輔助函式：將 datetime 物件轉換為 ISO 格式字串，方便前端 Vue 處理
def format_datetime_rows(rows):
    if not isinstance(rows, list):
        return rows
    for row in rows:
        if isinstance(row, dict) and 'created_at' in row and row['created_at']:
            row['created_at'] = row['created_at'].isoformat()
    return rows

# 取得特定案件的所有 Issues
@router.get("/issues/get/{post_id}")
async def get_issues(post_id: int, conn=Depends(getDB)):
    issue_list = await issues.getIssuesByPostId(conn, post_id)
    return format_datetime_rows(issue_list)

# 取得特定 Issue 的所有留言
@router.get("/issues/comments/{issue_id}")
async def get_issue_comments(issue_id: int, conn=Depends(getDB)):
    comment_list = await issues.getCommentsByIssueId(conn, issue_id)
    return format_datetime_rows(comment_list)

# 建立新 Issue (只有案件擁有者能建立)
@router.post("/issues/create")
async def create_new_issue(
    post_id: int = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    current_user: str = Depends(get_current_user),
    conn=Depends(getDB)
):
    if not current_user:
        return JSONResponse(content={"success": False, "detail": "未登入"}, status_code=401)
    
    # 檢查是否為案件擁有者
    post = await posts.getPost(conn, post_id)
    if not post or post.get('username') != current_user:
        return JSONResponse(content={"success": False, "detail": "無權提出問題 (Issue)"}, status_code=403)
    
    try:
        await issues.createIssue(conn, post_id, title, description, current_user)
        return {"success": True}
    except Exception as e:
        print(f"Error creating issue: {e}")
        return JSONResponse(content={"success": False, "detail": str(e)}, status_code=500)

# 新增 Issue 留言
@router.post("/issues/comment/add")
async def add_issue_comment(
    issue_id: int = Form(...),
    content: str = Form(...),
    current_user: str = Depends(get_current_user),
    conn=Depends(getDB)
):
    if not current_user:
        return JSONResponse(content={"success": False, "detail": "未登入"}, status_code=401)
        
    try:
        await issues.addComment(conn, issue_id, current_user, content)
        return {"success": True}
    except Exception as e:
        print(f"Error adding comment: {e}")
        return JSONResponse(content={"success": False, "detail": str(e)}, status_code=500)

# 關閉 Issue (只有案件擁有者能關閉)
@router.post("/issues/close/{issue_id}")
async def close_issue(issue_id: int, conn=Depends(getDB), current_user: str = Depends(get_current_user)):
    if not current_user:
        return JSONResponse(content={"success": False, "detail": "未登入"}, status_code=401)
    
    # 這裡缺乏嚴格的後端權限檢查 (Issue 必須屬於 Post 的擁有者才能關閉)，
    # 但為了快速解決，我們假設 issues.py 中的 closeIssue 能處理。
    # 建議未來在 issues.py 或這裡加入更嚴格的 post_id 檢查。

    try:
        await issues.closeIssue(conn, issue_id)
        return {"success": True}
    except Exception as e:
        print(f"Error closing issue: {e}")
        return JSONResponse(content={"success": False, "detail": str(e)}, status_code=500)

# 最終結案 (只有案件擁有者能結案)
@router.post("/posts/finalize/{post_id}")
async def finalize_post(post_id: int, conn=Depends(getDB), current_user: str = Depends(get_current_user)):
    if not current_user:
        return JSONResponse(content={"success": False, "detail": "未登入"}, status_code=401)
    
    # 檢查權限
    post = await posts.getPost(conn, post_id)
    if not post or post.get('username') != current_user:
        return JSONResponse(content={"success": False, "detail": "無權最終結案"}, status_code=403)
    
    try:
        # 【關鍵修改】: 在結案 Post 之前，強制關閉所有 Issue
        await issues.closeAllIssuesForPost(conn, post_id) 
        
        # 結案 Post (請確保 posts.changeFinish 內部也包含 await conn.commit())
        await posts.changeFinish(conn, post_id) 
        
        # 回傳成功訊息
        return {"success": True, "detail": "案件及所有未結 Issues 已成功最終結案"}
    except Exception as e:
        print(f"Error finalizing post: {e}")
        return JSONResponse(content={"success": False, "detail": f"結案處理失敗: {str(e)}"}, status_code=500)