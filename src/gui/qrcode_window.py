"""二维码显示窗口模块

提供 Web UI 访问地址的二维码显示功能。

功能：
- 生成 Web UI URL 二维码
- 独立窗口显示，不干扰主界面
- 控制台打印 URL
"""
import io
import socket
import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable
from PIL import Image, ImageTk

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False


def get_local_ip() -> str:
    """获取本机局域网 IP 地址
    
    Returns:
        本机 IP 地址，如果获取失败则返回 localhost
    """
    try:
        # 创建一个 UDP socket 来获取本机 IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


class QRCodeWindow:
    """二维码显示窗口
    
    显示 Web UI 访问地址的二维码，方便手机扫描访问。
    """
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        parent: Optional[tk.Tk] = None,
        on_close: Optional[Callable] = None
    ):
        """初始化二维码窗口
        
        Args:
            host: 服务器监听地址
            port: 服务器监听端口
            parent: 父窗口（可选）
            on_close: 窗口关闭回调（可选）
        """
        self._host = host
        self._port = port
        self._parent = parent
        self._on_close = on_close
        
        self._window: Optional[tk.Toplevel] = None
        self._qr_image: Optional[ImageTk.PhotoImage] = None
        
        # 生成访问 URL
        self._url = self._generate_url()
    
    def _generate_url(self) -> str:
        """生成 Web UI 访问 URL
        
        Returns:
            Web UI 访问地址
        """
        # 如果监听地址是 0.0.0.0，使用本机 IP
        if self._host == "0.0.0.0":
            ip = get_local_ip()
        else:
            ip = self._host
        
        return f"http://{ip}:{self._port}"

    def _generate_qr_code(self, size: int = 250) -> Optional[ImageTk.PhotoImage]:
        """生成二维码图片
        
        Args:
            size: 二维码尺寸（像素）
            
        Returns:
            Tkinter 可用的图片对象，如果生成失败则返回 None
        """
        if not HAS_QRCODE:
            return None
        
        try:
            # 创建二维码
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=2,
            )
            qr.add_data(self._url)
            qr.make(fit=True)
            
            # 生成图片
            img = qr.make_image(fill_color="black", back_color="white")
            
            # 调整大小
            img = img.resize((size, size), Image.Resampling.LANCZOS)
            
            # 转换为 Tkinter 可用的格式
            return ImageTk.PhotoImage(img)
            
        except Exception as e:
            print(f"生成二维码失败: {e}")
            return None
    
    def show(self) -> None:
        """显示二维码窗口"""
        if self._window is not None:
            # 窗口已存在，将其置于前台
            self._window.lift()
            self._window.focus_force()
            return
        
        # 创建独立窗口
        if self._parent:
            self._window = tk.Toplevel(self._parent)
        else:
            self._window = tk.Toplevel()
        
        self._window.title("Web UI 访问地址")
        self._window.resizable(False, False)
        
        # 设置窗口关闭事件
        self._window.protocol("WM_DELETE_WINDOW", self._handle_close)
        
        # 创建主框架
        main_frame = ttk.Frame(self._window, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title_label = ttk.Label(
            main_frame,
            text="扫描二维码访问 Web UI",
            font=("", 14, "bold")
        )
        title_label.pack(pady=(0, 15))
        
        # 二维码图片
        self._qr_image = self._generate_qr_code(250)
        
        if self._qr_image:
            qr_label = ttk.Label(main_frame, image=self._qr_image)
            qr_label.pack(pady=10)
        else:
            # 如果无法生成二维码，显示提示
            no_qr_label = ttk.Label(
                main_frame,
                text="无法生成二维码\n请安装 qrcode 库:\npip install qrcode[pil]",
                justify=tk.CENTER,
                foreground="red"
            )
            no_qr_label.pack(pady=30)
        
        # URL 显示
        url_frame = ttk.Frame(main_frame)
        url_frame.pack(fill=tk.X, pady=15)
        
        url_label = ttk.Label(
            url_frame,
            text="访问地址:",
            font=("", 10)
        )
        url_label.pack(side=tk.LEFT)
        
        # URL 输入框（可复制）
        url_entry = ttk.Entry(url_frame, width=30, font=("", 10))
        url_entry.insert(0, self._url)
        url_entry.configure(state="readonly")
        url_entry.pack(side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True)
        
        # 复制按钮
        copy_btn = ttk.Button(
            url_frame,
            text="复制",
            command=lambda: self._copy_url(url_entry),
            width=6
        )
        copy_btn.pack(side=tk.LEFT, padx=(10, 0))
        
        # 提示信息
        tip_label = ttk.Label(
            main_frame,
            text="请确保手机与电脑在同一局域网内",
            font=("", 9),
            foreground="gray"
        )
        tip_label.pack(pady=(10, 0))
        
        # 关闭按钮
        close_btn = ttk.Button(
            main_frame,
            text="关闭",
            command=self._handle_close,
            width=10
        )
        close_btn.pack(pady=(15, 0))
        
        # 打印 URL 到控制台
        self._print_url()
        
        # 居中显示
        self._center_window()
    
    def _copy_url(self, entry: ttk.Entry) -> None:
        """复制 URL 到剪贴板
        
        Args:
            entry: URL 输入框
        """
        self._window.clipboard_clear()
        self._window.clipboard_append(self._url)
        
        # 显示复制成功提示
        entry.configure(state="normal")
        entry.delete(0, tk.END)
        entry.insert(0, "已复制!")
        entry.configure(state="readonly")
        
        # 1秒后恢复显示 URL
        self._window.after(1000, lambda: self._restore_url(entry))
    
    def _restore_url(self, entry: ttk.Entry) -> None:
        """恢复 URL 显示
        
        Args:
            entry: URL 输入框
        """
        entry.configure(state="normal")
        entry.delete(0, tk.END)
        entry.insert(0, self._url)
        entry.configure(state="readonly")
    
    def _center_window(self) -> None:
        """将窗口居中显示"""
        self._window.update_idletasks()
        
        width = self._window.winfo_width()
        height = self._window.winfo_height()
        
        # 获取屏幕尺寸
        screen_width = self._window.winfo_screenwidth()
        screen_height = self._window.winfo_screenheight()
        
        # 计算居中位置
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        
        self._window.geometry(f"+{x}+{y}")
    
    def _print_url(self) -> None:
        """打印 URL 到控制台"""
        print("\n" + "=" * 50)
        print("Web UI 访问地址:")
        print(f"  {self._url}")
        print("=" * 50 + "\n")
    
    def _handle_close(self) -> None:
        """处理窗口关闭"""
        if self._window:
            self._window.destroy()
            self._window = None
            self._qr_image = None
        
        if self._on_close:
            self._on_close()
    
    def close(self) -> None:
        """关闭窗口"""
        self._handle_close()
    
    def is_visible(self) -> bool:
        """检查窗口是否可见
        
        Returns:
            窗口是否可见
        """
        return self._window is not None and self._window.winfo_exists()
    
    @property
    def url(self) -> str:
        """获取 Web UI 访问 URL
        
        Returns:
            Web UI 访问地址
        """
        return self._url


def show_qrcode_window(
    host: str = "0.0.0.0",
    port: int = 8080,
    parent: Optional[tk.Tk] = None
) -> QRCodeWindow:
    """显示二维码窗口的便捷函数
    
    Args:
        host: 服务器监听地址
        port: 服务器监听端口
        parent: 父窗口（可选）
        
    Returns:
        QRCodeWindow 实例
    """
    window = QRCodeWindow(host, port, parent)
    window.show()
    return window
