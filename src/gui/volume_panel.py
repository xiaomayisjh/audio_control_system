"""
音量控制面板模块

实现音量控制的 GUI 界面，包含：
- BGM 音量滑块
- 音效音量滑块
- 实时无延迟调节

**Requirements: 6.1-6.4**
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict, Any

from src.core.controller import CoreController, EventType


class VolumePanel:
    """
    音量控制面板
    
    提供音量控制功能：
    - BGM 音量独立控制
    - 音效音量独立控制
    - 实时无延迟调节
    
    **Requirements: 6.1-6.4**
    """
    
    # 滑块长度
    SLIDER_LENGTH = 150
    
    def __init__(
        self,
        parent: ttk.Frame,
        controller: CoreController
    ):
        """
        初始化音量控制面板
        
        Args:
            parent: 父容器
            controller: 核心控制器
        """
        self._parent = parent
        self._controller = controller
        
        # 音量变量
        self._bgm_volume_var: Optional[tk.DoubleVar] = None
        self._sfx_volume_var: Optional[tk.DoubleVar] = None
        
        # 滑块组件
        self._bgm_slider: Optional[ttk.Scale] = None
        self._sfx_slider: Optional[ttk.Scale] = None
        
        # 音量标签
        self._bgm_value_label: Optional[ttk.Label] = None
        self._sfx_value_label: Optional[ttk.Label] = None
        
        # 静音按钮
        self._bgm_mute_btn: Optional[ttk.Button] = None
        self._sfx_mute_btn: Optional[ttk.Button] = None
        
        # 静音状态
        self._bgm_muted = False
        self._sfx_muted = False
        self._bgm_volume_before_mute = 1.0
        self._sfx_volume_before_mute = 1.0
        
        # 创建界面
        self._create_ui()
        
        # 注册事件监听
        self._register_listeners()
        
        # 初始化音量值
        self._init_volume_values()
    
    def _create_ui(self) -> None:
        """创建用户界面"""
        # BGM 音量控制
        self._create_bgm_control()
        
        # 分隔线
        ttk.Separator(self._parent, orient=tk.HORIZONTAL).pack(
            fill=tk.X, pady=10
        )
        
        # 音效音量控制
        self._create_sfx_control()
    
    def _create_bgm_control(self) -> None:
        """创建 BGM 音量控制"""
        bgm_frame = ttk.Frame(self._parent)
        bgm_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 标题行
        title_frame = ttk.Frame(bgm_frame)
        title_frame.pack(fill=tk.X)
        
        ttk.Label(
            title_frame,
            text="BGM 音量",
            font=("微软雅黑", 10, "bold")
        ).pack(side=tk.LEFT)
        
        # 音量值标签
        self._bgm_value_label = ttk.Label(
            title_frame,
            text="100%",
            font=("微软雅黑", 9)
        )
        self._bgm_value_label.pack(side=tk.RIGHT)
        
        # 滑块
        self._bgm_volume_var = tk.DoubleVar(value=100)
        self._bgm_slider = ttk.Scale(
            bgm_frame,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            variable=self._bgm_volume_var,
            command=self._on_bgm_volume_change,
            length=self.SLIDER_LENGTH
        )
        self._bgm_slider.pack(fill=tk.X, pady=(5, 0))
        
        # 静音按钮
        self._bgm_mute_btn = ttk.Button(
            bgm_frame,
            text="🔊",
            width=3,
            command=self._on_bgm_mute_toggle
        )
        self._bgm_mute_btn.pack(pady=(5, 0))
    
    def _create_sfx_control(self) -> None:
        """创建音效音量控制"""
        sfx_frame = ttk.Frame(self._parent)
        sfx_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 标题行
        title_frame = ttk.Frame(sfx_frame)
        title_frame.pack(fill=tk.X)
        
        ttk.Label(
            title_frame,
            text="音效音量",
            font=("微软雅黑", 10, "bold")
        ).pack(side=tk.LEFT)
        
        # 音量值标签
        self._sfx_value_label = ttk.Label(
            title_frame,
            text="100%",
            font=("微软雅黑", 9)
        )
        self._sfx_value_label.pack(side=tk.RIGHT)
        
        # 滑块
        self._sfx_volume_var = tk.DoubleVar(value=100)
        self._sfx_slider = ttk.Scale(
            sfx_frame,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            variable=self._sfx_volume_var,
            command=self._on_sfx_volume_change,
            length=self.SLIDER_LENGTH
        )
        self._sfx_slider.pack(fill=tk.X, pady=(5, 0))
        
        # 静音按钮
        self._sfx_mute_btn = ttk.Button(
            sfx_frame,
            text="🔊",
            width=3,
            command=self._on_sfx_mute_toggle
        )
        self._sfx_mute_btn.pack(pady=(5, 0))
    
    def _register_listeners(self) -> None:
        """注册控制器事件监听"""
        self._controller.add_listener(EventType.VOLUME_CHANGED, self._on_volume_changed)
    
    def _init_volume_values(self) -> None:
        """初始化音量值"""
        bgm_volume = self._controller.get_bgm_volume()
        sfx_volume = self._controller.get_sfx_volume()
        
        self._bgm_volume_var.set(bgm_volume * 100)
        self._sfx_volume_var.set(sfx_volume * 100)
        
        self._update_bgm_label()
        self._update_sfx_label()
    
    def _on_bgm_volume_change(self, value: str) -> None:
        """
        BGM 音量滑块变化事件
        
        Args:
            value: 滑块值（字符串）
        """
        volume = float(value) / 100.0
        self._controller.set_bgm_volume(volume)
        self._update_bgm_label()
        
        # 如果调节音量，取消静音状态
        if self._bgm_muted and volume > 0:
            self._bgm_muted = False
            self._update_bgm_mute_button()
    
    def _on_sfx_volume_change(self, value: str) -> None:
        """
        音效音量滑块变化事件
        
        Args:
            value: 滑块值（字符串）
        """
        volume = float(value) / 100.0
        self._controller.set_sfx_volume(volume)
        self._update_sfx_label()
        
        # 如果调节音量，取消静音状态
        if self._sfx_muted and volume > 0:
            self._sfx_muted = False
            self._update_sfx_mute_button()
    
    def _on_bgm_mute_toggle(self) -> None:
        """BGM 静音切换"""
        if self._bgm_muted:
            # 取消静音
            self._bgm_muted = False
            self._bgm_volume_var.set(self._bgm_volume_before_mute * 100)
            self._controller.set_bgm_volume(self._bgm_volume_before_mute)
        else:
            # 静音
            self._bgm_volume_before_mute = self._bgm_volume_var.get() / 100.0
            self._bgm_muted = True
            self._bgm_volume_var.set(0)
            self._controller.set_bgm_volume(0)
        
        self._update_bgm_label()
        self._update_bgm_mute_button()
    
    def _on_sfx_mute_toggle(self) -> None:
        """音效静音切换"""
        if self._sfx_muted:
            # 取消静音
            self._sfx_muted = False
            self._sfx_volume_var.set(self._sfx_volume_before_mute * 100)
            self._controller.set_sfx_volume(self._sfx_volume_before_mute)
        else:
            # 静音
            self._sfx_volume_before_mute = self._sfx_volume_var.get() / 100.0
            self._sfx_muted = True
            self._sfx_volume_var.set(0)
            self._controller.set_sfx_volume(0)
        
        self._update_sfx_label()
        self._update_sfx_mute_button()
    
    def _update_bgm_label(self) -> None:
        """更新 BGM 音量标签"""
        if self._bgm_value_label:
            value = int(self._bgm_volume_var.get())
            self._bgm_value_label.config(text=f"{value}%")
    
    def _update_sfx_label(self) -> None:
        """更新音效音量标签"""
        if self._sfx_value_label:
            value = int(self._sfx_volume_var.get())
            self._sfx_value_label.config(text=f"{value}%")
    
    def _update_bgm_mute_button(self) -> None:
        """更新 BGM 静音按钮"""
        if self._bgm_mute_btn:
            if self._bgm_muted:
                self._bgm_mute_btn.config(text="🔇")
            else:
                self._bgm_mute_btn.config(text="🔊")
    
    def _update_sfx_mute_button(self) -> None:
        """更新音效静音按钮"""
        if self._sfx_mute_btn:
            if self._sfx_muted:
                self._sfx_mute_btn.config(text="🔇")
            else:
                self._sfx_mute_btn.config(text="🔊")
    
    def _on_volume_changed(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """
        音量变化事件回调
        
        Args:
            event_type: 事件类型
            data: 事件数据
        """
        volume_type = data.get("type")
        volume = data.get("volume", 0)
        
        if volume_type == "bgm":
            self._bgm_volume_var.set(volume * 100)
            self._update_bgm_label()
        elif volume_type == "sfx":
            self._sfx_volume_var.set(volume * 100)
            self._update_sfx_label()
    
    # ==================== 公共方法 ====================
    
    def set_bgm_volume(self, volume: float) -> None:
        """
        设置 BGM 音量
        
        Args:
            volume: 音量值 (0.0 - 1.0)
        """
        self._bgm_volume_var.set(volume * 100)
        self._controller.set_bgm_volume(volume)
        self._update_bgm_label()
    
    def set_sfx_volume(self, volume: float) -> None:
        """
        设置音效音量
        
        Args:
            volume: 音量值 (0.0 - 1.0)
        """
        self._sfx_volume_var.set(volume * 100)
        self._controller.set_sfx_volume(volume)
        self._update_sfx_label()
    
    def get_bgm_volume(self) -> float:
        """
        获取 BGM 音量
        
        Returns:
            float: 音量值 (0.0 - 1.0)
        """
        return self._bgm_volume_var.get() / 100.0
    
    def get_sfx_volume(self) -> float:
        """
        获取音效音量
        
        Returns:
            float: 音量值 (0.0 - 1.0)
        """
        return self._sfx_volume_var.get() / 100.0
    
    def mute_bgm(self) -> None:
        """静音 BGM"""
        if not self._bgm_muted:
            self._on_bgm_mute_toggle()
    
    def unmute_bgm(self) -> None:
        """取消静音 BGM"""
        if self._bgm_muted:
            self._on_bgm_mute_toggle()
    
    def mute_sfx(self) -> None:
        """静音音效"""
        if not self._sfx_muted:
            self._on_sfx_mute_toggle()
    
    def unmute_sfx(self) -> None:
        """取消静音音效"""
        if self._sfx_muted:
            self._on_sfx_mute_toggle()
    
    def is_bgm_muted(self) -> bool:
        """检查 BGM 是否静音"""
        return self._bgm_muted
    
    def is_sfx_muted(self) -> bool:
        """检查音效是否静音"""
        return self._sfx_muted
    
    def refresh(self) -> None:
        """刷新面板"""
        self._init_volume_values()
    
    def destroy(self) -> None:
        """销毁面板"""
        pass
