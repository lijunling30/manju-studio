"""诊断脚本：登录 → 项目 → 剧本/分镜/关键帧/角色 → 图片 URL 可达性 + 响应耗时。"""
import time
import httpx

B = "http://127.0.0.1:8000/api"
c = httpx.Client(timeout=60, follow_redirects=True)

t0 = time.time()
r = c.post(B + "/auth/login", json={"username": "demo", "password": "123456"})
print(f"[login] {r.status_code} {time.time()-t0:.2f}s")
H = {"Authorization": f"Bearer {r.json()['access_token']}"}

t0 = time.time()
projs = c.get(B + "/projects", headers=H).json()
print(f"[projects] {time.time()-t0:.2f}s count={len(projs)}")
pid = projs[0]["id"]

for path in ["novel", "script", "characters"]:
    t0 = time.time()
    r = c.get(f"{B}/projects/{pid}/{path}", headers=H)
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    n = len(body) if isinstance(body, list) else (len(body.get("chapters", [])) if isinstance(body, dict) else "?")
    print(f"[{path}] {r.status_code} {time.time()-t0:.2f}s items={n}")

# 分镜
t0 = time.time()
shots = c.get(f"{B}/projects/{pid}/shots", headers=H).json()
print(f"[shots] {time.time()-t0:.2f}s count={len(shots) if isinstance(shots, list) else shots}")

# 关键帧：项目级抽卡列表
for ep in ["keyframes", "characters"]:
    t0 = time.time()
    r = c.get(f"{B}/projects/{pid}/{ep}", headers=H)
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else None
    print(f"[{ep} list] {r.status_code} {time.time()-t0:.2f}s type={type(body).__name__} len={len(body) if isinstance(body, list) else '?'}")

# 汇总所有含 image_url / preview_url / cover 的字段，验证可达性
img_urls = set()
def walk(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if isinstance(v, str) and ("/storage/" in v or v.startswith("http")):
                img_urls.add(v)
            else:
                walk(v)
    elif isinstance(o, list):
        for x in o:
            walk(x)
walk(projs)
for path in ["script", "characters"]:
    r = c.get(f"{B}/projects/{pid}/{path}", headers=H)
    if r.headers.get("content-type", "").startswith("application/json"):
        walk(r.json())
r = c.get(f"{B}/projects/{pid}/shots", headers=H)
if r.headers.get("content-type", "").startswith("application/json"):
    walk(r.json())
for ep in ["keyframes", "characters"]:
    r = c.get(f"{B}/projects/{pid}/{ep}", headers=H)
    if r.headers.get("content-type", "").startswith("application/json"):
        walk(r.json())

print(f"\n共发现 {len(img_urls)} 个资产 URL：")
for u in sorted(img_urls):
    t0 = time.time()
    try:
        rr = c.get(u)
        size = len(rr.content)
        print(f"  {rr.status_code} {size//1024}KB {time.time()-t0:.2f}s  {u}")
    except Exception as e:
        print(f"  ERR {e}  {u}")
