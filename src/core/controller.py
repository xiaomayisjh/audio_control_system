"""核心控制器模块 - 协调所有播放控制操作"""
import asyncio
import threading
import time
from enum import Enum
from typing import Callable, Dict, List, Optional, Any

from src.core.audio_engine import AudioEngine
from src.core.cue_manager import CueManager
from src.core.breakpoint_manager import BreakpointManager
from src.models.playback_state import PlaybackState
from src.models.audio_track import AudioTrack
from src.models.cue import Cue


class PlayMode(Enum):
    """播放模式枚举"""
    AUTO = "auto"
    MANUAL = "manual"


class EventType(Enum):
    """事件类型枚举"""
    STATE_CHANGED = "state_changed"
    MODE_CHANGED = "mode_changed"
    CUE_CHANGED = "cue_changed"
    PLAYBACK_STARTED = "playback_started"
    PLAYBACK_PAUSED = "playback_paused"
    PLAYBACK_STOPPED = "playback_stopped"
    PLAYBACK_COMPLETED = "playback_completed"
    BREAKPOINT_SAVED = "breakpoint_saved"
    VOLUME_CHANGED = "volume_changed"
    SILENCE_STARTED = "silence_started"
    SILENCE_ENDED = "silence_ended"
    SFX_STARTED = "sfx_started"
    SFX_STOPPED = "sfx_stopped"


class CoreController:
    """核心控制器 - 单例模式
    
    负责协调所有操作，管理播放状态，处理优先级调度。
    
    功能：
    - 整合 AudioEngine, CueManager, BreakpointManager
    - 实现播放/暂停/停止/跳转控制
    - 实现自动模式播放逻辑（静音间隔处理）
    - 实现手动模式播放逻辑
    - 实现模式切换（位置保持）
    - 实现本地优先级调度
    - 实现事件监听器机制
    """
    
    _instance: Optional["CoreController"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """单例模式实现"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        audio_engine: Optional[AudioEngine] = None,
        cue_manager: Optional[CueManager] = None,
        breakpoint_manager: Optional[BreakpointManager] = None
    ):
        """初始化核心控制器
        
        Args:
            audio_engine: 音频引擎实例
            cue_manager: Cue 管理器实例
            breakpoint_manager: 断点管理器实例
        """
        # 防止重复初始化
        if hasattr(self, "_initialized") and self._initialized:
            return
        
        self._audio_engine = audio_engine or AudioEngine()
        self._cue_manager = cue_manager or CueManager()
        self._breakpoint_manager = breakpoint_manager or BreakpointManager()
        
        # 播放状态
        self._mode: PlayMode = PlayMode.AUTO
        self._is_playing: bool = False
        self._is_paused: bool = False
        self._current_audio_id: Optional[str] = None
        self._current_position: float = 0.0
        self._bgm_volume: float = 1.0
        self._sfx_volume: float = 1.0
        
        # 静音间隔状态
        self._in_silence: bool = False
        self._silence_remaining: float = 0.0
        self._silence_start_time: Optional[float] = None
        self._silence_duration: float = 0.0
        
        # 手动模式状态
        self._manual_audio: Optional[AudioTrack] = None
        self._manual_start_pos: float = 0.0
        self._manual_silence_before: float = 0.0
        
        # 暂停恢复状态
        self._paused_audio_id: Optional[str] = None
        self._paused_position: float = 0.0
        
        # 操作锁和优先级
        self._operation_lock = threading.Lock()
        self._local_priority: bool = True
        self._pending_remote_ops: List[Dict[str, Any]] = []
        
        # 事件监听器
        self._listeners: Dict[EventType, List[Callable]] = {
            event_type: [] for event_type in EventType
        }
        
        # 播放位置追踪
        self._playback_start_time: Optional[float] = None
        self._playback_start_position: float = 0.0
        
        # 设置 BGM 结束回调
        self._audio_engine.set_on_bgm_end(self._on_bgm_end)
        
        self._initialized = True
    
    @classmethod
    def reset_instance(cls) -> None:
        """重置单例实例（主要用于测试）"""
        with cls._lock:
            if cls._instance is not None:
                if hasattr(cls._instance, "_audio_engine"):
                    try:
                        cls._instance._audio_engine.shutdown()
                    except:
                        pass
            cls._instance = None
    
    # ==================== 属性访问 ====================
    
    @property
    def audio_engine(self) -> AudioEngine:
        """获取音频引擎"""
        return self._audio_engine
    
    @property
    def cue_manager(self) -> CueManager:
        """获取 Cue 管理器"""
        return self._cue_manager
    
    @property
    def breakpoint_manager(self) -> BreakpointManager:
        """获取断点管理器"""
        return self._breakpoint_manager
    
    @property
    def mode(self) -> PlayMode:
        """获取当前播放模式"""
        return self._mode
    
    @property
    def is_playing(self) -> bool:
        """是否正在播放"""
        return self._is_playing
    
    @property
    def is_paused(self) -> bool:
        """是否已暂停"""
        return self._is_paused
    
    @property
    def current_position(self) -> float:
        """获取当前播放位置"""
        return self._get_current_position()
    
    @property
    def in_silence(self) -> bool:
        """是否在静音间隔中"""
        return self._in_silence

    # ==================== 播放控制 ====================
    
    async def play(self, source: str = "local") -> bool:
        """开始播放
        
        Args:
            source: 操作来源 ("local" 或 "remote")
            
        Returns:
            是否成功开始播放
        """
        if not self._check_priority(source):
            self._queue_remote_op("play", source)
            return False
        
        with self._operation_lock:
            if self._mode == PlayMode.AUTO:
                return await self._play_auto_mode()
            else:
                return await self._play_manual_mode()
    
    async def _play_auto_mode(self) -> bool:
        """自动模式播放逻辑"""
        cue = self._cue_manager.get_current_cue()
        if cue is None:
            return False
        
        audio = self._cue_manager.get_audio_file(cue.audio_id)
        if audio is None:
            return False
        
        # 处理前置静音
        if cue.silence_before > 0 and not self._in_silence and not self._is_playing:
            await self._start_silence(cue.silence_before, is_before=True)
            return True
        
        # 开始播放
        self._audio_engine.play_bgm(audio, cue.start_time)
        self._is_playing = True
        self._is_paused = False
        self._current_audio_id = audio.id
        self._current_position = cue.start_time
        self._playback_start_time = time.time()
        self._playback_start_position = cue.start_time
        self._cue_manager.is_playing = True
        
        self._notify_listeners(EventType.PLAYBACK_STARTED, {
            "audio_id": audio.id,
            "position": cue.start_time,
            "cue_id": cue.id
        })
        
        return True
    
    async def _play_manual_mode(self) -> bool:
        """手动模式播放逻辑"""
        if self._manual_audio is None:
            return False
        
        # 处理前置静音
        if self._manual_silence_before > 0 and not self._in_silence and not self._is_playing:
            await self._start_silence(self._manual_silence_before, is_before=True)
            return True
        
        # 开始播放
        self._audio_engine.play_bgm(self._manual_audio, self._manual_start_pos)
        self._is_playing = True
        self._is_paused = False
        self._current_audio_id = self._manual_audio.id
        self._current_position = self._manual_start_pos
        self._playback_start_time = time.time()
        self._playback_start_position = self._manual_start_pos
        
        self._notify_listeners(EventType.PLAYBACK_STARTED, {
            "audio_id": self._manual_audio.id,
            "position": self._manual_start_pos
        })
        
        return True
    
    async def pause(self, source: str = "local") -> bool:
        """暂停播放
        
        Args:
            source: 操作来源
            
        Returns:
            是否成功暂停
        """
        if not self._check_priority(source):
            self._queue_remote_op("pause", source)
            return False
        
        with self._operation_lock:
            if not self._is_playing or self._is_paused:
                return False
            
            # 记录当前位置
            self._current_position = self._get_current_position()
            
            # 自动保存断点（用于恢复）
            if self._current_audio_id:
                self._breakpoint_manager.save_breakpoint(
                    self._current_audio_id,
                    self._current_position,
                    label="暂停自动保存",
                    auto_saved=True
                )
            
            # 暂停音频
            self._audio_engine.pause_bgm()
            self._is_paused = True
            
            # 记录暂停位置用于恢复
            self._paused_audio_id = self._current_audio_id
            self._paused_position = self._current_position
            
            self._notify_listeners(EventType.PLAYBACK_PAUSED, {
                "position": self._current_position
            })
            
            return True
    
    async def resume(self, source: str = "local") -> bool:
        """继续播放
        
        Args:
            source: 操作来源
            
        Returns:
            是否成功继续
        """
        if not self._check_priority(source):
            self._queue_remote_op("resume", source)
            return False
        
        with self._operation_lock:
            if not self._is_paused:
                return False
            
            # 获取恢复位置
            resume_position = self._paused_position if self._paused_position > 0 else self._current_position
            
            # 获取当前音频（优先使用手动模式的音频）
            audio = None
            if self._mode == PlayMode.MANUAL and self._manual_audio:
                audio = self._manual_audio
            elif self._paused_audio_id:
                # 先尝试从 cue_manager 获取
                audio = self._cue_manager.get_audio_file(self._paused_audio_id)
                # 如果获取不到，检查是否是手动模式的音频
                if audio is None and self._manual_audio and self._manual_audio.id == self._paused_audio_id:
                    audio = self._manual_audio
            elif self._mode == PlayMode.AUTO:
                cue = self._cue_manager.get_current_cue()
                if cue:
                    audio = self._cue_manager.get_audio_file(cue.audio_id)
            
            if audio is None:
                return False
            
            # 直接从保存的位置重新播放（更可靠）
            # pygame 的 unpause 在某些情况下不可靠
            self._audio_engine.play_bgm(audio, resume_position)
            
            self._is_paused = False
            self._is_playing = True
            self._playback_start_time = time.time()
            self._playback_start_position = resume_position
            self._current_position = resume_position
            
            self._notify_listeners(EventType.PLAYBACK_STARTED, {
                "position": self._current_position,
                "resumed": True
            })
            
            return True
    
    async def stop(self, source: str = "local") -> bool:
        """停止播放
        
        Args:
            source: 操作来源
            
        Returns:
            是否成功停止
        """
        if not self._check_priority(source):
            self._queue_remote_op("stop", source)
            return False
        
        with self._operation_lock:
            # 保存当前音频 ID 用于事件通知
            stopped_audio_id = self._current_audio_id
            position = self._audio_engine.stop_bgm()
            
            # 重置所有播放状态
            self._is_playing = False
            self._is_paused = False
            self._current_position = 0.0
            self._playback_start_time = None
            self._playback_start_position = 0.0
            self._cue_manager.is_playing = False
            
            # 清除暂停恢复状态
            self._paused_audio_id = None
            self._paused_position = 0.0
            
            # 停止静音间隔
            if self._in_silence:
                self._in_silence = False
                self._silence_remaining = 0.0
                self._silence_start_time = None
                self._silence_duration = 0.0
            
            self._notify_listeners(EventType.PLAYBACK_STOPPED, {
                "position": position,
                "audio_id": stopped_audio_id
            })
            
            return True

    async def next_cue(self, source: str = "local") -> bool:
        """跳至下一个 Cue（仅自动模式）
        
        Args:
            source: 操作来源
            
        Returns:
            是否成功跳转
        """
        if not self._check_priority(source):
            self._queue_remote_op("next_cue", source)
            return False
        
        with self._operation_lock:
            if self._mode != PlayMode.AUTO:
                return False
            
            # 停止当前播放
            self._audio_engine.stop_bgm()
            
            # 停止静音间隔
            if self._in_silence:
                self._in_silence = False
                self._silence_remaining = 0.0
            
            # 前进到下一个 Cue
            next_cue = self._cue_manager.advance()
            if next_cue is None:
                self._is_playing = False
                self._is_paused = False
                self._cue_manager.is_playing = False
                return False
            
            self._notify_listeners(EventType.CUE_CHANGED, {
                "cue_index": self._cue_manager.current_index,
                "cue_id": next_cue.id
            })
            
            # 开始播放下一个 Cue
            return await self._play_auto_mode()
    
    async def seek(self, position: float, source: str = "local") -> bool:
        """跳转到指定位置
        
        Args:
            position: 目标位置（秒）
            source: 操作来源
            
        Returns:
            是否成功跳转
        """
        if not self._check_priority(source):
            self._queue_remote_op("seek", source, position=position)
            return False
        
        with self._operation_lock:
            if self._current_audio_id is None:
                return False
            
            # 获取当前音频
            if self._mode == PlayMode.AUTO:
                cue = self._cue_manager.get_current_cue()
                if cue is None:
                    return False
                audio = self._cue_manager.get_audio_file(cue.audio_id)
            else:
                audio = self._manual_audio
            
            if audio is None:
                return False
            
            # 验证位置有效性
            if position < 0 or position > audio.duration:
                return False
            
            # 重新播放到指定位置
            was_playing = self._is_playing and not self._is_paused
            self._audio_engine.stop_bgm()
            self._audio_engine.play_bgm(audio, position)
            
            self._current_position = position
            self._playback_start_time = time.time()
            self._playback_start_position = position
            
            if not was_playing:
                self._audio_engine.pause_bgm()
                self._is_paused = True
            
            return True
    
    async def replay(self, source: str = "local") -> bool:
        """重播当前音频（从头开始）
        
        Args:
            source: 操作来源
            
        Returns:
            是否成功重播
        """
        if not self._check_priority(source):
            self._queue_remote_op("replay", source)
            return False
        
        with self._operation_lock:
            # 获取当前音频
            if self._mode == PlayMode.AUTO:
                cue = self._cue_manager.get_current_cue()
                if cue is None:
                    return False
                audio = self._cue_manager.get_audio_file(cue.audio_id)
                start_pos = cue.start_time
            else:
                audio = self._manual_audio
                start_pos = 0.0
            
            if audio is None:
                return False
            
            # 停止当前播放
            self._audio_engine.stop_bgm()
            
            # 从头开始播放
            self._audio_engine.play_bgm(audio, start_pos)
            self._is_playing = True
            self._is_paused = False
            self._current_position = start_pos
            self._playback_start_time = time.time()
            self._playback_start_position = start_pos
            
            self._notify_listeners(EventType.PLAYBACK_STARTED, {
                "audio_id": audio.id,
                "position": start_pos,
                "replay": True
            })
            
            return True
    
    # ==================== 音效控制 ====================
    
    def play_sfx(self, sfx_id: str, track: AudioTrack) -> bool:
        """播放音效
        
        Args:
            sfx_id: 音效 ID
            track: 音频轨道
            
        Returns:
            是否成功播放
        """
        with self._operation_lock:
            result = self._audio_engine.play_sfx(sfx_id, track)
            if result:
                self._notify_listeners(EventType.SFX_STARTED, {
                    "sfx_id": sfx_id
                })
            return result
    
    def stop_sfx(self, sfx_id: str) -> bool:
        """停止音效
        
        Args:
            sfx_id: 音效 ID
            
        Returns:
            是否成功停止
        """
        with self._operation_lock:
            result = self._audio_engine.stop_sfx(sfx_id)
            if result:
                self._notify_listeners(EventType.SFX_STOPPED, {
                    "sfx_id": sfx_id
                })
            return result
    
    def toggle_sfx(self, sfx_id: str, track: AudioTrack) -> bool:
        """切换音效状态（播放中则停止，停止则播放）
        
        Args:
            sfx_id: 音效 ID
            track: 音频轨道
            
        Returns:
            操作后是否正在播放
        """
        with self._operation_lock:
            if self._audio_engine.is_sfx_playing(sfx_id):
                self._audio_engine.stop_sfx(sfx_id)
                self._notify_listeners(EventType.SFX_STOPPED, {"sfx_id": sfx_id})
                return False
            else:
                self._audio_engine.play_sfx(sfx_id, track)
                self._notify_listeners(EventType.SFX_STARTED, {"sfx_id": sfx_id})
                return True
    
    def is_sfx_playing(self, sfx_id: str) -> bool:
        """检查音效是否正在播放"""
        return self._audio_engine.is_sfx_playing(sfx_id)

    # ==================== 音量控制 ====================
    
    def set_bgm_volume(self, volume: float) -> None:
        """设置 BGM 音量
        
        Args:
            volume: 音量值 (0.0 - 3.0，即 0%-300%)
        """
        self._bgm_volume = max(0.0, min(3.0, volume))
        self._audio_engine.set_bgm_volume(self._bgm_volume)
        self._notify_listeners(EventType.VOLUME_CHANGED, {
            "type": "bgm",
            "volume": self._bgm_volume
        })
    
    def get_bgm_volume(self) -> float:
        """获取 BGM 音量"""
        return self._bgm_volume
    
    def set_sfx_volume(self, volume: float) -> None:
        """设置音效音量
        
        Args:
            volume: 音量值 (0.0 - 3.0，即 0%-300%)
        """
        self._sfx_volume = max(0.0, min(3.0, volume))
        self._audio_engine.set_sfx_volume(self._sfx_volume)
        self._notify_listeners(EventType.VOLUME_CHANGED, {
            "type": "sfx",
            "volume": self._sfx_volume
        })
    
    def get_sfx_volume(self) -> float:
        """获取音效音量"""
        return self._sfx_volume
    
    # ==================== 模式切换 ====================
    
    async def switch_mode(self, mode: PlayMode) -> bool:
        """切换播放模式（无缝切换，保持播放状态）
        
        Args:
            mode: 目标模式
            
        Returns:
            是否成功切换
        """
        with self._operation_lock:
            if self._mode == mode:
                return True
            
            # 记录当前状态
            current_pos = self._get_current_position()
            was_playing = self._is_playing and not self._is_paused
            was_paused = self._is_paused
            current_audio = None
            
            # 获取当前播放的音频
            if self._mode == PlayMode.AUTO:
                cue = self._cue_manager.get_current_cue()
                if cue:
                    current_audio = self._cue_manager.get_audio_file(cue.audio_id)
            else:
                current_audio = self._manual_audio
            
            # 切换模式
            old_mode = self._mode
            self._mode = mode
            
            # 同步状态 - 无缝切换
            if mode == PlayMode.MANUAL:
                # 从自动切换到手动
                if current_audio:
                    self._manual_audio = current_audio
                    self._manual_start_pos = current_pos if was_playing or was_paused else 0.0
            else:
                # 从手动切换到自动
                # 尝试找到匹配的 Cue
                if self._manual_audio:
                    found = False
                    for i, cue in enumerate(self._cue_manager.cue_list):
                        if cue.audio_id == self._manual_audio.id:
                            self._cue_manager.set_index(i)
                            found = True
                            break
                    if not found and self._cue_manager.cue_list:
                        # 如果没找到匹配的 Cue，保持当前索引
                        pass
            
            # 保持播放/暂停状态不变
            # 音频引擎不需要重新操作，因为音频本身没有变化
            
            self._notify_listeners(EventType.MODE_CHANGED, {
                "old_mode": old_mode.value,
                "new_mode": mode.value,
                "position": current_pos,
                "was_playing": was_playing,
                "was_paused": was_paused
            })
            
            return True
    
    # ==================== 手动模式设置 ====================
    
    def set_manual_audio(self, audio: AudioTrack) -> None:
        """设置手动模式的音频
        
        Args:
            audio: 音频轨道
        """
        # 如果正在播放其他音频，先保存断点
        if self._is_playing and self._current_audio_id and self._current_audio_id != audio.id:
            current_pos = self._get_current_position()
            self._breakpoint_manager.save_breakpoint(
                self._current_audio_id,
                current_pos,
                label="切换音频自动保存",
                auto_saved=True
            )
        
        self._manual_audio = audio
        self._manual_start_pos = 0.0
        self._manual_silence_before = 0.0
    
    def set_manual_start_position(self, position: float) -> None:
        """设置手动模式的入点
        
        Args:
            position: 入点位置（秒）
        """
        self._manual_start_pos = max(0.0, position)
    
    def set_manual_silence_before(self, duration: float) -> None:
        """设置手动模式的前置静音
        
        Args:
            duration: 静音时长（秒）
        """
        self._manual_silence_before = max(0.0, duration)
    
    # ==================== 断点管理 ====================
    
    def save_breakpoint(self, label: str = "") -> Optional[str]:
        """保存当前位置为断点
        
        Args:
            label: 断点标签
            
        Returns:
            断点 ID，失败返回 None
        """
        if self._current_audio_id is None:
            return None
        
        position = self._get_current_position()
        bp_id = self._breakpoint_manager.save_breakpoint(
            self._current_audio_id,
            position,
            label
        )
        
        self._notify_listeners(EventType.BREAKPOINT_SAVED, {
            "audio_id": self._current_audio_id,
            "position": position,
            "bp_id": bp_id
        })
        
        return bp_id
    
    async def restore_breakpoint(self, audio_id: str, bp_id: str) -> bool:
        """从断点恢复播放
        
        Args:
            audio_id: 音频 ID
            bp_id: 断点 ID
            
        Returns:
            是否成功恢复
        """
        bp = self._breakpoint_manager.get_breakpoint(audio_id, bp_id)
        if bp is None:
            return False
        
        # 获取音频
        audio = self._cue_manager.get_audio_file(audio_id)
        if audio is None:
            return False
        
        with self._operation_lock:
            # 如果当前有 BGM 在播放，保存断点
            if self._is_playing and self._current_audio_id:
                current_pos = self._get_current_position()
                self._breakpoint_manager.save_breakpoint(
                    self._current_audio_id,
                    current_pos,
                    auto_saved=True
                )
            
            # 停止当前播放
            self._audio_engine.stop_bgm()
            
            # 从断点位置播放
            self._audio_engine.play_bgm(audio, bp.position)
            self._is_playing = True
            self._is_paused = False
            self._current_audio_id = audio_id
            self._current_position = bp.position
            self._playback_start_time = time.time()
            self._playback_start_position = bp.position
            
            # 更新手动模式状态
            if self._mode == PlayMode.MANUAL:
                self._manual_audio = audio
                self._manual_start_pos = bp.position
            
            self._notify_listeners(EventType.PLAYBACK_STARTED, {
                "audio_id": audio_id,
                "position": bp.position,
                "from_breakpoint": True,
                "bp_id": bp_id
            })
            
            return True

    # ==================== BGM 互斥与自动断点 ====================
    
    async def play_new_bgm(self, audio: AudioTrack, start_pos: float = 0.0) -> bool:
        """播放新 BGM（自动保存当前 BGM 断点）
        
        Args:
            audio: 新的音频轨道
            start_pos: 开始位置
            
        Returns:
            是否成功播放
        """
        with self._operation_lock:
            # 如果当前有 BGM 在播放，保存断点
            if self._is_playing and self._current_audio_id and not self._is_paused:
                current_pos = self._get_current_position()
                self._breakpoint_manager.save_breakpoint(
                    self._current_audio_id,
                    current_pos,
                    label="自动保存",
                    auto_saved=True
                )
            
            # 停止当前 BGM
            self._audio_engine.stop_bgm()
            
            # 播放新 BGM
            self._audio_engine.play_bgm(audio, start_pos)
            self._is_playing = True
            self._is_paused = False
            self._current_audio_id = audio.id
            self._current_position = start_pos
            self._playback_start_time = time.time()
            self._playback_start_position = start_pos
            
            # 更新手动模式状态
            if self._mode == PlayMode.MANUAL:
                self._manual_audio = audio
                self._manual_start_pos = start_pos
            
            self._notify_listeners(EventType.PLAYBACK_STARTED, {
                "audio_id": audio.id,
                "position": start_pos
            })
            
            return True
    
    # ==================== 静音间隔处理 ====================
    
    async def _start_silence(self, duration: float, is_before: bool = True) -> None:
        """开始静音间隔
        
        Args:
            duration: 静音时长（秒）
            is_before: 是否为前置静音
        """
        self._in_silence = True
        self._silence_duration = duration
        self._silence_remaining = duration
        self._silence_start_time = time.time()
        
        self._notify_listeners(EventType.SILENCE_STARTED, {
            "duration": duration,
            "is_before": is_before
        })
    
    async def skip_silence(self) -> bool:
        """跳过静音间隔
        
        Returns:
            是否成功跳过
        """
        with self._operation_lock:
            if not self._in_silence:
                return False
            
            self._in_silence = False
            self._silence_remaining = 0.0
            
            self._notify_listeners(EventType.SILENCE_ENDED, {
                "skipped": True
            })
            
            # 开始播放
            if self._mode == PlayMode.AUTO:
                return await self._play_auto_mode()
            else:
                return await self._play_manual_mode()
    
    def update_silence(self) -> bool:
        """更新静音间隔状态（应在主循环中调用）
        
        Returns:
            静音是否已结束
        """
        if not self._in_silence:
            return False
        
        elapsed = time.time() - self._silence_start_time
        self._silence_remaining = max(0.0, self._silence_duration - elapsed)
        
        if self._silence_remaining <= 0:
            self._in_silence = False
            self._notify_listeners(EventType.SILENCE_ENDED, {
                "skipped": False
            })
            return True
        
        return False
    
    # ==================== 状态查询 ====================
    
    def get_state(self) -> PlaybackState:
        """获取当前播放状态
        
        Returns:
            PlaybackState 对象
        """
        # 获取当前音频时长
        duration = 0.0
        current_audio = self.get_current_audio()
        if current_audio:
            duration = current_audio.duration
        
        return PlaybackState(
            mode=self._mode.value,
            is_playing=self._is_playing,
            is_paused=self._is_paused,
            current_audio_id=self._current_audio_id,
            current_position=self._get_current_position(),
            current_cue_index=self._cue_manager.current_index,
            bgm_volume=self._bgm_volume,
            sfx_volume=self._sfx_volume,
            in_silence=self._in_silence,
            silence_remaining=self._silence_remaining,
            duration=duration
        )
    
    def get_state_dict(self) -> dict:
        """获取当前播放状态（字典格式）
        
        Returns:
            状态字典
        """
        return self.get_state().to_dict()
    
    def _get_current_position(self) -> float:
        """获取当前播放位置（内部方法）"""
        if self._is_paused:
            return self._current_position
        
        if not self._is_playing or self._playback_start_time is None:
            return self._current_position
        
        # 计算已播放时间
        elapsed = time.time() - self._playback_start_time
        return self._playback_start_position + elapsed
    
    # ==================== 事件监听器 ====================
    
    def add_listener(self, event_type: EventType, callback: Callable) -> None:
        """添加事件监听器
        
        Args:
            event_type: 事件类型
            callback: 回调函数
        """
        if event_type in self._listeners:
            self._listeners[event_type].append(callback)
    
    def remove_listener(self, event_type: EventType, callback: Callable) -> None:
        """移除事件监听器
        
        Args:
            event_type: 事件类型
            callback: 回调函数
        """
        if event_type in self._listeners and callback in self._listeners[event_type]:
            self._listeners[event_type].remove(callback)
    
    def _notify_listeners(self, event_type: EventType, data: dict) -> None:
        """通知所有监听器
        
        Args:
            event_type: 事件类型
            data: 事件数据
        """
        for callback in self._listeners.get(event_type, []):
            try:
                callback(event_type, data)
            except Exception as e:
                # 记录错误但不中断其他监听器
                print(f"Listener error: {e}")
        
        # 同时触发通用状态变化事件
        if event_type != EventType.STATE_CHANGED:
            for callback in self._listeners.get(EventType.STATE_CHANGED, []):
                try:
                    callback(EventType.STATE_CHANGED, {
                        "event": event_type.value,
                        "data": data
                    })
                except Exception as e:
                    print(f"State listener error: {e}")

    # ==================== 优先级调度 ====================
    
    def _check_priority(self, source: str) -> bool:
        """检查操作优先级
        
        Args:
            source: 操作来源
            
        Returns:
            是否允许执行
        """
        if source == "local":
            return True
        
        # 远程操作需要检查本地优先级
        return not self._local_priority
    
    def _queue_remote_op(self, op: str, source: str, **kwargs) -> None:
        """将远程操作加入队列
        
        Args:
            op: 操作名称
            source: 操作来源
            **kwargs: 操作参数
        """
        self._pending_remote_ops.append({
            "op": op,
            "source": source,
            "kwargs": kwargs,
            "timestamp": time.time()
        })
    
    def set_local_priority(self, enabled: bool) -> None:
        """设置本地优先级
        
        Args:
            enabled: 是否启用本地优先级
        """
        self._local_priority = enabled
    
    async def process_pending_ops(self) -> None:
        """处理待执行的远程操作"""
        if not self._pending_remote_ops:
            return
        
        # 获取最新的操作
        op_info = self._pending_remote_ops.pop(0)
        op = op_info["op"]
        kwargs = op_info["kwargs"]
        
        if op == "play":
            await self.play(source="remote")
        elif op == "pause":
            await self.pause(source="remote")
        elif op == "resume":
            await self.resume(source="remote")
        elif op == "stop":
            await self.stop(source="remote")
        elif op == "next_cue":
            await self.next_cue(source="remote")
        elif op == "seek":
            await self.seek(kwargs.get("position", 0), source="remote")
        elif op == "replay":
            await self.replay(source="remote")
    
    # ==================== BGM 结束回调 ====================
    
    def _on_bgm_end(self) -> None:
        """BGM 播放结束回调"""
        # 保存完成的音频 ID
        completed_audio_id = self._current_audio_id
        
        # 重置播放状态
        self._is_playing = False
        self._is_paused = False
        self._playback_start_time = None
        self._paused_audio_id = None
        self._paused_position = 0.0
        
        self._notify_listeners(EventType.PLAYBACK_COMPLETED, {
            "audio_id": completed_audio_id
        })
        
        # 自动模式下处理后置静音和下一个 Cue
        if self._mode == PlayMode.AUTO:
            cue = self._cue_manager.get_current_cue()
            if cue and cue.silence_after > 0:
                # 启动后置静音（异步处理）
                try:
                    asyncio.create_task(self._handle_auto_next(cue.silence_after))
                except RuntimeError:
                    # 如果没有事件循环，忽略
                    pass
            else:
                # 直接播放下一个
                try:
                    asyncio.create_task(self._auto_advance())
                except RuntimeError:
                    # 如果没有事件循环，忽略
                    pass
    
    async def _handle_auto_next(self, silence_duration: float) -> None:
        """处理自动模式的下一个 Cue（包含静音间隔）
        
        Args:
            silence_duration: 静音时长
        """
        await self._start_silence(silence_duration, is_before=False)
        
        # 等待静音结束
        while self._in_silence:
            await asyncio.sleep(0.1)
            self.update_silence()
        
        await self._auto_advance()
    
    async def _auto_advance(self) -> None:
        """自动前进到下一个 Cue"""
        next_cue = self._cue_manager.advance()
        if next_cue:
            self._notify_listeners(EventType.CUE_CHANGED, {
                "cue_index": self._cue_manager.current_index,
                "cue_id": next_cue.id
            })
            await self._play_auto_mode()
    
    # ==================== 工具方法 ====================
    
    def get_current_cue(self) -> Optional[Cue]:
        """获取当前 Cue"""
        return self._cue_manager.get_current_cue()
    
    def get_next_cue(self) -> Optional[Cue]:
        """获取下一个 Cue"""
        return self._cue_manager.get_next_cue()
    
    def get_current_audio(self) -> Optional[AudioTrack]:
        """获取当前音频"""
        if self._mode == PlayMode.MANUAL:
            return self._manual_audio
        
        cue = self._cue_manager.get_current_cue()
        if cue:
            return self._cue_manager.get_audio_file(cue.audio_id)
        return None
    
    def load_config(self, config_path: str) -> None:
        """加载配置文件
        
        Args:
            config_path: 配置文件路径
        """
        self._cue_manager.load_config(config_path)
    
    def save_config(self, config_path: str) -> None:
        """保存配置文件
        
        Args:
            config_path: 配置文件路径
        """
        self._cue_manager.save_config(config_path)
    
    def load_breakpoints(self, path: str) -> None:
        """加载断点数据
        
        Args:
            path: 断点文件路径
        """
        self._breakpoint_manager.load_from_file(path)
    
    def save_breakpoints(self, path: str) -> None:
        """保存断点数据
        
        Args:
            path: 断点文件路径
        """
        self._breakpoint_manager.save_to_file(path)
