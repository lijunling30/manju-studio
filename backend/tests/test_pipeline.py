"""端到端流水线测试：项目 → 小说 → 剧本 → 分镜 → 角色 → 关键帧 → 视频 → 配音 → 成片 → 合规。

（跳过闸口以直通流水线；闸口逻辑由 test_gate.py 单独覆盖。）
"""
import time

from conftest import create_project, disable_gate, wait_task


def test_end_to_end_pipeline(client, user_headers):
    disable_gate(client, user_headers)
    pid = create_project(client, user_headers)

    # ---- M2 小说 ----
    r = client.post("/api/novels/generate", headers=user_headers,
                    json={"project_id": pid, "genre": "末世", "setting": "废土",
                          "protagonist": "陈默", "chapter_count": 3})
    assert r.status_code == 200, r.text
    assert r.json()["ai_request"]["status"] == "bypassed"
    wait_task(client, user_headers, "/api/tasks")
    novel = client.get(f"/api/projects/{pid}/novel", headers=user_headers).json()
    assert novel and novel["status"] == "completed"
    assert len(novel["chapters"]) == 3
    assert novel["characters"]

    # ---- M3 剧本 ----
    r = client.post("/api/scripts/convert", headers=user_headers,
                    json={"project_id": pid})
    assert r.status_code == 200, r.text
    script = client.get(f"/api/projects/{pid}/script", headers=user_headers).json()
    assert script["status"] == "completed"
    assert script["scenes"] and script["emotion_curve"]

    # ---- M4 分镜 ----
    r = client.post("/api/shots/generate", headers=user_headers,
                    json={"project_id": pid, "shot_count": 6})
    assert r.status_code == 200, r.text
    shots = client.get(f"/api/projects/{pid}/shots", headers=user_headers).json()
    assert len(shots) == 6
    assert shots[0]["prompt_zh"]                       # 纯中文提示词
    assert "风格" in shots[0]["prompt_zh"] or shots[0]["style_id"]

    # ---- M5 角色 ----
    r = client.post("/api/character-libraries", headers=user_headers,
                    json={"name": "测试人物库", "project_ids": [pid]})
    lib_id = r.json()["id"]
    r = client.post("/api/characters", headers=user_headers,
                    json={"library_id": lib_id, "name": "陈默", "appearance": "短发硬朗",
                          "personality": "冷静"})
    char_id = r.json()["id"]
    r = client.post(f"/api/characters/{char_id}/images", headers=user_headers, json={})
    assert r.status_code == 200, r.text
    # 角色资产生成已异步化（真实模式 7 张图需数分钟），轮询等待落库
    deadline = time.time() + 15
    char = {}
    while time.time() < deadline:
        char = client.get(f"/api/character-libraries/{lib_id}/characters",
                          headers=user_headers).json()[0]
        if len(char.get("ref_images") or []) == 3 and len(char.get("expression_set") or []) == 4:
            break
        time.sleep(0.2)
    assert len(char["ref_images"]) == 3
    assert len(char["expression_set"]) == 4

    # ---- M6 关键帧 ----
    shot_id = shots[0]["id"]
    r = client.post("/api/keyframes/generate", headers=user_headers,
                    json={"shot_id": shot_id, "count": 2})
    assert r.status_code == 200, r.text
    # 抽卡为异步任务，轮询等待候选帧落库
    deadline = time.time() + 15
    kfs = []
    while time.time() < deadline:
        kfs = client.get(f"/api/shots/{shot_id}/keyframes", headers=user_headers).json()
        if len(kfs) >= 2:
            break
        time.sleep(0.2)
    assert len(kfs) == 2
    assert all(k["score"]["overall"] > 0 for k in kfs)
    client.post(f"/api/keyframes/{kfs[0]['id']}/approve", headers=user_headers)

    # ---- M7 视频 ----
    r = client.post("/api/video-tasks", headers=user_headers,
                    json={"shot_id": shot_id, "duration": 3.0})
    assert r.status_code == 200, r.text
    vt_id = r.json()["dispatch"]["task_id"]
    vt = wait_task(client, user_headers, f"/api/video-tasks/{vt_id}")
    assert vt["status"] == "success"
    assert vt["preview_url"]

    # ---- M8 配音 ----
    r = client.post("/api/audio/generate", headers=user_headers,
                    json={"project_id": pid, "shot_ids": [shot_id], "with_bgm": True})
    assert r.status_code == 200, r.text
    # 配音为异步任务，轮询等待音轨落库
    deadline = time.time() + 15
    audios = []
    while time.time() < deadline:
        audios = client.get(f"/api/projects/{pid}/audio", headers=user_headers).json()
        if any(a["type"] == "voice" for a in audios) and any(a["type"] == "bgm" for a in audios):
            break
        time.sleep(0.2)
    assert any(a["type"] == "voice" for a in audios)
    assert any(a["type"] == "bgm" for a in audios)

    # ---- M9 成片渲染（强制 AI 标识）----
    r = client.post("/api/final-videos/render", headers=user_headers,
                    json={"project_id": pid, "episode_no": 1})
    assert r.status_code == 200, r.text
    fv_id = r.json()["dispatch"]["final_video_id"]
    fv = wait_task(client, user_headers, f"/api/final-videos/{fv_id}", target=("completed",))
    assert fv["status"] == "completed"
    assert fv["ai_label_burned"] is True            # ★强制项
    assert len(fv["platform_versions"]) >= 2

    # ---- M13 合规检验（用户可选）----
    r = client.post(f"/api/final-videos/{fv_id}/export", headers=user_headers,
                    json={"compliance": "run", "platforms": ["douyin_9_16"]})
    assert r.status_code == 200, r.text
    # 审核报告异步生成，轮询等待
    deadline = time.time() + 15
    reports = []
    while time.time() < deadline:
        reports = client.get(f"/api/final-videos/{fv_id}/audit", headers=user_headers).json()
        if len(reports) >= 1:
            break
        time.sleep(0.2)
    assert len(reports) >= 1

    # ---- 流程状态 ----
    flow = client.get(f"/api/projects/{pid}/flow", headers=user_headers).json()
    assert all(s["status"] == "done" for s in flow["steps"])


def test_export_blocked_without_ai_label(client, user_headers):
    """无成功镜头视频时渲染失败；成片未完成即禁止导出（合规底线）。"""
    disable_gate(client, user_headers)
    pid = create_project(client, user_headers)
    r = client.post("/api/final-videos/render", headers=user_headers,
                    json={"project_id": pid})
    assert r.status_code == 200, r.text
    fv_id = r.json()["dispatch"]["final_video_id"]
    # 渲染任务因无视频素材而失败 → 人工介入
    wait_task(client, user_headers, "/api/tasks", target=("manual_review", "failed"))
    # 未完成的成片禁止导出（无论 AI 标识）
    r = client.post(f"/api/final-videos/{fv_id}/export", headers=user_headers,
                    json={"compliance": "skip"})
    assert r.status_code == 400
