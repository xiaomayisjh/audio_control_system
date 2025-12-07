"""
API 通信层模块

实现远程客户端与控制台服务器的通信，包含：
- 所有 API 调用封装
- WebSocket 状态同步
- 断线重连

**Requirements: 16.3-16.6**
"""
import asyncio
import json
import aiohttp
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import threading
import time


class ConnectionState(Enum):
    """连接状态枚举"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"


@dataclass
class APIResponse:
    """API 响应数据类"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class APIClient:
    """
    API 客户端类
    
    封装所有与控制台服务器的 HTTP API 和 WebSocket 通信。
    
    **Requirements: 16.3-16.6**
    """
    
    # 重连配置
    MAX_RECONNECT_ATTEMPTS = 5
    RECONNECT_DELAY_BASE = 1.0  # 基础重连延迟（秒）
    RECONNECT_DELAY_MAX = 30.0  # 最大重连延迟（秒）
    
    # 请求超时
    REQUEST_TIMEOUT = 10.0
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8080
    ):
        """
        初始化 API 客户端
        
        Args:
            host: 服务器地址
            port: 服务器端口
        """
        self._host = host
        self._port = port
        
        # HTTP 会话
        self._session: Optional[aiohttp.ClientSession] = None
        
        # WebSocket 连接
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._ws_task: Optional[asyncio.Task] = None
        
        # 连接状态
        self._connection_state = ConnectionState.DISCONNECTED
        self._reconnect_attempts = 0
        
        # 事件回调
        self._state_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._connection_callbacks: List[Callable[[ConnectionState], None]] = []
        
        # 事件循环
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._running = False
    
    @property
    def base_url(self) -> str:
        """获取 API 基础 URL"""
        return f"http://{self._host}:{self._port}"
    
    @property
    def ws_url(self) -> str:
        """获取 WebSocket URL"""
        return f"ws://{self._host}:{self._port}/ws"
    
    @property
    def connection_state(self) -> ConnectionState:
        """获取当前连接状态"""
        return self._connection_state
    
    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connection_state == ConnectionState.CONNECTED
    
    def set_server(self, host: str, port: int) -> None:
        """
        设置服务器地址
        
        Args:
            host: 服务器地址
            port: 服务器端口
        """
        self._host = host
        self._port = port
    
    # ==================== 连接管理 ====================
    
    async def connect(self) -> bool:
        """
        连接到服务器
        
        Returns:
            bool: 是否连接成功
        """
        if self._connection_state == ConnectionState.CONNECTED:
            return True
        
        self._set_connection_state(ConnectionState.CONNECTING)
        
        try:
            # 创建 HTTP 会话
            if not self._session:
                self._session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=self.REQUEST_TIMEOUT)
                )
            
            # 测试连接
            async with self._session.get(f"{self.base_url}/api/state") as resp:
                if resp.status != 200:
                    raise ConnectionError(f"Server returned status {resp.status}")
            
            # 启动 WebSocket 连接
            await self._connect_websocket()
            
            self._reconnect_attempts = 0
            self._set_connection_state(ConnectionState.CONNECTED)
            return True
            
        except Exception as e:
            print(f"Connection failed: {e}")
            self._set_connection_state(ConnectionState.DISCONNECTED)
            return False
    
    async def disconnect(self) -> None:
        """断开连接"""
        self._running = False
        
        # 关闭 WebSocket
        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._ws = None
        
        # 取消 WebSocket 任务
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            self._ws_task = None
        
        # 关闭 HTTP 会话
        if self._session:
            await self._session.close()
            self._session = None
        
        self._set_connection_state(ConnectionState.DISCONNECTED)
    
    async def _connect_websocket(self) -> None:
        """建立 WebSocket 连接"""
        if not self._session:
            return
        
        try:
            self._ws = await self._session.ws_connect(self.ws_url)
            self._running = True
            
            # 启动消息接收任务
            self._ws_task = asyncio.create_task(self._ws_receive_loop())
            
        except Exception as e:
            print(f"WebSocket connection failed: {e}")
            raise
    
    async def _ws_receive_loop(self) -> None:
        """WebSocket 消息接收循环"""
        while self._running and self._ws and not self._ws.closed:
            try:
                msg = await self._ws.receive(timeout=30)
                
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    await self._handle_ws_message(data)
                    
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    break
                    
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break
                    
            except asyncio.TimeoutError:
                # 发送心跳
                if self._ws and not self._ws.closed:
                    await self._ws.send_json({"type": "ping"})
                    
            except Exception as e:
                print(f"WebSocket receive error: {e}")
                break
        
        # 连接断开，尝试重连
        if self._running:
            await self._handle_disconnect()
    
    async def _handle_ws_message(self, data: Dict[str, Any]) -> None:
        """
        处理 WebSocket 消息
        
        Args:
            data: 消息数据
        """
        msg_type = data.get("type")
        
        if msg_type == "state":
            # 状态更新
            state_data = data.get("data", {})
            self._notify_state_change(state_data)
            
        elif msg_type == "event":
            # 事件通知
            state_data = data.get("state", {})
            self._notify_state_change(state_data)
            
        elif msg_type == "pong":
            # 心跳响应
            pass
    
    async def _handle_disconnect(self) -> None:
        """处理连接断开"""
        self._set_connection_state(ConnectionState.RECONNECTING)
        
        # 尝试重连
        while self._running and self._reconnect_attempts < self.MAX_RECONNECT_ATTEMPTS:
            self._reconnect_attempts += 1
            
            # 计算重连延迟（指数退避）
            delay = min(
                self.RECONNECT_DELAY_BASE * (2 ** (self._reconnect_attempts - 1)),
                self.RECONNECT_DELAY_MAX
            )
            
            print(f"Reconnecting in {delay:.1f}s (attempt {self._reconnect_attempts}/{self.MAX_RECONNECT_ATTEMPTS})")
            await asyncio.sleep(delay)
            
            try:
                # 重新建立 WebSocket 连接
                await self._connect_websocket()
                self._reconnect_attempts = 0
                self._set_connection_state(ConnectionState.CONNECTED)
                return
                
            except Exception as e:
                print(f"Reconnect failed: {e}")
        
        # 重连失败
        self._set_connection_state(ConnectionState.DISCONNECTED)
    
    def _set_connection_state(self, state: ConnectionState) -> None:
        """
        设置连接状态并通知回调
        
        Args:
            state: 新的连接状态
        """
        if self._connection_state != state:
            self._connection_state = state
            for callback in self._connection_callbacks:
                try:
                    callback(state)
                except Exception as e:
                    print(f"Connection callback error: {e}")
    
    # ==================== 事件回调 ====================
    
    def add_state_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        添加状态变化回调
        
        Args:
            callback: 回调函数
        """
        if callback not in self._state_callbacks:
            self._state_callbacks.append(callback)
    
    def remove_state_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        移除状态变化回调
        
        Args:
            callback: 回调函数
        """
        if callback in self._state_callbacks:
            self._state_callbacks.remove(callback)
    
    def add_connection_callback(self, callback: Callable[[ConnectionState], None]) -> None:
        """
        添加连接状态回调
        
        Args:
            callback: 回调函数
        """
        if callback not in self._connection_callbacks:
            self._connection_callbacks.append(callback)
    
    def remove_connection_callback(self, callback: Callable[[ConnectionState], None]) -> None:
        """
        移除连接状态回调
        
        Args:
            callback: 回调函数
        """
        if callback in self._connection_callbacks:
            self._connection_callbacks.remove(callback)
    
    def _notify_state_change(self, state: Dict[str, Any]) -> None:
        """
        通知状态变化
        
        Args:
            state: 状态数据
        """
        for callback in self._state_callbacks:
            try:
                callback(state)
            except Exception as e:
                print(f"State callback error: {e}")

    # ==================== HTTP API 调用 ====================
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None
    ) -> APIResponse:
        """
        发送 HTTP 请求
        
        Args:
            method: HTTP 方法
            endpoint: API 端点
            data: 请求数据
            
        Returns:
            APIResponse: 响应对象
        """
        if not self._session:
            return APIResponse(success=False, error="Not connected")
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == "GET":
                async with self._session.get(url) as resp:
                    result = await resp.json()
                    return APIResponse(
                        success=resp.status == 200,
                        data=result,
                        error=result.get("error") if resp.status != 200 else None
                    )
            elif method == "POST":
                async with self._session.post(url, json=data) as resp:
                    result = await resp.json()
                    return APIResponse(
                        success=resp.status == 200 and result.get("success", True),
                        data=result,
                        error=result.get("error") if resp.status != 200 else None
                    )
            elif method == "DELETE":
                async with self._session.delete(url) as resp:
                    result = await resp.json()
                    return APIResponse(
                        success=resp.status == 200,
                        data=result,
                        error=result.get("error") if resp.status != 200 else None
                    )
            else:
                return APIResponse(success=False, error=f"Unknown method: {method}")
                
        except asyncio.TimeoutError:
            return APIResponse(success=False, error="Request timeout")
        except aiohttp.ClientError as e:
            return APIResponse(success=False, error=str(e))
        except Exception as e:
            return APIResponse(success=False, error=str(e))
    
    # ==================== 播放控制 API ====================
    
    async def play(self) -> APIResponse:
        """播放"""
        return await self._request("POST", "/api/play")
    
    async def pause(self) -> APIResponse:
        """暂停"""
        return await self._request("POST", "/api/pause")
    
    async def resume(self) -> APIResponse:
        """继续播放"""
        return await self._request("POST", "/api/resume")
    
    async def stop(self) -> APIResponse:
        """停止"""
        return await self._request("POST", "/api/stop")
    
    async def next_cue(self) -> APIResponse:
        """跳至下一段"""
        return await self._request("POST", "/api/next")
    
    async def seek(self, position: float) -> APIResponse:
        """
        跳转到指定位置
        
        Args:
            position: 目标位置（秒）
        """
        return await self._request("POST", "/api/seek", {"position": position})
    
    async def replay(self) -> APIResponse:
        """重播"""
        return await self._request("POST", "/api/replay")
    
    # ==================== 音量控制 API ====================
    
    async def set_bgm_volume(self, volume: float) -> APIResponse:
        """
        设置 BGM 音量
        
        Args:
            volume: 音量值 (0.0 - 1.0)
        """
        return await self._request("POST", "/api/volume/bgm", {"volume": volume})
    
    async def set_sfx_volume(self, volume: float) -> APIResponse:
        """
        设置音效音量
        
        Args:
            volume: 音量值 (0.0 - 1.0)
        """
        return await self._request("POST", "/api/volume/sfx", {"volume": volume})
    
    async def get_volume(self) -> APIResponse:
        """获取当前音量"""
        return await self._request("GET", "/api/volume")
    
    # ==================== 状态查询 API ====================
    
    async def get_state(self) -> APIResponse:
        """获取当前播放状态"""
        return await self._request("GET", "/api/state")
    
    # ==================== 模式切换 API ====================
    
    async def switch_mode(self, mode: str) -> APIResponse:
        """
        切换播放模式
        
        Args:
            mode: 模式 ("auto" 或 "manual")
        """
        return await self._request("POST", "/api/mode", {"mode": mode})
    
    async def get_mode(self) -> APIResponse:
        """获取当前播放模式"""
        return await self._request("GET", "/api/mode")
    
    # ==================== Cue 列表 API ====================
    
    async def get_cues(self) -> APIResponse:
        """获取 Cue 列表"""
        return await self._request("GET", "/api/cues")
    
    async def update_cues(self, cues: List[Dict[str, Any]], config_name: str = "") -> APIResponse:
        """
        更新 Cue 列表
        
        Args:
            cues: Cue 列表数据
            config_name: 配置名称
        """
        return await self._request("POST", "/api/cues", {
            "cues": cues,
            "config_name": config_name
        })
    
    async def add_cue(self, cue: Dict[str, Any]) -> APIResponse:
        """
        添加 Cue
        
        Args:
            cue: Cue 数据
        """
        return await self._request("POST", "/api/cues/add", cue)
    
    async def delete_cue(self, cue_id: str) -> APIResponse:
        """
        删除 Cue
        
        Args:
            cue_id: Cue ID
        """
        return await self._request("DELETE", f"/api/cues/{cue_id}")
    
    # ==================== 音频管理 API ====================
    
    async def get_audio_list(self) -> APIResponse:
        """获取音频文件列表"""
        return await self._request("GET", "/api/audio")
    
    async def upload_audio(
        self,
        file_path: str,
        title: Optional[str] = None,
        track_type: str = "bgm",
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> APIResponse:
        """
        上传音频文件
        
        Args:
            file_path: 文件路径
            title: 标题
            track_type: 轨道类型 ("bgm" 或 "sfx")
            progress_callback: 上传进度回调
            
        Returns:
            APIResponse: 响应对象
        """
        if not self._session:
            return APIResponse(success=False, error="Not connected")
        
        import os
        from pathlib import Path
        
        file_path = Path(file_path)
        if not file_path.exists():
            return APIResponse(success=False, error="File not found")
        
        try:
            # 创建 multipart 表单数据
            data = aiohttp.FormData()
            
            # 添加文件
            file_size = file_path.stat().st_size
            
            with open(file_path, "rb") as f:
                data.add_field(
                    "file",
                    f,
                    filename=file_path.name,
                    content_type="audio/mpeg"
                )
                
                # 添加其他字段
                data.add_field("title", title or file_path.stem)
                data.add_field("track_type", track_type)
                
                # 发送请求
                url = f"{self.base_url}/api/audio/upload"
                async with self._session.post(url, data=data) as resp:
                    result = await resp.json()
                    return APIResponse(
                        success=resp.status == 200 and result.get("success", False),
                        data=result,
                        error=result.get("error") if resp.status != 200 else None
                    )
                    
        except Exception as e:
            return APIResponse(success=False, error=str(e))
    
    async def delete_audio(self, audio_id: str) -> APIResponse:
        """
        删除音频文件
        
        Args:
            audio_id: 音频 ID
        """
        return await self._request("DELETE", f"/api/audio/{audio_id}")
    
    # ==================== 断点管理 API ====================
    
    async def get_breakpoints(self, audio_id: str) -> APIResponse:
        """
        获取指定音频的断点列表
        
        Args:
            audio_id: 音频 ID
        """
        return await self._request("GET", f"/api/breakpoints/{audio_id}")
    
    async def save_breakpoint(
        self,
        audio_id: str,
        position: float,
        label: str = ""
    ) -> APIResponse:
        """
        保存断点
        
        Args:
            audio_id: 音频 ID
            position: 位置（秒）
            label: 标签
        """
        return await self._request("POST", f"/api/breakpoints/{audio_id}", {
            "position": position,
            "label": label
        })
    
    async def delete_breakpoint(self, audio_id: str, bp_id: str) -> APIResponse:
        """
        删除断点
        
        Args:
            audio_id: 音频 ID
            bp_id: 断点 ID
        """
        return await self._request("DELETE", f"/api/breakpoints/{audio_id}/{bp_id}")
    
    async def clear_breakpoints(self, audio_id: str) -> APIResponse:
        """
        清除指定音频的所有断点
        
        Args:
            audio_id: 音频 ID
        """
        return await self._request("DELETE", f"/api/breakpoints/{audio_id}")
    
    # ==================== 音效控制 API ====================
    
    async def play_sfx(self, sfx_id: str) -> APIResponse:
        """
        播放音效
        
        Args:
            sfx_id: 音效 ID
        """
        return await self._request("POST", f"/api/sfx/play/{sfx_id}")
    
    async def stop_sfx(self, sfx_id: str) -> APIResponse:
        """
        停止音效
        
        Args:
            sfx_id: 音效 ID
        """
        return await self._request("POST", f"/api/sfx/stop/{sfx_id}")
    
    async def toggle_sfx(self, sfx_id: str) -> APIResponse:
        """
        切换音效状态
        
        Args:
            sfx_id: 音效 ID
        """
        return await self._request("POST", f"/api/sfx/toggle/{sfx_id}")


class SyncAPIClient:
    """
    同步 API 客户端包装器
    
    为 Tkinter 等同步环境提供同步接口。
    """
    
    def __init__(self, host: str = "localhost", port: int = 8080):
        """
        初始化同步客户端
        
        Args:
            host: 服务器地址
            port: 服务器端口
        """
        self._async_client = APIClient(host, port)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
    
    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        """确保事件循环存在"""
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
        return self._loop
    
    def _run_loop(self) -> None:
        """在后台线程运行事件循环"""
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()
    
    def _run_async(self, coro) -> Any:
        """
        在事件循环中运行协程
        
        Args:
            coro: 协程对象
            
        Returns:
            协程返回值
        """
        loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=15)
    
    @property
    def connection_state(self) -> ConnectionState:
        """获取连接状态"""
        return self._async_client.connection_state
    
    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._async_client.is_connected
    
    def set_server(self, host: str, port: int) -> None:
        """设置服务器地址"""
        self._async_client.set_server(host, port)
    
    def connect(self) -> bool:
        """连接到服务器"""
        return self._run_async(self._async_client.connect())
    
    def disconnect(self) -> None:
        """断开连接"""
        self._run_async(self._async_client.disconnect())
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
    
    def add_state_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """添加状态变化回调"""
        self._async_client.add_state_callback(callback)
    
    def add_connection_callback(self, callback: Callable[[ConnectionState], None]) -> None:
        """添加连接状态回调"""
        self._async_client.add_connection_callback(callback)
    
    # 播放控制
    def play(self) -> APIResponse:
        return self._run_async(self._async_client.play())
    
    def pause(self) -> APIResponse:
        return self._run_async(self._async_client.pause())
    
    def resume(self) -> APIResponse:
        return self._run_async(self._async_client.resume())
    
    def stop(self) -> APIResponse:
        return self._run_async(self._async_client.stop())
    
    def next_cue(self) -> APIResponse:
        return self._run_async(self._async_client.next_cue())
    
    def seek(self, position: float) -> APIResponse:
        return self._run_async(self._async_client.seek(position))
    
    def replay(self) -> APIResponse:
        return self._run_async(self._async_client.replay())
    
    # 音量控制
    def set_bgm_volume(self, volume: float) -> APIResponse:
        return self._run_async(self._async_client.set_bgm_volume(volume))
    
    def set_sfx_volume(self, volume: float) -> APIResponse:
        return self._run_async(self._async_client.set_sfx_volume(volume))
    
    def get_volume(self) -> APIResponse:
        return self._run_async(self._async_client.get_volume())
    
    # 状态查询
    def get_state(self) -> APIResponse:
        return self._run_async(self._async_client.get_state())
    
    # 模式切换
    def switch_mode(self, mode: str) -> APIResponse:
        return self._run_async(self._async_client.switch_mode(mode))
    
    def get_mode(self) -> APIResponse:
        return self._run_async(self._async_client.get_mode())
    
    # Cue 列表
    def get_cues(self) -> APIResponse:
        return self._run_async(self._async_client.get_cues())
    
    def update_cues(self, cues: List[Dict[str, Any]], config_name: str = "") -> APIResponse:
        return self._run_async(self._async_client.update_cues(cues, config_name))
    
    def add_cue(self, cue: Dict[str, Any]) -> APIResponse:
        return self._run_async(self._async_client.add_cue(cue))
    
    def delete_cue(self, cue_id: str) -> APIResponse:
        return self._run_async(self._async_client.delete_cue(cue_id))
    
    # 音频管理
    def get_audio_list(self) -> APIResponse:
        return self._run_async(self._async_client.get_audio_list())
    
    def upload_audio(
        self,
        file_path: str,
        title: Optional[str] = None,
        track_type: str = "bgm",
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> APIResponse:
        return self._run_async(
            self._async_client.upload_audio(file_path, title, track_type, progress_callback)
        )
    
    def delete_audio(self, audio_id: str) -> APIResponse:
        return self._run_async(self._async_client.delete_audio(audio_id))
    
    # 断点管理
    def get_breakpoints(self, audio_id: str) -> APIResponse:
        return self._run_async(self._async_client.get_breakpoints(audio_id))
    
    def save_breakpoint(self, audio_id: str, position: float, label: str = "") -> APIResponse:
        return self._run_async(self._async_client.save_breakpoint(audio_id, position, label))
    
    def delete_breakpoint(self, audio_id: str, bp_id: str) -> APIResponse:
        return self._run_async(self._async_client.delete_breakpoint(audio_id, bp_id))
    
    def clear_breakpoints(self, audio_id: str) -> APIResponse:
        return self._run_async(self._async_client.clear_breakpoints(audio_id))
    
    # 音效控制
    def play_sfx(self, sfx_id: str) -> APIResponse:
        return self._run_async(self._async_client.play_sfx(sfx_id))
    
    def stop_sfx(self, sfx_id: str) -> APIResponse:
        return self._run_async(self._async_client.stop_sfx(sfx_id))
    
    def toggle_sfx(self, sfx_id: str) -> APIResponse:
        return self._run_async(self._async_client.toggle_sfx(sfx_id))
