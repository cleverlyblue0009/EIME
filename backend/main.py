from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.analyze import analyze_router
from backend.routes.simulate import simulate_router


app = FastAPI(title="ACRE/EIME", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ ONLY include once with prefix
app.include_router(analyze_router, prefix="/api")
app.include_router(simulate_router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}