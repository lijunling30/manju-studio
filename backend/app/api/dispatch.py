"""AI 任务派发：确认闸口通过（confirmed/bypassed）后，按模块创建具体任务。

- 异步模块（novel/keyframe/video/audio/render/compliance）→ 创建 TaskRecord/VideoTask 入队；
- 同步模块（script/shot/character）→ 直接执行并落库；
- 所有计费任务在执行前做预算拦截（达 100% 拒绝，达 80% 返回预警）。
"""
import random

from sqlalchemy.orm import Session

from ..config import settings
from ..core import costs as cost_model
from ..gateway.router import gateway
from ..models import (Character, CharacterLibrary, FinalVideo, Keyframe, Novel,
                      Project, Script, Shot, TaskRecord, VideoTask)


def _seed(project_id: int, salt: str = "") -> int:
    return random.Random(f"{project_id}-{salt}").randint(0, 10 ** 9)


def _char_names(db: Session, project: Project) -> list[str]:
    novel = db.query(Novel).filter(Novel.project_id == project.id,
                                   Novel.status == "completed").first()
    if novel and novel.characters:
        return [c["name"] for c in novel.characters]
    return []


def _char_lookup(db: Session, user_id: int, project: Project) -> dict[str, int]:
    """按角色名 → 资产库角色 ID（一致性绑定：下游必须引用资产库参考图）。"""
    libs = db.query(CharacterLibrary).filter(CharacterLibrary.user_id == user_id,
                                             CharacterLibrary.status == "active").all()
    lib_ids = [l.id for l in libs if project.id in (l.project_ids or [])] or [l.id for l in libs]
    if not lib_ids:
        return {}
    chars = db.query(Character).filter(Character.library_id.in_(lib_ids)).all()
    return {c.name: c.id for c in chars}


def _budget_guard(db: Session, user, project: Project, module: str, params: dict) -> None:
    """预算护栏（A-2）：达 100% 拦截并抛错；达 80% 仅记录。"""
    est = gateway.estimate(module, params)
    guard = cost_model.check_budget(db, project, est["high"])
    if guard["blocked"]:
        raise ValueError(
            f"项目预算已用尽（已用 ¥{guard['spent']:.2f} / ¥{guard['limit']:.2f}），"
            f"请在成本中心调整预算上限后再生成")
    return guard


# ---------- 模块派发 ----------
def dispatch_job(db: Session, user, module: str, params: dict, req_id: int) -> dict:
    project_id = params.get("project_id")
    project = db.get(Project, project_id) if project_id else None

    if module == "novel":
        if not project:
            raise ValueError("缺少 project_id")
        _budget_guard(db, user, project, "novel", params)
        novel = Novel(project_id=project.id, status="generating",
                      genre=params.get("genre", project.genre))
        db.add(novel)
        db.commit()
        tr = TaskRecord(user_id=user.id, project_id=project.id, module="novel",
                        kind="novel_generate", ref_id=novel.id, params=dict(params),
                        status="queued")
        db.add(tr)
        db.commit()
        return {"kind": "novel_generate", "task_id": tr.id, "novel_id": novel.id}

    if module == "script":
        if not project:
            raise ValueError("缺少 project_id")
        _budget_guard(db, user, project, "script", params)
        novel = db.query(Novel).filter(Novel.project_id == project.id,
                                       Novel.status == "completed").order_by(Novel.id.desc()).first()
        if not novel:
            raise ValueError("请先完成小说生成（M2）")
        data = gateway.generate_script(novel.title, novel.chapters, _seed(project.id, "script"))
        script = db.query(Script).filter(Script.project_id == project.id).first()
        if not script:
            script = Script(project_id=project.id, novel_id=novel.id, title=f"{novel.title} · 剧本")
            db.add(script)
        script.scenes = data["scenes"]
        script.emotion_curve = data["emotion_curve"]
        script.status = "completed"
        cost_model.record_cost(db, user_id=user.id, project_id=project.id, module="script",
                               vendor=data["vendor"], model="qwen-plus", tokens=data["tokens"],
                               amount=data["amount"], meta={"script_id": script.id})
        db.commit()
        return {"kind": "script", "script_id": script.id, "scenes": len(data["scenes"])}

    if module == "shot":
        if not project:
            raise ValueError("缺少 project_id")
        params = dict(params)
        params["batch_count"] = params.get("shot_count", 9)
        _budget_guard(db, user, project, "shot", params)
        script = db.query(Script).filter(Script.project_id == project.id,
                                         Script.status == "completed").first()
        if not script:
            raise ValueError("请先完成剧本结构化（M3）")
        char_names = _char_names(db, project)
        char_ids = _char_lookup(db, user.id, project)
        data = gateway.generate_shots(script.scenes, params.get("shot_count", 9),
                                      project.style_id or "默认漫画风格", char_names,
                                      _seed(project.id, "shot"))
        # 提示词强制携带角色引用 [CHAR:x] 与风格 ID
        prompts, ref_ids, char_token = data["shots"], [], {}
        for i, c in enumerate(char_names):
            cid = char_ids.get(c)
            if cid:
                char_token[c] = f"[CHAR:{cid}]"
                ref_ids.append(cid)
            else:
                char_token[c] = f"[CHAR:{i + 1}]"
        db.query(Shot).filter(Shot.project_id == project.id).delete(synchronize_session=False)
        for s in prompts:
            prompt = s["prompt_zh"]
            for name, token in char_token.items():
                prompt = prompt.replace(name, f"{token}{name}")
            db.add(Shot(project_id=project.id, script_id=script.id, shot_no=s["shot_no"],
                        scene_no=s["scene_no"], shot_type=s["shot_type"],
                        camera_move=s["camera_move"], duration=s["duration"],
                        prompt_zh=prompt, char_ref_ids=list(dict.fromkeys(ref_ids)),
                        style_id=project.style_id or s["style_id"], dialogue=s["dialogue"],
                        narration=s["narration"], transition=s["transition"],
                        order_index=s["shot_no"], status="待生成"))
        cost_model.record_cost(db, user_id=user.id, project_id=project.id, module="shot",
                               vendor=data["vendor"], model="deepseek-v3", tokens=data["tokens"],
                               amount=data["amount"], meta={"script_id": script.id, "shots": len(prompts)})
        db.commit()
        return {"kind": "shot", "shots": len(prompts), "script_id": script.id}

    if module == "character":
        char = db.get(Character, params.get("character_id", 0))
        if not char:
            # 支持「创建并生成形象」：闸口参数携带角色信息时先建角色记录
            lib_id = params.get("library_id")
            if lib_id and params.get("name"):
                lib = db.get(CharacterLibrary, lib_id)
                if not lib or lib.user_id != user.id:
                    raise ValueError("人物子库不存在")
                char = Character(user_id=user.id, library_id=lib_id, name=params["name"],
                                 appearance=params.get("appearance") or "",
                                 personality=params.get("personality") or "")
                db.add(char)
                db.commit()
                db.refresh(char)
                params = dict(params, character_id=char.id)
            else:
                raise ValueError("角色不存在")
        proj = db.get(Project, params.get("project_id", 0)) if params.get("project_id") else None
        if proj:
            _budget_guard(db, user, proj, "character", params)
        # 生成三视图参考图 + 表情集（异步任务队列：真实模式单张图 10-60s）
        tr = TaskRecord(user_id=user.id, project_id=proj.id if proj else None,
                        module="character", kind="character", ref_id=char.id,
                        params=dict(params), status="queued")
        db.add(tr)
        db.commit()
        return {"kind": "character", "task_id": tr.id, "character_id": char.id}

    if module == "keyframe":
        shot = db.get(Shot, params.get("shot_id"))
        if not shot:
            raise ValueError("分镜不存在")
        _budget_guard(db, user, db.get(Project, shot.project_id), "keyframe", params)
        tr = TaskRecord(user_id=user.id, project_id=shot.project_id, module="keyframe",
                        kind="keyframe_batch", ref_id=shot.id, params=dict(params),
                        status="queued")
        db.add(tr)
        db.commit()
        return {"kind": "keyframe_batch", "task_id": tr.id, "shot_id": shot.id}

    if module == "video":
        shot = db.get(Shot, params.get("shot_id"))
        if not shot:
            raise ValueError("分镜不存在")
        project = db.get(Project, shot.project_id)
        _budget_guard(db, user, project, "video", params)
        vendor = params.get("vendor") or settings.video_vendors[0]
        vt = VideoTask(shot_id=shot.id, project_id=shot.project_id, vendor=vendor,
                       model={"vidu_q3": "Q3", "seedance_2_0": "Seedance 2.0",
                              "kling_2_0": "Kling 2.0"}.get(vendor, vendor),
                       duration=params.get("duration", 5.0), status="queued",
                       params=dict(params))
        db.add(vt)
        db.commit()
        return {"kind": "video", "task_id": vt.id, "shot_id": shot.id}

    if module in ("audio_tts", "bgm", "sfx"):
        project = db.get(Project, params.get("project_id"))
        if not project:
            raise ValueError("缺少 project_id")
        _budget_guard(db, user, project, module, params)
        tr = TaskRecord(user_id=user.id, project_id=project.id, module=module,
                        kind="audio", ref_id=project.id, params=dict(params), status="queued")
        db.add(tr)
        db.commit()
        return {"kind": "audio", "task_id": tr.id, "project_id": project.id}

    if module == "render":
        project = db.get(Project, params.get("project_id"))
        if not project:
            raise ValueError("缺少 project_id")
        vids = db.query(VideoTask).filter(VideoTask.project_id == project.id,
                                          VideoTask.status == "success").all()
        total_duration = round(sum(v.duration for v in vids), 1)
        params = dict(params, total_duration=total_duration)
        _budget_guard(db, user, project, "render", params)
        fv = FinalVideo(project_id=project.id, episode_no=params.get("episode_no", 1),
                        title=params.get("title", f"{project.name} · 第{params.get('episode_no', 1)}集"),
                        status="draft")
        db.add(fv)
        db.commit()
        tr = TaskRecord(user_id=user.id, project_id=project.id, module="render",
                        kind="render", ref_id=fv.id, params=dict(params), status="queued")
        db.add(tr)
        db.commit()
        return {"kind": "render", "task_id": tr.id, "final_video_id": fv.id}

    if module == "compliance":
        fv = db.get(FinalVideo, params.get("final_video_id"))
        if not fv:
            raise ValueError("成片不存在")
        _budget_guard(db, user, db.get(Project, fv.project_id), "compliance", params)
        tr = TaskRecord(user_id=user.id, project_id=fv.project_id, module="compliance",
                        kind="compliance", ref_id=fv.id, params=dict(params), status="queued")
        db.add(tr)
        db.commit()
        return {"kind": "compliance", "task_id": tr.id, "final_video_id": fv.id}

    raise ValueError(f"不支持的模块: {module}")
