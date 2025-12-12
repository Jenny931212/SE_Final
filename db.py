from psycopg_pool import AsyncConnectionPool #使用connection pool
from psycopg.rows import dict_row
# db.py
defaultDB="job_platform_rating"
dbUser="postgres"
dbPassword="931212"
dbHost="localhost"
dbPort=5432

DATABASE_URL = f"postgresql://{dbUser}:{dbPassword}@{dbHost}:{dbPort}/{defaultDB}"

_pool: AsyncConnectionPool | None = None

async def getDB():
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(
            conninfo=DATABASE_URL,
            kwargs={"row_factory": dict_row},
            open=False
        )
        await _pool.open()
    async with _pool.connection() as conn:
        yield conn

async def close_pool():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None