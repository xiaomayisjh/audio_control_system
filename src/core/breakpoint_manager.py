"""断点管理器 - 各音频独立存储"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from src.models.breakpoint import Breakpoint


class BreakpointManager:
    """断点管理器 - 各音频独立存储
    
    负责管理各个音频的独立断点，支持：
    - 断点的增删改查操作
    - 各音频独立存储逻辑
    - 持久化到 JSON 文件
    """
    
    def __init__(self):
        """初始化断点管理器"""
        self._breakpoints: Dict[str, List[Breakpoint]] = {}
    
    @property
    def breakpoints(self) -> Dict[str, List[Breakpoint]]:
        """获取所有断点数据（只读）"""
        return self._breakpoints.copy()
    
    def save_breakpoint(
        self, 
        audio_id: str, 
        position: float, 
        label: str = "",
        auto_saved: bool = False
    ) -> str:
        """为指定音频保存断点
        
        Args:
            audio_id: 音频 ID
            position: 播放位置（秒）
            label: 断点标签
            auto_saved: 是否为自动保存（被打断时）
            
        Returns:
            新创建的断点 ID
        """
        bp_id = str(uuid.uuid4())
        breakpoint = Breakpoint(
            id=bp_id,
            audio_id=audio_id,
            position=position,
            label=label,
            created_at=datetime.now(),
            auto_saved=auto_saved
        )

        if audio_id not in self._breakpoints:
            self._breakpoints[audio_id] = []
        
        self._breakpoints[audio_id].append(breakpoint)
        return bp_id
    
    def get_breakpoints(self, audio_id: str) -> List[Breakpoint]:
        """获取指定音频的所有断点
        
        Args:
            audio_id: 音频 ID
            
        Returns:
            该音频的断点列表（副本）
        """
        return list(self._breakpoints.get(audio_id, []))
    
    def get_breakpoint(self, audio_id: str, bp_id: str) -> Optional[Breakpoint]:
        """获取指定断点
        
        Args:
            audio_id: 音频 ID
            bp_id: 断点 ID
            
        Returns:
            断点对象，不存在则返回 None
        """
        for bp in self._breakpoints.get(audio_id, []):
            if bp.id == bp_id:
                return bp
        return None
    
    def delete_breakpoint(self, audio_id: str, bp_id: str) -> bool:
        """删除指定断点
        
        Args:
            audio_id: 音频 ID
            bp_id: 断点 ID
            
        Returns:
            是否删除成功
        """
        if audio_id not in self._breakpoints:
            return False
        
        original_len = len(self._breakpoints[audio_id])
        self._breakpoints[audio_id] = [
            bp for bp in self._breakpoints[audio_id] if bp.id != bp_id
        ]
        return len(self._breakpoints[audio_id]) < original_len
    
    def clear_audio_breakpoints(self, audio_id: str) -> None:
        """清除指定音频的所有断点
        
        Args:
            audio_id: 音频 ID
        """
        if audio_id in self._breakpoints:
            self._breakpoints[audio_id] = []
    
    def clear_selected(self, bp_ids: List[str]) -> int:
        """批量删除选中的断点
        
        Args:
            bp_ids: 要删除的断点 ID 列表
            
        Returns:
            实际删除的断点数量
        """
        bp_id_set = set(bp_ids)
        deleted_count = 0
        
        for audio_id in self._breakpoints:
            original_len = len(self._breakpoints[audio_id])
            self._breakpoints[audio_id] = [
                bp for bp in self._breakpoints[audio_id] if bp.id not in bp_id_set
            ]
            deleted_count += original_len - len(self._breakpoints[audio_id])
        
        return deleted_count

    
    def get_all_breakpoint_ids(self) -> List[str]:
        """获取所有断点的 ID 列表
        
        Returns:
            所有断点 ID 的列表
        """
        ids = []
        for breakpoints in self._breakpoints.values():
            ids.extend(bp.id for bp in breakpoints)
        return ids
    
    def load_from_file(self, path: str) -> None:
        """从 JSON 文件加载断点数据
        
        Args:
            path: JSON 文件路径
        """
        file_path = Path(path)
        if not file_path.exists():
            return
        
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        self._breakpoints.clear()
        for audio_id, bp_list in data.items():
            self._breakpoints[audio_id] = [
                Breakpoint.from_dict(bp_data) for bp_data in bp_list
            ]
    
    def save_to_file(self, path: str) -> None:
        """保存断点数据到 JSON 文件
        
        Args:
            path: JSON 文件路径
        """
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {}
        for audio_id, bp_list in self._breakpoints.items():
            data[audio_id] = [bp.to_dict() for bp in bp_list]
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def to_dict(self) -> Dict[str, List[dict]]:
        """将所有断点数据转换为字典
        
        Returns:
            断点数据字典
        """
        return {
            audio_id: [bp.to_dict() for bp in bp_list]
            for audio_id, bp_list in self._breakpoints.items()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, List[dict]]) -> "BreakpointManager":
        """从字典创建 BreakpointManager 实例
        
        Args:
            data: 断点数据字典
            
        Returns:
            BreakpointManager 实例
        """
        manager = cls()
        for audio_id, bp_list in data.items():
            manager._breakpoints[audio_id] = [
                Breakpoint.from_dict(bp_data) for bp_data in bp_list
            ]
        return manager
