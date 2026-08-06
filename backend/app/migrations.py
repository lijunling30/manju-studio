"""轻量级数据库迁移（幂等）。

SQLAlchemy 的 Base.metadata.create_all 只创建新表，不会给既有表添加新列。
本模块在启动时检查并补齐缺失列，避免老库升级后访问新字段报错。

每条迁移用 _ensure_column 包装：列已存在则跳过，否则 ALTER TABLE ADD COLUMN。
"""
import logging

from sqlalchemy import inspect, text

from .database import engine

logger = logging.getLogger("manju.migrations")


def _column_exists(table: str, column: str) -> bool:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return False
    return column in {c["name"] for c in insp.get_columns(table)}


def _ensure_column(table: str, column: str, ddl_type: str, default_expr: str = "") -> None:
    """给既有表补列。default_expr 形如 "0" / "'{}'" / "'[]'"。"""
    if _column_exists(table, column):
        return
    default_clause = f" DEFAULT {default_expr}" if default_expr else ""
    sql = f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}{default_clause}"
    logger.info("迁移：执行 %s", sql)
    with engine.begin() as conn:
        conn.execute(text(sql))


def run_migrations() -> None:
    """启动时执行所有迁移。新增迁移在此追加即可。"""
    # v1.3.0：User 增加 model_setting 字段（模型服务偏好）
    # SQLite ALTER TABLE 不支持 NOT NULL 无默认值，故带 DEFAULT '{}'
    _ensure_column("user", "model_setting", "JSON", "'{}'")
