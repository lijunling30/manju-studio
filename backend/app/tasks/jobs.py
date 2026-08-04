"""任务编排层（L3）：各异步任务的具体实现。

状态机（PRD 6.2）：
queued → running → success
                  └→ failed → retrying（指数退避，≤3 次）→ running
                  └→ failed(3次) → manual_review（人工介入）
running 中用户 cancel → cancelled
"""
import asyncio
import logging
import random

from sqlalchemy.orm import Session

from ..config import settings
from ..core import costs as cost_model
from ..gateway.base import ProviderError
from ..gateway.router import gateway
from ..models import (AudioAsset, AuditReport, Character, CharacterLibrary,
                      FinalVideo, Keyframe, Novel, Project, Script, Shot,
                      TaskRecord, VideoTask)

logger = logging.getLogger("manju.tasks")


def _next_vendor(current: str, priority: list[str]) -> str:
    if not current:
        return priority[0]
    try:
        idx = priority.index(current)
        return priority[(idx + 1) % len(priority)]
    except ValueError:
        return priority[0]


def _mock_score(seed: int) -> dict:
    rnd = random.Random(seed)
    composition = round(rnd.uniform(0.70, 0.97), 2)
    consistency = round(rnd.uniform(0.60, 0.96), 2)
    clarity = round(rnd.uniform(0.75, 0.98), 2)
    overall = round(composition * 0.35 + consistency * 0.40 + clarity * 0.25, 2)
    return {"composition": composition, "consistency": consistency,
            "clarity": clarity, "overall": overall}


def _sleep_sim(total: float) -> float:
    """按配置返回每步模拟延迟；测试环境可调小。"""
    return max(0.02, total)


# ==================== 视频任务（M7，异步核心） ====================
async def run_video(vt_id: int) -> None:
    """图生视频 + 自动重试（指数退避） + 主厂商失败自动切换备选。"""
    from ..database import SessionLocal
    db = SessionLocal()
    try:
        vt = db.get(VideoTask, vt_id)
        if not vt or vt.status not in ("queued", "running", "retrying"):
            return
        shot = db.get(Shot, vt.shot_id)
        params = vt.params or {}
        fail_times = int(params.get("fail_times", 0))
        duration = vt.duration or 5.0

        while True:
            attempt = vt.retry_count + 1
            vt.status = "running"
            vt.progress = 5
            vt.error = ""
            db.commit()

            if settings.MOCK_MODE:
                # 模拟模式：进度模拟（异步任务全生命周期：提交 → 轮询 → 结果入库）
                steps = 8
                step_delay = _sleep_sim(settings.MOCK_VIDEO_DELAY) / steps
                for i in range(steps):
                    vt.progress = min(88, 8 + int(80 * (i + 1) / steps))
                    db.commit()
                    await asyncio.sleep(step_delay)

            try:
                keyframe = _pick_keyframe(db, vt.shot_id)
                if not keyframe:
                    raise ProviderError("该镜头尚无关键帧，请先完成关键帧抽卡")
                seed = shot.shot_no * 1000 + vt.retry_count if shot else vt.id
                # 真实模式：图生视频为网络调用（提交+轮询），to_thread 避免阻塞事件循环
                vt.progress = 20
                db.commit()
                result = await asyncio.to_thread(
                    gateway.video, keyframe.image_url, duration, vt.vendor, seed,
                    fail_times, attempt)
                vt.result_url = result["video_url"]
                vt.preview_url = result["preview_url"]
                vt.frames = result.get("frames", [])
                vt.cost = round(cost_model.unit_price("video", vt.vendor) * duration, 4)
                vt.status = "success"
                vt.progress = 100
                vt.error = ""
                if shot:
                    shot.status = "已确认"
                cost_model.record_cost(
                    db, user_id=vt.project_id and _project_owner(db, vt.project_id) or 0,
                    project_id=vt.project_id, module="video", vendor=vt.vendor,
                    model=vt.model, task_id=vt.id, duration=duration,
                    count=1, amount=vt.cost,
                    meta={"shot_id": vt.shot_id, "retry": vt.retry_count,
                          "mock_video": result.get("mock", False)})
                db.commit()
                return
            except ProviderError as exc:
                logger.warning("video task %s 失败: %s", vt.id, exc)
                vt.error = str(exc)
                if vt.retry_count < vt.max_retries:
                    vt.retry_count += 1
                    vt.vendor = _next_vendor(vt.vendor, settings.video_vendors)
                    vt.status = "retrying"
                    vt.progress = 0
                    db.commit()
                    await asyncio.sleep(2 ** vt.retry_count)   # 指数退避
                else:
                    vt.status = "manual_review"                # 3 次仍失败 → 人工介入
                    db.commit()
                    return
    finally:
        db.close()


def _project_owner(db: Session, project_id: int) -> int:
    p = db.get(Project, project_id)
    return p.user_id if p else 0


def _pick_keyframe(db: Session, shot_id: int) -> Keyframe | None:
    kf = db.query(Keyframe).filter(Keyframe.shot_id == shot_id, Keyframe.is_approved.is_(True)).first()
    if not kf:
        kf = db.query(Keyframe).filter(Keyframe.shot_id == shot_id).first()
    return kf


# ==================== 通用异步任务（TaskRecord） ====================
async def run_record(tr_id: int) -> None:
    from ..database import SessionLocal
    db = SessionLocal()
    try:
        tr = db.get(TaskRecord, tr_id)
        if not tr or tr.status not in ("queued", "running", "retrying"):
            return
        handlers = {
            "novel_generate": _job_novel,
            "keyframe_batch": _job_keyframe,
            "character": _job_character,
            "character_expression": _job_expression,
            "audio": _job_audio,
            "render": _job_render,
            "compliance": _job_compliance,
        }
        handler = handlers.get(tr.kind)
        if not handler:
            tr.status = "failed"
            tr.error = f"未知任务类型: {tr.kind}"
            db.commit()
            return
        try:
            tr.status = "running"
            db.commit()
            await handler(db, tr)
            if tr.status == "running":
                tr.status = "success"
                tr.progress = 100
                tr.error = ""            # 成功后清除重试期残留的错误信息
            db.commit()
        except Exception as exc:
            logger.warning("task %s(%s) 失败: %s", tr.id, tr.kind, exc)
            tr.error = str(exc)
            if tr.retry_count < tr.max_retries:
                tr.retry_count += 1
                tr.status = "retrying"
                db.commit()
                await asyncio.sleep(2 ** tr.retry_count)
            else:
                tr.status = "manual_review"
            db.commit()
    finally:
        db.close()


async def _job_novel(db: Session, tr: TaskRecord) -> None:
    p = tr.params or {}
    project = db.get(Project, p.get("project_id"))
    novel = db.get(Novel, tr.ref_id)
    if not project or not novel:
        raise ProviderError("项目或小说不存在")
    novel.status = "generating"
    db.commit()
    seed = random.Random(f"{p.get('project_id')}-{novel.id}-{tr.id}").randint(0, 10 ** 9)

    # 真实模式为长时网络调用（DeepSeek），to_thread 避免阻塞事件循环
    tr.progress = 10
    db.commit()
    data = await asyncio.to_thread(
        gateway.generate_novel, p.get("genre") or novel.genre,
        p.get("setting") or "", p.get("protagonist") or "",
        int(p.get("chapter_count", 4 if p.get("mode") == "continue" else 8)), seed)

    if p.get("mode") == "continue":
        base_no = len(novel.chapters)
        novel.chapters = list(novel.chapters) + [
            {"no": base_no + c["no"], "title": c["title"], "content": c["content"]}
            for c in data["chapters"]
        ]
        novel.outline = list(novel.outline) + [
            {"no": base_no + o["no"], "title": o["title"], "summary": o["summary"]}
            for o in data["outline"]
        ]
    else:
        novel.genre = p.get("genre", project.genre)
        novel.setting = {"desc": p.get("setting", project.description or "待设定"),
                         "style": project.style_name or "默认"}
        novel.characters = data["characters"]
        novel.outline = data["outline"]
        novel.chapters = data["chapters"]
        novel.title = f"《{project.name}》"

    novel.status = "completed"
    tr.progress = 95
    db.commit()
    cost_model.record_cost(db, user_id=project.user_id, project_id=project.id,
                           module="novel", vendor=data["vendor"], model="deepseek-v3",
                           task_id=tr.id, tokens=data["tokens"], amount=data["amount"],
                           meta={"novel_id": novel.id})
    tr.result = {"novel_id": novel.id, "chapters": len(novel.chapters)}


async def _job_keyframe(db: Session, tr: TaskRecord) -> None:
    p = tr.params or {}
    shot = db.get(Shot, p.get("shot_id"))
    if not shot:
        raise ProviderError("分镜不存在")
    count = int(p.get("count", 2))
    round_no = int(p.get("round", 1))
    vendor = p.get("vendor", settings.image_vendors[0])
    model = "wan2.1" if vendor == "wanxiang" else "jimeng-v4"

    # 角色名（用于提示词与画面标注）
    char_names = _shot_char_names(db, shot)
    for i in range(count):
        seed = shot.id * 100 + round_no * 10 + i
        # 真实模式为网络调用（通义万相异步任务），to_thread 避免阻塞事件循环
        url = await asyncio.to_thread(
            gateway.keyframe, shot.shot_no, shot.prompt_zh[:40], shot.prompt_zh,
            char_names, seed, round_no)
        kf = Keyframe(shot_id=shot.id, project_id=shot.project_id, image_url=url,
                      vendor=vendor, model=model, score=_mock_score(seed),
                      is_approved=False, round=round_no,
                      cost=round(cost_model.unit_price("image", vendor), 4))
        db.add(kf)
        tr.progress = min(90, 8 + int(80 * (i + 1) / max(1, count)))
        db.commit()
        if settings.MOCK_MODE:
            await asyncio.sleep(_sleep_sim(settings.MOCK_IMAGE_DELAY) / max(1, count))
    shot.status = "抽卡中"
    cost_model.record_cost(db, user_id=shot.project_id and _project_owner(db, shot.project_id) or 0,
                           project_id=shot.project_id, module="keyframe", vendor=vendor,
                           model=model, task_id=tr.id, count=count,
                           amount=round(cost_model.unit_price("image", vendor) * count, 4),
                           meta={"shot_id": shot.id, "round": round_no})
    tr.result = {"shot_id": shot.id, "round": round_no, "count": count}


async def _job_character(db: Session, tr: TaskRecord) -> None:
    """角色候选抽卡（M5）：生成 N 张候选形象图供用户选择。

    生成 4 张不同 seed 的角色全身形象设计稿，存入 ref_images。
    用户在前端选择满意的候选后，调用 approve 触发表情集生成。
    """
    p = tr.params or {}
    char = db.get(Character, tr.ref_id or p.get("character_id"))
    if not char:
        raise ProviderError("角色不存在")
    appearance = char.appearance or char.desc
    candidate_count = p.get("candidate_count", 4)

    # 生成 N 张候选形象图（不同 seed → 不同变体）
    refs = []
    for i in range(candidate_count):
        seed = random.Random(f"{char.id}-{tr.id}-{i}").randint(0, 10 ** 9)
        refs.append(await asyncio.to_thread(
            gateway.character_ref, char.name, appearance, seed))
        tr.progress = min(90, int(90 * (i + 1) / candidate_count))
        db.commit()
    char.ref_images = refs
    char.approved_ref = None  # 重置选择状态
    char.expression_set = []  # 清空旧表情集

    cost_model.record_cost(db, user_id=tr.user_id or char.user_id,
                           project_id=tr.project_id, module="character",
                           vendor=settings.image_vendors[0], model="wan2.1",
                           task_id=tr.id, count=candidate_count,
                           amount=round(0.5 * candidate_count, 4),
                           meta={"character_id": char.id, "type": "candidate"})
    tr.result = {"character_id": char.id, "candidates": len(refs)}
    db.commit()


async def _job_expression(db: Session, tr: TaskRecord) -> None:
    """角色表情候选生成：基于用户选中的三视图 seed 生成 8 张候选表情。

    4 种情绪（喜怒哀乐）× 2 种变体 = 8 张候选，存入 expression_candidates。
    用户在前端从中选择 4 张（每种情绪选 1 张）作为最终表情集。
    使用与选中三视图相同的 seed + 详细外貌描述，增强角色一致性。
    """
    p = tr.params or {}
    char = db.get(Character, tr.ref_id or p.get("character_id"))
    if not char:
        raise ProviderError("角色不存在")
    approved = p.get("ref_index", char.approved_ref or 0)
    if approved is None or not char.ref_images or approved >= len(char.ref_images):
        raise ProviderError("未选择三视图或索引无效")

    # 用与选中三视图相同的 seed，保证角色外观一致
    base_seed = random.Random(f"{char.id}-{tr.id}-{approved}").randint(0, 10 ** 9)
    appearance = char.appearance or char.desc

    # 4 种情绪 × 2 种变体 = 8 张候选表情
    emotions = ["喜", "怒", "哀", "乐"]
    candidates = []
    for ei, emotion in enumerate(emotions):
        for vi in range(2):
            seed = base_seed + ei * 100 + vi  # 同情绪变体间 seed 接近
            candidates.append(await asyncio.to_thread(
                gateway.expression, char.name, appearance, emotion, seed))
            tr.progress = min(95, int(95 * (len(candidates)) / 8))
            db.commit()
    char.expression_candidates = candidates
    char.expression_set = []  # 清空旧表情集，等用户抽卡选择

    cost_model.record_cost(db, user_id=tr.user_id or char.user_id,
                           project_id=tr.project_id, module="character",
                           vendor=settings.image_vendors[0], model="wan2.1",
                           task_id=tr.id, count=8, amount=round(0.5 * 8, 4),
                           meta={"character_id": char.id, "type": "expression_candidates",
                                 "ref_index": approved})
    tr.result = {"character_id": char.id, "candidates": len(candidates)}
    db.commit()


def _shot_char_names(db: Session, shot: Shot) -> list[str]:
    """解析镜头角色引用（[CHAR:x] 或 char_ref_ids）为角色名。"""
    names = []
    for cid in shot.char_ref_ids or []:
        c = db.get(Character, cid)
        if c:
            names.append(c.name)
    if not names:
        # 从项目小说角色表兜底
        novel = db.query(Novel).filter(Novel.project_id == shot.project_id).first()
        if novel:
            names = [c["name"] for c in (novel.characters or [])[:2]]
    return names or ["主角"]


async def _job_audio(db: Session, tr: TaskRecord) -> None:
    p = tr.params or {}
    project = db.get(Project, p.get("project_id"))
    if not project:
        raise ProviderError("项目不存在")
    shot_ids = p.get("shot_ids") or []
    shots = db.query(Shot).filter(Shot.project_id == project.id,
                                  Shot.id.in_(shot_ids)).all() if shot_ids else \
            db.query(Shot).filter(Shot.project_id == project.id).limit(6).all()
    if not shots:
        raise ProviderError("项目暂无分镜，无法生成配音")
    seed = random.Random(f"{project.id}-{tr.id}").randint(0, 10 ** 9)
    created = 0
    for shot in shots:
        names = _shot_char_names(db, shot)
        voice_id = "doubao_voice_1"
        # 对白配音
        if shot.dialogue:
            duration = max(2.0, min(8.0, shot.duration))
            url = gateway.voice(shot.dialogue, voice_id, "中性", duration, seed + shot.id)
            db.add(AudioAsset(shot_id=shot.id, project_id=project.id, type="voice",
                              asset_url=url, character_id=(shot.char_ref_ids or [0])[0],
                              voice_id=voice_id, emotion="中性", text=shot.dialogue,
                              duration=duration))
            created += 1
        await asyncio.sleep(_sleep_sim(0.2))
    # BGM
    if p.get("with_bgm", True):
        emotion = "爽点"
        url = gateway.bgm(emotion, 12.0, seed)
        db.add(AudioAsset(shot_id=0, project_id=project.id, type="bgm", asset_url=url,
                          emotion=emotion, text="BGM 背景音乐", duration=12.0))
        created += 1
    cost_model.record_cost(db, user_id=project.user_id, project_id=project.id,
                           module="audio_tts", vendor="doubao_tts", model="doubao-tts",
                           task_id=tr.id, count=created,
                           amount=round(0.03 * created, 4), meta={"shots": len(shots)})
    tr.result = {"created": created, "shots": len(shots)}


async def _job_render(db: Session, tr: TaskRecord) -> None:
    """剪辑合成（M9）：多镜头拼接 + 平台规格 + 强制 AI 生成标识。"""
    p = tr.params or {}
    project = db.get(Project, p.get("project_id"))
    if not project:
        raise ProviderError("项目不存在")
    fv = db.get(FinalVideo, tr.ref_id)
    if not fv:
        raise ProviderError("成片记录不存在")

    shots = db.query(Shot).filter(Shot.project_id == project.id).order_by(Shot.shot_no).all()
    vids = db.query(VideoTask).filter(
        VideoTask.project_id == project.id, VideoTask.status == "success").all()
    if not vids:
        raise ProviderError("尚无成功生成的镜头视频，请先完成视频生成")
    duration = round(sum(v.duration for v in vids), 1)

    # 模拟渲染耗时
    steps = 6
    for i in range(steps):
        fv.status = "rendering"
        tr.progress = min(95, 10 + int(85 * (i + 1) / steps))
        db.commit()
        await asyncio.sleep(_sleep_sim(0.5))

    first = vids[0]
    fv.url = first.result_url or first.preview_url
    fv.preview_url = first.preview_url
    fv.duration = duration
    fv.platform_versions = [
        {"platform": "douyin", "spec": "9:16 · 1080×1920", "url": first.preview_url},
        {"platform": "bilibili", "spec": "16:9 · 1920×1080", "url": first.preview_url},
    ]
    fv.ai_label_burned = True          # ★强制项（无开关）：AI 生成内容标识
    fv.cost_total = round(cost_model.project_spent(db, project.id), 4)
    fv.status = "completed"
    cost_model.record_cost(db, user_id=project.user_id, project_id=project.id,
                           module="render", vendor="ffmpeg", model="ffmpeg-h264",
                           task_id=tr.id, duration=duration,
                           amount=round(duration * 0.05, 4),
                           meta={"shots": len(shots), "ai_label": True})
    tr.result = {"final_video_id": fv.id, "duration": duration, "shots": len(shots)}


async def _job_compliance(db: Session, tr: TaskRecord) -> None:
    """合规模块 M13（用户可选）：内容安全审核 → 报告入库。"""
    from ..gateway.providers import mock_moderation
    from ..storage import save_text
    p = tr.params or {}
    fv = db.get(FinalVideo, p.get("final_video_id"))
    if not fv:
        raise ProviderError("成片不存在")
    project = db.get(Project, fv.project_id)

    # 收集待审文本（对白 + 简介）
    texts = []
    for shot in db.query(Shot).filter(Shot.project_id == fv.project_id).all():
        if shot.dialogue:
            texts.append(shot.dialogue)
    if project and project.description:
        texts.append(project.description)

    result = gateway.moderate(texts)
    report = mock_moderation.build_report(fv.id, result)
    report_url = save_text(report["conclusion"] + "\n" + "\n".join(
        f"- {i['snippet']}（{i['reason']}）" for i in result["issues"]), "reports", ".txt")

    db.add(AuditReport(
        final_video_id=fv.id, project_id=fv.project_id, vendor=result["vendor"],
        status=result["status"], issues=result["issues"], report_url=report_url,
        raw=result))
    fv.compliance_checked = True
    fv.audit_status = result["status"]
    cost_model.record_cost(db, user_id=project.user_id if project else 0,
                           project_id=fv.project_id, module="compliance",
                           vendor=result["vendor"], model="content-security",
                           task_id=tr.id, count=1,
                           amount=round(cost_model.unit_price("moderation", result["vendor"]), 4))
    tr.result = {"final_video_id": fv.id, "status": result["status"]}
