"""应用配置：通过环境变量 / .env 覆盖，默认开箱即用（SQLite + Mock 网关）。"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "漫镜工场 ManJu Studio API"
    API_PREFIX: str = "/api"
    DEBUG: bool = True

    # 数据库：默认 SQLite 文件（便携、零依赖）；生产切换 PostgreSQL 仅需改 DATABASE_URL
    DATABASE_URL: str = f"sqlite:///{(BASE_DIR / 'manju.db').as_posix()}"

    # 生成资产存储目录（图片/视频/音频），由 FastAPI StaticFiles 对外服务
    STORAGE_DIR: Path = BASE_DIR / "storage"

    # 鉴权
    JWT_SECRET: str = "manju-dev-secret-change-me-in-production-2026"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7

    # 确认闸口（PRD 5.0.1 / A-4）
    GATE_TIMEOUT_SECONDS: int = 60           # 超时自动取消，不产生费用
    GATE_HIGH_COST_THRESHOLD: float = 50.0   # 单次 ≥50 元强制确认（即使闸口关闭）
    GATE_BATCH_THRESHOLD: int = 20           # 批量 ≥20 镜头强制确认
    GATE_MAX_CONFIRM_ROUNDS: int = 3         # 修改复述最多 3 轮，仍不符转人工

    # AI 模型网关（L4）：MOCK_MODE=true 时所有厂商为模拟实现（全流程可演示）
    MOCK_MODE: bool = True
    # 视频厂商优先级（主 → 备），主失败自动降级到下一个
    VENDOR_PRIORITY_VIDEO: str = "vidu_q3,seedance_2_0,kling_2_0"
    VENDOR_PRIORITY_IMAGE: str = "wanxiang,jimeng"
    VENDOR_PRIORITY_TEXT: str = "deepseek_v3,qwen_max"
    VENDOR_PRIORITY_TTS: str = "doubao_tts,cosyvoice"
    VENDOR_PRIORITY_MODERATION: str = "aliyun_sec"

    # 任务模拟耗时（秒）—— mock 模式下控制流水线演示节奏
    MOCK_TEXT_DELAY: float = 1.5
    MOCK_IMAGE_DELAY: float = 3.0
    MOCK_VIDEO_DELAY: float = 8.0
    MOCK_AUDIO_DELAY: float = 2.0

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def video_vendors(self) -> list[str]:
        return [v.strip() for v in self.VENDOR_PRIORITY_VIDEO.split(",") if v.strip()]

    @property
    def image_vendors(self) -> list[str]:
        return [v.strip() for v in self.VENDOR_PRIORITY_IMAGE.split(",") if v.strip()]

    @property
    def text_vendors(self) -> list[str]:
        return [v.strip() for v in self.VENDOR_PRIORITY_TEXT.split(",") if v.strip()]


settings = Settings()
