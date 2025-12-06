"""断点数据模型"""
from dataclasses import dataclass, asdict
from datetime import datetime
import json


@dataclass
class Breakpoint:
    """断点数据类"""
    id: str
    audio_id: str
    position: float  # 位置（秒）
    label: str
    created_at: datetime
    auto_saved: bool  # 是否为自动保存（被打断时）

    def to_dict(self) -> dict:
        """转换为字典"""
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data

    def to_json(self) -> str:
        """序列化为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> "Breakpoint":
        """从字典创建实例"""
        created_at = data["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        return cls(
            id=data["id"],
            audio_id=data["audio_id"],
            position=data["position"],
            label=data.get("label", ""),
            created_at=created_at,
            auto_saved=data.get("auto_saved", False)
        )

    @classmethod
    def from_json(cls, json_str: str) -> "Breakpoint":
        """从 JSON 字符串反序列化"""
        return cls.from_dict(json.loads(json_str))
