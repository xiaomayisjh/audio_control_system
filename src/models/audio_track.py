"""音频轨道数据模型"""
from dataclasses import dataclass, asdict
from typing import Literal
import json


@dataclass
class AudioTrack:
    """音频轨道数据类"""
    id: str
    file_path: str
    duration: float  # 总时长（秒）
    title: str
    track_type: Literal["bgm", "sfx"]  # 轨道类型

    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)

    def to_json(self) -> str:
        """序列化为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> "AudioTrack":
        """从字典创建实例"""
        return cls(
            id=data["id"],
            file_path=data["file_path"],
            duration=data["duration"],
            title=data["title"],
            track_type=data["track_type"]
        )

    @classmethod
    def from_json(cls, json_str: str) -> "AudioTrack":
        """从 JSON 字符串反序列化"""
        return cls.from_dict(json.loads(json_str))
