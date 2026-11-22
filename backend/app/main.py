from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.auth import router as auth_router
from app.client.telethon_manager import MOCK

app = FastAPI(
    title="TelegramCode",
    description="Улучшенный клиент Telegram",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")


@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "TelegramCode API",
        "version": "0.1.0",
        "mode": "mock" if MOCK else "real",
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "mock": MOCK}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
