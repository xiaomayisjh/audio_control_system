"""Cue 列表管理器"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from src.models.cue import Cue
from src.models.cue_config import CueListConfig
from src.models.audio_track import AudioTrack


class CueManager:
    """Cue 列表管理器
    
    负责管理自动模式的播放序列，支持：
    - Cue 列表的加载和保存
    - 当前/下一个 Cue 的获取
    - 索引管理和重置
    """
    
    def __init__(self):
        """初始化 Cue 管理器"""
        self._cue_list: List[Cue] = []
        self._audio_files: List[AudioTrack] = []
        self._current_index: int = 0
        self._is_playing: bool = False
        self._config_name: str = ""
        self._config_version: str = "1.0"
    
    @property
    def cue_list(self) -> List[Cue]:
        """获取 Cue 列表（只读副本）"""
        return list(self._cue_list)
    
    @property
    def audio_files(self) -> List[AudioTrack]:
        """获取音频文件列表（只读副本）"""
        return list(self._audio_files)
    
    @property
    def current_index(self) -> int:
        """获取当前 Cue 索引"""
        return self._current_index

    @property
    def is_playing(self) -> bool:
        """获取播放状态"""
        return self._is_playing
    
    @is_playing.setter
    def is_playing(self, value: bool) -> None:
        """设置播放状态"""
        self._is_playing = value
    
    def get_cue_count(self) -> int:
        """获取 Cue 总数"""
        return len(self._cue_list)
    
    def get_current_cue(self) -> Optional[Cue]:
        """获取当前 Cue
        
        Returns:
            当前 Cue 对象，如果列表为空或索引越界则返回 None
        """
        if not self._cue_list or self._current_index >= len(self._cue_list):
            return None
        return self._cue_list[self._current_index]
    
    def get_next_cue(self) -> Optional[Cue]:
        """获取下一个 Cue
        
        Returns:
            下一个 Cue 对象，如果不存在则返回 None
        """
        next_index = self._current_index + 1
        if not self._cue_list or next_index >= len(self._cue_list):
            return None
        return self._cue_list[next_index]
    
    def get_cue_by_id(self, cue_id: str) -> Optional[Cue]:
        """根据 ID 获取 Cue
        
        Args:
            cue_id: Cue ID
            
        Returns:
            Cue 对象，不存在则返回 None
        """
        for cue in self._cue_list:
            if cue.id == cue_id:
                return cue
        return None
    
    def get_cue_by_index(self, index: int) -> Optional[Cue]:
        """根据索引获取 Cue
        
        Args:
            index: Cue 索引
            
        Returns:
            Cue 对象，索引越界则返回 None
        """
        if 0 <= index < len(self._cue_list):
            return self._cue_list[index]
        return None
    
    def advance(self) -> Optional[Cue]:
        """前进到下一个 Cue
        
        Returns:
            新的当前 Cue，如果已是最后一个则返回 None
        """
        if self._current_index < len(self._cue_list) - 1:
            self._current_index += 1
            return self.get_current_cue()
        return None
    
    def reset(self) -> None:
        """重置到第一个 Cue"""
        self._current_index = 0
        self._is_playing = False
    
    def set_index(self, index: int) -> bool:
        """设置当前 Cue 索引
        
        Args:
            index: 目标索引
            
        Returns:
            是否设置成功
        """
        if 0 <= index < len(self._cue_list):
            self._current_index = index
            return True
        return False

    def add_cue(self, cue: Cue) -> None:
        """添加 Cue 到列表末尾
        
        Args:
            cue: 要添加的 Cue 对象
        """
        self._cue_list.append(cue)
    
    def insert_cue(self, index: int, cue: Cue) -> bool:
        """在指定位置插入 Cue
        
        Args:
            index: 插入位置
            cue: 要插入的 Cue 对象
            
        Returns:
            是否插入成功
        """
        if 0 <= index <= len(self._cue_list):
            self._cue_list.insert(index, cue)
            # 如果插入位置在当前索引之前或等于当前索引，需要调整当前索引
            if index <= self._current_index and self._cue_list:
                self._current_index += 1
            return True
        return False
    
    def remove_cue(self, cue_id: str) -> bool:
        """移除指定 Cue
        
        Args:
            cue_id: 要移除的 Cue ID
            
        Returns:
            是否移除成功
        """
        for i, cue in enumerate(self._cue_list):
            if cue.id == cue_id:
                self._cue_list.pop(i)
                # 调整当前索引
                if i < self._current_index:
                    self._current_index -= 1
                elif i == self._current_index and self._current_index >= len(self._cue_list):
                    self._current_index = max(0, len(self._cue_list) - 1)
                return True
        return False
    
    def update_cue(self, cue_id: str, **kwargs) -> bool:
        """更新指定 Cue 的属性
        
        Args:
            cue_id: Cue ID
            **kwargs: 要更新的属性
            
        Returns:
            是否更新成功
        """
        for i, cue in enumerate(self._cue_list):
            if cue.id == cue_id:
                # 创建新的 Cue 对象，更新指定属性
                cue_dict = cue.to_dict()
                cue_dict.update(kwargs)
                self._cue_list[i] = Cue.from_dict(cue_dict)
                return True
        return False
    
    def move_cue(self, from_index: int, to_index: int) -> bool:
        """移动 Cue 位置（用于拖拽排序）
        
        Args:
            from_index: 原位置
            to_index: 目标位置
            
        Returns:
            是否移动成功
        """
        if not (0 <= from_index < len(self._cue_list) and 0 <= to_index < len(self._cue_list)):
            return False
        
        cue = self._cue_list.pop(from_index)
        self._cue_list.insert(to_index, cue)
        
        # 调整当前索引
        if from_index == self._current_index:
            self._current_index = to_index
        elif from_index < self._current_index <= to_index:
            self._current_index -= 1
        elif to_index <= self._current_index < from_index:
            self._current_index += 1
        
        return True
    
    def clear_cues(self) -> None:
        """清空所有 Cue"""
        self._cue_list.clear()
        self._current_index = 0
        self._is_playing = False

    def add_audio_file(self, audio: AudioTrack) -> None:
        """添加音频文件
        
        Args:
            audio: 音频轨道对象
        """
        self._audio_files.append(audio)
    
    def remove_audio_file(self, audio_id: str) -> bool:
        """移除音频文件
        
        Args:
            audio_id: 音频 ID
            
        Returns:
            是否移除成功
        """
        for i, audio in enumerate(self._audio_files):
            if audio.id == audio_id:
                self._audio_files.pop(i)
                return True
        return False
    
    def get_audio_file(self, audio_id: str) -> Optional[AudioTrack]:
        """获取音频文件
        
        Args:
            audio_id: 音频 ID
            
        Returns:
            音频轨道对象，不存在则返回 None
        """
        for audio in self._audio_files:
            if audio.id == audio_id:
                return audio
        return None
    
    def load_config(self, config_path: str) -> None:
        """从 JSON 文件加载配置
        
        Args:
            config_path: 配置文件路径
        """
        file_path = Path(config_path)
        if not file_path.exists():
            return
        
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        config = CueListConfig.from_dict(data)
        self._cue_list = config.cues
        self._audio_files = config.audio_files
        self._config_name = config.name
        self._config_version = config.version
        self._current_index = 0
        self._is_playing = False
    
    def save_config(self, config_path: str) -> None:
        """保存配置到 JSON 文件
        
        Args:
            config_path: 配置文件路径
        """
        file_path = Path(config_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        config = CueListConfig(
            version=self._config_version,
            name=self._config_name,
            created_at=datetime.now(),
            cues=self._cue_list,
            audio_files=self._audio_files
        )
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(config.to_json())
    
    def load_from_config(self, config: CueListConfig) -> None:
        """从 CueListConfig 对象加载配置
        
        Args:
            config: CueListConfig 对象
        """
        self._cue_list = list(config.cues)
        self._audio_files = list(config.audio_files)
        self._config_name = config.name
        self._config_version = config.version
        self._current_index = 0
        self._is_playing = False

    def to_config(self) -> CueListConfig:
        """导出为 CueListConfig 对象
        
        Returns:
            CueListConfig 对象
        """
        return CueListConfig(
            version=self._config_version,
            name=self._config_name,
            created_at=datetime.now(),
            cues=list(self._cue_list),
            audio_files=list(self._audio_files)
        )
    
    def set_config_name(self, name: str) -> None:
        """设置配置名称
        
        Args:
            name: 配置名称
        """
        self._config_name = name
    
    def get_config_name(self) -> str:
        """获取配置名称
        
        Returns:
            配置名称
        """
        return self._config_name
    
    def contains_cue(self, cue_id: str) -> bool:
        """检查是否包含指定 Cue
        
        Args:
            cue_id: Cue ID
            
        Returns:
            是否包含
        """
        return any(cue.id == cue_id for cue in self._cue_list)
    
    def get_cue_index(self, cue_id: str) -> int:
        """获取 Cue 的索引
        
        Args:
            cue_id: Cue ID
            
        Returns:
            Cue 索引，不存在则返回 -1
        """
        for i, cue in enumerate(self._cue_list):
            if cue.id == cue_id:
                return i
        return -1
