
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row

defaultDB = "1141se"
dbUser = "postgres"
dbPassword = "jiajiun"
dbHost = "localhost"
dbPort = 5432

DATABASE_URL = f"dbname={defaultDB} user={dbUser} password={dbPassword} host={dbHost} port={dbPort}"

_pool: AsyncConnectionPool | None = None


async def getDB():
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(
            conninfo=DATABASE_URL,
            kwargs={"row_factory": dict_row},
            open=True, 
        )

    
    conn = await _pool.getconn()
    try:
        yield conn
    finally:
        # 結束後歸還連線給 pool（不關閉）
        await _pool.putconn(conn)
