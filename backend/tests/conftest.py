"""测试配置：独立临时库 + 快速 mock 延迟 + TestClient（含 lifespan/worker）。"""
import os
import tempfile

_tmpdir = tempfile.mkdtemp(prefix="manju_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_tmpdir, 'test.db')}"
os.environ["STORAGE_DIR"] = os.path.join(_tmpdir, "storage")
os.environ["MOCK_TEXT_DELAY"] = "0.01"
os.environ["MOCK_IMAGE_DELAY"] = "0.02"
os.environ["MOCK_VIDEO_DELAY"] = "0.05"
os.environ["GATE_TIMEOUT_SECONDS"] = "1"
os.environ["GATE_MAX_CONFIRM_ROUNDS"] = "3"

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def user_headers(client):
    import uuid
    name = f"user_{uuid.uuid4().hex[:8]}"
    r = client.post("/api/auth/register", json={"username": name, "password": "123456"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_project(client, headers, name="测试项目", budget=100.0):
    r = client.post("/api/projects", headers=headers,
                    json={"name": name, "genre": "末世", "description": "测试描述",
                          "style_id": "style_01", "style_name": "废土风",
                          "target_platform": "douyin_9_16", "budget_limit": budget})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def disable_gate(client, headers, session_id=""):
    """测试中默认关闭闸口以直通流水线（成本护栏仍强制确认）。"""
    r = client.put("/api/ai/settings/gate", headers=headers,
                   json={"global_enabled": False}, params={"session_id": session_id})
    assert r.status_code == 200, r.text


def wait_task(client, headers, url, target=("success",), timeout=30, interval=0.2):
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(url, headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        status = data["status"] if isinstance(data, dict) else data[0]["status"]
        if status in target:
            return data
        time.sleep(interval)
    raise AssertionError(f"任务超时未达到 {target}：{url}")
