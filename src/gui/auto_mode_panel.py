"""
自动模式面板模块

实现自动模式的 GUI 界面，包含：
- Cue 列表显示（当前高亮，下一个预览）
- 播放控制按钮（长按确认）
- 进度条和剩余时间显示
- 断点管理界面

**Requirements: 1.1-1.4, 2.1-2.5, 11.2, 11.4, 12.1-12.3**
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional, List, Dict, Any, Callable

from src.core.controller import CoreController, EventType, PlayMode
from src.gui.async_helper import run_async
from src.core.cue_manager import CueManager
from src.core.breakpoint_manager import BreakpointManager
from src.models.cue import Cue
from src.models.breakpoint import Breakpoint
from src.gui.long_press import LongPressHandler


class AutoModePanel:
    """
    自动模式面板
    
    提供自动模式下的所有控制功能：
    - Cue 列表显示和导航
    - 播放/暂停/停止/下一个控制
    - 进度显示
    - 断点管理
    
    **Requirements: 1.1-1.4, 2.1-2.5, 11.2, 11.4, 12.1-12.3**
    """
    
    # 更新间隔（毫秒）
    UPDATE_INTERVAL_MS = 100
    
    def __init__(
        self,
        parent: ttk.Frame,
        controller: CoreController
    ):
        """
        初始化自动模式面板
        
        Args:
            parent: 父容器
            controller: 核心控制器
        """
        self._parent = parent
        self._controller = controller
        
        # UI 组件
        self._cue_listbox: Optional[tk.Listbox] = None
        self._progress_var: Optional[tk.DoubleVar] = None
        self._progress_bar: Optional[ttk.Progressbar] = None
        self._time_label: Optional[ttk.Label] = None
        self._status_label: Optional[ttk.Label] = None
        
        # 播放控制按钮
        self._play_btn: Optional[ttk.Button] = None
        self._pause_btn: Optional[ttk.Button] = None
        self._stop_btn: Optional[ttk.Button] = None
        self._next_btn: Optional[ttk.Button] = None
        
        # 断点相关
        self._breakpoint_listbox: Optional[tk.Listbox] = None
        self._save_bp_btn: Optional[ttk.Button] = None
        self._restore_bp_btn: Optional[ttk.Button] = None
        self._delete_bp_btn: Optional[ttk.Button] = None
        self._clear_bp_btn: Optional[ttk.Button] = None
        
        # 长按处理器
        self._play_handler: Optional[LongPressHandler] = None
        self._pause_handler: Optional[LongPressHandler] = None
        
        # 进度条相关
        self._progress_canvas: Optional[tk.Canvas] = None
        self._progress_fill: Optional[int] = None
        
        # 更新定时器
        self._update_timer_id: Optional[str] = None
        
        # 创建界面
        self._create_ui()
        
        # 注册事件监听
        self._register_listeners()
        
        # 启动更新循环
        self._start_update_loop()
    
    def _create_ui(self) -> None:
        """创建用户界面"""
        # 主容器使用 grid 布局
        self._parent.columnconfigure(0, weight=1)
        self._parent.columnconfigure(1, weight=0)
        self._parent.rowconfigure(1, weight=1)
        
        # 顶部：状态和进度
        self._create_status_section()
        
        # 中部左侧：Cue 列表
        self._create_cue_list_section()
        
        # 中部右侧：断点管理
        self._create_breakpoint_section()
        
        # 底部：播放控制
        self._create_control_section()
    
    def _create_status_section(self) -> None:
        """创建状态和进度区域"""
        status_frame = ttk.Frame(self._parent)
        status_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        status_frame.columnconfigure(0, weight=1)
        
        # 状态标签
        self._status_label = ttk.Label(
            status_frame,
            text="就绪",
            style="Status.TLabel"
        )
        self._status_label.grid(row=0, column=0, sticky="w")
        
        # 时间标签
        self._time_label = ttk.Label(
            status_frame,
            text="00:00 / 00:00",
            style="Status.TLabel"
        )
        self._time_label.grid(row=0, column=1, sticky="e")
        
        # 进度条
        self._progress_var = tk.DoubleVar(value=0)
        self._progress_bar = ttk.Progressbar(
            status_frame,
            variable=self._progress_var,
            maximum=100,
            mode="determinate"
        )
        self._progress_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5, 0))
    
    def _create_cue_list_section(self) -> None:
        """创建 Cue 列表区域"""
        cue_frame = ttk.LabelFrame(self._parent, text="Cue 列表", padding="5")
        cue_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 5))
        cue_frame.rowconfigure(0, weight=1)
        cue_frame.columnconfigure(0, weight=1)
        
        # Cue 列表
        list_frame = ttk.Frame(cue_frame)
        list_frame.grid(row=0, column=0, sticky="nsew")
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        
        self._cue_listbox = tk.Listbox(
            list_frame,
            font=("微软雅黑", 11),
            selectmode=tk.SINGLE,
            activestyle="none"
        )
        self._cue_listbox.grid(row=0, column=0, sticky="nsew")
        
        # 滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._cue_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self._cue_listbox.yview)
        
        # 绑定双击事件
        self._cue_listbox.bind("<Double-1>", self._on_cue_double_click)
        
        # 刷新 Cue 列表
        self._refresh_cue_list()
    
    def _create_breakpoint_section(self) -> None:
        """创建断点管理区域"""
        bp_frame = ttk.LabelFrame(self._parent, text="断点", padding="5")
        bp_frame.grid(row=1, column=1, sticky="nsew")
        bp_frame.rowconfigure(0, weight=1)
        bp_frame.columnconfigure(0, weight=1)
        
        # 断点列表
        list_frame = ttk.Frame(bp_frame)
        list_frame.grid(row=0, column=0, sticky="nsew")
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        
        self._breakpoint_listbox = tk.Listbox(
            list_frame,
            font=("微软雅黑", 10),
            selectmode=tk.EXTENDED,
            width=25
        )
        self._breakpoint_listbox.grid(row=0, column=0, sticky="nsew")
        
        # 滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._breakpoint_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self._breakpoint_listbox.yview)
        
        # 断点操作按钮
        btn_frame = ttk.Frame(bp_frame)
        btn_frame.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        
        self._save_bp_btn = ttk.Button(
            btn_frame,
            text="保存断点",
            command=self._on_save_breakpoint
        )
        self._save_bp_btn.pack(side=tk.LEFT, padx=(0, 2))
        
        self._restore_bp_btn = ttk.Button(
            btn_frame,
            text="恢复",
            command=self._on_restore_breakpoint
        )
        self._restore_bp_btn.pack(side=tk.LEFT, padx=2)
        
        self._delete_bp_btn = ttk.Button(
            btn_frame,
            text="删除",
            command=self._on_delete_breakpoint
        )
        self._delete_bp_btn.pack(side=tk.LEFT, padx=2)
        
        self._clear_bp_btn = ttk.Button(
            btn_frame,
            text="清除全部",
            command=self._on_clear_breakpoints
        )
        self._clear_bp_btn.pack(side=tk.LEFT, padx=(2, 0))
        
        # 绑定双击恢复
        self._breakpoint_listbox.bind("<Double-1>", lambda e: self._on_restore_breakpoint())
    
    def _create_control_section(self) -> None:
        """创建播放控制区域"""
        control_frame = ttk.Frame(self._parent)
        control_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        
        # 居中按钮
        btn_container = ttk.Frame(control_frame)
        btn_container.pack(anchor=tk.CENTER)
        
        # 播放按钮（长按确认）
        self._play_btn = ttk.Button(
            btn_container,
            text="▶ 播放",
            style="Play.TButton",
            width=10
        )
        self._play_btn.pack(side=tk.LEFT, padx=5)
        
        # 绑定长按处理器
        self._play_handler = LongPressHandler(self._play_btn, duration_ms=500)
        self._play_handler.bind(
            callback=self._on_play,
            progress_callback=self._on_play_progress,
            cancel_callback=self._on_play_cancel
        )
        
        # 暂停按钮（长按确认）
        self._pause_btn = ttk.Button(
            btn_container,
            text="⏸ 暂停",
            width=10
        )
        self._pause_btn.pack(side=tk.LEFT, padx=5)
        
        self._pause_handler = LongPressHandler(self._pause_btn, duration_ms=500)
        self._pause_handler.bind(
            callback=self._on_pause,
            progress_callback=self._on_pause_progress,
            cancel_callback=self._on_pause_cancel
        )
        
        # 停止按钮
        self._stop_btn = ttk.Button(
            btn_container,
            text="⏹ 停止",
            width=10,
            command=self._on_stop
        )
        self._stop_btn.pack(side=tk.LEFT, padx=5)
        
        # 下一个按钮
        self._next_btn = ttk.Button(
            btn_container,
            text="⏭ 下一个",
            width=10,
            command=self._on_next
        )
        self._next_btn.pack(side=tk.LEFT, padx=5)
    
    def _register_listeners(self) -> None:
        """注册控制器事件监听"""
        self._controller.add_listener(EventType.PLAYBACK_STARTED, self._on_playback_started)
        self._controller.add_listener(EventType.PLAYBACK_PAUSED, self._on_playback_paused)
        self._controller.add_listener(EventType.PLAYBACK_STOPPED, self._on_playback_stopped)
        self._controller.add_listener(EventType.CUE_CHANGED, self._on_cue_changed)
        self._controller.add_listener(EventType.BREAKPOINT_SAVED, self._on_breakpoint_saved)
    
    def _start_update_loop(self) -> None:
        """启动更新循环"""
        self._update_ui()
    
    def _update_ui(self) -> None:
        """更新 UI 状态"""
        try:
            # 更新进度条和时间
            self._update_progress()
            
            # 更新 Cue 列表高亮
            self._update_cue_highlight()
            
            # 更新按钮状态
            self._update_button_states()
            
        except Exception as e:
            print(f"UI update error: {e}")
        
        # 继续更新循环
        self._update_timer_id = self._parent.after(
            self.UPDATE_INTERVAL_MS,
            self._update_ui
        )
    
    def _update_progress(self) -> None:
        """更新进度条和时间显示"""
        state = self._controller.get_state()
        
        # 获取当前 Cue 信息
        cue = self._controller.cue_manager.get_current_cue()
        if cue is None:
            self._progress_var.set(0)
            self._time_label.config(text="00:00 / 00:00")
            return
        
        # 计算进度
        current_pos = state.current_position
        start_time = cue.start_time
        end_time = cue.end_time if cue.end_time else 0
        
        # 获取音频时长
        audio = self._controller.cue_manager.get_audio_file(cue.audio_id)
        if audio:
            end_time = end_time if end_time > 0 else audio.duration
        
        duration = end_time - start_time
        if duration > 0:
            progress = ((current_pos - start_time) / duration) * 100
            progress = max(0, min(100, progress))
            self._progress_var.set(progress)
        else:
            self._progress_var.set(0)
        
        # 更新时间显示
        current_str = self._format_time(current_pos)
        total_str = self._format_time(end_time)
        self._time_label.config(text=f"{current_str} / {total_str}")
        
        # 更新状态标签
        if state.in_silence:
            remaining = state.silence_remaining
            self._status_label.config(text=f"静音等待中... {remaining:.1f}s")
        elif state.is_playing and not state.is_paused:
            self._status_label.config(text="播放中")
        elif state.is_paused:
            self._status_label.config(text="已暂停")
        else:
            self._status_label.config(text="就绪")
    
    def _update_cue_highlight(self) -> None:
        """更新 Cue 列表高亮"""
        if not self._cue_listbox:
            return
        
        current_index = self._controller.cue_manager.current_index
        
        # 清除所有高亮
        for i in range(self._cue_listbox.size()):
            self._cue_listbox.itemconfig(i, bg="white", fg="black")
        
        # 高亮当前 Cue
        if 0 <= current_index < self._cue_listbox.size():
            self._cue_listbox.itemconfig(current_index, bg="#4CAF50", fg="white")
            
            # 高亮下一个 Cue（预览）
            next_index = current_index + 1
            if next_index < self._cue_listbox.size():
                self._cue_listbox.itemconfig(next_index, bg="#FFC107", fg="black")
            
            # 确保当前项可见
            self._cue_listbox.see(current_index)
    
    def _update_button_states(self) -> None:
        """更新按钮状态"""
        state = self._controller.get_state()
        
        # 播放/暂停按钮状态
        # 暂停按钮在播放中或暂停状态都可用（用于暂停/继续切换）
        if state.is_playing and not state.is_paused:
            # 正在播放：播放按钮禁用，暂停按钮可用
            self._play_btn.config(state=tk.DISABLED)
            self._pause_btn.config(state=tk.NORMAL, text="暂停")
        elif state.is_paused:
            # 已暂停：播放按钮可用，暂停按钮显示"继续"
            self._play_btn.config(state=tk.NORMAL)
            self._pause_btn.config(state=tk.NORMAL, text="继续")
        else:
            # 停止状态：播放按钮可用，暂停按钮禁用
            self._play_btn.config(state=tk.NORMAL)
            self._pause_btn.config(state=tk.DISABLED, text="暂停")
    
    def _refresh_cue_list(self) -> None:
        """刷新 Cue 列表"""
        if not self._cue_listbox:
            return
        
        self._cue_listbox.delete(0, tk.END)
        
        cue_list = self._controller.cue_manager.cue_list
        for i, cue in enumerate(cue_list):
            # 获取音频信息
            audio = self._controller.cue_manager.get_audio_file(cue.audio_id)
            audio_name = audio.title if audio else cue.audio_id
            
            # 格式化显示
            start_str = self._format_time(cue.start_time)
            end_str = self._format_time(cue.end_time) if cue.end_time else "结束"
            
            display_text = f"{i+1}. {cue.label or audio_name} [{start_str} - {end_str}]"
            self._cue_listbox.insert(tk.END, display_text)
    
    def _refresh_breakpoint_list(self) -> None:
        """刷新断点列表"""
        if not self._breakpoint_listbox:
            return
        
        self._breakpoint_listbox.delete(0, tk.END)
        
        # 获取当前音频的断点
        current_audio_id = self._controller.get_state().current_audio_id
        if not current_audio_id:
            # 如果没有当前音频，获取当前 Cue 的音频
            cue = self._controller.cue_manager.get_current_cue()
            if cue:
                current_audio_id = cue.audio_id
        
        if not current_audio_id:
            return
        
        breakpoints = self._controller.breakpoint_manager.get_breakpoints(current_audio_id)
        for bp in breakpoints:
            time_str = self._format_time(bp.position)
            label = bp.label or "断点"
            auto_tag = " [自动]" if bp.auto_saved else ""
            display_text = f"{label} - {time_str}{auto_tag}"
            self._breakpoint_listbox.insert(tk.END, display_text)
    
    @staticmethod
    def _format_time(seconds: float) -> str:
        """
        格式化时间显示
        
        Args:
            seconds: 秒数
            
        Returns:
            str: 格式化的时间字符串 (MM:SS)
        """
        if seconds is None or seconds < 0:
            return "00:00"
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
    
    # ==================== 事件处理 ====================
    
    def _on_play(self) -> None:
        """播放按钮回调"""
        run_async(self._controller.play())
    
    def _on_play_progress(self, progress: float) -> None:
        """播放按钮长按进度回调"""
        # 可以在这里更新按钮视觉效果
        pass
    
    def _on_play_cancel(self) -> None:
        """播放按钮长按取消回调"""
        self._status_label.config(text="操作已取消")
    
    def _on_pause(self) -> None:
        """暂停按钮回调"""
        state = self._controller.get_state()
        if state.is_paused:
            run_async(self._controller.resume())
        else:
            run_async(self._controller.pause())
    
    def _on_pause_progress(self, progress: float) -> None:
        """暂停按钮长按进度回调"""
        pass
    
    def _on_pause_cancel(self) -> None:
        """暂停按钮长按取消回调"""
        self._status_label.config(text="操作已取消")
    
    def _on_stop(self) -> None:
        """停止按钮回调"""
        run_async(self._controller.stop())
    
    def _on_next(self) -> None:
        """下一个按钮回调"""
        run_async(self._controller.next_cue())
    
    def _on_cue_double_click(self, event: tk.Event) -> None:
        """Cue 列表双击事件"""
        selection = self._cue_listbox.curselection()
        if selection:
            index = selection[0]
            self._controller.cue_manager.set_index(index)
            run_async(self._controller.play())
    
    def _on_save_breakpoint(self) -> None:
        """保存断点"""
        bp_id = self._controller.save_breakpoint()
        if bp_id:
            self._refresh_breakpoint_list()
    
    def _on_restore_breakpoint(self) -> None:
        """恢复断点"""
        selection = self._breakpoint_listbox.curselection()
        if not selection:
            return
        
        # 获取当前音频 ID
        current_audio_id = self._controller.get_state().current_audio_id
        if not current_audio_id:
            cue = self._controller.cue_manager.get_current_cue()
            if cue:
                current_audio_id = cue.audio_id
        
        if not current_audio_id:
            return
        
        # 获取选中的断点
        breakpoints = self._controller.breakpoint_manager.get_breakpoints(current_audio_id)
        if selection[0] < len(breakpoints):
            bp = breakpoints[selection[0]]
            run_async(
                self._controller.restore_breakpoint(current_audio_id, bp.id)
            )
    
    def _on_delete_breakpoint(self) -> None:
        """删除选中的断点"""
        selection = self._breakpoint_listbox.curselection()
        if not selection:
            return
        
        # 获取当前音频 ID
        current_audio_id = self._controller.get_state().current_audio_id
        if not current_audio_id:
            cue = self._controller.cue_manager.get_current_cue()
            if cue:
                current_audio_id = cue.audio_id
        
        if not current_audio_id:
            return
        
        # 获取要删除的断点 ID
        breakpoints = self._controller.breakpoint_manager.get_breakpoints(current_audio_id)
        bp_ids = [breakpoints[i].id for i in selection if i < len(breakpoints)]
        
        # 删除断点
        self._controller.breakpoint_manager.clear_selected(bp_ids)
        self._refresh_breakpoint_list()
    
    def _on_clear_breakpoints(self) -> None:
        """清除当前音频的所有断点"""
        current_audio_id = self._controller.get_state().current_audio_id
        if not current_audio_id:
            cue = self._controller.cue_manager.get_current_cue()
            if cue:
                current_audio_id = cue.audio_id
        
        if current_audio_id:
            self._controller.breakpoint_manager.clear_audio_breakpoints(current_audio_id)
            self._refresh_breakpoint_list()
    
    # ==================== 控制器事件回调 ====================
    
    def _on_playback_started(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """播放开始事件"""
        self._refresh_breakpoint_list()
    
    def _on_playback_paused(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """播放暂停事件"""
        pass
    
    def _on_playback_stopped(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """播放停止事件"""
        pass
    
    def _on_cue_changed(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """Cue 变化事件"""
        self._refresh_breakpoint_list()
    
    def _on_breakpoint_saved(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """断点保存事件"""
        self._refresh_breakpoint_list()
    
    # ==================== 公共方法 ====================
    
    def destroy(self) -> None:
        """销毁面板"""
        if self._update_timer_id:
            self._parent.after_cancel(self._update_timer_id)
            self._update_timer_id = None
        
        if self._play_handler:
            self._play_handler.unbind()
        
        if self._pause_handler:
            self._pause_handler.unbind()
    
    def refresh(self) -> None:
        """刷新面板"""
        self._refresh_cue_list()
        self._refresh_breakpoint_list()
