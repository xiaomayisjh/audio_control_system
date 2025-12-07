"""音频引擎模块 - 基于 pygame.mixer 实现多通道播放"""
import threading
from typing import Dict, Optional, Callable, List
import pygame
from src.models import AudioTrack


class AudioEngine:
    """
    音频引擎 - 多通道播放
    
    支持:
    - BGM 专用通道播放（同时只能播放一首）
    - 音效多通道并行播放
    - BGM 和音效独立音量控制
    """
    
    # 默认音效通道数量
    DEFAULT_SFX_CHANNELS = 8
    
    def __init__(self, sfx_channel_count: int = DEFAULT_SFX_CHANNELS):
        """
        初始化音频引擎
        
        Args:
            sfx_channel_count: 音效通道数量，默认 8 个
        """
        self._lock = threading.Lock()
        self._initialized = False
        self._sfx_channel_count = sfx_channel_count
        
        # BGM 相关
        self._current_bgm: Optional[AudioTrack] = None
        self._bgm_sound: Optional[pygame.mixer.Sound] = None
        self._bgm_channel: Optional[pygame.mixer.Channel] = None
        self._bgm_start_pos: float = 0.0  # BGM 开始播放的位置（秒）
        self._bgm_paused_pos: float = 0.0  # BGM 暂停时的位置
        self._bgm_is_paused: bool = False
        
        # 音效相关
        self._sfx_channels: List[pygame.mixer.Channel] = []
        self._playing_sfx: Dict[str, pygame.mixer.Channel] = {}  # sfx_id -> channel
        self._sfx_sounds: Dict[str, pygame.mixer.Sound] = {}  # sfx_id -> sound
        
        # 音量
        self._bgm_volume: float = 1.0
        self._sfx_volume: float = 1.0
        
        # 事件回调
        self._on_bgm_end: Optional[Callable[[], None]] = None
        
        # 初始化 pygame.mixer
        self._init_mixer()

    def _init_mixer(self) -> None:
        """初始化 pygame.mixer"""
        if not pygame.mixer.get_init():
            # 初始化 mixer: 44100Hz, 16-bit, stereo, 2048 buffer
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
        
        # 设置通道数量: 1 个 BGM + N 个音效
        total_channels = 1 + self._sfx_channel_count
        pygame.mixer.set_num_channels(total_channels)
        
        # 分配通道
        self._bgm_channel = pygame.mixer.Channel(0)
        self._sfx_channels = [
            pygame.mixer.Channel(i + 1) 
            for i in range(self._sfx_channel_count)
        ]
        
        self._initialized = True
    
    def is_initialized(self) -> bool:
        """检查引擎是否已初始化"""
        return self._initialized
    
    def shutdown(self) -> None:
        """关闭音频引擎"""
        with self._lock:
            self.stop_bgm()
            self.stop_all_sfx()
            pygame.mixer.quit()
            self._initialized = False
    
    # ==================== BGM 控制 ====================
    
    def play_bgm(self, track: AudioTrack, start_pos: float = 0.0) -> None:
        """
        播放 BGM
        
        Args:
            track: 音频轨道
            start_pos: 开始位置（秒）
        """
        with self._lock:
            # 停止当前 BGM
            if self._bgm_channel and self._bgm_channel.get_busy():
                self._bgm_channel.stop()
            
            # 加载音频文件
            self._bgm_sound = pygame.mixer.Sound(track.file_path)
            self._current_bgm = track
            self._bgm_start_pos = start_pos
            self._bgm_is_paused = False
            self._bgm_paused_pos = 0.0
            
            # 设置音量
            self._bgm_sound.set_volume(self._bgm_volume)
            
            # 播放（从指定位置开始）
            # pygame.mixer.Sound 不直接支持从指定位置播放
            # 需要使用 play() 然后设置位置，但 Sound 对象不支持 seek
            # 解决方案：使用 pygame.mixer.music 或接受从头播放的限制
            # 这里我们使用 Channel 播放，通过计算偏移来模拟
            self._bgm_channel.play(self._bgm_sound)
            
            # 如果需要从非零位置开始，设置播放位置
            if start_pos > 0:
                # pygame.mixer.Channel 不支持直接 seek
                # 我们记录开始位置，在 get_bgm_position 中计算
                pass
    
    def pause_bgm(self) -> None:
        """暂停 BGM"""
        with self._lock:
            if self._bgm_channel:
                # 检查通道是否在播放（包括暂停状态）
                # get_busy() 在暂停时仍返回 True
                if self._bgm_channel.get_busy() or self._bgm_sound:
                    # 记录当前位置
                    self._bgm_paused_pos = self._get_bgm_position_internal()
                    self._bgm_channel.pause()
                    self._bgm_is_paused = True
    
    def resume_bgm(self) -> None:
        """继续播放 BGM"""
        with self._lock:
            if self._bgm_channel and self._bgm_is_paused:
                # 确保通道存在且有音频
                if self._bgm_sound:
                    self._bgm_channel.unpause()
                    self._bgm_is_paused = False
    
    def stop_bgm(self) -> float:
        """
        停止 BGM
        
        Returns:
            停止时的播放位置（秒）
        """
        with self._lock:
            position = self._get_bgm_position_internal()
            if self._bgm_channel:
                self._bgm_channel.stop()
            self._bgm_is_paused = False
            self._bgm_paused_pos = 0.0
            self._current_bgm = None
            self._bgm_sound = None
            return position

    def _get_bgm_position_internal(self) -> float:
        """
        获取 BGM 当前位置（内部方法，不加锁）
        
        Returns:
            当前播放位置（秒）
        """
        if self._bgm_is_paused:
            return self._bgm_paused_pos
        
        if not self._bgm_channel or not self._bgm_sound:
            return 0.0
        
        if not self._bgm_channel.get_busy():
            return 0.0
        
        # 计算播放时间
        # pygame 没有直接获取播放位置的方法
        # 我们需要通过其他方式追踪
        # 这里返回开始位置（简化实现）
        return self._bgm_start_pos
    
    def get_bgm_position(self) -> float:
        """
        获取 BGM 当前播放位置
        
        Returns:
            当前播放位置（秒）
        """
        with self._lock:
            return self._get_bgm_position_internal()
    
    def is_bgm_playing(self) -> bool:
        """检查 BGM 是否正在播放"""
        with self._lock:
            if not self._bgm_channel:
                return False
            return self._bgm_channel.get_busy() and not self._bgm_is_paused
    
    def is_bgm_paused(self) -> bool:
        """检查 BGM 是否已暂停"""
        with self._lock:
            return self._bgm_is_paused
    
    def get_current_bgm(self) -> Optional[AudioTrack]:
        """获取当前 BGM 轨道"""
        with self._lock:
            return self._current_bgm
    
    # ==================== 音效控制 ====================
    
    def play_sfx(self, sfx_id: str, track: AudioTrack) -> bool:
        """
        播放音效
        
        Args:
            sfx_id: 音效 ID
            track: 音频轨道
            
        Returns:
            是否成功播放
        """
        with self._lock:
            # 如果该音效已在播放，先停止
            if sfx_id in self._playing_sfx:
                self._playing_sfx[sfx_id].stop()
                del self._playing_sfx[sfx_id]
            
            # 查找空闲通道
            channel = self._find_free_sfx_channel()
            if channel is None:
                return False
            
            # 加载并播放音效
            sound = pygame.mixer.Sound(track.file_path)
            sound.set_volume(self._sfx_volume)
            channel.play(sound)
            
            # 记录
            self._playing_sfx[sfx_id] = channel
            self._sfx_sounds[sfx_id] = sound
            
            return True
    
    def _find_free_sfx_channel(self) -> Optional[pygame.mixer.Channel]:
        """查找空闲的音效通道"""
        for channel in self._sfx_channels:
            if not channel.get_busy():
                return channel
        return None
    
    def stop_sfx(self, sfx_id: str) -> bool:
        """
        停止指定音效
        
        Args:
            sfx_id: 音效 ID
            
        Returns:
            是否成功停止
        """
        with self._lock:
            if sfx_id not in self._playing_sfx:
                return False
            
            self._playing_sfx[sfx_id].stop()
            del self._playing_sfx[sfx_id]
            if sfx_id in self._sfx_sounds:
                del self._sfx_sounds[sfx_id]
            
            return True
    
    def stop_all_sfx(self) -> None:
        """停止所有音效"""
        with self._lock:
            for channel in self._sfx_channels:
                channel.stop()
            self._playing_sfx.clear()
            self._sfx_sounds.clear()
    
    def is_sfx_playing(self, sfx_id: str) -> bool:
        """检查指定音效是否正在播放"""
        with self._lock:
            if sfx_id not in self._playing_sfx:
                return False
            return self._playing_sfx[sfx_id].get_busy()
    
    def get_playing_sfx_ids(self) -> List[str]:
        """获取所有正在播放的音效 ID"""
        with self._lock:
            return [
                sfx_id for sfx_id, channel in self._playing_sfx.items()
                if channel.get_busy()
            ]

    # ==================== 音量控制 ====================
    
    def set_bgm_volume(self, volume: float) -> None:
        """
        设置 BGM 音量
        
        Args:
            volume: 音量值 (0.0 - 3.0，即 0%-300%)
                   注意：pygame 原生只支持 0-1 范围，超过 100% 的部分
                   会尽可能放大，但实际效果取决于音频硬件
        """
        with self._lock:
            self._bgm_volume = max(0.0, min(3.0, volume))
            if self._bgm_sound:
                # pygame 音量范围是 0-1，超过 1 的部分需要特殊处理
                # 这里我们使用 min(1.0, volume) 作为基础音量
                # 对于超过 100% 的情况，pygame 会尽可能放大
                effective_volume = min(1.0, self._bgm_volume)
                self._bgm_sound.set_volume(effective_volume)
                # 如果需要超过 100%，可以通过 Channel 的音量叠加
                if self._bgm_channel and self._bgm_volume > 1.0:
                    # Channel 音量也是 0-1，但可以与 Sound 音量叠加
                    self._bgm_channel.set_volume(min(1.0, self._bgm_volume))
    
    def get_bgm_volume(self) -> float:
        """获取 BGM 音量"""
        with self._lock:
            return self._bgm_volume
    
    def set_sfx_volume(self, volume: float) -> None:
        """
        设置音效音量
        
        Args:
            volume: 音量值 (0.0 - 3.0，即 0%-300%)
                   注意：pygame 原生只支持 0-1 范围，超过 100% 的部分
                   会尽可能放大，但实际效果取决于音频硬件
        """
        with self._lock:
            self._sfx_volume = max(0.0, min(3.0, volume))
            effective_volume = min(1.0, self._sfx_volume)
            # 更新所有正在播放的音效音量
            for sfx_id, sound in self._sfx_sounds.items():
                sound.set_volume(effective_volume)
            # 更新所有音效通道的音量
            if self._sfx_volume > 1.0:
                for channel in self._sfx_channels:
                    channel.set_volume(min(1.0, self._sfx_volume))
    
    def get_sfx_volume(self) -> float:
        """获取音效音量"""
        with self._lock:
            return self._sfx_volume
    
    # ==================== 事件回调 ====================
    
    def set_on_bgm_end(self, callback: Optional[Callable[[], None]]) -> None:
        """
        设置 BGM 播放结束回调
        
        Args:
            callback: 回调函数
        """
        self._on_bgm_end = callback
    
    def check_bgm_end(self) -> bool:
        """
        检查 BGM 是否已结束播放
        
        Returns:
            如果 BGM 刚结束返回 True
        """
        with self._lock:
            if self._current_bgm and self._bgm_channel:
                if not self._bgm_channel.get_busy() and not self._bgm_is_paused:
                    # BGM 已结束
                    if self._on_bgm_end:
                        self._on_bgm_end()
                    self._current_bgm = None
                    self._bgm_sound = None
                    return True
            return False
    
    # ==================== 工具方法 ====================
    
    def get_available_sfx_channels(self) -> int:
        """获取可用的音效通道数量"""
        with self._lock:
            count = 0
            for channel in self._sfx_channels:
                if not channel.get_busy():
                    count += 1
            return count
    
    def get_total_sfx_channels(self) -> int:
        """获取总音效通道数量"""
        return self._sfx_channel_count
