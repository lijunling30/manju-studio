"""查询数据库关键表数据量。"""
import sqlite3

c = sqlite3.connect("manju.db")
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
print("表:", tables)

for t in tables:
    try:
        n = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {n} 行")
    except Exception as e:
        print(f"  {t}: ERR {e}")

# 角色图片
print("\n角色 ref_images/expression_set:")
for r in c.execute("SELECT id, name, length(ref_images), length(expression_set) FROM character"):
    print("  ", r)
# 关键帧
print("关键帧:")
for r in c.execute("SELECT id, shot_id, image_url FROM keyframe"):
    print("  ", r)
# 脚本
print("剧本:")
for r in c.execute("SELECT id, project_id, title, status, length(scenes) FROM script"):
    print("  ", r)
