"""
主窗口框架模块

实现控制台主窗口，包含：
- 垂直布局，区分自动/手动模式区域
- 模式切换 Tab
- 关闭确认对话框
- 配置文件导入/导出菜单

**Requirements: 11.1, 11.6**
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Optional, Callable, Dict, Any
from pathlib import Path

from src.core.controller import CoreController, PlayMode, EventType
from src.gui.async_helper import run_async


class MainWindow:
    """
    主窗口类
    
    负责创建和管理控制台主窗口，包括：
    - 模式切换 Tab（自动/手动）
    - 各功能面板的容器
    - 关闭确认机制
    
    **Requirements: 11.1, 11.6**
    """
    
    WINDOW_TITLE = "舞台剧音效控制台"
    WINDOW_MIN_WIDTH = 800
    WINDOW_MIN_HEIGHT = 600
    
    def __init__(
        self,
        controller: Optional[CoreController] = None,
        on_close: Optional[Callable[[], None]] = None
    ):
        """
        初始化主窗口
        
        Args:
            controller: 核心控制器实例
            on_close: 窗口关闭时的回调函数
        """
        self._controller = controller
        self._on_close_callback = on_close
        
        # 创建主窗口
        self._root: Optional[tk.Tk] = None
        self._notebook: Optional[ttk.Notebook] = None
        
        # 面板容器
        self._auto_mode_frame: Optional[ttk.Frame] = None
        self._manual_mode_frame: Optional[ttk.Frame] = None
        self._sfx_frame: Optional[ttk.Frame] = None
        self._volume_frame: Optional[ttk.Frame] = None
        
        # 面板实例（由外部设置）
        self._auto_mode_panel: Any = None
        self._manual_mode_panel: Any = None
        self._sfx_panel: Any = None
        self._volume_panel: Any = None
        
        # 状态
        self._is_running = False
        self._close_confirmed = False
        
        # 当前配置文件路径
        self._current_config_file: Optional[str] = None
    
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
        
        # 创建菜单栏
        self._create_menu()
        
        # 创建主布局
        self._create_layout()
        
        # 绑定键盘快捷键
        self._bind_shortcuts()
        
        # 监听控制器事件
        if self._controller:
            self._controller.add_listener(EventType.MODE_CHANGED, self._on_mode_changed)
        
        return self._root
    
    def _configure_styles(self) -> None:
        """配置 ttk 样式"""
        style = ttk.Style()
        
        # 配置 Notebook 样式
        style.configure("TNotebook", background="#f0f0f0")
        style.configure("TNotebook.Tab", padding=[20, 10], font=("微软雅黑", 12))
        
        # 配置 Frame 样式
        style.configure("TFrame", background="#f0f0f0")
        
        # 配置 Label 样式
        style.configure("TLabel", background="#f0f0f0", font=("微软雅黑", 10))
        style.configure("Title.TLabel", font=("微软雅黑", 14, "bold"))
        style.configure("Status.TLabel", font=("微软雅黑", 11))
        
        # 配置 Button 样式
        style.configure("TButton", font=("微软雅黑", 10), padding=[10, 5])
        style.configure("Play.TButton", font=("微软雅黑", 12, "bold"))
        style.configure("Danger.TButton", foreground="red")
    
    def _create_menu(self) -> None:
        """创建菜单栏"""
        if not self._root:
            return
        
        menubar = tk.Menu(self._root)
        self._root.config(menu=menubar)
        
        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="导入配置...", command=self._import_config, accelerator="Ctrl+O")
        file_menu.add_command(label="导出配置...", command=self._export_config, accelerator="Ctrl+Shift+S")
        file_menu.add_separator()
        file_menu.add_command(label="打开配置编辑器", command=self._open_config_editor)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self._on_close_request, accelerator="Alt+F4")
        
        # 绑定快捷键
        self._root.bind("<Control-o>", lambda e: self._import_config())
        self._root.bind("<Control-Shift-S>", lambda e: self._export_config())
    
    def _import_config(self) -> None:
        """导入配置文件"""
        if not self._root or not self._controller:
            return
        
        filepath = filedialog.askopenfilename(
            parent=self._root,
            title="导入配置文件",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")],
            initialdir=str(Path("config"))
        )
        
        if filepath:
            try:
                self._controller.cue_manager.load_config(filepath)
                self._current_config_file = filepath
                
                # 更新窗口标题
                filename = Path(filepath).name
                self._root.title(f"{self.WINDOW_TITLE} - {filename}")
                
                # 刷新面板显示
                self._refresh_panels()
                
                messagebox.showinfo(
                    "导入成功",
                    f"已成功导入配置文件:\n{filename}",
                    parent=self._root
                )
            except Exception as e:
                messagebox.showerror(
                    "导入失败",
                    f"无法导入配置文件:\n{e}",
                    parent=self._root
                )
    
    def _export_config(self) -> None:
        """导出配置文件"""
        if not self._root or not self._controller:
            return
        
        # 默认文件名
        default_name = "cue_config.json"
        if self._current_config_file:
            default_name = Path(self._current_config_file).name
        
        filepath = filedialog.asksaveasfilename(
            parent=self._root,
            title="导出配置文件",
            defaultextension=".json",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")],
            initialfile=default_name,
            initialdir=str(Path("config"))
        )
        
        if filepath:
            try:
                self._controller.cue_manager.save_config(filepath)
                self._current_config_file = filepath
                
                # 更新窗口标题
                filename = Path(filepath).name
                self._root.title(f"{self.WINDOW_TITLE} - {filename}")
                
                messagebox.showinfo(
                    "导出成功",
                    f"已成功导出配置文件:\n{filename}",
                    parent=self._root
                )
            except Exception as e:
                messagebox.showerror(
                    "导出失败",
                    f"无法导出配置文件:\n{e}",
                    parent=self._root
                )
    
    def _open_config_editor(self) -> None:
        """打开配置编辑器"""
        try:
            from src.tools.config_editor import ConfigEditor
            
            # 创建配置编辑器窗口
            editor = ConfigEditor()
            
            # 如果当前有配置文件，加载它
            if self._current_config_file:
                try:
                    editor.cue_manager.load_config(self._current_config_file)
                    editor.current_file = self._current_config_file
                    editor._refresh_audio_list()
                    editor._refresh_cue_list()
                    editor._update_title()
                except Exception:
                    pass
            
            editor.mainloop()
            
            # 编辑器关闭后，询问是否重新加载配置
            if self._current_config_file and self._root:
                result = messagebox.askyesno(
                    "重新加载配置",
                    "配置编辑器已关闭。\n是否重新加载配置文件？",
                    parent=self._root
                )
                if result:
                    try:
                        self._controller.cue_manager.load_config(self._current_config_file)
                        self._refresh_panels()
                    except Exception as e:
                        messagebox.showerror(
                            "加载失败",
                            f"无法重新加载配置:\n{e}",
                            parent=self._root
                        )
        except Exception as e:
            messagebox.showerror(
                "错误",
                f"无法打开配置编辑器:\n{e}",
                parent=self._root
            )
    
    def _refresh_panels(self) -> None:
        """刷新所有面板显示"""
        # 刷新自动模式面板
        if self._auto_mode_panel and hasattr(self._auto_mode_panel, 'refresh'):
            self._auto_mode_panel.refresh()
        elif self._auto_mode_panel and hasattr(self._auto_mode_panel, '_refresh_cue_list'):
            self._auto_mode_panel._refresh_cue_list()
        
        # 刷新手动模式面板
        if self._manual_mode_panel and hasattr(self._manual_mode_panel, 'refresh'):
            self._manual_mode_panel.refresh()
        elif self._manual_mode_panel and hasattr(self._manual_mode_panel, '_refresh_audio_list'):
            self._manual_mode_panel._refresh_audio_list()
        
        # 刷新音效面板
        if self._sfx_panel and hasattr(self._sfx_panel, 'refresh'):
            self._sfx_panel.refresh()
        elif self._sfx_panel and hasattr(self._sfx_panel, '_refresh_sfx_buttons'):
            self._sfx_panel._refresh_sfx_buttons()
    
    def _create_layout(self) -> None:
        """创建主布局"""
        if not self._root:
            return
        
        # 主容器 - 垂直布局
        main_container = ttk.Frame(self._root, padding="10")
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # 顶部：模式切换 Tab
        self._create_mode_tabs(main_container)
        
        # 底部：音效和音量控制区域
        bottom_frame = ttk.Frame(main_container)
        bottom_frame.pack(fill=tk.X, pady=(10, 0))
        
        # 音效面板容器
        self._sfx_frame = ttk.LabelFrame(bottom_frame, text="音效", padding="5")
        self._sfx_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # 音量控制面板容器
        self._volume_frame = ttk.LabelFrame(bottom_frame, text="音量控制", padding="5")
        self._volume_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
    
    def _create_mode_tabs(self, parent: ttk.Frame) -> None:
        """
        创建模式切换 Tab
        
        Args:
            parent: 父容器
        """
        # 创建 Notebook
        self._notebook = ttk.Notebook(parent)
        self._notebook.pack(fill=tk.BOTH, expand=True)
        
        # 自动模式 Tab
        self._auto_mode_frame = ttk.Frame(self._notebook, padding="10")
        self._notebook.add(self._auto_mode_frame, text="自动模式")
        
        # 手动模式 Tab
        self._manual_mode_frame = ttk.Frame(self._notebook, padding="10")
        self._notebook.add(self._manual_mode_frame, text="手动模式")
        
        # 绑定 Tab 切换事件
        self._notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
    
    def _bind_shortcuts(self) -> None:
        """绑定键盘快捷键"""
        if not self._root:
            return
        
        # 空格键：播放/暂停
        self._root.bind("<space>", self._on_space_key)
        
        # Escape 键：停止
        self._root.bind("<Escape>", self._on_escape_key)
        
        # N 键：下一个
        self._root.bind("<n>", self._on_next_key)
        self._root.bind("<N>", self._on_next_key)
        
        # Tab 切换模式
        self._root.bind("<Control-Tab>", self._on_ctrl_tab)
    
    def _on_space_key(self, event: tk.Event) -> None:
        """处理空格键事件"""
        # 由面板处理具体逻辑
        pass
    
    def _on_escape_key(self, event: tk.Event) -> None:
        """处理 Escape 键事件"""
        # 由面板处理具体逻辑
        pass
    
    def _on_next_key(self, event: tk.Event) -> None:
        """处理 N 键事件"""
        # 由面板处理具体逻辑
        pass
    
    def _on_ctrl_tab(self, event: tk.Event) -> None:
        """处理 Ctrl+Tab 切换模式"""
        if self._notebook:
            current = self._notebook.index(self._notebook.select())
            next_tab = (current + 1) % self._notebook.index("end")
            self._notebook.select(next_tab)
    
    def _on_tab_changed(self, event: tk.Event) -> None:
        """
        处理 Tab 切换事件
        
        Args:
            event: Tkinter 事件对象
        """
        if not self._notebook or not self._controller:
            return
        
        # 获取当前选中的 Tab
        current_tab = self._notebook.index(self._notebook.select())
        
        # 切换控制器模式
        if current_tab == 0:
            run_async(self._controller.switch_mode(PlayMode.AUTO))
        else:
            run_async(self._controller.switch_mode(PlayMode.MANUAL))
    
    def _on_mode_changed(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """
        处理控制器模式变化事件
        
        Args:
            event_type: 事件类型
            data: 事件数据
        """
        if not self._notebook:
            return
        
        new_mode = data.get("new_mode")
        if new_mode == "auto":
            self._notebook.select(0)
        elif new_mode == "manual":
            self._notebook.select(1)
    
    def _on_close_request(self) -> None:
        """处理窗口关闭请求"""
        # 显示确认对话框
        if self._show_close_confirmation():
            self._close_confirmed = True
            self._close_window()
    
    def _show_close_confirmation(self) -> bool:
        """
        显示关闭确认对话框
        
        Returns:
            bool: 用户是否确认关闭
        
        **Requirements: 11.6, 12.4**
        """
        result = messagebox.askyesno(
            "确认关闭",
            "确定要关闭控制台吗？\n\n关闭后将停止所有音频播放。",
            icon="warning",
            parent=self._root
        )
        return result
    
    def _close_window(self) -> None:
        """关闭窗口"""
        # 停止控制器
        if self._controller:
            run_async(self._controller.stop())
        
        # 执行关闭回调
        if self._on_close_callback:
            self._on_close_callback()
        
        # 销毁窗口
        if self._root:
            self._root.destroy()
            self._root = None
        
        self._is_running = False
    
    # ==================== 面板管理 ====================
    
    def get_auto_mode_frame(self) -> Optional[ttk.Frame]:
        """获取自动模式面板容器"""
        return self._auto_mode_frame
    
    def get_manual_mode_frame(self) -> Optional[ttk.Frame]:
        """获取手动模式面板容器"""
        return self._manual_mode_frame
    
    def get_sfx_frame(self) -> Optional[ttk.Frame]:
        """获取音效面板容器"""
        return self._sfx_frame
    
    def get_volume_frame(self) -> Optional[ttk.Frame]:
        """获取音量控制面板容器"""
        return self._volume_frame
    
    def set_auto_mode_panel(self, panel: Any) -> None:
        """设置自动模式面板"""
        self._auto_mode_panel = panel
    
    def set_manual_mode_panel(self, panel: Any) -> None:
        """设置手动模式面板"""
        self._manual_mode_panel = panel
    
    def set_sfx_panel(self, panel: Any) -> None:
        """设置音效面板"""
        self._sfx_panel = panel
    
    def set_volume_panel(self, panel: Any) -> None:
        """设置音量控制面板"""
        self._volume_panel = panel
    
    # ==================== 窗口控制 ====================
    
    def run(self) -> None:
        """运行主窗口事件循环"""
        if self._root:
            self._is_running = True
            self._root.mainloop()
    
    def update(self) -> None:
        """更新窗口（用于异步环境）"""
        if self._root:
            self._root.update()
    
    def update_idletasks(self) -> None:
        """更新空闲任务"""
        if self._root:
            self._root.update_idletasks()
    
    def after(self, ms: int, func: Callable) -> str:
        """
        延迟执行函数
        
        Args:
            ms: 延迟毫秒数
            func: 要执行的函数
            
        Returns:
            str: 定时器 ID
        """
        if self._root:
            return self._root.after(ms, func)
        return ""
    
    def after_cancel(self, timer_id: str) -> None:
        """
        取消延迟执行
        
        Args:
            timer_id: 定时器 ID
        """
        if self._root and timer_id:
            try:
                self._root.after_cancel(timer_id)
            except Exception:
                pass
    
    @property
    def root(self) -> Optional[tk.Tk]:
        """获取根窗口"""
        return self._root
    
    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._is_running
    
    def set_title(self, title: str) -> None:
        """设置窗口标题"""
        if self._root:
            self._root.title(title)
    
    def set_geometry(self, geometry: str) -> None:
        """
        设置窗口大小和位置
        
        Args:
            geometry: 几何字符串，如 "800x600+100+100"
        """
        if self._root:
            self._root.geometry(geometry)
    
    def center_window(self) -> None:
        """将窗口居中显示"""
        if not self._root:
            return
        
        self._root.update_idletasks()
        width = self._root.winfo_width()
        height = self._root.winfo_height()
        screen_width = self._root.winfo_screenwidth()
        screen_height = self._root.winfo_screenheight()
        
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        
        self._root.geometry(f"+{x}+{y}")
    
    def focus(self) -> None:
        """使窗口获得焦点"""
        if self._root:
            self._root.focus_force()
    
    def select_auto_mode(self) -> None:
        """选择自动模式 Tab"""
        if self._notebook:
            self._notebook.select(0)
    
    def select_manual_mode(self) -> None:
        """选择手动模式 Tab"""
        if self._notebook:
            self._notebook.select(1)
    
    def get_current_mode_tab(self) -> int:
        """
        获取当前选中的模式 Tab 索引
        
        Returns:
            int: 0 为自动模式，1 为手动模式
        """
        if self._notebook:
            return self._notebook.index(self._notebook.select())
        return 0
