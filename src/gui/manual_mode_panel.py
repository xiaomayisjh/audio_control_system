"""
手动模式面板模块

实现手动模式的 GUI 界面，包含：
- 音频列表和选择
- 入点设置和静音设置
- 播放控制（长按确认）
- 断点管理（独立存储）
- 下一条提示按钮

**Requirements: 4.1-4.6, 5.1-5.6, 10.1-10.5, 12.1-12.3**
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional, List, Dict, Any

from src.core.controller import CoreController, EventType, PlayMode
from src.gui.async_helper import run_async
from src.models.audio_track import AudioTrack
from src.models.breakpoint import Breakpoint
from src.gui.long_press import LongPressHandler


class ManualModePanel:
    """
    手动模式面板
    
    提供手动模式下的所有控制功能：
    - 音频选择和加载
    - 入点/静音设置
    - 播放控制
    - 断点管理
    
    **Requirements: 4.1-4.6, 5.1-5.6, 10.1-10.5, 12.1-12.3**
    """
    
    UPDATE_INTERVAL_MS = 100
    
    def __init__(
        self,
        parent: ttk.Frame,
        controller: CoreController
    ):
        """
        初始化手动模式面板
        
        Args:
            parent: 父容器
            controller: 核心控制器
        """
        self._parent = parent
        self._controller = controller
        
        # 当前选中的音频
        self._selected_audio: Optional[AudioTrack] = None
        
        # UI 组件
        self._audio_listbox: Optional[tk.Listbox] = None
        self._audio_info_label: Optional[ttk.Label] = None
        
        # 入点和静音设置
        self._start_pos_var: Optional[tk.StringVar] = None
        self._start_pos_entry: Optional[ttk.Entry] = None
        self._silence_var: Optional[tk.StringVar] = None
        self._silence_entry: Optional[ttk.Entry] = None
        
        # 进度显示
        self._progress_var: Optional[tk.DoubleVar] = None
        self._progress_bar: Optional[ttk.Progressbar] = None
        self._time_label: Optional[ttk.Label] = None
        self._status_label: Optional[ttk.Label] = None
        
        # 播放控制按钮
        self._play_btn: Optional[ttk.Button] = None
        self._pause_btn: Optional[ttk.Button] = None
        self._stop_btn: Optional[ttk.Button] = None
        self._replay_btn: Optional[ttk.Button] = None
        self._next_hint_btn: Optional[ttk.Button] = None
        
        # 断点相关
        self._breakpoint_listbox: Optional[tk.Listbox] = None
        self._save_bp_btn: Optional[ttk.Button] = None
        self._restore_bp_btn: Optional[ttk.Button] = None
        self._delete_bp_btn: Optional[ttk.Button] = None
        self._clear_bp_btn: Optional[ttk.Button] = None
        
        # 长按处理器
        self._play_handler: Optional[LongPressHandler] = None
        self._pause_handler: Optional[LongPressHandler] = None
        
        # 更新定时器
        self._update_timer_id: Optional[str] = None
        
        # 下一条提示状态
        self._next_hint_visible = False
        
        # 创建界面
        self._create_ui()
        
        # 注册事件监听
        self._register_listeners()
        
        # 启动更新循环
        self._start_update_loop()
    
    def _create_ui(self) -> None:
        """创建用户界面"""
        self._parent.columnconfigure(0, weight=1)
        self._parent.columnconfigure(1, weight=0)
        self._parent.rowconfigure(1, weight=1)
        
        # 顶部：状态和进度
        self._create_status_section()
        
        # 中部左侧：音频列表和设置
        self._create_audio_section()
        
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
            text="请选择音频",
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
    
    def _create_audio_section(self) -> None:
        """创建音频列表和设置区域"""
        audio_frame = ttk.LabelFrame(self._parent, text="音频列表", padding="5")
        audio_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 5))
        audio_frame.rowconfigure(0, weight=1)
        audio_frame.columnconfigure(0, weight=1)
        
        # 音频列表
        list_frame = ttk.Frame(audio_frame)
        list_frame.grid(row=0, column=0, sticky="nsew")
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        
        self._audio_listbox = tk.Listbox(
            list_frame,
            font=("微软雅黑", 11),
            selectmode=tk.SINGLE
        )
        self._audio_listbox.grid(row=0, column=0, sticky="nsew")
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._audio_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self._audio_listbox.yview)
        
        # 绑定选择事件
        self._audio_listbox.bind("<<ListboxSelect>>", self._on_audio_select)
        self._audio_listbox.bind("<Double-1>", self._on_audio_double_click)
        
        # 音频信息
        self._audio_info_label = ttk.Label(
            audio_frame,
            text="未选择音频",
            style="Status.TLabel"
        )
        self._audio_info_label.grid(row=1, column=0, sticky="w", pady=(5, 0))
        
        # 设置区域
        settings_frame = ttk.Frame(audio_frame)
        settings_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        
        # 入点设置
        ttk.Label(settings_frame, text="入点 (秒):").grid(row=0, column=0, sticky="w")
        self._start_pos_var = tk.StringVar(value="0")
        self._start_pos_entry = ttk.Entry(
            settings_frame,
            textvariable=self._start_pos_var,
            width=10
        )
        self._start_pos_entry.grid(row=0, column=1, padx=(5, 20))
        self._start_pos_entry.bind("<Return>", self._on_start_pos_change)
        self._start_pos_entry.bind("<FocusOut>", self._on_start_pos_change)
        
        # 前置静音设置
        ttk.Label(settings_frame, text="前置静音 (秒):").grid(row=0, column=2, sticky="w")
        self._silence_var = tk.StringVar(value="0")
        self._silence_entry = ttk.Entry(
            settings_frame,
            textvariable=self._silence_var,
            width=10
        )
        self._silence_entry.grid(row=0, column=3, padx=(5, 0))
        self._silence_entry.bind("<Return>", self._on_silence_change)
        self._silence_entry.bind("<FocusOut>", self._on_silence_change)
        
        # 刷新音频列表
        self._refresh_audio_list()
    
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
        
        # 重播按钮
        self._replay_btn = ttk.Button(
            btn_container,
            text="🔄 重播",
            width=10,
            command=self._on_replay
        )
        self._replay_btn.pack(side=tk.LEFT, padx=5)
        
        # 下一条提示按钮
        self._next_hint_btn = ttk.Button(
            btn_container,
            text="⏭ 下一条",
            width=10,
            command=self._on_next_hint
        )
        self._next_hint_btn.pack(side=tk.LEFT, padx=5)
    
    def _register_listeners(self) -> None:
        """注册控制器事件监听"""
        self._controller.add_listener(EventType.PLAYBACK_STARTED, self._on_playback_started)
        self._controller.add_listener(EventType.PLAYBACK_PAUSED, self._on_playback_paused)
        self._controller.add_listener(EventType.PLAYBACK_STOPPED, self._on_playback_stopped)
        self._controller.add_listener(EventType.PLAYBACK_COMPLETED, self._on_playback_completed)
        self._controller.add_listener(EventType.BREAKPOINT_SAVED, self._on_breakpoint_saved)
    
    def _start_update_loop(self) -> None:
        """启动更新循环"""
        self._update_ui()
    
    def _update_ui(self) -> None:
        """更新 UI 状态"""
        try:
            self._update_progress()
            self._update_button_states()
            self._update_next_hint()
        except Exception as e:
            print(f"UI update error: {e}")
        
        self._update_timer_id = self._parent.after(
            self.UPDATE_INTERVAL_MS,
            self._update_ui
        )
    
    def _update_progress(self) -> None:
        """更新进度条和时间显示"""
        state = self._controller.get_state()
        
        if not self._selected_audio:
            self._progress_var.set(0)
            self._time_label.config(text="00:00 / 00:00")
            return
        
        current_pos = state.current_position
        duration = self._selected_audio.duration
        
        if duration > 0:
            progress = (current_pos / duration) * 100
            progress = max(0, min(100, progress))
            self._progress_var.set(progress)
        else:
            self._progress_var.set(0)
        
        current_str = self._format_time(current_pos)
        total_str = self._format_time(duration)
        self._time_label.config(text=f"{current_str} / {total_str}")
        
        # 更新状态标签
        if state.in_silence:
            remaining = state.silence_remaining
            self._status_label.config(text=f"静音等待中... {remaining:.1f}s")
        elif state.is_playing and not state.is_paused:
            self._status_label.config(text="播放中")
        elif state.is_paused:
            self._status_label.config(text="已暂停")
        elif self._selected_audio:
            self._status_label.config(text=f"已选择: {self._selected_audio.title}")
        else:
            self._status_label.config(text="请选择音频")
    
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
            # 停止状态：播放按钮可用（如果有选中音频），暂停按钮禁用
            self._play_btn.config(state=tk.NORMAL if self._selected_audio else tk.DISABLED)
            self._pause_btn.config(state=tk.DISABLED, text="暂停")
    
    def _update_next_hint(self) -> None:
        """更新下一条提示按钮状态"""
        # 当音频播放完成时高亮显示
        state = self._controller.get_state()
        
        if self._next_hint_visible:
            self._next_hint_btn.config(style="Danger.TButton")
        else:
            self._next_hint_btn.config(style="TButton")
    
    def _refresh_audio_list(self) -> None:
        """刷新音频列表"""
        if not self._audio_listbox:
            return
        
        self._audio_listbox.delete(0, tk.END)
        
        audio_files = self._controller.cue_manager.audio_files
        for i, audio in enumerate(audio_files):
            duration_str = self._format_time(audio.duration)
            display_text = f"{i+1}. {audio.title} [{duration_str}]"
            self._audio_listbox.insert(tk.END, display_text)
    
    def _refresh_breakpoint_list(self) -> None:
        """刷新断点列表"""
        if not self._breakpoint_listbox:
            return
        
        self._breakpoint_listbox.delete(0, tk.END)
        
        if not self._selected_audio:
            return
        
        breakpoints = self._controller.breakpoint_manager.get_breakpoints(
            self._selected_audio.id
        )
        for bp in breakpoints:
            time_str = self._format_time(bp.position)
            label = bp.label or "断点"
            auto_tag = " [自动]" if bp.auto_saved else ""
            display_text = f"{label} - {time_str}{auto_tag}"
            self._breakpoint_listbox.insert(tk.END, display_text)
    
    @staticmethod
    def _format_time(seconds: float) -> str:
        """格式化时间显示"""
        if seconds is None or seconds < 0:
            return "00:00"
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
    
    # ==================== 事件处理 ====================
    
    def _on_audio_select(self, event: tk.Event) -> None:
        """音频选择事件"""
        selection = self._audio_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        audio_files = self._controller.cue_manager.audio_files
        if index < len(audio_files):
            self._selected_audio = audio_files[index]
            self._controller.set_manual_audio(self._selected_audio)
            
            # 更新音频信息
            duration_str = self._format_time(self._selected_audio.duration)
            self._audio_info_label.config(
                text=f"{self._selected_audio.title} - 时长: {duration_str}"
            )
            
            # 重置入点和静音设置
            self._start_pos_var.set("0")
            self._silence_var.set("0")
            
            # 刷新断点列表
            self._refresh_breakpoint_list()
    
    def _on_audio_double_click(self, event: tk.Event) -> None:
        """音频双击播放"""
        if self._selected_audio:
            self._on_play()
    
    def _on_start_pos_change(self, event: tk.Event = None) -> None:
        """入点设置变化"""
        try:
            start_pos = float(self._start_pos_var.get())
            self._controller.set_manual_start_position(start_pos)
        except ValueError:
            self._start_pos_var.set("0")
    
    def _on_silence_change(self, event: tk.Event = None) -> None:
        """静音设置变化"""
        try:
            silence = float(self._silence_var.get())
            self._controller.set_manual_silence_before(silence)
        except ValueError:
            self._silence_var.set("0")
    
    def _on_play(self) -> None:
        """播放按钮回调"""
        if self._selected_audio:
            # 应用入点和静音设置
            self._on_start_pos_change()
            self._on_silence_change()
            run_async(self._controller.play())
            self._next_hint_visible = False
    
    def _on_play_progress(self, progress: float) -> None:
        """播放按钮长按进度回调"""
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
    
    def _on_replay(self) -> None:
        """重播按钮回调"""
        run_async(self._controller.replay())
        self._next_hint_visible = False
    
    def _on_next_hint(self) -> None:
        """下一条提示按钮回调"""
        # 选择下一个音频
        if not self._audio_listbox:
            return
        
        selection = self._audio_listbox.curselection()
        current_index = selection[0] if selection else -1
        next_index = current_index + 1
        
        audio_files = self._controller.cue_manager.audio_files
        if next_index < len(audio_files):
            self._audio_listbox.selection_clear(0, tk.END)
            self._audio_listbox.selection_set(next_index)
            self._audio_listbox.see(next_index)
            self._audio_listbox.event_generate("<<ListboxSelect>>")
        
        self._next_hint_visible = False
    
    def _on_save_breakpoint(self) -> None:
        """保存断点"""
        if self._selected_audio:
            bp_id = self._controller.save_breakpoint()
            if bp_id:
                self._refresh_breakpoint_list()
    
    def _on_restore_breakpoint(self) -> None:
        """恢复断点"""
        selection = self._breakpoint_listbox.curselection()
        if not selection or not self._selected_audio:
            return
        
        breakpoints = self._controller.breakpoint_manager.get_breakpoints(
            self._selected_audio.id
        )
        if selection[0] < len(breakpoints):
            bp = breakpoints[selection[0]]
            run_async(
                self._controller.restore_breakpoint(self._selected_audio.id, bp.id)
            )
    
    def _on_delete_breakpoint(self) -> None:
        """删除选中的断点"""
        selection = self._breakpoint_listbox.curselection()
        if not selection or not self._selected_audio:
            return
        
        breakpoints = self._controller.breakpoint_manager.get_breakpoints(
            self._selected_audio.id
        )
        bp_ids = [breakpoints[i].id for i in selection if i < len(breakpoints)]
        
        self._controller.breakpoint_manager.clear_selected(bp_ids)
        self._refresh_breakpoint_list()
    
    def _on_clear_breakpoints(self) -> None:
        """清除当前音频的所有断点"""
        if self._selected_audio:
            self._controller.breakpoint_manager.clear_audio_breakpoints(
                self._selected_audio.id
            )
            self._refresh_breakpoint_list()
    
    # ==================== 控制器事件回调 ====================
    
    def _on_playback_started(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """播放开始事件"""
        pass
    
    def _on_playback_paused(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """播放暂停事件"""
        pass
    
    def _on_playback_stopped(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """播放停止事件"""
        pass
    
    def _on_playback_completed(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """播放完成事件 - 显示下一条提示"""
        self._next_hint_visible = True
        # 高亮下一个音频
        if self._audio_listbox:
            selection = self._audio_listbox.curselection()
            if selection:
                current_index = selection[0]
                next_index = current_index + 1
                if next_index < self._audio_listbox.size():
                    # 高亮下一个
                    self._audio_listbox.itemconfig(next_index, bg="#FFC107", fg="black")
    
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
        self._refresh_audio_list()
        self._refresh_breakpoint_list()
