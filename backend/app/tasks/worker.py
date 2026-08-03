"""任务编排 Worker：进程内异步调度（演示版 Celery）。

生产环境将本模块替换为 Celery + Redis / Temporal，业务语义不变：
- 扫描 queued/retrying 任务 → 并发执行；
- 确认闸口超时清扫（60s 未确认 → timeout，不产生费用）；
- 卡死任务兜底（running 超时 → manual_review）。
"""
import asyncio
import logging
from datetime import timedelta

from ..config import settings
from ..core.gate import sweep_timeouts
from ..database import SessionLocal
from ..models import TaskRecord, VideoTask, utcnow
from .jobs import run_record, run_video

logger = logging.getLogger("manju.worker")

_STUCK_MINUTES = 30


class Worker:
    def __init__(self):
        self._running: dict[str, asyncio.Task] = {}
        self._stop = False
        self._loop_task: asyncio.Task | None = None

    def start(self) -> None:
        if self._loop_task is None or self._loop_task.done():
            self._loop_task = asyncio.create_task(self._loop())
            logger.info("任务编排 Worker 已启动")

    async def stop(self) -> None:
        self._stop = True
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        for t in self._running.values():
            t.cancel()
        logger.info("任务编排 Worker 已停止")

    # ---------- 主循环 ----------
    async def _loop(self) -> None:
        while not self._stop:
            try:
                self._dispatch()
                self._sweep()
            except Exception as exc:  # 保证调度循环不崩
                logger.exception("worker tick error: %s", exc)
            await asyncio.sleep(0.5)

    # ---------- 派发 ----------
    def _dispatch(self) -> None:
        db = SessionLocal()
        try:
            for vt in db.query(VideoTask).filter(VideoTask.status.in_(["queued", "retrying"])).all():
                key = f"video:{vt.id}"
                if key not in self._running:
                    self._running[key] = asyncio.create_task(
                        self._watch(key, run_video(vt.id)))
            for tr in db.query(TaskRecord).filter(TaskRecord.status.in_(["queued", "retrying"])).all():
                key = f"record:{tr.id}"
                if key not in self._running:
                    self._running[key] = asyncio.create_task(
                        self._watch(key, run_record(tr.id)))
        finally:
            db.close()

    async def _watch(self, key: str, coro) -> None:
        try:
            await coro
        except Exception as exc:
            logger.exception("task %s crashed: %s", key, exc)
        finally:
            self._running.pop(key, None)

    # ---------- 清扫 ----------
    def _sweep(self) -> None:
        db = SessionLocal()
        try:
            # 1) 确认闸口超时（60s 未确认 → timeout，不产生费用）
            try:
                n = sweep_timeouts(db)
                if n:
                    logger.info("确认闸口超时取消 %d 条", n)
            except Exception:
                db.rollback()

            # 2) 卡死任务兜底：running 超时且无对应执行协程 → 人工介入
            cutoff = utcnow() - timedelta(minutes=_STUCK_MINUTES)
            for vt in db.query(VideoTask).filter(
                    VideoTask.status == "running", VideoTask.updated_at < cutoff).all():
                if f"video:{vt.id}" not in self._running:
                    vt.status = "manual_review"
                    vt.error = "任务执行超时，已转入人工介入"
            for tr in db.query(TaskRecord).filter(
                    TaskRecord.status == "running", TaskRecord.updated_at < cutoff).all():
                if f"record:{tr.id}" not in self._running:
                    tr.status = "manual_review"
                    tr.error = "任务执行超时，已转入人工介入"
            db.commit()
        finally:
            db.close()


worker = Worker()
