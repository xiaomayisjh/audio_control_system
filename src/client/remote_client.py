"""
远程客户端主窗口模块

实现 Tkinter 远程客户端，包含：
- 与本地控制台相同的界面布局
- API 地址配置组件
- 通过 API 远程控制音效系统

**Requirements: 16.1-16.2**
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Optional, Dict, Any, List, Callable
import threading

from src.client.api_client import SyncAPIClient, APIResponse, ConnectionState


class RemoteClient:
    """
    远程客户端主窗口
    
    提供与本地控制台相同的界面布局，通过 API 远程控制音效系统。
    
    **Requirements: 16.1-16.2**
    """
    
    WINDOW_TITLE = "舞台剧音效控制台 - 远程客户端"
    WINDOW_MIN_WIDTH = 900
    WINDOW_MIN_HEIGHT = 700
    
    # 更新间隔（毫秒）
    UPDATE_INTERVAL_MS = 200
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8080
    ):
        """
        初始化远程客户端
        
        Args:
            host: 服务器地址
            port: 服务器端口
        """
        self._host = host
        self._port = port
        
        # API 客户端
        self._api_client = SyncAPIClient(host, port)
        
        # 主窗口
        self._root: Optional[tk.Tk] = None
        
        # 连接配置组件
        self._host_var: Optional[tk.StringVar] = None
        self._port_var: Optional[tk.StringVar] = None
        self._connect_btn: Optional[ttk.Button] = None
        self._status_label: Optional[ttk.Label] = None
        
        # 模式切换
        self._notebook: Optional[ttk.Notebook] = None
        
        # 自动模式组件
        self._auto_cue_listbox: Optional[tk.Listbox] = None
        self._auto_progress_var: Optional[tk.DoubleVar] = None
        self._auto_time_label: Optional[ttk.Label] = None
        self._auto_status_label: Optional[ttk.Label] = None
        self._auto_bp_listbox: Optional[tk.Listbox] = None
        
        # 手动模式组件
        self._manual_audio_listbox: Optional[tk.Listbox] = None
        self._manual_progress_var: Optional[tk.DoubleVar] = None
        self._manual_time_label: Optional[ttk.Label] = None
        self._manual_status_label: Optional[ttk.Label] = None
        self._manual_bp_listbox: Optional[tk.Listbox] = None
        self._start_pos_var: Optional[tk.StringVar] = None
        self._silence_var: Optional[tk.StringVar] = None
        
        # 音量控制
        self._bgm_volume_var: Optional[tk.DoubleVar] = None
        self._sfx_volume_var: Optional[tk.DoubleVar] = None
        self._bgm_value_label: Optional[ttk.Label] = None
        self._sfx_value_label: Optional[ttk.Label] = None
        
        # 音效按钮
        self._sfx_buttons: Dict[str, tk.Button] = {}
        self._sfx_frame: Optional[ttk.Frame] = None
        
        # 状态缓存
        self._current_state: Dict[str, Any] = {}
        self._cue_list: List[Dict[str, Any]] = []
        self._audio_list: List[Dict[str, Any]] = []
        self._breakpoints: Dict[str, List[Dict[str, Any]]] = {}
        
        # 选中的音频
        self._selected_audio_id: Optional[str] = None
        
        # 更新定时器
        self._update_timer_id: Optional[str] = None
        
        # 运行状态
        self._is_running = False
    
    def create(self) -> tk.Tk:
        """
        创建主窗口
        
        Returns:
            tk.Tk: 主窗口实例
        """
        self._root = tk.Tk()
        self._root.title(self.WINDOW_TITLE)
        self._root.minsize(self.WINDOW_MIN_WIDTH, self.WINDOW_MIN_HEIGHT)
        
        # 设置窗口关闭处理
        self._root.protocol("WM_DELETE_WINDOW", self._on_close_request)
        
        # 配置样式
        self._configure_styles()
        
        # 创建主布局
        self._create_layout()
        
        # 注册 API 回调
        self._api_client.add_state_callback(self._on_state_update)
        self._api_client.add_connection_callback(self._on_connection_change)
        
        return self._root
    
    def _configure_styles(self) -> None:
        """配置 ttk 样式"""
        style = ttk.Style()
        
        style.configure("TNotebook", background="#f0f0f0")
        style.configure("TNotebook.Tab", padding=[20, 10], font=("微软雅黑", 12))
        style.configure("TFrame", background="#f0f0f0")
        style.configure("TLabel", background="#f0f0f0", font=("微软雅黑", 10))
        style.configure("Title.TLabel", font=("微软雅黑", 14, "bold"))
        style.configure("Status.TLabel", font=("微软雅黑", 11))
        style.configure("TButton", font=("微软雅黑", 10), padding=[10, 5])
        style.configure("Play.TButton", font=("微软雅黑", 12, "bold"))
        style.configure("Connected.TLabel", foreground="green")
        style.configure("Disconnected.TLabel", foreground="red")
    
    def _create_layout(self) -> None:
        """创建主布局"""
        if not self._root:
            return
        
        main_container = ttk.Frame(self._root, padding="10")
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # 顶部：连接配置
        self._create_connection_section(main_container)
        
        # 中部：模式切换 Tab
        self._create_mode_tabs(main_container)
        
        # 底部：音效和音量控制
        bottom_frame = ttk.Frame(main_container)
        bottom_frame.pack(fill=tk.X, pady=(10, 0))
        
        # 音效面板
        sfx_frame = ttk.LabelFrame(bottom_frame, text="音效", padding="5")
        sfx_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        self._sfx_frame = sfx_frame
        
        # 音量控制面板
        volume_frame = ttk.LabelFrame(bottom_frame, text="音量控制", padding="5")
        volume_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        self._create_volume_section(volume_frame)
    
    def _create_connection_section(self, parent: ttk.Frame) -> None:
        """创建连接配置区域"""
        conn_frame = ttk.LabelFrame(parent, text="服务器连接", padding="5")
        conn_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 地址输入
        ttk.Label(conn_frame, text="地址:").pack(side=tk.LEFT, padx=(0, 5))
        self._host_var = tk.StringVar(value=self._host)
        host_entry = ttk.Entry(conn_frame, textvariable=self._host_var, width=20)
        host_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        # 端口输入
        ttk.Label(conn_frame, text="端口:").pack(side=tk.LEFT, padx=(0, 5))
        self._port_var = tk.StringVar(value=str(self._port))
        port_entry = ttk.Entry(conn_frame, textvariable=self._port_var, width=8)
        port_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        # 连接按钮
        self._connect_btn = ttk.Button(
            conn_frame,
            text="连接",
            command=self._on_connect_click
        )
        self._connect_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 状态标签
        self._status_label = ttk.Label(
            conn_frame,
            text="未连接",
            style="Disconnected.TLabel"
        )
        self._status_label.pack(side=tk.LEFT)
        
        # 上传按钮
        upload_btn = ttk.Button(
            conn_frame,
            text="上传音频",
            command=self._on_upload_click
        )
        upload_btn.pack(side=tk.RIGHT)
    
    def _create_mode_tabs(self, parent: ttk.Frame) -> None:
        """创建模式切换 Tab"""
        self._notebook = ttk.Notebook(parent)
        self._notebook.pack(fill=tk.BOTH, expand=True)
        
        # 自动模式 Tab
        auto_frame = ttk.Frame(self._notebook, padding="10")
        self._notebook.add(auto_frame, text="自动模式")
        self._create_auto_mode_panel(auto_frame)
        
        # 手动模式 Tab
        manual_frame = ttk.Frame(self._notebook, padding="10")
        self._notebook.add(manual_frame, text="手动模式")
        self._create_manual_mode_panel(manual_frame)
        
        # 绑定 Tab 切换事件
        self._notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
    
    def _create_auto_mode_panel(self, parent: ttk.Frame) -> None:
        """创建自动模式面板"""
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=0)
        parent.rowconfigure(1, weight=1)
        
        # 状态和进度
        status_frame = ttk.Frame(parent)
        status_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        status_frame.columnconfigure(0, weight=1)
        
        self._auto_status_label = ttk.Label(status_frame, text="就绪", style="Status.TLabel")
        self._auto_status_label.grid(row=0, column=0, sticky="w")
        
        self._auto_time_label = ttk.Label(status_frame, text="00:00 / 00:00", style="Status.TLabel")
        self._auto_time_label.grid(row=0, column=1, sticky="e")
        
        self._auto_progress_var = tk.DoubleVar(value=0)
        progress_bar = ttk.Progressbar(status_frame, variable=self._auto_progress_var, maximum=100)
        progress_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        
        # Cue 列表
        cue_frame = ttk.LabelFrame(parent, text="Cue 列表", padding="5")
        cue_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 5))
        cue_frame.rowconfigure(0, weight=1)
        cue_frame.columnconfigure(0, weight=1)
        
        list_frame = ttk.Frame(cue_frame)
        list_frame.grid(row=0, column=0, sticky="nsew")
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        
        self._auto_cue_listbox = tk.Listbox(list_frame, font=("微软雅黑", 11), selectmode=tk.SINGLE)
        self._auto_cue_listbox.grid(row=0, column=0, sticky="nsew")
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._auto_cue_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self._auto_cue_listbox.yview)
        
        self._auto_cue_listbox.bind("<Double-1>", self._on_auto_cue_double_click)
        
        # 断点列表
        bp_frame = ttk.LabelFrame(parent, text="断点", padding="5")
        bp_frame.grid(row=1, column=1, sticky="nsew")
        bp_frame.rowconfigure(0, weight=1)
        bp_frame.columnconfigure(0, weight=1)
        
        bp_list_frame = ttk.Frame(bp_frame)
        bp_list_frame.grid(row=0, column=0, sticky="nsew")
        bp_list_frame.rowconfigure(0, weight=1)
        bp_list_frame.columnconfigure(0, weight=1)
        
        self._auto_bp_listbox = tk.Listbox(bp_list_frame, font=("微软雅黑", 10), selectmode=tk.EXTENDED, width=25)
        self._auto_bp_listbox.grid(row=0, column=0, sticky="nsew")
        
        bp_scrollbar = ttk.Scrollbar(bp_list_frame, orient=tk.VERTICAL)
        bp_scrollbar.grid(row=0, column=1, sticky="ns")
        self._auto_bp_listbox.config(yscrollcommand=bp_scrollbar.set)
        bp_scrollbar.config(command=self._auto_bp_listbox.yview)
        
        # 断点按钮
        bp_btn_frame = ttk.Frame(bp_frame)
        bp_btn_frame.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        
        ttk.Button(bp_btn_frame, text="保存", command=self._on_auto_save_bp).pack(side=tk.LEFT, padx=2)
        ttk.Button(bp_btn_frame, text="恢复", command=self._on_auto_restore_bp).pack(side=tk.LEFT, padx=2)
        ttk.Button(bp_btn_frame, text="删除", command=self._on_auto_delete_bp).pack(side=tk.LEFT, padx=2)
        
        # 播放控制
        control_frame = ttk.Frame(parent)
        control_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        
        btn_container = ttk.Frame(control_frame)
        btn_container.pack(anchor=tk.CENTER)
        
        ttk.Button(btn_container, text="▶ 播放", style="Play.TButton", width=10, command=self._on_play).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_container, text="⏸ 暂停", width=10, command=self._on_pause).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_container, text="⏹ 停止", width=10, command=self._on_stop).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_container, text="⏭ 下一个", width=10, command=self._on_next).pack(side=tk.LEFT, padx=5)

    def _create_manual_mode_panel(self, parent: ttk.Frame) -> None:
        """创建手动模式面板"""
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=0)
        parent.rowconfigure(1, weight=1)
        
        # 状态和进度
        status_frame = ttk.Frame(parent)
        status_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        status_frame.columnconfigure(0, weight=1)
        
        self._manual_status_label = ttk.Label(status_frame, text="请选择音频", style="Status.TLabel")
        self._manual_status_label.grid(row=0, column=0, sticky="w")
        
        self._manual_time_label = ttk.Label(status_frame, text="00:00 / 00:00", style="Status.TLabel")
        self._manual_time_label.grid(row=0, column=1, sticky="e")
        
        self._manual_progress_var = tk.DoubleVar(value=0)
        progress_bar = ttk.Progressbar(status_frame, variable=self._manual_progress_var, maximum=100)
        progress_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        
        # 音频列表
        audio_frame = ttk.LabelFrame(parent, text="音频列表", padding="5")
        audio_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 5))
        audio_frame.rowconfigure(0, weight=1)
        audio_frame.columnconfigure(0, weight=1)
        
        list_frame = ttk.Frame(audio_frame)
        list_frame.grid(row=0, column=0, sticky="nsew")
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        
        self._manual_audio_listbox = tk.Listbox(list_frame, font=("微软雅黑", 11), selectmode=tk.SINGLE)
        self._manual_audio_listbox.grid(row=0, column=0, sticky="nsew")
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._manual_audio_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self._manual_audio_listbox.yview)
        
        self._manual_audio_listbox.bind("<<ListboxSelect>>", self._on_audio_select)
        self._manual_audio_listbox.bind("<Double-1>", self._on_audio_double_click)
        
        # 设置区域
        settings_frame = ttk.Frame(audio_frame)
        settings_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        
        ttk.Label(settings_frame, text="入点 (秒):").grid(row=0, column=0, sticky="w")
        self._start_pos_var = tk.StringVar(value="0")
        ttk.Entry(settings_frame, textvariable=self._start_pos_var, width=10).grid(row=0, column=1, padx=(5, 20))
        
        ttk.Label(settings_frame, text="前置静音 (秒):").grid(row=0, column=2, sticky="w")
        self._silence_var = tk.StringVar(value="0")
        ttk.Entry(settings_frame, textvariable=self._silence_var, width=10).grid(row=0, column=3, padx=(5, 0))
        
        # 断点列表
        bp_frame = ttk.LabelFrame(parent, text="断点", padding="5")
        bp_frame.grid(row=1, column=1, sticky="nsew")
        bp_frame.rowconfigure(0, weight=1)
        bp_frame.columnconfigure(0, weight=1)
        
        bp_list_frame = ttk.Frame(bp_frame)
        bp_list_frame.grid(row=0, column=0, sticky="nsew")
        bp_list_frame.rowconfigure(0, weight=1)
        bp_list_frame.columnconfigure(0, weight=1)
        
        self._manual_bp_listbox = tk.Listbox(bp_list_frame, font=("微软雅黑", 10), selectmode=tk.EXTENDED, width=25)
        self._manual_bp_listbox.grid(row=0, column=0, sticky="nsew")
        
        bp_scrollbar = ttk.Scrollbar(bp_list_frame, orient=tk.VERTICAL)
        bp_scrollbar.grid(row=0, column=1, sticky="ns")
        self._manual_bp_listbox.config(yscrollcommand=bp_scrollbar.set)
        bp_scrollbar.config(command=self._manual_bp_listbox.yview)
        
        # 断点按钮
        bp_btn_frame = ttk.Frame(bp_frame)
        bp_btn_frame.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        
        ttk.Button(bp_btn_frame, text="保存", command=self._on_manual_save_bp).pack(side=tk.LEFT, padx=2)
        ttk.Button(bp_btn_frame, text="恢复", command=self._on_manual_restore_bp).pack(side=tk.LEFT, padx=2)
        ttk.Button(bp_btn_frame, text="删除", command=self._on_manual_delete_bp).pack(side=tk.LEFT, padx=2)
        ttk.Button(bp_btn_frame, text="清除全部", command=self._on_manual_clear_bp).pack(side=tk.LEFT, padx=2)
        
        # 播放控制
        control_frame = ttk.Frame(parent)
        control_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        
        btn_container = ttk.Frame(control_frame)
        btn_container.pack(anchor=tk.CENTER)
        
        ttk.Button(btn_container, text="▶ 播放", style="Play.TButton", width=10, command=self._on_play).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_container, text="⏸ 暂停", width=10, command=self._on_pause).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_container, text="⏹ 停止", width=10, command=self._on_stop).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_container, text="🔄 重播", width=10, command=self._on_replay).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_container, text="⏭ 下一条", width=10, command=self._on_next_hint).pack(side=tk.LEFT, padx=5)
    
    def _create_volume_section(self, parent: ttk.Frame) -> None:
        """创建音量控制区域"""
        # BGM 音量
        bgm_frame = ttk.Frame(parent)
        bgm_frame.pack(fill=tk.X, padx=5, pady=5)
        
        title_frame = ttk.Frame(bgm_frame)
        title_frame.pack(fill=tk.X)
        
        ttk.Label(title_frame, text="BGM 音量", font=("微软雅黑", 10, "bold")).pack(side=tk.LEFT)
        self._bgm_value_label = ttk.Label(title_frame, text="100%", font=("微软雅黑", 9))
        self._bgm_value_label.pack(side=tk.RIGHT)
        
        self._bgm_volume_var = tk.DoubleVar(value=100)
        bgm_slider = ttk.Scale(
            bgm_frame, from_=0, to=100, orient=tk.HORIZONTAL,
            variable=self._bgm_volume_var, command=self._on_bgm_volume_change, length=150
        )
        bgm_slider.pack(fill=tk.X, pady=(5, 0))
        
        # 分隔线
        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        # 音效音量
        sfx_frame = ttk.Frame(parent)
        sfx_frame.pack(fill=tk.X, padx=5, pady=5)
        
        title_frame2 = ttk.Frame(sfx_frame)
        title_frame2.pack(fill=tk.X)
        
        ttk.Label(title_frame2, text="音效音量", font=("微软雅黑", 10, "bold")).pack(side=tk.LEFT)
        self._sfx_value_label = ttk.Label(title_frame2, text="100%", font=("微软雅黑", 9))
        self._sfx_value_label.pack(side=tk.RIGHT)
        
        self._sfx_volume_var = tk.DoubleVar(value=100)
        sfx_slider = ttk.Scale(
            sfx_frame, from_=0, to=100, orient=tk.HORIZONTAL,
            variable=self._sfx_volume_var, command=self._on_sfx_volume_change, length=150
        )
        sfx_slider.pack(fill=tk.X, pady=(5, 0))
    
    # ==================== 连接管理 ====================
    
    def _on_connect_click(self) -> None:
        """连接按钮点击"""
        if self._api_client.is_connected:
            # 断开连接
            self._disconnect()
        else:
            # 连接
            self._connect()
    
    def _connect(self) -> None:
        """连接到服务器"""
        host = self._host_var.get().strip()
        port_str = self._port_var.get().strip()
        
        try:
            port = int(port_str)
        except ValueError:
            messagebox.showerror("错误", "端口必须是数字")
            return
        
        self._api_client.set_server(host, port)
        self._status_label.config(text="连接中...", style="TLabel")
        self._connect_btn.config(state=tk.DISABLED)
        
        # 在后台线程连接
        def do_connect():
            success = self._api_client.connect()
            if self._root:
                self._root.after(0, lambda: self._on_connect_result(success))
        
        threading.Thread(target=do_connect, daemon=True).start()
    
    def _on_connect_result(self, success: bool) -> None:
        """连接结果回调"""
        self._connect_btn.config(state=tk.NORMAL)
        
        if success:
            self._connect_btn.config(text="断开")
            self._status_label.config(text="已连接", style="Connected.TLabel")
            self._start_update_loop()
            self._load_initial_data()
        else:
            self._status_label.config(text="连接失败", style="Disconnected.TLabel")
            messagebox.showerror("错误", "无法连接到服务器")
    
    def _disconnect(self) -> None:
        """断开连接"""
        self._stop_update_loop()
        self._api_client.disconnect()
        self._connect_btn.config(text="连接")
        self._status_label.config(text="未连接", style="Disconnected.TLabel")
    
    def _on_connection_change(self, state: ConnectionState) -> None:
        """连接状态变化回调"""
        if not self._root:
            return
        
        def update_ui():
            if state == ConnectionState.CONNECTED:
                self._status_label.config(text="已连接", style="Connected.TLabel")
                self._connect_btn.config(text="断开")
            elif state == ConnectionState.DISCONNECTED:
                self._status_label.config(text="未连接", style="Disconnected.TLabel")
                self._connect_btn.config(text="连接")
            elif state == ConnectionState.RECONNECTING:
                self._status_label.config(text="重连中...", style="TLabel")
        
        self._root.after(0, update_ui)
    
    # ==================== 数据加载 ====================
    
    def _load_initial_data(self) -> None:
        """加载初始数据"""
        def do_load():
            # 加载状态
            state_resp = self._api_client.get_state()
            if state_resp.success and state_resp.data:
                self._current_state = state_resp.data
            
            # 加载 Cue 列表
            cues_resp = self._api_client.get_cues()
            if cues_resp.success and cues_resp.data:
                self._cue_list = cues_resp.data.get("cues", [])
            
            # 加载音频列表
            audio_resp = self._api_client.get_audio_list()
            if audio_resp.success and audio_resp.data:
                self._audio_list = audio_resp.data.get("audio_files", [])
            
            # 加载音量
            volume_resp = self._api_client.get_volume()
            if volume_resp.success and volume_resp.data:
                bgm_vol = volume_resp.data.get("bgm_volume", 1.0)
                sfx_vol = volume_resp.data.get("sfx_volume", 1.0)
                if self._root:
                    self._root.after(0, lambda: self._update_volume_ui(bgm_vol, sfx_vol))
            
            # 更新 UI
            if self._root:
                self._root.after(0, self._refresh_all_lists)
        
        threading.Thread(target=do_load, daemon=True).start()
    
    def _refresh_all_lists(self) -> None:
        """刷新所有列表"""
        self._refresh_cue_list()
        self._refresh_audio_list()
        self._refresh_sfx_buttons()
    
    def _refresh_cue_list(self) -> None:
        """刷新 Cue 列表"""
        if not self._auto_cue_listbox:
            return
        
        self._auto_cue_listbox.delete(0, tk.END)
        
        for i, cue in enumerate(self._cue_list):
            audio_id = cue.get("audio_id", "")
            label = cue.get("label", "")
            start_time = cue.get("start_time", 0)
            end_time = cue.get("end_time")
            
            # 查找音频标题
            audio_title = audio_id
            for audio in self._audio_list:
                if audio.get("id") == audio_id:
                    audio_title = audio.get("title", audio_id)
                    break
            
            start_str = self._format_time(start_time)
            end_str = self._format_time(end_time) if end_time else "结束"
            
            display_text = f"{i+1}. {label or audio_title} [{start_str} - {end_str}]"
            self._auto_cue_listbox.insert(tk.END, display_text)
        
        # 高亮当前 Cue
        current_index = self._current_state.get("current_cue_index", 0)
        self._update_cue_highlight(current_index)
    
    def _refresh_audio_list(self) -> None:
        """刷新音频列表"""
        if not self._manual_audio_listbox:
            return
        
        self._manual_audio_listbox.delete(0, tk.END)
        
        for i, audio in enumerate(self._audio_list):
            title = audio.get("title", "Unknown")
            duration = audio.get("duration", 0)
            duration_str = self._format_time(duration)
            
            display_text = f"{i+1}. {title} [{duration_str}]"
            self._manual_audio_listbox.insert(tk.END, display_text)
    
    def _refresh_sfx_buttons(self) -> None:
        """刷新音效按钮"""
        if not self._sfx_frame:
            return
        
        # 清除现有按钮
        for widget in self._sfx_frame.winfo_children():
            widget.destroy()
        self._sfx_buttons.clear()
        
        # 获取音效列表
        sfx_list = [a for a in self._audio_list if a.get("track_type") == "sfx"]
        
        if not sfx_list:
            ttk.Label(self._sfx_frame, text="暂无音效", style="Status.TLabel").pack(pady=20)
            return
        
        # 创建按钮网格
        columns = 4
        for index, sfx in enumerate(sfx_list):
            sfx_id = sfx.get("id")
            title = sfx.get("title", "Unknown")
            
            row = index // columns
            col = index % columns
            
            btn = tk.Button(
                self._sfx_frame,
                text=title,
                width=12,
                height=2,
                font=("微软雅黑", 10),
                bg="#E0E0E0",
                command=lambda sid=sfx_id: self._on_sfx_click(sid)
            )
            btn.grid(row=row, column=col, padx=3, pady=3)
            self._sfx_buttons[sfx_id] = btn
    
    def _refresh_breakpoint_list(self, audio_id: str, listbox: tk.Listbox) -> None:
        """刷新断点列表"""
        listbox.delete(0, tk.END)
        
        breakpoints = self._breakpoints.get(audio_id, [])
        for bp in breakpoints:
            position = bp.get("position", 0)
            label = bp.get("label", "断点")
            auto_saved = bp.get("auto_saved", False)
            
            time_str = self._format_time(position)
            auto_tag = " [自动]" if auto_saved else ""
            display_text = f"{label} - {time_str}{auto_tag}"
            listbox.insert(tk.END, display_text)
    
    def _load_breakpoints(self, audio_id: str) -> None:
        """加载断点"""
        def do_load():
            resp = self._api_client.get_breakpoints(audio_id)
            if resp.success and resp.data:
                self._breakpoints[audio_id] = resp.data.get("breakpoints", [])
                if self._root:
                    self._root.after(0, lambda: self._on_breakpoints_loaded(audio_id))
        
        threading.Thread(target=do_load, daemon=True).start()
    
    def _on_breakpoints_loaded(self, audio_id: str) -> None:
        """断点加载完成"""
        # 根据当前模式刷新对应的断点列表
        current_tab = self._notebook.index(self._notebook.select()) if self._notebook else 0
        
        if current_tab == 0:
            # 自动模式
            current_cue_index = self._current_state.get("current_cue_index", 0)
            if current_cue_index < len(self._cue_list):
                cue = self._cue_list[current_cue_index]
                if cue.get("audio_id") == audio_id:
                    self._refresh_breakpoint_list(audio_id, self._auto_bp_listbox)
        else:
            # 手动模式
            if self._selected_audio_id == audio_id:
                self._refresh_breakpoint_list(audio_id, self._manual_bp_listbox)

    # ==================== 状态更新 ====================
    
    def _start_update_loop(self) -> None:
        """启动更新循环"""
        self._is_running = True
        self._update_ui()
    
    def _stop_update_loop(self) -> None:
        """停止更新循环"""
        self._is_running = False
        if self._update_timer_id:
            self._root.after_cancel(self._update_timer_id)
            self._update_timer_id = None
    
    def _update_ui(self) -> None:
        """更新 UI"""
        if not self._is_running or not self._root:
            return
        
        try:
            self._update_progress()
            self._update_cue_highlight(self._current_state.get("current_cue_index", 0))
        except Exception as e:
            print(f"UI update error: {e}")
        
        self._update_timer_id = self._root.after(self.UPDATE_INTERVAL_MS, self._update_ui)
    
    def _on_state_update(self, state: Dict[str, Any]) -> None:
        """状态更新回调"""
        self._current_state = state
        
        if self._root:
            self._root.after(0, self._update_progress)
    
    def _update_progress(self) -> None:
        """更新进度显示"""
        state = self._current_state
        
        is_playing = state.get("is_playing", False)
        is_paused = state.get("is_paused", False)
        current_position = state.get("current_position", 0)
        in_silence = state.get("in_silence", False)
        silence_remaining = state.get("silence_remaining", 0)
        
        # 更新状态标签
        if in_silence:
            status_text = f"静音等待中... {silence_remaining:.1f}s"
        elif is_playing and not is_paused:
            status_text = "播放中"
        elif is_paused:
            status_text = "已暂停"
        else:
            status_text = "就绪"
        
        # 根据当前模式更新对应的 UI
        current_tab = self._notebook.index(self._notebook.select()) if self._notebook else 0
        
        if current_tab == 0:
            # 自动模式
            if self._auto_status_label:
                self._auto_status_label.config(text=status_text)
            
            # 获取当前 Cue 的时长
            current_cue_index = state.get("current_cue_index", 0)
            duration = 0
            if current_cue_index < len(self._cue_list):
                cue = self._cue_list[current_cue_index]
                end_time = cue.get("end_time")
                start_time = cue.get("start_time", 0)
                
                if end_time:
                    duration = end_time
                else:
                    # 查找音频时长
                    audio_id = cue.get("audio_id")
                    for audio in self._audio_list:
                        if audio.get("id") == audio_id:
                            duration = audio.get("duration", 0)
                            break
            
            if duration > 0:
                progress = (current_position / duration) * 100
                progress = max(0, min(100, progress))
                self._auto_progress_var.set(progress)
            
            if self._auto_time_label:
                current_str = self._format_time(current_position)
                total_str = self._format_time(duration)
                self._auto_time_label.config(text=f"{current_str} / {total_str}")
        else:
            # 手动模式
            if self._manual_status_label:
                self._manual_status_label.config(text=status_text)
            
            # 获取选中音频的时长
            duration = 0
            if self._selected_audio_id:
                for audio in self._audio_list:
                    if audio.get("id") == self._selected_audio_id:
                        duration = audio.get("duration", 0)
                        break
            
            if duration > 0:
                progress = (current_position / duration) * 100
                progress = max(0, min(100, progress))
                self._manual_progress_var.set(progress)
            
            if self._manual_time_label:
                current_str = self._format_time(current_position)
                total_str = self._format_time(duration)
                self._manual_time_label.config(text=f"{current_str} / {total_str}")
    
    def _update_cue_highlight(self, current_index: int) -> None:
        """更新 Cue 列表高亮"""
        if not self._auto_cue_listbox:
            return
        
        # 清除所有高亮
        for i in range(self._auto_cue_listbox.size()):
            self._auto_cue_listbox.itemconfig(i, bg="white", fg="black")
        
        # 高亮当前 Cue
        if 0 <= current_index < self._auto_cue_listbox.size():
            self._auto_cue_listbox.itemconfig(current_index, bg="#4CAF50", fg="white")
            
            # 高亮下一个 Cue
            next_index = current_index + 1
            if next_index < self._auto_cue_listbox.size():
                self._auto_cue_listbox.itemconfig(next_index, bg="#FFC107", fg="black")
            
            self._auto_cue_listbox.see(current_index)
    
    def _update_volume_ui(self, bgm_vol: float, sfx_vol: float) -> None:
        """更新音量 UI"""
        if self._bgm_volume_var:
            self._bgm_volume_var.set(bgm_vol * 100)
        if self._sfx_volume_var:
            self._sfx_volume_var.set(sfx_vol * 100)
        if self._bgm_value_label:
            self._bgm_value_label.config(text=f"{int(bgm_vol * 100)}%")
        if self._sfx_value_label:
            self._sfx_value_label.config(text=f"{int(sfx_vol * 100)}%")
    
    # ==================== 播放控制 ====================
    
    def _on_play(self) -> None:
        """播放"""
        threading.Thread(target=self._api_client.play, daemon=True).start()
    
    def _on_pause(self) -> None:
        """暂停/继续"""
        if self._current_state.get("is_paused"):
            threading.Thread(target=self._api_client.resume, daemon=True).start()
        else:
            threading.Thread(target=self._api_client.pause, daemon=True).start()
    
    def _on_stop(self) -> None:
        """停止"""
        threading.Thread(target=self._api_client.stop, daemon=True).start()
    
    def _on_next(self) -> None:
        """下一个"""
        threading.Thread(target=self._api_client.next_cue, daemon=True).start()
    
    def _on_replay(self) -> None:
        """重播"""
        threading.Thread(target=self._api_client.replay, daemon=True).start()
    
    def _on_next_hint(self) -> None:
        """下一条提示"""
        if not self._manual_audio_listbox:
            return
        
        selection = self._manual_audio_listbox.curselection()
        current_index = selection[0] if selection else -1
        next_index = current_index + 1
        
        if next_index < self._manual_audio_listbox.size():
            self._manual_audio_listbox.selection_clear(0, tk.END)
            self._manual_audio_listbox.selection_set(next_index)
            self._manual_audio_listbox.see(next_index)
            self._manual_audio_listbox.event_generate("<<ListboxSelect>>")
    
    # ==================== 音量控制 ====================
    
    def _on_bgm_volume_change(self, value: str) -> None:
        """BGM 音量变化"""
        volume = float(value) / 100.0
        if self._bgm_value_label:
            self._bgm_value_label.config(text=f"{int(float(value))}%")
        threading.Thread(target=lambda: self._api_client.set_bgm_volume(volume), daemon=True).start()
    
    def _on_sfx_volume_change(self, value: str) -> None:
        """音效音量变化"""
        volume = float(value) / 100.0
        if self._sfx_value_label:
            self._sfx_value_label.config(text=f"{int(float(value))}%")
        threading.Thread(target=lambda: self._api_client.set_sfx_volume(volume), daemon=True).start()
    
    # ==================== 音效控制 ====================
    
    def _on_sfx_click(self, sfx_id: str) -> None:
        """音效按钮点击"""
        def do_toggle():
            resp = self._api_client.toggle_sfx(sfx_id)
            if resp.success and resp.data:
                is_playing = resp.data.get("is_playing", False)
                if self._root:
                    self._root.after(0, lambda: self._update_sfx_button(sfx_id, is_playing))
        
        threading.Thread(target=do_toggle, daemon=True).start()
    
    def _update_sfx_button(self, sfx_id: str, is_playing: bool) -> None:
        """更新音效按钮状态"""
        btn = self._sfx_buttons.get(sfx_id)
        if not btn:
            return
        
        if is_playing:
            btn.config(bg="#4CAF50", fg="white", relief=tk.SUNKEN)
        else:
            btn.config(bg="#E0E0E0", fg="black", relief=tk.RAISED)
    
    # ==================== Tab 切换 ====================
    
    def _on_tab_changed(self, event: tk.Event) -> None:
        """Tab 切换事件"""
        if not self._notebook or not self._api_client.is_connected:
            return
        
        current_tab = self._notebook.index(self._notebook.select())
        mode = "auto" if current_tab == 0 else "manual"
        
        threading.Thread(target=lambda: self._api_client.switch_mode(mode), daemon=True).start()
    
    # ==================== Cue 列表操作 ====================
    
    def _on_auto_cue_double_click(self, event: tk.Event) -> None:
        """Cue 双击播放"""
        selection = self._auto_cue_listbox.curselection()
        if selection:
            # TODO: 实现跳转到指定 Cue 并播放
            threading.Thread(target=self._api_client.play, daemon=True).start()
    
    # ==================== 音频选择 ====================
    
    def _on_audio_select(self, event: tk.Event) -> None:
        """音频选择事件"""
        selection = self._manual_audio_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        if index < len(self._audio_list):
            audio = self._audio_list[index]
            self._selected_audio_id = audio.get("id")
            
            # 加载断点
            self._load_breakpoints(self._selected_audio_id)
    
    def _on_audio_double_click(self, event: tk.Event) -> None:
        """音频双击播放"""
        if self._selected_audio_id:
            threading.Thread(target=self._api_client.play, daemon=True).start()
    
    # ==================== 断点操作 ====================
    
    def _on_auto_save_bp(self) -> None:
        """自动模式保存断点"""
        current_cue_index = self._current_state.get("current_cue_index", 0)
        if current_cue_index < len(self._cue_list):
            cue = self._cue_list[current_cue_index]
            audio_id = cue.get("audio_id")
            position = self._current_state.get("current_position", 0)
            
            def do_save():
                resp = self._api_client.save_breakpoint(audio_id, position)
                if resp.success:
                    self._load_breakpoints(audio_id)
            
            threading.Thread(target=do_save, daemon=True).start()
    
    def _on_auto_restore_bp(self) -> None:
        """自动模式恢复断点"""
        selection = self._auto_bp_listbox.curselection()
        if not selection:
            return
        
        current_cue_index = self._current_state.get("current_cue_index", 0)
        if current_cue_index < len(self._cue_list):
            cue = self._cue_list[current_cue_index]
            audio_id = cue.get("audio_id")
            breakpoints = self._breakpoints.get(audio_id, [])
            
            if selection[0] < len(breakpoints):
                bp = breakpoints[selection[0]]
                position = bp.get("position", 0)
                
                threading.Thread(target=lambda: self._api_client.seek(position), daemon=True).start()
    
    def _on_auto_delete_bp(self) -> None:
        """自动模式删除断点"""
        selection = self._auto_bp_listbox.curselection()
        if not selection:
            return
        
        current_cue_index = self._current_state.get("current_cue_index", 0)
        if current_cue_index < len(self._cue_list):
            cue = self._cue_list[current_cue_index]
            audio_id = cue.get("audio_id")
            breakpoints = self._breakpoints.get(audio_id, [])
            
            def do_delete():
                for i in selection:
                    if i < len(breakpoints):
                        bp_id = breakpoints[i].get("id")
                        self._api_client.delete_breakpoint(audio_id, bp_id)
                self._load_breakpoints(audio_id)
            
            threading.Thread(target=do_delete, daemon=True).start()
    
    def _on_manual_save_bp(self) -> None:
        """手动模式保存断点"""
        if not self._selected_audio_id:
            return
        
        position = self._current_state.get("current_position", 0)
        
        def do_save():
            resp = self._api_client.save_breakpoint(self._selected_audio_id, position)
            if resp.success:
                self._load_breakpoints(self._selected_audio_id)
        
        threading.Thread(target=do_save, daemon=True).start()
    
    def _on_manual_restore_bp(self) -> None:
        """手动模式恢复断点"""
        selection = self._manual_bp_listbox.curselection()
        if not selection or not self._selected_audio_id:
            return
        
        breakpoints = self._breakpoints.get(self._selected_audio_id, [])
        if selection[0] < len(breakpoints):
            bp = breakpoints[selection[0]]
            position = bp.get("position", 0)
            
            threading.Thread(target=lambda: self._api_client.seek(position), daemon=True).start()
    
    def _on_manual_delete_bp(self) -> None:
        """手动模式删除断点"""
        selection = self._manual_bp_listbox.curselection()
        if not selection or not self._selected_audio_id:
            return
        
        breakpoints = self._breakpoints.get(self._selected_audio_id, [])
        
        def do_delete():
            for i in selection:
                if i < len(breakpoints):
                    bp_id = breakpoints[i].get("id")
                    self._api_client.delete_breakpoint(self._selected_audio_id, bp_id)
            self._load_breakpoints(self._selected_audio_id)
        
        threading.Thread(target=do_delete, daemon=True).start()
    
    def _on_manual_clear_bp(self) -> None:
        """手动模式清除所有断点"""
        if not self._selected_audio_id:
            return
        
        def do_clear():
            self._api_client.clear_breakpoints(self._selected_audio_id)
            self._load_breakpoints(self._selected_audio_id)
        
        threading.Thread(target=do_clear, daemon=True).start()
    
    # ==================== 文件上传 ====================
    
    def _on_upload_click(self) -> None:
        """上传按钮点击"""
        if not self._api_client.is_connected:
            messagebox.showwarning("警告", "请先连接到服务器")
            return
        
        file_paths = filedialog.askopenfilenames(
            title="选择音频文件（可多选）",
            filetypes=[
                ("音频文件", "*.mp3 *.m4a *.wav *.ogg"),
                ("所有文件", "*.*")
            ]
        )
        
        if not file_paths:
            return
        
        # 询问轨道类型
        track_type = messagebox.askquestion(
            "轨道类型",
            "这些是音效吗？\n\n是 = 音效 (SFX)\n否 = 背景音乐 (BGM)"
        )
        track_type = "sfx" if track_type == "yes" else "bgm"
        
        # 创建上传进度对话框
        self._show_upload_progress(list(file_paths), track_type)
    
    def _show_upload_progress(self, file_paths: List[str], track_type: str) -> None:
        """
        显示上传进度对话框
        
        Args:
            file_paths: 文件路径列表
            track_type: 轨道类型
        """
        # 创建进度对话框
        progress_window = tk.Toplevel(self._root)
        progress_window.title("上传音频")
        progress_window.geometry("400x150")
        progress_window.resizable(False, False)
        progress_window.transient(self._root)
        progress_window.grab_set()
        
        # 居中显示
        progress_window.update_idletasks()
        x = self._root.winfo_x() + (self._root.winfo_width() - 400) // 2
        y = self._root.winfo_y() + (self._root.winfo_height() - 150) // 2
        progress_window.geometry(f"+{x}+{y}")
        
        # 进度标签
        status_label = ttk.Label(
            progress_window,
            text=f"准备上传 {len(file_paths)} 个文件...",
            font=("微软雅黑", 10)
        )
        status_label.pack(pady=(20, 10))
        
        # 进度条
        progress_var = tk.DoubleVar(value=0)
        progress_bar = ttk.Progressbar(
            progress_window,
            variable=progress_var,
            maximum=100,
            length=350
        )
        progress_bar.pack(pady=10)
        
        # 文件名标签
        file_label = ttk.Label(
            progress_window,
            text="",
            font=("微软雅黑", 9)
        )
        file_label.pack(pady=5)
        
        # 上传状态
        upload_state = {"cancelled": False, "completed": 0, "failed": 0}
        
        def do_upload():
            total = len(file_paths)
            for i, file_path in enumerate(file_paths):
                if upload_state["cancelled"]:
                    break
                
                # 更新 UI
                from pathlib import Path
                filename = Path(file_path).name
                if self._root:
                    self._root.after(0, lambda f=filename, idx=i: update_ui(f, idx, total))
                
                # 上传文件
                resp = self._api_client.upload_audio(file_path, track_type=track_type)
                
                if resp.success:
                    upload_state["completed"] += 1
                else:
                    upload_state["failed"] += 1
            
            # 完成
            if self._root:
                self._root.after(0, on_complete)
        
        def update_ui(filename: str, current: int, total: int):
            progress = ((current + 0.5) / total) * 100
            progress_var.set(progress)
            status_label.config(text=f"上传中 ({current + 1}/{total})...")
            file_label.config(text=filename)
        
        def on_complete():
            progress_window.destroy()
            
            completed = upload_state["completed"]
            failed = upload_state["failed"]
            
            if failed == 0:
                messagebox.showinfo("成功", f"成功上传 {completed} 个文件")
            else:
                messagebox.showwarning(
                    "部分成功",
                    f"上传完成\n成功: {completed}\n失败: {failed}"
                )
            
            self._load_initial_data()
        
        def on_cancel():
            upload_state["cancelled"] = True
            progress_window.destroy()
        
        # 取消按钮
        cancel_btn = ttk.Button(progress_window, text="取消", command=on_cancel)
        cancel_btn.pack(pady=10)
        
        # 开始上传
        threading.Thread(target=do_upload, daemon=True).start()
    
    def _on_upload_result(self, resp: APIResponse) -> None:
        """上传结果回调"""
        if resp.success:
            messagebox.showinfo("成功", "音频上传成功")
            self._load_initial_data()
        else:
            messagebox.showerror("错误", f"上传失败: {resp.error}")
    
    # ==================== 窗口控制 ====================
    
    def _on_close_request(self) -> None:
        """窗口关闭请求"""
        if messagebox.askyesno("确认关闭", "确定要关闭远程客户端吗？"):
            self._close_window()
    
    def _close_window(self) -> None:
        """关闭窗口"""
        self._stop_update_loop()
        
        if self._api_client.is_connected:
            self._api_client.disconnect()
        
        if self._root:
            self._root.destroy()
            self._root = None
    
    def run(self) -> None:
        """运行主窗口"""
        if self._root:
            self._root.mainloop()
    
    @staticmethod
    def _format_time(seconds: float) -> str:
        """格式化时间"""
        if seconds is None or seconds < 0:
            return "00:00"
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"


def main():
    """主函数"""
    import sys
    
    host = "localhost"
    port = 8080
    
    # 解析命令行参数
    if len(sys.argv) > 1:
        host = sys.argv[1]
    if len(sys.argv) > 2:
        try:
            port = int(sys.argv[2])
        except ValueError:
            pass
    
    client = RemoteClient(host, port)
    client.create()
    client.run()


if __name__ == "__main__":
    main()
