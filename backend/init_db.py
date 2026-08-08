"""数据库初始化脚本：建表 + 迁移 + 创建资产目录。"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import Base, engine
from app.models import *  # noqa: F401,F403  确保所有模型被导入
from app.migrations import run_migrations
from app.storage import ensure_dirs

Base.metadata.create_all(bind=engine)
run_migrations()
ensure_dirs()
print("DB_OK")
