-- 使用 UTF8
SET client_encoding = 'UTF8';

-- ================= 1.使用者 =================
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT CHECK (role IN ('client', 'contractor')) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ================= 2.案件 =================
CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT CHECK (
        status IN ('open', 'in_progress', 'submitted', 'reject', 'closed')
    ) NOT NULL DEFAULT 'open',
    client_id INT NOT NULL REFERENCES users(id),
    contractor_id INT REFERENCES users(id),
    bid_deadline TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ================= 3.投標 / 提案 =================
CREATE TABLE proposals (
    id SERIAL PRIMARY KEY,
    project_id INT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    contractor_id INT NOT NULL REFERENCES users(id),
    message TEXT,
    price NUMERIC,
    proposal_filename TEXT,
    proposal_filepath TEXT,
    accepted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ================= 4.結案檔案 =================
CREATE TABLE closure_files (
    id SERIAL PRIMARY KEY,
    project_id INT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    contractor_id INT NOT NULL REFERENCES users(id),
    version INT NOT NULL DEFAULT 1,
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ================= 5.評價 =================
CREATE TABLE ratings (
    id SERIAL PRIMARY KEY,
    project_id INT NOT NULL REFERENCES projects(id),
    target_id INT NOT NULL REFERENCES users(id),
    target_role TEXT CHECK (target_role IN ('client', 'contractor')),
    rater_id INT NOT NULL REFERENCES users(id),
    rater_role TEXT CHECK (rater_role IN ('client', 'contractor')),
    score_1 INT CHECK (score_1 BETWEEN 1 AND 5),
    score_2 INT CHECK (score_2 BETWEEN 1 AND 5),
    score_3 INT CHECK (score_3 BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ================= 6.Issue =================
CREATE TABLE issues (
    id SERIAL PRIMARY KEY,
    project_id INT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    opener_id INT NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    description TEXT,
    status TEXT CHECK (status IN ('open', 'resolved')) DEFAULT 'open',
    created_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP
);

-- ================= 7.Issue留言 =================
CREATE TABLE issue_comments (
    id SERIAL PRIMARY KEY,
    issue_id INT NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    author_id INT NOT NULL REFERENCES users(id),
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
