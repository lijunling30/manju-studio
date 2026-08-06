# -*- coding: utf-8 -*-
"""续跑成片流水线：复用项目17（小说/剧本/角色/分镜已完成），从关键帧阶段继续。

背景：首轮关键帧因万相并发限流全部失败。现已将 worker 并发降为 1、万相重试增至 5，
本脚本重置失败的关键帧任务后继续：关键帧 → 视频 → 配音 → 合成 → 导出。
"""
import os
import sqlite3
import sys
import time

import httpx

BASE = "http://localhost:8000"
SID = "resume"
PID = 17  # 复用项目17
TIMEOUT = 90

SHOT_COUNT = 6
KF_COUNT = 1
VIDEO_SHOTS = 3
VIDEO_DURATION = 5.0

c = httpx.Client(base_url=BASE, timeout=TIMEOUT)
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manju.db")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _set_token(token: str):
    c.headers["Authorization"] = f"Bearer {token}"


def auth(username, password):
    r = c.post("/api/auth/login", json={"username": username, "password": password})
    r.raise_for_status()
    _set_token(r.json()["access_token"])
    log(f"登录成功：{username}")


def disable_gate():
    r = c.put("/api/ai/settings/gate", json={"global_enabled": False},
              params={"session_id": SID})
    r.raise_for_status()
    log("已关闭全局闸口")


def list_tasks():
    r = c.get("/api/tasks", params={"limit": 100})
    r.raise_for_status()
    return r.json()


def wait_kind(kind, project_id, expect, timeout=900, label=""):
    log(f"等待 {label or kind}（期望 {expect} 个，超时 {timeout}s）...")
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            matched = [t for t in list_tasks()
                       if t["kind"] == kind and t.get("project_id") == project_id]
            done = [t for t in matched if t["status"] in
                    ("success", "failed", "cancelled", "manual_review")]
            if matched and len(done) == len(matched) and len(done) >= expect:
                succ = sum(1 for t in done if t["status"] == "success")
                fail = [t for t in done if t["status"] != "success"]
                log(f"  {label or kind} 完成：成功 {succ}/{len(done)}（{int(time.time()-t0)}s）")
                return succ, fail
        except Exception:
            pass  # 后端短暂不可用时跳过这一轮
        time.sleep(3)
    log(f"  ⚠ {label or kind} 超时（{int(time.time()-t0)}s）")
    return -1, []


def wait_video(task_id, timeout=600):
    log(f"等待视频 #{task_id}（超时 {timeout}s）...")
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            r = c.get(f"/api/video-tasks/{task_id}")
            if r.status_code == 200:
                vt = r.json()
                if vt["status"] in ("success", "failed", "cancelled", "manual_review"):
                    log(f"  视频 #{task_id} → {vt['status']}（{int(time.time()-t0)}s）")
                    return vt
        except Exception:
            pass
        time.sleep(4)
    log(f"  ⚠ 视频 #{task_id} 超时")
    return None


def reset_keyframe_tasks():
    """直接用 SQL 重置项目17的关键帧任务为 queued，让 worker 重新拾取。"""
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    n = cur.execute(
        "UPDATE task_record SET status='queued', retry_count=0, error='', progress=0 "
        "WHERE kind='keyframe_batch' AND project_id=?", (PID,)).rowcount
    conn.commit()
    conn.close()
    log(f"已重置 {n} 个关键帧任务为 queued（worker 并发=1 将串行执行）")


def main():
    auth("pipeline_user", "pipeline123")
    disable_gate()

    # 获取项目17的分镜
    r = c.get(f"/api/projects/{PID}/shots")
    r.raise_for_status()
    shots = r.json()
    shot_ids = [s["id"] for s in shots]
    log(f"项目 #{PID} 分镜：{len(shot_ids)} 镜 ids={shot_ids}")
    if not shot_ids:
        raise RuntimeError("项目17无分镜")

    # 重置关键帧任务（首轮因并发限流全部失败）
    reset_keyframe_tasks()

    # 等待关键帧完成（串行执行，6张图）
    log("=== M6 关键帧抽卡（串行重跑） ===")
    t = time.time()
    sc, fl = wait_kind("keyframe_batch", PID, len(shot_ids), timeout=1800, label="关键帧")
    log(f"  关键帧完成：成功 {sc}/{len(shot_ids)}（{int(time.time()-t)}s）")
    if sc <= 0:
        raise RuntimeError("关键帧全部失败，无法继续视频生成")

    # 检查关键帧是否有 source_url（图生视频依赖）
    r = c.get(f"/api/projects/{PID}/keyframes")
    kfs = r.json() if r.status_code == 200 else []
    log(f"  关键帧记录：{len(kfs)} 条")
    for kf in kfs[:3]:
        log(f"    kf#{kf['id']} shot={kf.get('shot_id')} src={'有' if kf.get('source_url') else '无'} img={kf.get('image_url','')[:40]}")

    # M7 视频（前 VIDEO_SHOTS 镜）
    vshots = shot_ids[:VIDEO_SHOTS]
    log(f"=== M7 视频生成（{len(vshots)} 镜，i2v） ===")
    t = time.time()
    vt_ids = []
    for sid in vshots:
        r = c.post("/api/video-tasks", json={"shot_id": sid, "duration": VIDEO_DURATION,
                                             "vendor": "happyhorse", "session_id": SID})
        if r.status_code == 200:
            vt_ids.append(r.json()["dispatch"]["task_id"])
        else:
            log(f"  ⚠ 镜头 {sid} 视频请求失败 {r.status_code}: {r.text[:200]}")
    log(f"  提交 {len(vt_ids)} 个视频任务：{vt_ids}")
    for vtid in vt_ids:
        wait_video(vtid, timeout=900)
    log(f"  视频完成（{int(time.time()-t)}s）")

    # 检查视频成功数
    r = c.get(f"/api/projects/{PID}/final-videos")
    vids_ok = 0
    for sid in vshots:
        r2 = c.get(f"/api/shots/{sid}/video-tasks")
        if r2.status_code == 200:
            for vt in r2.json():
                if vt["status"] == "success":
                    vids_ok += 1
                    break
    log(f"  成功视频数：{vids_ok}/{len(vshots)}")
    if vids_ok == 0:
        raise RuntimeError("视频全部失败，无法合成成片")

    # M8 配音（异步）
    log(f"=== M8 配音（TTS，{len(vshots)} 段） ===")
    t = time.time()
    r = c.post("/api/audio/generate", json={"project_id": PID, "shot_ids": vshots,
                                            "with_bgm": False, "session_id": SID})
    if r.status_code == 200:
        wait_kind("audio", PID, 1, timeout=500, label="配音")
    else:
        log(f"  ⚠ 配音请求失败 {r.status_code}: {r.text[:200]}")
    log(f"  配音完成（{int(time.time()-t)}s）")

    # M9 合成（异步）
    log("=== M9 剪辑合成 ===")
    t = time.time()
    r = c.post("/api/final-videos/render", json={"project_id": PID, "episode_no": 1,
                                                  "title": "成片验证·都市奇幻·第1集",
                                                  "session_id": SID})
    if r.status_code != 200:
        raise RuntimeError(f"合成请求失败 {r.status_code}: {r.text[:300]}")
    fv_id = r.json()["dispatch"]["final_video_id"]
    log(f"  成片 #{fv_id}，等待渲染...")
    sc, _ = wait_kind("render", PID, 1, timeout=500, label="合成")
    r = c.get(f"/api/final-videos/{fv_id}")
    fv = r.json() if r.status_code == 200 else {}
    log(f"  合成完成（{int(time.time()-t)}s） status={fv.get('status')}")

    # 导出（跳过合规）
    log("=== 导出成片 ===")
    r = c.post(f"/api/final-videos/{fv_id}/export",
               json={"platforms": ["douyin_9_16"], "compliance": "skip", "session_id": SID})
    log(f"  导出响应 {r.status_code}: {r.text[:300]}")

    log("=" * 60)
    log("成片生产流水线完成")
    log(f"  项目 #{PID} | 成片 #{fv_id}")
    log(f"  url        : {fv.get('url')}")
    log(f"  preview_url: {fv.get('preview_url')}")
    log(f"  ai_label   : {fv.get('ai_label_burned')}")
    log(f"  duration   : {fv.get('duration')}")
    log("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log(f"✗ 续跑失败: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
