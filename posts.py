from psycopg_pool import AsyncConnectionPool #使用connection pool


async def getList(conn):
	async with conn.cursor() as cur:
		sql="select * from posts order by id desc;"
		await cur.execute(sql)
		rows = await cur.fetchall()
		return rows

async def getPost(conn, id):
	async with conn.cursor() as cur:
		sql="select * from posts where id=%s;"
		await cur.execute(sql,(id,))
		row = await cur.fetchone()
		return row
	
async def getApply(conn, id):
	async with conn.cursor() as cur:
		sql="select  id, username, price  from apply where id=%s;"
		await cur.execute(sql,(id,))
		rows = await cur.fetchall()
		return rows

async def deletePost(conn, id):
	async with conn.cursor() as cur:
		sql="delete from posts where id=%s;"
		await cur.execute(sql,(id,))
		# 這裡缺少 commit，但 deletePost 在一般流程中不常用，建議也加上
		await conn.commit()
		return True

async def addPost(conn, username, content):
	async with conn.cursor() as cur:
		sql="insert into posts (username,content) values (%s,%s);"
		await cur.execute(sql,(username,content))
		await conn.commit()
		return True

async def addPrice(conn, id,username, price):
	async with conn.cursor() as cur:
		sql="insert into apply (id,username,price) values (%s,%s,%s);"
		await cur.execute(sql,(id,username,price))
		await conn.commit()
		return True
	
async def setUploadFile(conn, id, filename):
	async with conn.cursor() as cur:
		sql="update posts set filename=%s where id=%s;"
		await cur.execute(sql,(filename,id))
		await conn.commit()
		return True

async def addUsers(conn, username, password):
	async with conn.cursor() as cur:
		sql="insert into users (username,password) values (%s,%s);"
		await cur.execute(sql,(username,password))
		await conn.commit()
		return True

async def getUsers(conn, username):
	async with conn.cursor() as cur:
		sql="select username, password from users where username=%s;"
		await cur.execute(sql,(username,))
		u = await cur.fetchone()
		if u:
			return {"username": u["username"], "password": u["password"]}
		return None
	
async def chooseWinner(conn, id, winner,winnerprice):
	async with conn.cursor() as cur:
		sql="update posts set winner=%s,winnerprice=%s where id=%s;"
		await cur.execute(sql,(winner, winnerprice, id))
		await conn.commit()
		return True

async def getMyPosts(conn, username):
	async with conn.cursor() as cur:
		sql="select * from posts where username=%s order by id desc;"
		await cur.execute(sql,(username,))
		rows = await cur.fetchall()
		return rows

async def getMyApplies(conn, username):
	async with conn.cursor() as cur:
		sql="select * from posts where winner=%s order by id desc;"
		await cur.execute(sql,(username,))
		rows = await cur.fetchall()
		return rows

async def delCases(conn, id):
	async with conn.cursor() as cur:
		sql="UPDATE posts SET filename = NULL WHERE id = %s;"
		await cur.execute(sql,(id,))
		await conn.commit()
		return True
	
async def changeFinish(conn, id):
	async with conn.cursor() as cur:
		sql="UPDATE posts SET finish = true WHERE id = %s;"
		await cur.execute(sql,(id,))
		# 【關鍵修正】: 必須加上 commit 才能將 Post 的 finish 狀態寫入資料庫
		await conn.commit()
		return True