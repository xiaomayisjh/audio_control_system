"""Cue 列表配置编辑工具

提供可视化的 Cue 列表编辑界面，支持：
- Cue 列表可视化编辑
- 音频文件添加和管理
- 入点、出点、静音间隔设置
- Cue 顺序调整（上移/下移按钮）
- JSON 导入/导出

Requirements: 9.1-9.4
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import uuid
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from src.models.cue import Cue
from src.models.audio_track import AudioTrack
from src.models.cue_config import CueListConfig
from src.core.cue_manager import CueManager


class CueEditDialog(tk.Toplevel):
    """Cue 编辑对话框"""
    
    def __init__(self, parent, audio_files: List[AudioTrack], cue: Optional[Cue] = None):
        """初始化 Cue 编辑对话框
        
        Args:
            parent: 父窗口
            audio_files: 可用的音频文件列表
            cue: 要编辑的 Cue（None 表示新建）
        """
        super().__init__(parent)
        self.audio_files = audio_files
        self.cue = cue
        self.result: Optional[Cue] = None
        
        self.title("编辑 Cue" if cue else "新建 Cue")
        self.geometry("450x400")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        self._load_cue_data()
        
        # 居中显示
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    
    def _create_widgets(self):
        """创建界面组件"""
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标签
        ttk.Label(main_frame, text="标签:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.label_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.label_var, width=35).grid(
            row=0, column=1, columnspan=2, sticky=tk.W, pady=5
        )
        
        # 音频选择
        ttk.Label(main_frame, text="音频文件:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.audio_var = tk.StringVar()
        audio_combo = ttk.Combobox(
            main_frame, textvariable=self.audio_var, width=32, state="readonly"
        )
        audio_combo["values"] = [f"{a.title} ({a.id})" for a in self.audio_files]
        audio_combo.grid(row=1, column=1, columnspan=2, sticky=tk.W, pady=5)
        
        # 入点
        ttk.Label(main_frame, text="入点 (秒):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.start_time_var = tk.StringVar(value="0.0")
        ttk.Entry(main_frame, textvariable=self.start_time_var, width=15).grid(
            row=2, column=1, sticky=tk.W, pady=5
        )
        
        # 出点
        ttk.Label(main_frame, text="出点 (秒):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.end_time_var = tk.StringVar(value="")
        ttk.Entry(main_frame, textvariable=self.end_time_var, width=15).grid(
            row=3, column=1, sticky=tk.W, pady=5
        )
        ttk.Label(main_frame, text="(留空表示播放到结束)").grid(
            row=3, column=2, sticky=tk.W, pady=5
        )
        
        # 前置静音
        ttk.Label(main_frame, text="前置静音 (秒):").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.silence_before_var = tk.StringVar(value="0.0")
        ttk.Entry(main_frame, textvariable=self.silence_before_var, width=15).grid(
            row=4, column=1, sticky=tk.W, pady=5
        )
        
        # 后置静音
        ttk.Label(main_frame, text="后置静音 (秒):").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.silence_after_var = tk.StringVar(value="0.0")
        ttk.Entry(main_frame, textvariable=self.silence_after_var, width=15).grid(
            row=5, column=1, sticky=tk.W, pady=5
        )
        
        # 音量
        ttk.Label(main_frame, text="音量:").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.volume_var = tk.DoubleVar(value=1.0)
        volume_frame = ttk.Frame(main_frame)
        volume_frame.grid(row=6, column=1, columnspan=2, sticky=tk.W, pady=5)
        
        volume_scale = ttk.Scale(
            volume_frame, from_=0.0, to=1.0, variable=self.volume_var,
            orient=tk.HORIZONTAL, length=150
        )
        volume_scale.pack(side=tk.LEFT)
        
        self.volume_label = ttk.Label(volume_frame, text="100%")
        self.volume_label.pack(side=tk.LEFT, padx=10)
        self.volume_var.trace_add("write", self._update_volume_label)
        
        # 按钮
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=7, column=0, columnspan=3, pady=20)
        
        ttk.Button(btn_frame, text="确定", command=self._on_ok, width=10).pack(
            side=tk.LEFT, padx=10
        )
        ttk.Button(btn_frame, text="取消", command=self._on_cancel, width=10).pack(
            side=tk.LEFT, padx=10
        )
    
    def _update_volume_label(self, *args):
        """更新音量标签"""
        self.volume_label.config(text=f"{int(self.volume_var.get() * 100)}%")
    
    def _load_cue_data(self):
        """加载 Cue 数据到表单"""
        if self.cue:
            self.label_var.set(self.cue.label)
            # 查找音频索引
            for i, audio in enumerate(self.audio_files):
                if audio.id == self.cue.audio_id:
                    self.audio_var.set(f"{audio.title} ({audio.id})")
                    break
            self.start_time_var.set(str(self.cue.start_time))
            if self.cue.end_time is not None:
                self.end_time_var.set(str(self.cue.end_time))
            self.silence_before_var.set(str(self.cue.silence_before))
            self.silence_after_var.set(str(self.cue.silence_after))
            self.volume_var.set(self.cue.volume)
    
    def _on_ok(self):
        """确定按钮处理"""
        # 验证输入
        if not self.audio_var.get():
            messagebox.showerror("错误", "请选择音频文件", parent=self)
            return
        
        try:
            start_time = float(self.start_time_var.get() or "0")
            end_time_str = self.end_time_var.get().strip()
            end_time = float(end_time_str) if end_time_str else None
            silence_before = float(self.silence_before_var.get() or "0")
            silence_after = float(self.silence_after_var.get() or "0")
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字", parent=self)
            return
        
        # 验证时间值
        if start_time < 0:
            messagebox.showerror("错误", "入点不能为负数", parent=self)
            return
        if end_time is not None and end_time <= start_time:
            messagebox.showerror("错误", "出点必须大于入点", parent=self)
            return
        if silence_before < 0 or silence_after < 0:
            messagebox.showerror("错误", "静音时间不能为负数", parent=self)
            return
        
        # 获取音频 ID
        audio_str = self.audio_var.get()
        audio_id = audio_str.split("(")[-1].rstrip(")")
        
        # 创建 Cue
        cue_id = self.cue.id if self.cue else f"cue_{uuid.uuid4().hex[:8]}"
        self.result = Cue(
            id=cue_id,
            audio_id=audio_id,
            start_time=start_time,
            end_time=end_time,
            silence_before=silence_before,
            silence_after=silence_after,
            volume=self.volume_var.get(),
            label=self.label_var.get() or f"Cue {cue_id}"
        )
        self.destroy()
    
    def _on_cancel(self):
        """取消按钮处理"""
        self.destroy()


class AudioEditDialog(tk.Toplevel):
    """音频文件编辑对话框"""
    
    def __init__(self, parent, audio: Optional[AudioTrack] = None):
        """初始化音频编辑对话框
        
        Args:
            parent: 父窗口
            audio: 要编辑的音频（None 表示新建）
        """
        super().__init__(parent)
        self.audio = audio
        self.result: Optional[AudioTrack] = None
        
        self.title("编辑音频" if audio else "添加音频")
        self.geometry("500x280")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        self._load_audio_data()
        
        # 居中显示
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    
    def _create_widgets(self):
        """创建界面组件"""
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 文件路径
        ttk.Label(main_frame, text="文件路径:").grid(row=0, column=0, sticky=tk.W, pady=5)
        path_frame = ttk.Frame(main_frame)
        path_frame.grid(row=0, column=1, sticky=tk.W, pady=5)
        
        self.path_var = tk.StringVar()
        ttk.Entry(path_frame, textvariable=self.path_var, width=30).pack(side=tk.LEFT)
        ttk.Button(path_frame, text="浏览...", command=self._browse_file).pack(
            side=tk.LEFT, padx=5
        )
        
        # 标题
        ttk.Label(main_frame, text="标题:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.title_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.title_var, width=35).grid(
            row=1, column=1, sticky=tk.W, pady=5
        )
        
        # 时长
        ttk.Label(main_frame, text="时长 (秒):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.duration_var = tk.StringVar(value="0.0")
        ttk.Entry(main_frame, textvariable=self.duration_var, width=15).grid(
            row=2, column=1, sticky=tk.W, pady=5
        )
        
        # 类型
        ttk.Label(main_frame, text="类型:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.type_var = tk.StringVar(value="bgm")
        type_frame = ttk.Frame(main_frame)
        type_frame.grid(row=3, column=1, sticky=tk.W, pady=5)
        ttk.Radiobutton(type_frame, text="BGM", variable=self.type_var, value="bgm").pack(
            side=tk.LEFT, padx=5
        )
        ttk.Radiobutton(type_frame, text="音效", variable=self.type_var, value="sfx").pack(
            side=tk.LEFT, padx=5
        )
        
        # 按钮
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=20)
        
        ttk.Button(btn_frame, text="确定", command=self._on_ok, width=10).pack(
            side=tk.LEFT, padx=10
        )
        ttk.Button(btn_frame, text="取消", command=self._on_cancel, width=10).pack(
            side=tk.LEFT, padx=10
        )
    
    def _browse_file(self):
        """浏览文件"""
        filetypes = [
            ("音频文件", "*.mp3 *.m4a *.wav *.ogg"),
            ("所有文件", "*.*")
        ]
        filepath = filedialog.askopenfilename(
            parent=self,
            title="选择音频文件",
            filetypes=filetypes
        )
        if filepath:
            self.path_var.set(filepath)
            # 自动填充标题
            if not self.title_var.get():
                filename = os.path.basename(filepath)
                name_without_ext = os.path.splitext(filename)[0]
                self.title_var.set(name_without_ext)
            
            # 自动获取音频时长
            duration = self._get_audio_duration(filepath)
            if duration > 0:
                self.duration_var.set(f"{duration:.1f}")
    
    def _get_audio_duration(self, filepath: str) -> float:
        """获取音频文件时长
        
        Args:
            filepath: 音频文件路径
            
        Returns:
            时长（秒），失败返回 0
        """
        try:
            # 尝试使用 mutagen 库（更准确）
            try:
                from mutagen import File as MutagenFile
                audio = MutagenFile(filepath)
                if audio is not None and audio.info:
                    return audio.info.length
            except ImportError:
                pass
            
            # 尝试使用 pygame
            try:
                import pygame
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                sound = pygame.mixer.Sound(filepath)
                duration = sound.get_length()
                return duration
            except Exception:
                pass
            
            return 0.0
        except Exception:
            return 0.0
    
    def _load_audio_data(self):
        """加载音频数据到表单"""
        if self.audio:
            self.path_var.set(self.audio.file_path)
            self.title_var.set(self.audio.title)
            self.duration_var.set(str(self.audio.duration))
            self.type_var.set(self.audio.track_type)
    
    def _on_ok(self):
        """确定按钮处理"""
        # 验证输入
        if not self.path_var.get():
            messagebox.showerror("错误", "请选择音频文件", parent=self)
            return
        if not self.title_var.get():
            messagebox.showerror("错误", "请输入标题", parent=self)
            return
        
        try:
            duration = float(self.duration_var.get() or "0")
        except ValueError:
            messagebox.showerror("错误", "请输入有效的时长", parent=self)
            return
        
        if duration < 0:
            messagebox.showerror("错误", "时长不能为负数", parent=self)
            return
        
        # 创建 AudioTrack
        audio_id = self.audio.id if self.audio else f"audio_{uuid.uuid4().hex[:8]}"
        self.result = AudioTrack(
            id=audio_id,
            file_path=self.path_var.get(),
            duration=duration,
            title=self.title_var.get(),
            track_type=self.type_var.get()
        )
        self.destroy()
    
    def _on_cancel(self):
        """取消按钮处理"""
        self.destroy()


class ConfigEditor(tk.Tk):
    """Cue 列表配置编辑器主窗口
    
    提供可视化的 Cue 列表编辑界面，支持：
    - Cue 列表可视化编辑
    - 音频文件添加和管理
    - 入点、出点、静音间隔设置
    - Cue 顺序调整（上移/下移按钮）
    - JSON 导入/导出
    
    Requirements: 9.1-9.4
    """
    
    def __init__(self):
        """初始化配置编辑器"""
        super().__init__()
        
        self.title("Cue 列表配置编辑器")
        self.geometry("900x650")
        self.minsize(800, 550)
        
        # 初始化 CueManager
        self.cue_manager = CueManager()
        self.current_file: Optional[str] = None
        self.modified = False
        
        self._create_menu()
        self._create_widgets()
        self._bind_events()
        
        # 更新窗口标题
        self._update_title()
    
    def _create_menu(self):
        """创建菜单栏"""
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        
        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="新建", command=self._new_config, accelerator="Ctrl+N")
        file_menu.add_command(label="打开...", command=self._open_config, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="保存", command=self._save_config, accelerator="Ctrl+S")
        file_menu.add_command(label="另存为...", command=self._save_config_as)
        file_menu.add_separator()
        file_menu.add_command(label="导入 JSON...", command=self._import_json)
        file_menu.add_command(label="导出 JSON...", command=self._export_json)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self._on_close)
        
        # 编辑菜单
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="编辑", menu=edit_menu)
        edit_menu.add_command(label="配置名称...", command=self._edit_config_name)
        
        # 绑定快捷键
        self.bind("<Control-n>", lambda e: self._new_config())
        self.bind("<Control-o>", lambda e: self._open_config())
        self.bind("<Control-s>", lambda e: self._save_config())
    
    def _create_widgets(self):
        """创建界面组件"""
        # 主容器
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 左侧：音频文件列表
        left_frame = ttk.LabelFrame(main_frame, text="音频文件", padding=5)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 5))
        
        # 音频列表（支持多选）
        audio_list_frame = ttk.Frame(left_frame)
        audio_list_frame.pack(fill=tk.BOTH, expand=True)
        
        self.audio_listbox = tk.Listbox(
            audio_list_frame, width=30, height=20,
            selectmode=tk.EXTENDED  # 支持多选
        )
        audio_scrollbar = ttk.Scrollbar(audio_list_frame, orient=tk.VERTICAL,
                                        command=self.audio_listbox.yview)
        self.audio_listbox.config(yscrollcommand=audio_scrollbar.set)
        
        self.audio_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        audio_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 音频按钮 - 第一行
        audio_btn_frame1 = ttk.Frame(left_frame)
        audio_btn_frame1.pack(fill=tk.X, pady=(5, 2))
        
        ttk.Button(audio_btn_frame1, text="添加", command=self._add_audio, width=8).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(audio_btn_frame1, text="批量添加", command=self._batch_add_audio, width=8).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(audio_btn_frame1, text="编辑", command=self._edit_audio, width=8).pack(
            side=tk.LEFT, padx=2
        )
        
        # 音频按钮 - 第二行
        audio_btn_frame2 = ttk.Frame(left_frame)
        audio_btn_frame2.pack(fill=tk.X, pady=(2, 5))
        
        ttk.Button(audio_btn_frame2, text="删除", command=self._delete_audio, width=8).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(audio_btn_frame2, text="批量删除", command=self._batch_delete_audio, width=8).pack(
            side=tk.LEFT, padx=2
        )
        
        # 右侧：Cue 列表
        right_frame = ttk.LabelFrame(main_frame, text="Cue 列表", padding=5)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Cue 列表 Treeview
        cue_list_frame = ttk.Frame(right_frame)
        cue_list_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ("序号", "标签", "音频", "入点", "出点", "前静音", "后静音", "音量")
        self.cue_tree = ttk.Treeview(cue_list_frame, columns=columns, show="headings",
                                     selectmode="extended")  # 支持多选
        
        # 设置列
        self.cue_tree.heading("序号", text="#")
        self.cue_tree.heading("标签", text="标签")
        self.cue_tree.heading("音频", text="音频")
        self.cue_tree.heading("入点", text="入点")
        self.cue_tree.heading("出点", text="出点")
        self.cue_tree.heading("前静音", text="前静音")
        self.cue_tree.heading("后静音", text="后静音")
        self.cue_tree.heading("音量", text="音量")
        
        self.cue_tree.column("序号", width=40, anchor=tk.CENTER)
        self.cue_tree.column("标签", width=120)
        self.cue_tree.column("音频", width=100)
        self.cue_tree.column("入点", width=60, anchor=tk.CENTER)
        self.cue_tree.column("出点", width=60, anchor=tk.CENTER)
        self.cue_tree.column("前静音", width=60, anchor=tk.CENTER)
        self.cue_tree.column("后静音", width=60, anchor=tk.CENTER)
        self.cue_tree.column("音量", width=50, anchor=tk.CENTER)
        
        cue_scrollbar = ttk.Scrollbar(cue_list_frame, orient=tk.VERTICAL,
                                      command=self.cue_tree.yview)
        self.cue_tree.config(yscrollcommand=cue_scrollbar.set)
        
        self.cue_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cue_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Cue 按钮 - 第一行
        cue_btn_frame1 = ttk.Frame(right_frame)
        cue_btn_frame1.pack(fill=tk.X, pady=(5, 2))
        
        ttk.Button(cue_btn_frame1, text="添加", command=self._add_cue, width=8).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(cue_btn_frame1, text="编辑", command=self._edit_cue, width=8).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(cue_btn_frame1, text="删除", command=self._delete_cue, width=8).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(cue_btn_frame1, text="批量删除", command=self._batch_delete_cue, width=8).pack(
            side=tk.LEFT, padx=2
        )
        
        # Cue 按钮 - 第二行
        cue_btn_frame2 = ttk.Frame(right_frame)
        cue_btn_frame2.pack(fill=tk.X, pady=(2, 5))
        
        ttk.Button(cue_btn_frame2, text="上移", command=self._move_cue_up, width=6).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(cue_btn_frame2, text="下移", command=self._move_cue_down, width=6).pack(
            side=tk.LEFT, padx=2
        )
        
        ttk.Separator(cue_btn_frame2, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        ttk.Button(cue_btn_frame2, text="批量设置音量", command=self._batch_set_volume, width=10).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(cue_btn_frame2, text="批量设置静音", command=self._batch_set_silence, width=10).pack(
            side=tk.LEFT, padx=2
        )
        
        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN,
                               anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def _bind_events(self):
        """绑定事件"""
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.cue_tree.bind("<Double-1>", lambda e: self._edit_cue())
        self.audio_listbox.bind("<Double-1>", lambda e: self._edit_audio())
    
    def _update_title(self):
        """更新窗口标题"""
        title = "Cue 列表配置编辑器"
        if self.current_file:
            title += f" - {os.path.basename(self.current_file)}"
        if self.modified:
            title += " *"
        self.title(title)
    
    def _set_modified(self, modified: bool = True):
        """设置修改状态"""
        self.modified = modified
        self._update_title()
    
    def _refresh_audio_list(self):
        """刷新音频列表"""
        self.audio_listbox.delete(0, tk.END)
        for audio in self.cue_manager.audio_files:
            display = f"{audio.title} [{audio.track_type.upper()}]"
            self.audio_listbox.insert(tk.END, display)
    
    def _refresh_cue_list(self):
        """刷新 Cue 列表"""
        # 清空列表
        for item in self.cue_tree.get_children():
            self.cue_tree.delete(item)
        
        # 添加 Cue
        for i, cue in enumerate(self.cue_manager.cue_list):
            # 获取音频标题
            audio = self.cue_manager.get_audio_file(cue.audio_id)
            audio_title = audio.title if audio else cue.audio_id
            
            # 格式化出点
            end_time_str = f"{cue.end_time:.1f}" if cue.end_time is not None else "结束"
            
            values = (
                i + 1,
                cue.label,
                audio_title,
                f"{cue.start_time:.1f}",
                end_time_str,
                f"{cue.silence_before:.1f}",
                f"{cue.silence_after:.1f}",
                f"{int(cue.volume * 100)}%"
            )
            self.cue_tree.insert("", tk.END, iid=cue.id, values=values)
    
    def _get_selected_cue_id(self) -> Optional[str]:
        """获取选中的 Cue ID"""
        selection = self.cue_tree.selection()
        return selection[0] if selection else None
    
    def _get_selected_audio_index(self) -> Optional[int]:
        """获取选中的音频索引"""
        selection = self.audio_listbox.curselection()
        return selection[0] if selection else None
    
    # ========== 文件操作 ==========
    
    def _new_config(self):
        """新建配置"""
        if self.modified:
            if not self._confirm_discard():
                return
        
        self.cue_manager = CueManager()
        self.cue_manager.set_config_name("新配置")
        self.current_file = None
        self._set_modified(False)
        self._refresh_audio_list()
        self._refresh_cue_list()
        self.status_var.set("已创建新配置")
    
    def _open_config(self):
        """打开配置文件"""
        if self.modified:
            if not self._confirm_discard():
                return
        
        filepath = filedialog.askopenfilename(
            parent=self,
            title="打开配置文件",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")]
        )
        if filepath:
            try:
                self.cue_manager.load_config(filepath)
                self.current_file = filepath
                self._set_modified(False)
                self._refresh_audio_list()
                self._refresh_cue_list()
                self.status_var.set(f"已打开: {os.path.basename(filepath)}")
            except Exception as e:
                messagebox.showerror("错误", f"无法打开文件:\n{e}")
    
    def _save_config(self):
        """保存配置"""
        if self.current_file:
            try:
                self.cue_manager.save_config(self.current_file)
                self._set_modified(False)
                self.status_var.set(f"已保存: {os.path.basename(self.current_file)}")
            except Exception as e:
                messagebox.showerror("错误", f"无法保存文件:\n{e}")
        else:
            self._save_config_as()
    
    def _save_config_as(self):
        """另存为"""
        filepath = filedialog.asksaveasfilename(
            parent=self,
            title="保存配置文件",
            defaultextension=".json",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")]
        )
        if filepath:
            try:
                self.cue_manager.save_config(filepath)
                self.current_file = filepath
                self._set_modified(False)
                self.status_var.set(f"已保存: {os.path.basename(filepath)}")
            except Exception as e:
                messagebox.showerror("错误", f"无法保存文件:\n{e}")
    
    def _import_json(self):
        """导入 JSON"""
        filepath = filedialog.askopenfilename(
            parent=self,
            title="导入 JSON 配置",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")]
        )
        if filepath:
            try:
                self.cue_manager.load_config(filepath)
                self._set_modified(True)
                self._refresh_audio_list()
                self._refresh_cue_list()
                self.status_var.set(f"已导入: {os.path.basename(filepath)}")
            except Exception as e:
                messagebox.showerror("错误", f"无法导入文件:\n{e}")
    
    def _export_json(self):
        """导出 JSON"""
        filepath = filedialog.asksaveasfilename(
            parent=self,
            title="导出 JSON 配置",
            defaultextension=".json",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")]
        )
        if filepath:
            try:
                self.cue_manager.save_config(filepath)
                self.status_var.set(f"已导出: {os.path.basename(filepath)}")
            except Exception as e:
                messagebox.showerror("错误", f"无法导出文件:\n{e}")
    
    def _confirm_discard(self) -> bool:
        """确认放弃修改"""
        result = messagebox.askyesnocancel(
            "未保存的更改",
            "当前配置已修改，是否保存？",
            parent=self
        )
        if result is True:  # 是
            self._save_config()
            return not self.modified  # 如果保存成功则返回 True
        elif result is False:  # 否
            return True
        else:  # 取消
            return False
    
    def _on_close(self):
        """关闭窗口"""
        if self.modified:
            if not self._confirm_discard():
                return
        self.destroy()
    
    # ========== 编辑操作 ==========
    
    def _edit_config_name(self):
        """编辑配置名称"""
        current_name = self.cue_manager.get_config_name()
        
        dialog = tk.Toplevel(self)
        dialog.title("配置名称")
        dialog.geometry("300x100")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        
        frame = ttk.Frame(dialog, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="配置名称:").pack(anchor=tk.W)
        name_var = tk.StringVar(value=current_name)
        entry = ttk.Entry(frame, textvariable=name_var, width=35)
        entry.pack(fill=tk.X, pady=5)
        entry.select_range(0, tk.END)
        entry.focus()
        
        def on_ok():
            self.cue_manager.set_config_name(name_var.get())
            self._set_modified(True)
            dialog.destroy()
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="确定", command=on_ok, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy, width=10).pack(side=tk.LEFT)
        
        dialog.bind("<Return>", lambda e: on_ok())
        dialog.bind("<Escape>", lambda e: dialog.destroy())
        
        # 居中
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - dialog.winfo_width()) // 2
        y = self.winfo_y() + (self.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")
    
    # ========== 音频操作 ==========
    
    def _add_audio(self):
        """添加音频"""
        dialog = AudioEditDialog(self)
        self.wait_window(dialog)
        
        if dialog.result:
            self.cue_manager.add_audio_file(dialog.result)
            self._set_modified(True)
            self._refresh_audio_list()
            self.status_var.set(f"已添加音频: {dialog.result.title}")
    
    def _edit_audio(self):
        """编辑音频"""
        index = self._get_selected_audio_index()
        if index is None:
            messagebox.showinfo("提示", "请先选择要编辑的音频", parent=self)
            return
        
        audio_list = self.cue_manager.audio_files
        if index >= len(audio_list):
            return
        
        audio = audio_list[index]
        dialog = AudioEditDialog(self, audio)
        self.wait_window(dialog)
        
        if dialog.result:
            # 更新音频（通过删除再添加）
            self.cue_manager.remove_audio_file(audio.id)
            # 保持原 ID
            updated_audio = AudioTrack(
                id=audio.id,
                file_path=dialog.result.file_path,
                duration=dialog.result.duration,
                title=dialog.result.title,
                track_type=dialog.result.track_type
            )
            self.cue_manager._audio_files.insert(index, updated_audio)
            self._set_modified(True)
            self._refresh_audio_list()
            self._refresh_cue_list()
            self.status_var.set(f"已更新音频: {updated_audio.title}")
    
    def _delete_audio(self):
        """删除音频"""
        index = self._get_selected_audio_index()
        if index is None:
            messagebox.showinfo("提示", "请先选择要删除的音频", parent=self)
            return
        
        audio_list = self.cue_manager.audio_files
        if index >= len(audio_list):
            return
        
        audio = audio_list[index]
        
        # 检查是否有 Cue 使用此音频
        using_cues = [c for c in self.cue_manager.cue_list if c.audio_id == audio.id]
        if using_cues:
            messagebox.showwarning(
                "无法删除",
                f"有 {len(using_cues)} 个 Cue 正在使用此音频，请先删除相关 Cue。",
                parent=self
            )
            return
        
        if messagebox.askyesno("确认删除", f"确定要删除音频 \"{audio.title}\" 吗？", parent=self):
            self.cue_manager.remove_audio_file(audio.id)
            self._set_modified(True)
            self._refresh_audio_list()
            self.status_var.set(f"已删除音频: {audio.title}")
    
    # ========== Cue 操作 ==========
    
    def _add_cue(self):
        """添加 Cue"""
        if not self.cue_manager.audio_files:
            messagebox.showinfo("提示", "请先添加音频文件", parent=self)
            return
        
        dialog = CueEditDialog(self, self.cue_manager.audio_files)
        self.wait_window(dialog)
        
        if dialog.result:
            self.cue_manager.add_cue(dialog.result)
            self._set_modified(True)
            self._refresh_cue_list()
            self.status_var.set(f"已添加 Cue: {dialog.result.label}")
    
    def _edit_cue(self):
        """编辑 Cue"""
        cue_id = self._get_selected_cue_id()
        if not cue_id:
            messagebox.showinfo("提示", "请先选择要编辑的 Cue", parent=self)
            return
        
        cue = self.cue_manager.get_cue_by_id(cue_id)
        if not cue:
            return
        
        dialog = CueEditDialog(self, self.cue_manager.audio_files, cue)
        self.wait_window(dialog)
        
        if dialog.result:
            # 更新 Cue
            self.cue_manager.update_cue(
                cue_id,
                audio_id=dialog.result.audio_id,
                start_time=dialog.result.start_time,
                end_time=dialog.result.end_time,
                silence_before=dialog.result.silence_before,
                silence_after=dialog.result.silence_after,
                volume=dialog.result.volume,
                label=dialog.result.label
            )
            self._set_modified(True)
            self._refresh_cue_list()
            self.status_var.set(f"已更新 Cue: {dialog.result.label}")
    
    def _delete_cue(self):
        """删除 Cue"""
        cue_id = self._get_selected_cue_id()
        if not cue_id:
            messagebox.showinfo("提示", "请先选择要删除的 Cue", parent=self)
            return
        
        cue = self.cue_manager.get_cue_by_id(cue_id)
        if not cue:
            return
        
        if messagebox.askyesno("确认删除", f"确定要删除 Cue \"{cue.label}\" 吗？", parent=self):
            self.cue_manager.remove_cue(cue_id)
            self._set_modified(True)
            self._refresh_cue_list()
            self.status_var.set(f"已删除 Cue: {cue.label}")
    
    def _move_cue_up(self):
        """上移 Cue"""
        cue_id = self._get_selected_cue_id()
        if not cue_id:
            messagebox.showinfo("提示", "请先选择要移动的 Cue", parent=self)
            return
        
        index = self.cue_manager.get_cue_index(cue_id)
        if index <= 0:
            return
        
        if self.cue_manager.move_cue(index, index - 1):
            self._set_modified(True)
            self._refresh_cue_list()
            # 保持选中
            self.cue_tree.selection_set(cue_id)
            self.cue_tree.see(cue_id)
            self.status_var.set("已上移 Cue")
    
    def _move_cue_down(self):
        """下移 Cue"""
        cue_id = self._get_selected_cue_id()
        if not cue_id:
            messagebox.showinfo("提示", "请先选择要移动的 Cue", parent=self)
            return
        
        index = self.cue_manager.get_cue_index(cue_id)
        if index < 0 or index >= self.cue_manager.get_cue_count() - 1:
            return
        
        if self.cue_manager.move_cue(index, index + 1):
            self._set_modified(True)
            self._refresh_cue_list()
            # 保持选中
            self.cue_tree.selection_set(cue_id)
            self.cue_tree.see(cue_id)
            self.status_var.set("已下移 Cue")
    
    # ========== 批量操作 ==========
    
    def _batch_add_audio(self):
        """批量添加音频文件"""
        filetypes = [
            ("音频文件", "*.mp3 *.m4a *.wav *.ogg"),
            ("所有文件", "*.*")
        ]
        filepaths = filedialog.askopenfilenames(
            parent=self,
            title="选择音频文件（可多选）",
            filetypes=filetypes
        )
        
        if not filepaths:
            return
        
        added_count = 0
        for filepath in filepaths:
            try:
                # 获取文件信息
                filename = os.path.basename(filepath)
                name_without_ext = os.path.splitext(filename)[0]
                
                # 获取音频时长
                duration = self._get_audio_duration_static(filepath)
                
                # 创建音频轨道
                audio = AudioTrack(
                    id=f"audio_{uuid.uuid4().hex[:8]}",
                    file_path=filepath,
                    duration=duration,
                    title=name_without_ext,
                    track_type="bgm"
                )
                
                self.cue_manager.add_audio_file(audio)
                added_count += 1
            except Exception as e:
                messagebox.showwarning(
                    "添加失败",
                    f"无法添加文件 {os.path.basename(filepath)}:\n{e}",
                    parent=self
                )
        
        if added_count > 0:
            self._set_modified(True)
            self._refresh_audio_list()
            self.status_var.set(f"已批量添加 {added_count} 个音频文件")
    
    def _get_audio_duration_static(self, filepath: str) -> float:
        """获取音频文件时长（静态方法）"""
        try:
            from mutagen import File as MutagenFile
            audio = MutagenFile(filepath)
            if audio is not None and audio.info:
                return audio.info.length
        except Exception:
            pass
        
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            sound = pygame.mixer.Sound(filepath)
            return sound.get_length()
        except Exception:
            pass
        
        return 0.0
    
    def _batch_delete_audio(self):
        """批量删除音频文件"""
        selection = self.audio_listbox.curselection()
        if not selection:
            messagebox.showinfo("提示", "请先选择要删除的音频（可按住 Ctrl 多选）", parent=self)
            return
        
        audio_list = self.cue_manager.audio_files
        to_delete = []
        blocked = []
        
        for index in selection:
            if index < len(audio_list):
                audio = audio_list[index]
                # 检查是否有 Cue 使用此音频
                using_cues = [c for c in self.cue_manager.cue_list if c.audio_id == audio.id]
                if using_cues:
                    blocked.append(f"{audio.title} (被 {len(using_cues)} 个 Cue 使用)")
                else:
                    to_delete.append(audio)
        
        if not to_delete:
            if blocked:
                messagebox.showwarning(
                    "无法删除",
                    f"以下音频正在被使用，无法删除:\n" + "\n".join(blocked),
                    parent=self
                )
            return
        
        msg = f"确定要删除以下 {len(to_delete)} 个音频吗？\n\n"
        msg += "\n".join([a.title for a in to_delete[:10]])
        if len(to_delete) > 10:
            msg += f"\n... 等共 {len(to_delete)} 个"
        
        if blocked:
            msg += f"\n\n注意：以下 {len(blocked)} 个音频因被使用将跳过:\n"
            msg += "\n".join(blocked[:5])
        
        if messagebox.askyesno("确认批量删除", msg, parent=self):
            for audio in to_delete:
                self.cue_manager.remove_audio_file(audio.id)
            
            self._set_modified(True)
            self._refresh_audio_list()
            self.status_var.set(f"已批量删除 {len(to_delete)} 个音频")
    
    def _get_selected_cue_ids(self) -> List[str]:
        """获取所有选中的 Cue ID"""
        return list(self.cue_tree.selection())
    
    def _batch_delete_cue(self):
        """批量删除 Cue"""
        cue_ids = self._get_selected_cue_ids()
        if not cue_ids:
            messagebox.showinfo("提示", "请先选择要删除的 Cue（可按住 Ctrl 多选）", parent=self)
            return
        
        cues = [self.cue_manager.get_cue_by_id(cid) for cid in cue_ids]
        cues = [c for c in cues if c is not None]
        
        if not cues:
            return
        
        msg = f"确定要删除以下 {len(cues)} 个 Cue 吗？\n\n"
        msg += "\n".join([c.label for c in cues[:10]])
        if len(cues) > 10:
            msg += f"\n... 等共 {len(cues)} 个"
        
        if messagebox.askyesno("确认批量删除", msg, parent=self):
            for cue_id in cue_ids:
                self.cue_manager.remove_cue(cue_id)
            
            self._set_modified(True)
            self._refresh_cue_list()
            self.status_var.set(f"已批量删除 {len(cues)} 个 Cue")
    
    def _batch_set_volume(self):
        """批量设置 Cue 音量"""
        cue_ids = self._get_selected_cue_ids()
        if not cue_ids:
            messagebox.showinfo("提示", "请先选择要修改的 Cue（可按住 Ctrl 多选）", parent=self)
            return
        
        # 创建音量设置对话框
        dialog = tk.Toplevel(self)
        dialog.title("批量设置音量")
        dialog.geometry("300x120")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        
        frame = ttk.Frame(dialog, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text=f"为选中的 {len(cue_ids)} 个 Cue 设置音量:").pack(anchor=tk.W)
        
        volume_frame = ttk.Frame(frame)
        volume_frame.pack(fill=tk.X, pady=10)
        
        volume_var = tk.DoubleVar(value=1.0)
        volume_scale = ttk.Scale(volume_frame, from_=0.0, to=1.0, variable=volume_var,
                                 orient=tk.HORIZONTAL, length=180)
        volume_scale.pack(side=tk.LEFT)
        
        volume_label = ttk.Label(volume_frame, text="100%", width=6)
        volume_label.pack(side=tk.LEFT, padx=5)
        
        def update_label(*args):
            volume_label.config(text=f"{int(volume_var.get() * 100)}%")
        volume_var.trace_add("write", update_label)
        
        def on_ok():
            volume = volume_var.get()
            for cue_id in cue_ids:
                self.cue_manager.update_cue(cue_id, volume=volume)
            self._set_modified(True)
            self._refresh_cue_list()
            self.status_var.set(f"已为 {len(cue_ids)} 个 Cue 设置音量为 {int(volume * 100)}%")
            dialog.destroy()
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="确定", command=on_ok, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy, width=8).pack(side=tk.LEFT)
        
        # 居中
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - dialog.winfo_width()) // 2
        y = self.winfo_y() + (self.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")
    
    def _batch_set_silence(self):
        """批量设置 Cue 静音间隔"""
        cue_ids = self._get_selected_cue_ids()
        if not cue_ids:
            messagebox.showinfo("提示", "请先选择要修改的 Cue（可按住 Ctrl 多选）", parent=self)
            return
        
        # 创建静音设置对话框
        dialog = tk.Toplevel(self)
        dialog.title("批量设置静音间隔")
        dialog.geometry("320x180")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        
        frame = ttk.Frame(dialog, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text=f"为选中的 {len(cue_ids)} 个 Cue 设置静音间隔:").pack(anchor=tk.W)
        
        # 前置静音
        before_frame = ttk.Frame(frame)
        before_frame.pack(fill=tk.X, pady=5)
        ttk.Label(before_frame, text="前置静音 (秒):").pack(side=tk.LEFT)
        before_var = tk.StringVar(value="0.0")
        ttk.Entry(before_frame, textvariable=before_var, width=10).pack(side=tk.LEFT, padx=5)
        
        # 后置静音
        after_frame = ttk.Frame(frame)
        after_frame.pack(fill=tk.X, pady=5)
        ttk.Label(after_frame, text="后置静音 (秒):").pack(side=tk.LEFT)
        after_var = tk.StringVar(value="0.0")
        ttk.Entry(after_frame, textvariable=after_var, width=10).pack(side=tk.LEFT, padx=5)
        
        def on_ok():
            try:
                silence_before = float(before_var.get() or "0")
                silence_after = float(after_var.get() or "0")
                
                if silence_before < 0 or silence_after < 0:
                    messagebox.showerror("错误", "静音时间不能为负数", parent=dialog)
                    return
                
                for cue_id in cue_ids:
                    self.cue_manager.update_cue(
                        cue_id,
                        silence_before=silence_before,
                        silence_after=silence_after
                    )
                
                self._set_modified(True)
                self._refresh_cue_list()
                self.status_var.set(f"已为 {len(cue_ids)} 个 Cue 设置静音间隔")
                dialog.destroy()
            except ValueError:
                messagebox.showerror("错误", "请输入有效的数字", parent=dialog)
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="确定", command=on_ok, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy, width=8).pack(side=tk.LEFT)
        
        # 居中
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - dialog.winfo_width()) // 2
        y = self.winfo_y() + (self.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")


def main():
    """配置编辑器入口"""
    app = ConfigEditor()
    app.mainloop()


if __name__ == "__main__":
    main()
