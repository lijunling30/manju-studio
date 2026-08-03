"""演示数据脚本：创建 demo 账号与一个「端到端已跑通」的示例项目。

用法：cd backend && python scripts/seed_demo.py
账号：demo / 123456
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base, SessionLocal, engine
from app.gateway.router import gateway
from app.models import (Character, CharacterLibrary, Novel, Project, Script,
                        Shot, User)
from app.security import hash_password

GENRE = "末世"
SETTING = "丧尸横行的末日废土，人类在残破城市中争夺生存资源"
PROTAGONIST = "陈默"
CHAPTER_COUNT = 8


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "demo").first()
        if not user:
            user = User(username="demo", phone="13800000000",
                        password_hash=hash_password("123456"),
                        gate_setting={"global_enabled": True, "modules_disabled": [],
                                      "high_cost_threshold": 50.0, "batch_threshold": 20})
            db.add(user)
            db.flush()
        project = db.query(Project).filter(Project.name == "我在末世开超市").first()
        if not project:
            project = Project(user_id=user.id, name="我在末世开超市", genre=GENRE,
                              description="末世废土中，陈默靠一间破旧超市与聪明头脑活下去的故事。",
                              style_id="manju_default_01", style_name="漫镜·末世废土风",
                              target_platform="douyin_9_16", budget_limit=200.0,
                              ip_license={"source": "原创", "authorized": True})
            db.add(project)
            db.flush()
        # 人物子库 + 角色
        lib = db.query(CharacterLibrary).filter(CharacterLibrary.user_id == user.id).first()
        if not lib:
            lib = CharacterLibrary(user_id=user.id, name=f"《{project.name}》人物库",
                                   desc="主角与主要配角", project_ids=[project.id])
            db.add(lib)
            db.flush()
        seed = random.Random(project.id).randint(0, 10 ** 9)
        existing = {c.name: c for c in db.query(Character).filter(Character.library_id == lib.id).all()}
        for name, appearance, personality in [
            (PROTAGONIST, "短发、轮廓硬朗、总是穿着深色冲锋衣", "冷静果敢，善于在绝境中寻找生机"),
            ("苏晴", "长发、白大褂、医学出身的药剂师", "外冷内热，是队伍里的定心丸"),
            ("老周", "络腮胡、彪形大汉", "重情重义，关键时刻靠得住"),
        ]:
            if name not in existing:
                c = Character(library_id=lib.id, user_id=user.id, name=name,
                              desc=f"《{project.name}》角色", appearance=appearance,
                              personality=personality, voice_id="doubao_voice_1")
                db.add(c)
                db.flush()
                c.ref_images = [gateway.character_ref(c.name, c.appearance, seed + c.id)
                                for _ in range(3)]
                c.expression_set = [gateway.expression(c.name, e, seed + c.id + i)
                                    for i, e in enumerate(["喜", "怒", "哀", "乐"])]
                existing[name] = c
        # 小说 → 剧本 → 分镜（全链路预生成）
        novel = db.query(Novel).filter(Novel.project_id == project.id).first()
        if not novel:
            novel = Novel(project_id=project.id, title=f"《{project.name}》", genre=GENRE,
                          setting={"desc": SETTING, "style": project.style_name}, status="completed")
            db.add(novel)
            db.flush()
            data = gateway.generate_novel(GENRE, SETTING, PROTAGONIST, CHAPTER_COUNT, seed)
            novel.characters = data["characters"]
            novel.outline = data["outline"]
            novel.chapters = data["chapters"]
        script = db.query(Script).filter(Script.project_id == project.id).first()
        if not script:
            sdata = gateway.generate_script(novel.title, novel.chapters, seed + 1)
            script = Script(project_id=project.id, novel_id=novel.id,
                            title=f"{novel.title} · 剧本", scenes=sdata["scenes"],
                            emotion_curve=sdata["emotion_curve"], status="completed")
            db.add(script)
            db.flush()
        if not db.query(Shot).filter(Shot.project_id == project.id).first():
            names = [c.name for c in db.query(Character).filter(Character.library_id == lib.id).all()]
            cids = {c.name: c.id for c in db.query(Character).filter(Character.library_id == lib.id).all()}
            sdata = gateway.generate_shots(script.scenes, 9, project.style_id, names, seed + 2)
            for s in sdata["shots"]:
                prompt = s["prompt_zh"]
                for n, cid in cids.items():
                    prompt = prompt.replace(n, f"[CHAR:{cid}]{n}")
                db.add(Shot(project_id=project.id, script_id=script.id,
                            shot_no=s["shot_no"], scene_no=s["scene_no"],
                            shot_type=s["shot_type"], camera_move=s["camera_move"],
                            duration=s["duration"], prompt_zh=prompt,
                            char_ref_ids=list(cids.values()), style_id=project.style_id,
                            dialogue=s["dialogue"], narration=s["narration"],
                            transition=s["transition"], order_index=s["shot_no"],
                            status="待生成"))
        db.commit()
        print("✅ 演示数据就绪：账号 demo/123456，项目《我在末世开超市》")
        print(f"   角色：{', '.join(existing)} | 章节：{len(novel.chapters)} | 分镜：{db.query(Shot).filter(Shot.project_id == project.id).count()}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
