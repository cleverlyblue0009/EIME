from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router as api_router, stream_analysis


app = FastAPI(title="IME Universal", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Primary routes without prefix (matches spec)
app.include_router(api_router)
# Compatibility prefix for existing clients
app.include_router(api_router, prefix="/api")


@app.websocket("/ws/analyze")
async def ws_analyze(websocket):
    await stream_analysis(websocket)
