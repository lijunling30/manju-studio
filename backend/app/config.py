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

    # ============ 真实 AI 厂商配置（MOCK_MODE=false 时启用） ============
    # 文本：DeepSeek 官方 API（OpenAI 兼容接口）
    # 模型：deepseek-v4-flash（便宜）/ deepseek-v4-pro（更强）
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-v4-flash"
    # 图像 + 视频 + TTS：通义万相 / HappyHorse / Qwen-Audio（阿里云百炼 DashScope）
    # 注意：Token Plan (sk-sp-) 必须用 token-plan.cn-beijing.maas.aliyuncs.com 域名
    # 套餐内：
    #   图像：wan2.7-image / wan2.7-image-pro（同步 multimodal-generation 接口）
    #   视频：happyhorse-1.1-i2v / happyhorse-1.1-t2v / happyhorse-1.1-r2v（异步 video-synthesis）
    #   TTS ：qwen-audio-3.0-tts-plus（同步 SpeechSynthesizer 接口，响应为音频二进制流）
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_BASE_URL: str = "https://token-plan.cn-beijing.maas.aliyuncs.com"
    DASHSCOPE_IMAGE_MODEL: str = "wan2.7-image-pro"     # 万相 2.7 文生图
    DASHSCOPE_VIDEO_MODEL: str = "happyhorse-1.1-i2v"   # HappyHorse 1.1 图生视频

    # 真实调用超时与轮询节奏（秒）
    AI_HTTP_TIMEOUT: float = 120.0        # 单次 HTTP 请求超时（文本生成长时响应）
    AI_TASK_POLL_INTERVAL: float = 3.0    # 异步任务（图像/视频）轮询间隔
    AI_IMAGE_TASK_TIMEOUT: float = 300.0  # 单张图任务超时（5 分钟）
    AI_VIDEO_TASK_TIMEOUT: float = 1800.0  # 单条视频任务超时（30 分钟）

    # ============ TTS 语音合成（套餐内 qwen-audio-3.0-tts-plus） ============
    # 同步 HTTP 接口：POST /api/v1/services/audio/tts/SpeechSynthesizer
    # 响应为音频二进制流（非 JSON），直接保存为文件
    DASHSCOPE_TTS_MODEL: str = "qwen-audio-3.0-tts-plus"
    DASHSCOPE_TTS_VOICE: str = "longanhuan_v3.6"   # 套餐默认音色（男声）；女声用 longxiaochun_v3.6
    DASHSCOPE_TTS_FORMAT: str = "mp3"            # mp3 / wav / pcm / opus

    # 文本生成内容质量（用户反馈「内容非常少」——默认每章 2500 字）
    NOVEL_CHAPTER_WORDS: int = 2500       # 目标每章字数（真实 LLM 按此提示）
    SCRIPT_SCENE_WORDS: int = 400         # 目标每场戏描述字数

    # 图生视频要求关键帧为「公网可访问」URL；部署后请配置为本机公网地址或 OSS 域名
    STORAGE_PUBLIC_BASE: str = ""

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


# ============ 模型目录（供前端"模型服务设置"展示可选模型） ============
# 每个模块列出套餐内可用的模型；provider 字段标识走哪个 API 网关
MODEL_CATALOG: dict = {
    "text": {
        "label": "文本模型（小说/剧本/分镜）",
        "models": [
            {"id": "deepseek-v4-flash", "label": "DeepSeek V4 Flash（便宜·推荐）", "provider": "deepseek"},
            {"id": "deepseek-v4-pro", "label": "DeepSeek V4 Pro（更强）", "provider": "deepseek"},
            {"id": "qwen3.8-max", "label": "Qwen3.8 Max（阿里云·视觉理解）", "provider": "dashscope"},
            {"id": "qwen3.7-plus", "label": "Qwen3.7 Plus（阿里云）", "provider": "dashscope"},
            {"id": "glm-5.2", "label": "GLM-5.2（智谱·阿里云）", "provider": "dashscope"},
        ],
    },
    "image": {
        "label": "图像模型（角色三视图/表情/关键帧）",
        "models": [
            {"id": "wan2.7-image-pro", "label": "万相 2.7 Pro（高质量·推荐）", "provider": "dashscope"},
            {"id": "wan2.7-image", "label": "万相 2.7（快速）", "provider": "dashscope"},
        ],
    },
    "video": {
        "label": "视频模型",
        "models": [
            {"id": "happyhorse-1.1-i2v", "label": "HappyHorse 1.1 图生视频（推荐）", "provider": "dashscope"},
            {"id": "happyhorse-1.1-t2v", "label": "HappyHorse 1.1 文生视频", "provider": "dashscope"},
            {"id": "happyhorse-1.1-r2v", "label": "HappyHorse 1.1 参考生视频（角色一致性）", "provider": "dashscope"},
        ],
    },
    "tts": {
        "label": "语音合成模型",
        "models": [
            {"id": "qwen-audio-3.0-tts-plus", "label": "Qwen-Audio 3.0 TTS Plus", "provider": "dashscope"},
        ],
    },
    "tts_voice": {
        "label": "TTS 音色",
        "models": [
            {"id": "longanhuan_v3.6", "label": "龙安欢（男声·套餐唯一可用）", "provider": "dashscope"},
        ],
    },
}

# .env 中的默认模型（前端展示"系统默认"标签用）
DEFAULT_MODELS: dict = {
    "text": "deepseek-v4-flash",
    "image": "wan2.7-image-pro",
    "video": "happyhorse-1.1-i2v",
    "tts": "qwen-audio-3.0-tts-plus",
    "tts_voice": "longanhuan_v3.6",
}


settings = Settings()
