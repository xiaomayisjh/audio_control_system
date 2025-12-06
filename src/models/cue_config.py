"""Cue 列表配置数据模型"""
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List
import json

from .cue import Cue
from .audio_track import AudioTrack


@dataclass
class CueListConfig:
    """Cue 列表配置数据类"""
    version: str
    name: str
    created_at: datetime
    cues: List[Cue]
    audio_files: List[AudioTrack]

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "version": self.version,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "cues": [cue.to_dict() for cue in self.cues],
            "audio_files": [track.to_dict() for track in self.audio_files]
        }

    def to_json(self) -> str:
        """序列化为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "CueListConfig":
        """从字典创建实例"""
        created_at = data["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        return cls(
            version=data["version"],
            name=data["name"],
            created_at=created_at,
            cues=[Cue.from_dict(c) for c in data.get("cues", [])],
            audio_files=[AudioTrack.from_dict(a) for a in data.get("audio_files", [])]
        )

    @classmethod
    def from_json(cls, json_str: str) -> "CueListConfig":
        """从 JSON 字符串反序列化"""
        return cls.from_dict(json.loads(json_str))
