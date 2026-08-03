"""确认闸口测试（5.0.1）：draft→confirm/reject/cancel、旁路、成本护栏、超时。"""
import time

from conftest import create_project, disable_gate


def _mk(client, headers, module="novel", params=None, batch=1):
    return client.post("/api/ai/requests", headers=headers,
                       json={"module": module, "project_id": None,
                             "params": params or {"chapter_count": 8}, "batch_count": batch,
                             "session_id": ""})


def test_create_draft_card(client, user_headers):
    r = _mk(client, user_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    req = body["ai_request"]
    assert req["status"] == "draft"          # 默认闸口开启 → 必须确认
    assert req["intent"]                      # AI 结构化复述
    assert req["output_desc"]
    assert req["cost_estimate"]["currency"] == "CNY"
    assert body["execute_now"] is False


def test_confirm_execute(client, user_headers):
    pid = create_project(client, user_headers)
    r = client.post("/api/ai/requests", headers=user_headers,
                    json={"module": "novel", "project_id": pid,
                          "params": {"chapter_count": 2}, "batch_count": 1, "session_id": ""})
    req_id = r.json()["ai_request"]["id"]
    r = client.post(f"/api/ai/requests/{req_id}/confirm", headers=user_headers)
    assert r.status_code == 200 and r.json()["status"] == "confirmed"
    # 确认后执行
    r = client.post(f"/api/ai/requests/{req_id}/execute", headers=user_headers)
    assert r.status_code == 200, r.text
    assert r.json()["kind"] == "novel_generate"


def test_reject_restate_rounds(client, user_headers):
    r = _mk(client, user_headers)
    req_id = r.json()["ai_request"]["id"]
    r = client.post(f"/api/ai/requests/{req_id}/reject", headers=user_headers,
                    params={"correction": "改成都市爱情题材"})
    assert r.status_code == 200
    req = r.json()
    assert req["status"] == "draft"
    assert req["confirm_round"] == 2
    assert "都市爱情" in req["intent"]
    # 达到 3 轮仍不符 → 转人工
    client.post(f"/api/ai/requests/{req_id}/reject", headers=user_headers)
    r = client.post(f"/api/ai/requests/{req_id}/reject", headers=user_headers)
    assert r.json()["status"] == "cancelled"


def test_cancel_zero_cost(client, user_headers):
    r = _mk(client, user_headers)
    req_id = r.json()["ai_request"]["id"]
    r = client.post(f"/api/ai/requests/{req_id}/cancel", headers=user_headers)
    assert r.json()["status"] == "cancelled"


def test_gate_bypass_when_disabled(client, user_headers):
    disable_gate(client, user_headers, session_id="s1")
    pid = create_project(client, user_headers)
    r = client.post("/api/ai/requests", headers=user_headers,
                    json={"module": "novel", "project_id": pid,
                          "params": {"chapter_count": 2}, "batch_count": 1,
                          "session_id": "s1"})
    body = r.json()
    assert body["ai_request"]["status"] == "bypassed"
    assert body["execute_now"] is True
    assert body["dispatch"]["kind"] == "novel_generate"


def test_high_cost_guardrail_forces_confirm(client, user_headers):
    """即使全局关闭闸口，高成本（≥50 元）仍强制确认（5.0.1 成本护栏）。"""
    disable_gate(client, user_headers, session_id="s2")
    # 视频 60 秒 → 60 * 1.2 = 72 元 > 50
    r = client.post("/api/ai/requests", headers=user_headers,
                    json={"module": "video", "project_id": None,
                          "params": {"shot_id": 1, "duration": 60, "vendor": "vidu_q3"},
                          "batch_count": 1, "session_id": "s2"})
    body = r.json()
    assert body["ai_request"]["status"] == "draft"
    assert body["execute_now"] is False


def test_batch_guardrail_forces_confirm(client, user_headers):
    disable_gate(client, user_headers, session_id="s3")
    r = client.post("/api/ai/requests", headers=user_headers,
                    json={"module": "shot", "project_id": None,
                          "params": {"shot_count": 25}, "batch_count": 25, "session_id": "s3"})
    assert r.json()["ai_request"]["status"] == "draft"


def test_timeout_auto_cancel(client, user_headers):
    r = _mk(client, user_headers)
    req_id = r.json()["ai_request"]["id"]
    # worker 每 0.5s 清扫一次；GATE_TIMEOUT_SECONDS=1
    deadline = time.time() + 6
    while time.time() < deadline:
        r = client.get(f"/api/ai/requests/{req_id}", headers=user_headers)
        if r.json()["status"] == "timeout":
            return
        time.sleep(0.3)
    raise AssertionError("确认闸口超时未自动取消")
