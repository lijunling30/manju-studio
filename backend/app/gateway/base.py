"""网关统一接口与异常。"""
from dataclasses import dataclass, field
from typing import Any


class ProviderError(Exception):
    """厂商调用失败（网络/限流/生成翻车），由网关路由负责重试与降级。"""


@dataclass
class GenResult:
    """一次生成的统一结果。"""
    data: Any = None            # 业务结果（文本/URL/结构化数据）
    cost_info: dict = field(default_factory=dict)  # {vendor, model, tokens, duration, count, amount}
