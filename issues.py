from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row 

# 建立 Issue
async def createIssue(conn, post_id: int, title: str, description: str, current_user: str):
    async with conn.cursor() as cur:
        # 1. 插入新的 Issue 記錄 (注意：預設 status 為 open)
        issue_sql = "INSERT INTO issues (post_id, opener_user, title, description) VALUES (%s, %s, %s, %s) RETURNING id;"
        await cur.execute(issue_sql, (post_id, current_user, title, description))
        
        # 取得新建立的 Issue ID
        issue_id_result = await cur.fetchone()
        issue_id = issue_id_result['id']
        
        # 2. 同時為 Issue 建立第一條留言
        comment_sql = "INSERT INTO issue_comments (issue_id, comment_user, content) VALUES (%s, %s, %s);"
        await cur.execute(comment_sql, (issue_id, current_user, description))
        
        await conn.commit() 
        return issue_id

# 取得某個案件的所有 Issues
async def getIssuesByPostId(conn, post_id: int):
    async with conn.cursor() as cur:
        # 使用 LOWER() 確保狀態查詢的一致性
        sql = "SELECT id, post_id, opener_user, title, description, status, created_at FROM issues WHERE post_id = %s ORDER BY created_at DESC;"
        await cur.execute(sql, (post_id,))
        rows = await cur.fetchall()
        return rows

# 取得某個 Issue 的所有留言
async def getCommentsByIssueId(conn, issue_id: int):
    async with conn.cursor() as cur:
        sql = "SELECT id, issue_id, comment_user, content, created_at FROM issue_comments WHERE issue_id = %s ORDER BY created_at ASC;"
        await cur.execute(sql, (issue_id,))
        rows = await cur.fetchall()
        return rows

# 新增留言
async def addComment(conn, issue_id: int, comment_user: str, content: str):
    async with conn.cursor() as cur:
        sql = "INSERT INTO issue_comments (issue_id, comment_user, content) VALUES (%s, %s, %s);"
        await cur.execute(sql, (issue_id, comment_user, content))
        await conn.commit()
        return True

# 關閉 Issue (將 status 設為 'closed')
async def closeIssue(conn, issue_id: int):
    async with conn.cursor() as cur:
        # 確保更新為小寫 'closed'
        sql = "UPDATE issues SET status = 'closed' WHERE id = %s;"
        await cur.execute(sql, (issue_id,))
        await conn.commit()
        return True
    
# 【最終修正】: 關閉某個案件下的所有 Issues
async def closeAllIssuesForPost(conn, post_id: int):
    """
    將特定 post_id 下所有 'open' 狀態的 Issues 變更為 'closed'，使用 LOWER 確保匹配。
    """
    async with conn.cursor() as cur:
        # ⚠️ 關鍵修正：使用 LOWER(status) = 'open' 忽略大小寫進行比對
        # 並將狀態強制更新為小寫 'closed'
        sql = "UPDATE issues SET status = 'closed' WHERE post_id = %s AND LOWER(status) = 'open';"
        await cur.execute(sql, (post_id,))
        
        # 取得實際更新的行數 (用於除錯，如果 > 0 表示成功)
        rows_affected = cur.rowcount 
        
        await conn.commit() 
        
        return rows_affected