import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.services.api.ChatRouter import router as chat_router
from src.api.routes.diary_routes import router as diary_router
from src.api.routes.user_routes import router as user_router
from src.api.routes.mattermost_routes import router as mattermost_router

logger = logging.getLogger(__name__)

def create_app():
    app = FastAPI()

    # Добавляем CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Подключение роутов
    app.include_router(chat_router)  # уже имеет prefix="/api"
    app.include_router(diary_router, prefix="/api")
    app.include_router(user_router, prefix="/api")
    app.include_router(mattermost_router, prefix="/api")

    return app

app = create_app()

@app.on_event("startup")
async def startup_event():
    # Здесь можно инициализировать соединение с БД и другими сервисами
    logger.info("Запуск приложения...")
    # Пример инициализации БД:
    # app.state.db_service = MongoDBService(...)
    # await app.state.db_service.connect()

@app.on_event("shutdown")
async def shutdown_event():
    # Здесь можно закрыть соединения и освободить ресурсы
    logger.info("Выключение приложения...")
    # Пример закрытия соединения с БД:
    # await app.state.db_service.close()
    # del app.state.db_service

# Пример эндпоинта
@app.get("/")
async def read_root():
    return {"Hello": "World"}