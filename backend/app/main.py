from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, chats
from app.api import settings as settings_api
from app.config import settings

app = FastAPI(title="TelegramCode API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(chats.router, prefix="/api")
app.include_router(settings_api.router, prefix="/api")


@app.get("/")
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "mock": settings.is_mock,
        "has_api_keys": settings.has_api_keys,
        "api_id_set": bool(settings.API_ID),
        "api_hash_len": len(settings.API_HASH or "") if settings.API_HASH else 0,
        "version": "0.3.0",
    }
