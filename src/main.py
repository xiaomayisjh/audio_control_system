"""舞台剧音效控制系统 - 主程序入口

初始化所有组件，启动 GUI 和 API 服务器，加载上次保存的配置和断点。

Requirements: 8.4, 14.1
"""
import asyncio
import os
import sys
import threading
from pathlib import Path
from typing import Optional

# 确保项目根目录在 Python 路径中
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pygame

from src.core.controller import CoreController, PlayMode
from src.core.audio_engine import AudioEngine
from src.core.cue_manager import CueManager
from src.core.breakpoint_manager import BreakpointManager
from src.gui.main_window import MainWindow
from src.gui.auto_mode_panel import AutoModePanel
from src.gui.manual_mode_panel import ManualModePanel
from src.gui.sfx_panel import SFXPanel
from src.gui.volume_panel import VolumePanel
from src.gui.qrcode_window import QRCodeWindow
from src.api.server import APIServer


# 默认配置路径
DEFAULT_CONFIG_DIR = Path("config")
DEFAULT_CUE_CONFIG = DEFAULT_CONFIG_DIR / "cue_config.json"
DEFAULT_BREAKPOINTS = DEFAULT_CONFIG_DIR / "breakpoints.json"
DEFAULT_AUDIO_DIR = Path("source_files")

# API 服务器配置
API_HOST = "0.0.0.0"
API_PORT = 8080


class Application:
    """应用程序主类
    
    负责初始化和协调所有组件：
    - 核心控制器
    - GUI 主窗口和各面板
    - API 服务器
    - 配置和断点的加载/保存
    """
    
    def __init__(self):
        """初始化应用程序"""
        self._controller: Optional[CoreController] = None
        self._main_window: Optional[MainWindow] = None
        self._api_server: Optional[APIServer] = None
        self._qrcode_window: Optional[QRCodeWindow] = None
        
        # 面板实例
        self._auto_mode_panel: Optional[AutoModePanel] = None
        self._manual_mode_panel: Optional[ManualModePanel] = None
        self._sfx_panel: Optional[SFXPanel] = None
        self._volume_panel: Optional[VolumePanel] = None
        
        # 异步事件循环
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._api_thread: Optional[threading.Thread] = None
        
        # 运行状态
        self._running = False
    
    def initialize(self) -> bool:
        """初始化所有组件
        
        Returns:
            是否初始化成功
        """
        try:
            # 初始化 pygame
            pygame.init()
            
            # 确保配置目录存在
            DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            
            # 初始化核心组件
            audio_engine = AudioEngine()
            cue_manager = CueManager()
            breakpoint_manager = BreakpointManager()
            
            # 加载上次保存的配置和断点 (Requirements: 8.4)
            self._load_saved_data(cue_manager, breakpoint_manager)
            
            # 创建核心控制器
            CoreController.reset_instance()  # 确保单例重置
            self._controller = CoreController(
                audio_engine=audio_engine,
                cue_manager=cue_manager,
                breakpoint_manager=breakpoint_manager
            )
            
            # 创建 API 服务器 (Requirements: 14.1)
            self._api_server = APIServer(
                controller=self._controller,
                host=API_HOST,
                port=API_PORT,
                audio_dir=str(DEFAULT_AUDIO_DIR)
            )
            
            # 创建 GUI
            self._create_gui()
            
            return True
            
        except Exception as e:
            print(f"初始化失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _load_saved_data(
        self,
        cue_manager: CueManager,
        breakpoint_manager: BreakpointManager
    ) -> None:
        """加载上次保存的配置和断点
        
        Args:
            cue_manager: Cue 管理器
            breakpoint_manager: 断点管理器
        
        Requirements: 8.4
        """
        # 加载 Cue 配置
        if DEFAULT_CUE_CONFIG.exists():
            try:
                cue_manager.load_config(str(DEFAULT_CUE_CONFIG))
                print(f"已加载 Cue 配置: {DEFAULT_CUE_CONFIG}")
            except Exception as e:
                print(f"加载 Cue 配置失败: {e}")
        
        # 加载断点数据
        if DEFAULT_BREAKPOINTS.exists():
            try:
                breakpoint_manager.load_from_file(str(DEFAULT_BREAKPOINTS))
                print(f"已加载断点数据: {DEFAULT_BREAKPOINTS}")
            except Exception as e:
                print(f"加载断点数据失败: {e}")
    
    def _save_data(self) -> None:
        """保存配置和断点数据"""
        if not self._controller:
            return
        
        try:
            # 保存 Cue 配置
            self._controller.cue_manager.save_config(str(DEFAULT_CUE_CONFIG))
            print(f"已保存 Cue 配置: {DEFAULT_CUE_CONFIG}")
        except Exception as e:
            print(f"保存 Cue 配置失败: {e}")
        
        try:
            # 保存断点数据
            self._controller.breakpoint_manager.save_to_file(str(DEFAULT_BREAKPOINTS))
            print(f"已保存断点数据: {DEFAULT_BREAKPOINTS}")
        except Exception as e:
            print(f"保存断点数据失败: {e}")
    
    def _create_gui(self) -> None:
        """创建 GUI 界面"""
        # 创建主窗口
        self._main_window = MainWindow(
            controller=self._controller,
            on_close=self._on_close
        )
        root = self._main_window.create()
        
        # 创建自动模式面板
        auto_frame = self._main_window.get_auto_mode_frame()
        if auto_frame and self._controller:
            self._auto_mode_panel = AutoModePanel(
                parent=auto_frame,
                controller=self._controller
            )
            self._main_window.set_auto_mode_panel(self._auto_mode_panel)
        
        # 创建手动模式面板
        manual_frame = self._main_window.get_manual_mode_frame()
        if manual_frame and self._controller:
            self._manual_mode_panel = ManualModePanel(
                parent=manual_frame,
                controller=self._controller
            )
            self._main_window.set_manual_mode_panel(self._manual_mode_panel)
        
        # 创建音效面板
        sfx_frame = self._main_window.get_sfx_frame()
        if sfx_frame and self._controller:
            self._sfx_panel = SFXPanel(
                parent=sfx_frame,
                controller=self._controller
            )
            self._main_window.set_sfx_panel(self._sfx_panel)
        
        # 创建音量控制面板
        volume_frame = self._main_window.get_volume_frame()
        if volume_frame and self._controller:
            self._volume_panel = VolumePanel(
                parent=volume_frame,
                controller=self._controller
            )
            self._main_window.set_volume_panel(self._volume_panel)
        
        # 居中显示窗口
        self._main_window.center_window()
    
    def _start_api_server(self) -> None:
        """在后台线程启动 API 服务器"""
        def run_server():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            
            try:
                self._loop.run_until_complete(self._api_server.start())
                print(f"API 服务器已启动: http://{API_HOST}:{API_PORT}")
                
                # 显示二维码窗口
                self._show_qrcode()
                
                # 保持事件循环运行
                self._loop.run_forever()
            except Exception as e:
                print(f"API 服务器错误: {e}")
            finally:
                self._loop.close()
        
        self._api_thread = threading.Thread(target=run_server, daemon=True)
        self._api_thread.start()
    
    def _show_qrcode(self) -> None:
        """显示 Web UI 访问二维码"""
        if not self._main_window or not self._main_window.root:
            return
        
        # 在主线程中创建二维码窗口
        def create_qrcode():
            try:
                self._qrcode_window = QRCodeWindow(
                    host=API_HOST,
                    port=API_PORT,
                    parent=self._main_window.root
                )
                self._qrcode_window.show()
            except Exception as e:
                print(f"创建二维码窗口失败: {e}")
        
        if self._main_window.root:
            self._main_window.root.after(100, create_qrcode)
    
    def _stop_api_server(self) -> None:
        """停止 API 服务器"""
        if self._loop and self._api_server:
            try:
                # 在事件循环中停止服务器
                future = asyncio.run_coroutine_threadsafe(
                    self._api_server.stop(),
                    self._loop
                )
                # 等待停止完成（最多 2 秒）
                try:
                    future.result(timeout=2.0)
                except Exception:
                    pass
            except Exception as e:
                print(f"停止 API 服务器时出错: {e}")
            finally:
                # 停止事件循环
                if self._loop.is_running():
                    self._loop.call_soon_threadsafe(self._loop.stop)
    
    def _on_close(self) -> None:
        """窗口关闭回调"""
        self._running = False
        
        # 保存数据
        self._save_data()
        
        # 停止 API 服务器
        self._stop_api_server()
        
        # 关闭二维码窗口
        if self._qrcode_window:
            try:
                self._qrcode_window.destroy()
            except Exception:
                pass
        
        # 关闭音频引擎
        if self._controller:
            try:
                self._controller.audio_engine.shutdown()
            except Exception:
                pass
        
        # 退出 pygame
        pygame.quit()
        
        print("应用程序已关闭")
    
    def run(self) -> None:
        """运行应用程序"""
        if not self._main_window:
            print("错误: GUI 未初始化")
            return
        
        self._running = True
        
        # 启动 API 服务器
        self._start_api_server()
        
        # 运行 GUI 主循环
        print("启动 GUI...")
        self._main_window.run()


def main():
    """主程序入口"""
    print("="*50)
    print("舞台剧音效控制系统")
    print("="*50)
    
    app = Application()
    
    if app.initialize():
        print("初始化完成，启动应用程序...")
        app.run()
    else:
        print("初始化失败，程序退出")
        sys.exit(1)


if __name__ == "__main__":
    main()
