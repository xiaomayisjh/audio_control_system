"""播放状态数据模型"""
from dataclasses import dataclass, asdict
from typing import Optional, Literal
import json


@dataclass
class PlaybackState:
    """播放状态数据类"""
    mode: Literal["auto", "manual"]  # 播放模式
    is_playing: bool
    is_paused: bool
    current_audio_id: Optional[str]
    current_position: float
    current_cue_index: int
    bgm_volume: float
    sfx_volume: float
    in_silence: bool  # 是否在静音间隔中
    silence_remaining: float
    duration: float = 0.0  # 当前音频总时长

    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)

    def to_json(self) -> str:
        """序列化为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> "PlaybackState":
        """从字典创建实例"""
        return cls(
            mode=data["mode"],
            is_playing=data["is_playing"],
            is_paused=data["is_paused"],
            current_audio_id=data.get("current_audio_id"),
            current_position=data.get("current_position", 0.0),
            current_cue_index=data.get("current_cue_index", 0),
            bgm_volume=data.get("bgm_volume", 1.0),
            sfx_volume=data.get("sfx_volume", 1.0),
            in_silence=data.get("in_silence", False),
            silence_remaining=data.get("silence_remaining", 0.0),
            duration=data.get("duration", 0.0)
        )

    @classmethod
    def from_json(cls, json_str: str) -> "PlaybackState":
        """从 JSON 字符串反序列化"""
        return cls.from_dict(json.loads(json_str))
