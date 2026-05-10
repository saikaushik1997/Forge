from contextlib import asynccontextmanager
import traceback
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from database import create_tables
import models  # noqa: F401 — registers all ORM models before create_all
from api.agents import router as agents_router
from api.workflows import router as workflows_router
from api.runs import router as runs_router
from bot.telegram_bot import start_bots, stop_bots
from runtime.templates import seed_templates
from database import AsyncSessionLocal


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    async with AsyncSessionLocal() as db:
        await seed_templates(db)
    app.state.bots = await start_bots()
    yield
    await stop_bots(app.state.bots)


app = FastAPI(title="Forge", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents_router, prefix="/api")
app.include_router(workflows_router, prefix="/api")
app.include_router(runs_router, prefix="/api")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": traceback.format_exc()})


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/bots/reload")
async def reload_bots(request: Request):
    await stop_bots(request.app.state.bots)
    request.app.state.bots = await start_bots()
    return {"started": len(request.app.state.bots)}
