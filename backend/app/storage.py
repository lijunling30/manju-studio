"""资产存储：生成文件写入 storage/ 目录，经 /storage 静态路由对外访问。"""
import uuid
from pathlib import Path

from .config import settings


def ensure_dirs() -> None:
    for sub in ("images", "videos", "audio", "reports", "frames"):
        (settings.STORAGE_DIR / sub).mkdir(parents=True, exist_ok=True)


def save_bytes(data: bytes, subdir: str, ext: str) -> str:
    """返回相对 URL 路径（如 /storage/images/xxx.png）。"""
    ensure_dirs()
    filename = f"{uuid.uuid4().hex}{ext}"
    (settings.STORAGE_DIR / subdir / filename).write_bytes(data)
    return f"/storage/{subdir}/{filename}"


def save_text(text: str, subdir: str, ext: str = ".txt") -> str:
    return save_bytes(text.encode("utf-8"), subdir, ext)


def abs_path(rel_url: str) -> Path:
    """将 /storage/... 相对 URL 转为磁盘绝对路径。"""
    return settings.STORAGE_DIR / rel_url.replace("/storage/", "")
