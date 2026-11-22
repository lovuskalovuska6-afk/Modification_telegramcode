from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.auth import router as auth_router
from app.api.chats import router as chats_router
from app.client.telethon_manager import MOCK

app = FastAPI(
    title="TelegramCode",
    description="Улучшенный клиент Telegram",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(chats_router, prefix="/api")


@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "TelegramCode API",
        "version": "0.2.0",
        "mode": "mock" if MOCK else "real",
        "has_api_keys": settings.has_api_keys,
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "mock": MOCK,
        "has_api_keys": settings.has_api_keys,
        "api_id_set": bool(settings.API_ID),
        "api_hash_len": len(settings.API_HASH or ""),
    }
