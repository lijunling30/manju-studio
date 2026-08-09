"""端到端成片生产流水线（自动化）。

跑通：小说 → 剧本 → 角色资产库 → 分镜 → 关键帧 → 视频 → 配音 → 合成 → 导出。
关闭闸口后各模块直接 dispatch，异步任务轮询直到完成，最后导出成片。

规模控制（控时控费）：2章小说 / 6分镜 / 每镜1关键帧 / 3个视频 / 3段配音。
跳过表情集（不影响图生视频成片），角色三视图候选生成后直接进分镜。
"""
import sys
import time

import httpx

BASE = "http://localhost:8000"
SID = "pipeline"
TIMEOUT = 90

CHAPTERS = 2
SHOT_COUNT = 6
KF_COUNT = 1
VIDEO_SHOTS = 3
VIDEO_DURATION = 5.0

c = httpx.Client(base_url=BASE, timeout=TIMEOUT)


def _set_token(token: str):
    """登录/注册成功后，把 token 写入 client 默认 header，所有后续请求自动携带。"""
    c.headers["Authorization"] = f"Bearer {token}"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def register(username, password):
    r = c.post("/api/auth/register", json={"username": username, "password": password,
                                           "plan": "personal"})
    if r.status_code == 200:
        _set_token(r.json()['access_token'])
        log(f"注册并登录：{username}")
        return True
    return False


def auth(username, password):
    r = c.post("/api/auth/login", json={"username": username, "password": password})
    r.raise_for_status()
    _set_token(r.json()['access_token'])
    log(f"登录成功：{username}")


def disable_gate():
    r = c.put("/api/ai/settings/gate", json={"global_enabled": False},
              params={"session_id": SID})
    r.raise_for_status()
    log("已关闭全局闸口（直接派发，省去确认步骤）")


def list_tasks():
    r = c.get("/api/tasks", params={"limit": 100})
    r.raise_for_status()
    return r.json()


def wait_kind(kind, project_id, expect, timeout=900, label=""):
    """等待指定 kind+project 任务全部到终态。"""
    log(f"等待 {label or kind}（期望 {expect} 个，超时 {timeout}s）...")
    t0 = time.time()
    while time.time() - t0 < timeout:
        matched = [t for t in list_tasks()
                   if t["kind"] == kind and t.get("project_id") == project_id]
        done = [t for t in matched if t["status"] in
                ("success", "failed", "cancelled", "manual_review")]
        if matched and len(done) == len(matched) and len(done) >= expect:
            succ = sum(1 for t in done if t["status"] == "success")
            fail = [t for t in done if t["status"] != "success"]
            log(f"  {label or kind} 完成：成功 {succ}/{len(done)}（{int(time.time()-t0)}s）")
            return succ, fail
        time.sleep(3)
    log(f"  ⚠ {label or kind} 超时（{int(time.time()-t0)}s）")
    return -1, []


def wait_video(task_id, timeout=600):
    log(f"等待视频 #{task_id}（超时 {timeout}s）...")
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = c.get(f"/api/video-tasks/{task_id}")
        if r.status_code != 200:
            time.sleep(4); continue
        vt = r.json()
        if vt["status"] in ("success", "failed", "cancelled", "manual_review"):
            log(f"  视频 #{task_id} → {vt['status']}（{int(time.time()-t0)}s）")
            return vt
        time.sleep(4)
    log(f"  ⚠ 视频 #{task_id} 超时")
    return None


def main():
    user, pwd = "pipeline_user", "pipeline123"
    if not register(user, pwd):
        auth(user, pwd)
    disable_gate()

    # 创建项目
    r = c.post("/api/projects", json={
        "name": "成片验证·都市奇幻", "genre": "都市奇幻",
        "description": "现代都市暗藏修真界，少年林默意外觉醒上古异能",
        "style_id": "guoman", "style_name": "国漫精致风",
        "target_platform": "douyin_9_16", "budget_limit": 100.0})
    r.raise_for_status()
    pid = r.json()["id"]
    log(f"创建项目 #{pid}")

    # M2 小说（异步）
    log("=== M2 小说生成 ===")
    t = time.time()
    r = c.post("/api/novels/generate", json={
        "project_id": pid, "genre": "都市奇幻",
        "setting": "现代都市暗藏修真界，少年林默意外觉醒上古异能",
        "protagonist": "林默", "chapter_count": CHAPTERS, "session_id": SID})
    if r.status_code != 200:
        raise RuntimeError(f"小说请求失败 {r.status_code}: {r.text[:300]}")
    log(f"  小说任务 #{r.json()['dispatch']['task_id']}")
    sc, _ = wait_kind("novel_generate", pid, 1, timeout=500, label="小说")
    if sc != 1:
        raise RuntimeError("小说生成失败")
    log(f"  小说完成（{int(time.time()-t)}s）")

    # M3 剧本（同步）
    log("=== M3 剧本结构化 ===")
    t = time.time()
    r = c.post("/api/scripts/convert", json={"project_id": pid, "session_id": SID})
    if r.status_code != 200:
        raise RuntimeError(f"剧本请求失败 {r.status_code}: {r.text[:300]}")
    log(f"  剧本完成（{int(time.time()-t)}s） scenes={r.json().get('dispatch',{}).get('scenes')}")

    # M5 角色资产库（异步，每角色一个 character 任务）
    log("=== M5 角色资产库（自动生成三视图候选） ===")
    t = time.time()
    r = c.post("/api/ai/requests", json={
        "module": "character", "project_id": pid,
        "params": {"auto_generate": True, "candidate_count": 3, "project_id": pid},
        "batch_count": 1, "session_id": SID})
    if r.status_code != 200:
        raise RuntimeError(f"角色请求失败 {r.status_code}: {r.text[:300]}")
    time.sleep(3)
    r2 = c.get(f"/api/projects/{pid}/characters")
    chars = r2.json() if r2.status_code == 200 else []
    nchar = len(chars)
    log(f"  项目角色数：{nchar} {[c['name'] for c in chars]}")
    if nchar == 0:
        raise RuntimeError("小说未生成角色，无法继续")
    sc, fl = wait_kind("character", pid, nchar, timeout=1200, label=f"角色三视图({nchar})")
    log(f"  角色三视图完成：成功 {sc}/{nchar}（{int(time.time()-t)}s）")
    # 跳过表情集（不影响图生视频成片）

    # M4 分镜（同步）
    log("=== M4 分镜设计 ===")
    t = time.time()
    r = c.post("/api/shots/generate", json={"project_id": pid, "shot_count": SHOT_COUNT,
                                            "session_id": SID})
    if r.status_code != 200:
        raise RuntimeError(f"分镜请求失败 {r.status_code}: {r.text[:300]}")
    r2 = c.get(f"/api/projects/{pid}/shots")
    shots = r2.json() if r2.status_code == 200 else []
    shot_ids = [s["id"] for s in shots]
    log(f"  分镜完成（{int(time.time()-t)}s） {len(shot_ids)} 镜 ids={shot_ids}")
    if not shot_ids:
        raise RuntimeError("分镜为空")

    # M6 关键帧（异步，每镜1张）
    log(f"=== M6 关键帧抽卡（每镜 {KF_COUNT} 张） ===")
    t = time.time()
    kf_ids = []
    for sid in shot_ids:
        r = c.post("/api/keyframes/generate", json={"shot_id": sid, "count": KF_COUNT,
                                                     "session_id": SID})
        if r.status_code == 200:
            kf_ids.append(r.json()["dispatch"]["task_id"])
    log(f"  提交 {len(kf_ids)} 个关键帧任务")
    sc, _ = wait_kind("keyframe_batch", pid, len(kf_ids), timeout=1200, label="关键帧")
    log(f"  关键帧完成：成功 {sc}/{len(kf_ids)}（{int(time.time()-t)}s）")

    # M7 视频（异步，前 VIDEO_SHOTS 镜）
    vshots = shot_ids[:VIDEO_SHOTS]
    log(f"=== M7 视频生成（{len(vshots)} 镜，i2v） ===")
    t = time.time()
    vt_ids = []
    for sid in vshots:
        r = c.post("/api/video-tasks", json={"shot_id": sid, "duration": VIDEO_DURATION,
                                             "vendor": "happyhorse", "session_id": SID})
        if r.status_code == 200:
            vt_ids.append(r.json()["dispatch"]["task_id"])
    log(f"  提交 {len(vt_ids)} 个视频任务：{vt_ids}")
    for vtid in vt_ids:
        wait_video(vtid, timeout=600)
    log(f"  视频完成（{int(time.time()-t)}s）")

    # M8 配音（异步）
    log(f"=== M8 配音（TTS，{len(vshots)} 段） ===")
    t = time.time()
    r = c.post("/api/audio/generate", json={"project_id": pid, "shot_ids": vshots,
                                            "with_bgm": False, "session_id": SID})
    if r.status_code == 200:
        wait_kind("audio", pid, 1, timeout=500, label="配音")
    else:
        log(f"  ⚠ 配音请求失败 {r.status_code}: {r.text[:200]}")
    log(f"  配音完成（{int(time.time()-t)}s）")

    # M9 合成（异步）
    log("=== M9 剪辑合成 ===")
    t = time.time()
    r = c.post("/api/final-videos/render", json={"project_id": pid, "episode_no": 1,
                                                  "title": "成片验证·都市奇幻·第1集",
                                                  "session_id": SID})
    if r.status_code != 200:
        raise RuntimeError(f"合成请求失败 {r.status_code}: {r.text[:300]}")
    fv_id = r.json()["dispatch"]["final_video_id"]
    log(f"  成片 #{fv_id}，等待渲染...")
    sc, _ = wait_kind("render", pid, 1, timeout=500, label="合成")
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
    log(f"  项目 #{pid} | 成片 #{fv_id}")
    log(f"  preview_url: {fv.get('preview_url')}")
    log(f"  result_url : {fv.get('result_url')}")
    log(f"  ai_label   : {fv.get('ai_label_burned')}")
    log("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log(f"✗ 流水线失败: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
