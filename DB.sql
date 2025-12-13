-- 1. 建立 issues 資料表 (問題主表)
CREATE TABLE issues (
    id SERIAL PRIMARY KEY,
    post_id INTEGER NOT NULL,
    opener_user VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- 外鍵：關聯到 posts 資料表
    -- 確保每個 Issue 都屬於一個 Posts 案件
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
);

-- 2. 建立 issue_comments 資料表 (問題留言表)
CREATE TABLE issue_comments (
    id SERIAL PRIMARY KEY,
    issue_id INTEGER NOT NULL,
    comment_user VARCHAR(50) NOT NULL,
    content TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- 外鍵：關聯到 issues 資料表
    -- 確保每個留言都屬於一個特定的 Issue
    FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE
);
