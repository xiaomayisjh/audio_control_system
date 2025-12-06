"""Cue 播放提示数据模型"""
from dataclasses import dataclass, asdict
from typing import Optional
import json


@dataclass
class Cue:
    """Cue 播放提示数据类"""
    id: str
    audio_id: str
    start_time: float  # 入点（秒）
    end_time: Optional[float]  # 出点（秒），None 表示播放到结束
    silence_before: float  # 前置静音（秒）
    silence_after: float  # 后置静音（秒）
    volume: float  # 0.0 - 1.0
    label: str  # 显示标签

    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)

    def to_json(self) -> str:
        """序列化为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> "Cue":
        """从字典创建实例"""
        return cls(
            id=data["id"],
            audio_id=data["audio_id"],
            start_time=data["start_time"],
            end_time=data.get("end_time"),
            silence_before=data.get("silence_before", 0.0),
            silence_after=data.get("silence_after", 0.0),
            volume=data.get("volume", 1.0),
            label=data.get("label", "")
        )

    @classmethod
    def from_json(cls, json_str: str) -> "Cue":
        """从 JSON 字符串反序列化"""
        return cls.from_dict(json.loads(json_str))
