"""漫镜工场（ManJu Studio）API 入口。

启动：cd backend && uvicorn app.main:app --reload --port 8000
文档：http://localhost:8000/docs
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import (ai_requests, audio, auth, characters, costs, final_videos,
                  keyframes, novels, projects, scripts, shots, tasks_api,
                  video_tasks)
from .config import settings
from .database import Base, engine
from .storage import ensure_dirs
from .tasks.worker import worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)   # 建表
    ensure_dirs()                           # 资产目录
    worker.start()                          # 任务编排 Worker
    yield
    await worker.stop()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.3.0",
    description="AI 漫剧工业化生产平台 · 从小说到成片的一站式流水线（含需求确认闸口 5.0.1）",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PREFIX = settings.API_PREFIX
for router in (auth.router, projects.router, novels.router, scripts.router,
               shots.router, characters.router, keyframes.router,
               video_tasks.router, audio.router, final_videos.router,
               costs.router, ai_requests.router, tasks_api.router):
    app.include_router(router, prefix=PREFIX)

# 生成资产静态服务（图片/视频/音频）—— 目录须先存在
ensure_dirs()
app.mount("/storage", StaticFiles(directory=settings.STORAGE_DIR), name="storage")


@app.get(f"{PREFIX}/health", tags=["系统"])
def health():
    return {"status": "ok", "app": settings.APP_NAME,
            "mock_mode": settings.MOCK_MODE, "version": "1.3.0"}


@app.get("/", include_in_schema=False)
def root():
    return {"name": settings.APP_NAME, "docs": "/docs", "health": f"{PREFIX}/health"}
