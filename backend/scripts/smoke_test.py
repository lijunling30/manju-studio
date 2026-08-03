"""联调冒烟测试：登录 → 项目 → 闸口 → 小说生成（bypassed）→ 流程。"""
import time

import httpx

B = "http://127.0.0.1:8000/api"
c = httpx.Client(timeout=30)
H = {}


def check(name, cond, extra=""):
    print(("✅" if cond else "❌"), name, extra)
    if not cond:
        raise SystemExit(1)


r = c.get("http://127.0.0.1:8000/api/health")
check("health", r.status_code == 200, str(r.json()))

r = c.post(B + "/auth/login", json={"username": "demo", "password": "123456"})
check("login", r.status_code == 200)
H["Authorization"] = f"Bearer {r.json()['access_token']}"

projs = c.get(B + "/projects", headers=H).json()
check("项目列表", len(projs) >= 1, projs[0]["name"])
pid = projs[0]["id"]

flow = c.get(f"{B}/projects/{pid}/flow", headers=H).json()
check("9 步流程", len(flow["steps"]) == 9, "done=" + str(sum(1 for s in flow["steps"] if s["status"] == "done")))

# 会话级关闭闸口 → novel 直接 bypassed 派发
c.put(B + "/ai/settings/gate", headers=H, json={"session_disabled": True},
      params={"session_id": "smoke"})
r = c.post(B + "/ai/requests", headers=H, json={
    "module": "novel", "project_id": pid,
    "params": {"chapter_count": 2, "genre": "末世", "setting": "废土", "protagonist": "陈默"},
    "batch_count": 1, "session_id": "smoke"})
body = r.json()
check("novel bypassed", body["ai_request"]["status"] == "bypassed", body["ai_request"]["intent"][:40])

n = None
for _ in range(20):
    r = c.get(f"{B}/projects/{pid}/novel", headers=H)
    if r.status_code == 200 and r.json().get("status") == "completed":
        n = r.json()
        break
    time.sleep(1)
check("小说生成完成", n is not None and n["status"] == "completed", f"章节 {len(n['chapters'])}")

flow = c.get(f"{B}/projects/{pid}/flow", headers=H).json()
novel_step = next(s for s in flow["steps"] if s["key"] == "novel")
check("流程 novel=done", novel_step["status"] == "done")

print("冒烟测试全部通过 ✔")
