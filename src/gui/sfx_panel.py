"""
音效面板模块

实现音效控制的 GUI 界面，包含：
- 音效按钮网格
- 点击播放/再点停止

**Requirements: 3.1-3.4**
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional, List, Dict, Any
import math

from src.core.controller import CoreController, EventType
from src.models.audio_track import AudioTrack


class SFXPanel:
    """
    音效面板
    
    提供音效控制功能：
    - 音效按钮网格显示
    - 点击播放，再点停止
    - 支持多个音效同时播放
    
    **Requirements: 3.1-3.4**
    """
    
    # 默认网格列数
    DEFAULT_COLUMNS = 4
    
    # 按钮尺寸
    BUTTON_WIDTH = 12
    BUTTON_HEIGHT = 2
    
    def __init__(
        self,
        parent: ttk.Frame,
        controller: CoreController,
        columns: int = DEFAULT_COLUMNS
    ):
        """
        初始化音效面板
        
        Args:
            parent: 父容器
            controller: 核心控制器
            columns: 网格列数
        """
        self._parent = parent
        self._controller = controller
        self._columns = columns
        
        # 音效按钮字典: sfx_id -> Button
        self._sfx_buttons: Dict[str, tk.Button] = {}
        
        # 音效数据: sfx_id -> AudioTrack
        self._sfx_tracks: Dict[str, AudioTrack] = {}
        
        # 按钮容器
        self._button_frame: Optional[ttk.Frame] = None
        
        # 创建界面
        self._create_ui()
        
        # 注册事件监听
        self._register_listeners()
        
        # 加载音效
        self._load_sfx_tracks()
    
    def _create_ui(self) -> None:
        """创建用户界面"""
        # 按钮网格容器
        self._button_frame = ttk.Frame(self._parent)
        self._button_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    def _register_listeners(self) -> None:
        """注册控制器事件监听"""
        self._controller.add_listener(EventType.SFX_STARTED, self._on_sfx_started)
        self._controller.add_listener(EventType.SFX_STOPPED, self._on_sfx_stopped)
    
    def _load_sfx_tracks(self) -> None:
        """加载音效轨道"""
        # 从 CueManager 获取音效类型的音频
        audio_files = self._controller.cue_manager.audio_files
        
        for audio in audio_files:
            if audio.track_type == "sfx":
                self._sfx_tracks[audio.id] = audio
        
        # 创建按钮
        self._create_sfx_buttons()
    
    def _create_sfx_buttons(self) -> None:
        """创建音效按钮网格"""
        if not self._button_frame:
            return
        
        # 清除现有按钮
        for widget in self._button_frame.winfo_children():
            widget.destroy()
        self._sfx_buttons.clear()
        
        # 获取音效列表
        sfx_list = list(self._sfx_tracks.items())
        
        if not sfx_list:
            # 显示提示
            ttk.Label(
                self._button_frame,
                text="暂无音效",
                style="Status.TLabel"
            ).pack(pady=20)
            return
        
        # 计算行数
        rows = math.ceil(len(sfx_list) / self._columns)
        
        # 配置网格
        for i in range(self._columns):
            self._button_frame.columnconfigure(i, weight=1)
        
        # 创建按钮
        for index, (sfx_id, track) in enumerate(sfx_list):
            row = index // self._columns
            col = index % self._columns
            
            # 创建按钮
            btn = tk.Button(
                self._button_frame,
                text=track.title,
                width=self.BUTTON_WIDTH,
                height=self.BUTTON_HEIGHT,
                font=("微软雅黑", 10),
                bg="#E0E0E0",
                activebackground="#BDBDBD",
                relief=tk.RAISED,
                command=lambda sid=sfx_id: self._on_sfx_click(sid)
            )
            btn.grid(row=row, column=col, padx=3, pady=3, sticky="nsew")
            
            self._sfx_buttons[sfx_id] = btn
    
    def _on_sfx_click(self, sfx_id: str) -> None:
        """
        音效按钮点击事件
        
        Args:
            sfx_id: 音效 ID
        """
        track = self._sfx_tracks.get(sfx_id)
        if not track:
            return
        
        # 切换音效状态
        is_playing = self._controller.toggle_sfx(sfx_id, track)
        
        # 更新按钮状态
        self._update_button_state(sfx_id, is_playing)
    
    def _update_button_state(self, sfx_id: str, is_playing: bool) -> None:
        """
        更新按钮状态
        
        Args:
            sfx_id: 音效 ID
            is_playing: 是否正在播放
        """
        btn = self._sfx_buttons.get(sfx_id)
        if not btn:
            return
        
        if is_playing:
            # 播放中 - 高亮显示
            btn.config(
                bg="#4CAF50",
                fg="white",
                relief=tk.SUNKEN
            )
        else:
            # 停止 - 恢复默认
            btn.config(
                bg="#E0E0E0",
                fg="black",
                relief=tk.RAISED
            )
    
    def _on_sfx_started(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """音效开始播放事件"""
        sfx_id = data.get("sfx_id")
        if sfx_id:
            self._update_button_state(sfx_id, True)
    
    def _on_sfx_stopped(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """音效停止播放事件"""
        sfx_id = data.get("sfx_id")
        if sfx_id:
            self._update_button_state(sfx_id, False)
    
    # ==================== 公共方法 ====================
    
    def add_sfx(self, track: AudioTrack) -> None:
        """
        添加音效
        
        Args:
            track: 音效轨道
        """
        self._sfx_tracks[track.id] = track
        self._create_sfx_buttons()
    
    def remove_sfx(self, sfx_id: str) -> None:
        """
        移除音效
        
        Args:
            sfx_id: 音效 ID
        """
        if sfx_id in self._sfx_tracks:
            del self._sfx_tracks[sfx_id]
            self._create_sfx_buttons()
    
    def refresh(self) -> None:
        """刷新面板"""
        self._load_sfx_tracks()
    
    def stop_all(self) -> None:
        """停止所有音效"""
        self._controller.audio_engine.stop_all_sfx()
        
        # 更新所有按钮状态
        for sfx_id in self._sfx_buttons:
            self._update_button_state(sfx_id, False)
    
    def set_columns(self, columns: int) -> None:
        """
        设置网格列数
        
        Args:
            columns: 列数
        """
        self._columns = max(1, columns)
        self._create_sfx_buttons()
    
    def get_playing_sfx(self) -> List[str]:
        """
        获取正在播放的音效 ID 列表
        
        Returns:
            List[str]: 正在播放的音效 ID 列表
        """
        return self._controller.audio_engine.get_playing_sfx_ids()
    
    def destroy(self) -> None:
        """销毁面板"""
        # 停止所有音效
        self.stop_all()
        
        # 清除按钮
        self._sfx_buttons.clear()
        self._sfx_tracks.clear()
