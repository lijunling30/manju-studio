"""计费与预算护栏测试（A-2）：成本记账、预算拦截、账单汇总。"""
from conftest import create_project, disable_gate, wait_task


def test_cost_logging_and_summary(client, user_headers):
    disable_gate(client, user_headers)
    pid = create_project(client, user_headers, budget=500.0)

    r = client.post("/api/novels/generate", headers=user_headers,
                    json={"project_id": pid, "genre": "都市", "chapter_count": 2})
    assert r.status_code == 200, r.text
    wait_task(client, user_headers, "/api/tasks")

    summary = client.get(f"/api/projects/{pid}/costs", headers=user_headers).json()
    assert summary["total"] > 0
    assert "novel" in summary["by_module"]
    assert summary["logs"], "应有成本明细记录"

    bills = client.get("/api/bills", headers=user_headers).json()
    assert any(b["project_id"] == pid for b in bills["items"])


def test_budget_block_before_generation(client, user_headers):
    """预算达 100% → 生成前拦截（A-2）。"""
    disable_gate(client, user_headers)
    # 极小预算（0.01 元），视频任务预估成本远高于预算 → 创建即拦截
    pid = create_project(client, user_headers, budget=0.01)
    r = client.post("/api/video-tasks", headers=user_headers,
                    json={"shot_id": 999999, "duration": 5.0})
    # shot 不存在 → 404 优先
    assert r.status_code in (400, 404)

    # 构造有分镜的项目：预算耗尽后拦截小说生成
    pid2 = create_project(client, user_headers, budget=0.0001)
    r = client.post("/api/novels/generate", headers=user_headers,
                    json={"project_id": pid2, "chapter_count": 1})
    assert r.status_code == 400
    assert "预算" in r.json()["detail"]
