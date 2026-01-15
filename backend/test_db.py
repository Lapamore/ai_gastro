import asyncio
from src.infrastructure.impl.mysql_client.MySQLImpl import MySQLService
from src.infrastructure.dependencies.Config import AppConfig

async def test():
    c = AppConfig()
    impl = MySQLService(
        host=c.mysql_host,
        port=c.mysql_port,
        user=c.mysql_user,
        password=c.mysql_password,
        database=c.mysql_database
    )
    await impl._ensure_pool()
    print('Tables created successfully!')
    impl.pool.close()
    await impl.pool.wait_closed()

if __name__ == "__main__":
    asyncio.run(test())
