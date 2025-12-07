"""WebSocket 服务模块

提供实时状态推送和双向通信功能。

功能：
- 客户端连接管理
- 状态变化广播
- 心跳检测
- 断线重连支持
"""
import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Dict, Set, Optional, Callable, Any
from weakref import WeakSet

from aiohttp import web, WSMsgType

from src.core.controller import CoreController, EventType


@dataclass
class WebSocketClient:
    """WebSocket 客户端信息"""
    ws: web.WebSocketResponse
    client_id: str
    connected_at: float = field(default_factory=time.time)
    last_ping: float = field(default_factory=time.time)
    subscriptions: Set[str] = field(default_factory=set)
    
    @property
    def is_alive(self) -> bool:
        """检查连接是否存活"""
        return not self.ws.closed
    
    def update_ping(self) -> None:
        """更新最后心跳时间"""
        self.last_ping = time.time()


class WebSocketManager:
    """WebSocket 连接管理器
    
    负责管理所有 WebSocket 客户端连接，提供：
    - 客户端连接/断开管理
    - 状态变化广播
    - 心跳检测
    - 订阅机制
    """
    
    def __init__(
        self,
        controller: CoreController,
        heartbeat_interval: float = 30.0,
        heartbeat_timeout: float = 60.0
    ):
        """初始化 WebSocket 管理器
        
        Args:
            controller: 核心控制器实例
            heartbeat_interval: 心跳间隔（秒）
            heartbeat_timeout: 心跳超时时间（秒）
        """
        self._controller = controller
        self._heartbeat_interval = heartbeat_interval
        self._heartbeat_timeout = heartbeat_timeout
        
        # 客户端连接映射
        self._clients: Dict[str, WebSocketClient] = {}
        
        # 事件订阅者
        self._event_subscribers: Dict[str, Set[str]] = {}
        
        # 心跳任务
        self._heartbeat_task: Optional[asyncio.Task] = None
        
        # 消息处理器
        self._message_handlers: Dict[str, Callable] = {
            "ping": self._handle_ping,
            "pong": self._handle_pong,
            "subscribe": self._handle_subscribe,
            "unsubscribe": self._handle_unsubscribe,
            "get_state": self._handle_get_state,
            "command": self._handle_command,
        }
        
        # 设置控制器事件监听
        self._setup_controller_listeners()
    
    def _setup_controller_listeners(self) -> None:
        """设置控制器事件监听器"""
        for event_type in EventType:
            self._controller.add_listener(event_type, self._on_controller_event)
    
    def _on_controller_event(self, event_type: EventType, data: dict) -> None:
        """控制器事件回调"""
        asyncio.create_task(self.broadcast_event(event_type.value, data))
    
    async def start(self) -> None:
        """启动 WebSocket 管理器"""
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
    
    async def stop(self) -> None:
        """停止 WebSocket 管理器"""
        # 取消心跳任务
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # 关闭所有连接
        for client in list(self._clients.values()):
            await self._close_client(client, "Server shutting down")
        
        self._clients.clear()
    
    async def handle_connection(
        self,
        request: web.Request
    ) -> web.WebSocketResponse:
        """处理新的 WebSocket 连接
        
        Args:
            request: HTTP 请求对象
            
        Returns:
            WebSocket 响应对象
        """
        ws = web.WebSocketResponse(heartbeat=self._heartbeat_interval)
        await ws.prepare(request)
        
        # 生成客户端 ID
        client_id = f"client_{int(time.time() * 1000)}_{len(self._clients)}"
        
        # 创建客户端对象
        client = WebSocketClient(ws=ws, client_id=client_id)
        self._clients[client_id] = client
        
        try:
            # 发送欢迎消息和当前状态
            await self._send_welcome(client)
            
            # 处理消息循环
            await self._message_loop(client)
            
        finally:
            # 清理客户端
            await self._cleanup_client(client)
        
        return ws
    
    async def _send_welcome(self, client: WebSocketClient) -> None:
        """发送欢迎消息"""
        state = self._controller.get_state_dict()
        await self._send_to_client(client, {
            "type": "welcome",
            "client_id": client.client_id,
            "state": state,
            "server_time": time.time()
        })
    
    async def _message_loop(self, client: WebSocketClient) -> None:
        """消息处理循环"""
        async for msg in client.ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    await self._handle_message(client, data)
                except json.JSONDecodeError:
                    await self._send_error(client, "Invalid JSON format")
            elif msg.type == WSMsgType.BINARY:
                # 暂不处理二进制消息
                pass
            elif msg.type == WSMsgType.ERROR:
                break
    
    async def _handle_message(
        self,
        client: WebSocketClient,
        data: dict
    ) -> None:
        """处理客户端消息
        
        Args:
            client: 客户端对象
            data: 消息数据
        """
        msg_type = data.get("type", "")
        handler = self._message_handlers.get(msg_type)
        
        if handler:
            await handler(client, data)
        else:
            await self._send_error(client, f"Unknown message type: {msg_type}")
    
    async def _handle_ping(self, client: WebSocketClient, data: dict) -> None:
        """处理 ping 消息"""
        client.update_ping()
        await self._send_to_client(client, {
            "type": "pong",
            "timestamp": time.time()
        })
    
    async def _handle_pong(self, client: WebSocketClient, data: dict) -> None:
        """处理 pong 消息"""
        client.update_ping()
    
    async def _handle_subscribe(
        self,
        client: WebSocketClient,
        data: dict
    ) -> None:
        """处理订阅请求"""
        events = data.get("events", [])
        if isinstance(events, str):
            events = [events]
        
        for event in events:
            client.subscriptions.add(event)
            if event not in self._event_subscribers:
                self._event_subscribers[event] = set()
            self._event_subscribers[event].add(client.client_id)
        
        await self._send_to_client(client, {
            "type": "subscribed",
            "events": list(client.subscriptions)
        })
    
    async def _handle_unsubscribe(
        self,
        client: WebSocketClient,
        data: dict
    ) -> None:
        """处理取消订阅请求"""
        events = data.get("events", [])
        if isinstance(events, str):
            events = [events]
        
        for event in events:
            client.subscriptions.discard(event)
            if event in self._event_subscribers:
                self._event_subscribers[event].discard(client.client_id)
        
        await self._send_to_client(client, {
            "type": "unsubscribed",
            "events": events
        })
    
    async def _handle_get_state(
        self,
        client: WebSocketClient,
        data: dict
    ) -> None:
        """处理获取状态请求"""
        state = self._controller.get_state_dict()
        await self._send_to_client(client, {
            "type": "state",
            "data": state
        })
    
    async def _handle_command(
        self,
        client: WebSocketClient,
        data: dict
    ) -> None:
        """处理控制命令"""
        command = data.get("command", "")
        params = data.get("params", {})
        request_id = data.get("request_id")
        
        result = await self._execute_command(command, params)
        
        response = {
            "type": "command_result",
            "command": command,
            "success": result.get("success", False),
            "data": result
        }
        
        if request_id:
            response["request_id"] = request_id
        
        await self._send_to_client(client, response)
    
    async def _execute_command(
        self,
        command: str,
        params: dict
    ) -> dict:
        """执行控制命令
        
        Args:
            command: 命令名称
            params: 命令参数
            
        Returns:
            执行结果
        """
        try:
            if command == "play":
                result = await self._controller.play(source="remote")
                return {"success": result}
            
            elif command == "pause":
                result = await self._controller.pause(source="remote")
                return {"success": result}
            
            elif command == "resume":
                result = await self._controller.resume(source="remote")
                return {"success": result}
            
            elif command == "stop":
                result = await self._controller.stop(source="remote")
                return {"success": result}
            
            elif command == "next":
                result = await self._controller.next_cue(source="remote")
                return {"success": result}
            
            elif command == "seek":
                position = float(params.get("position", 0))
                result = await self._controller.seek(position, source="remote")
                return {"success": result}
            
            elif command == "replay":
                result = await self._controller.replay(source="remote")
                return {"success": result}
            
            elif command == "set_bgm_volume":
                volume = float(params.get("volume", 1.0))
                self._controller.set_bgm_volume(volume)
                return {"success": True, "volume": self._controller.get_bgm_volume()}
            
            elif command == "set_sfx_volume":
                volume = float(params.get("volume", 1.0))
                self._controller.set_sfx_volume(volume)
                return {"success": True, "volume": self._controller.get_sfx_volume()}
            
            else:
                return {"success": False, "error": f"Unknown command: {command}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def broadcast_event(self, event: str, data: dict) -> None:
        """广播事件到所有订阅的客户端
        
        Args:
            event: 事件名称
            data: 事件数据
        """
        message = {
            "type": "event",
            "event": event,
            "data": data,
            "timestamp": time.time()
        }
        
        # 获取订阅该事件的客户端
        subscriber_ids = self._event_subscribers.get(event, set())
        
        # 如果没有特定订阅者，广播给所有客户端
        if not subscriber_ids:
            await self.broadcast_all(message)
        else:
            tasks = []
            for client_id in subscriber_ids:
                client = self._clients.get(client_id)
                if client and client.is_alive:
                    tasks.append(self._send_to_client(client, message))
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
    
    async def broadcast_all(self, message: dict) -> None:
        """广播消息到所有客户端
        
        Args:
            message: 消息内容
        """
        tasks = []
        for client in list(self._clients.values()):
            if client.is_alive:
                tasks.append(self._send_to_client(client, message))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def broadcast_state(self) -> None:
        """广播当前状态到所有客户端"""
        state = self._controller.get_state_dict()
        await self.broadcast_all({
            "type": "state",
            "data": state,
            "timestamp": time.time()
        })
    
    async def _send_to_client(
        self,
        client: WebSocketClient,
        message: dict
    ) -> bool:
        """发送消息到指定客户端
        
        Args:
            client: 客户端对象
            message: 消息内容
            
        Returns:
            是否发送成功
        """
        if not client.is_alive:
            return False
        
        try:
            await client.ws.send_json(message)
            return True
        except Exception:
            return False
    
    async def _send_error(
        self,
        client: WebSocketClient,
        error_message: str
    ) -> None:
        """发送错误消息"""
        await self._send_to_client(client, {
            "type": "error",
            "message": error_message
        })
    
    async def _heartbeat_loop(self) -> None:
        """心跳检测循环"""
        while True:
            try:
                await asyncio.sleep(self._heartbeat_interval)
                await self._check_heartbeats()
            except asyncio.CancelledError:
                break
            except Exception:
                pass
    
    async def _check_heartbeats(self) -> None:
        """检查所有客户端心跳"""
        current_time = time.time()
        dead_clients = []
        
        for client_id, client in list(self._clients.items()):
            if not client.is_alive:
                dead_clients.append(client)
            elif current_time - client.last_ping > self._heartbeat_timeout:
                dead_clients.append(client)
            else:
                # 发送 ping
                await self._send_to_client(client, {
                    "type": "ping",
                    "timestamp": current_time
                })
        
        # 清理死亡连接
        for client in dead_clients:
            await self._cleanup_client(client)
    
    async def _close_client(
        self,
        client: WebSocketClient,
        reason: str = ""
    ) -> None:
        """关闭客户端连接"""
        if client.is_alive:
            try:
                await client.ws.close(message=reason.encode() if reason else None)
            except Exception:
                pass
    
    async def _cleanup_client(self, client: WebSocketClient) -> None:
        """清理客户端资源"""
        # 从客户端列表移除
        self._clients.pop(client.client_id, None)
        
        # 从订阅列表移除
        for event in client.subscriptions:
            if event in self._event_subscribers:
                self._event_subscribers[event].discard(client.client_id)
        
        # 关闭连接
        await self._close_client(client)
    
    @property
    def client_count(self) -> int:
        """获取当前连接的客户端数量"""
        return len(self._clients)
    
    @property
    def clients(self) -> Dict[str, WebSocketClient]:
        """获取所有客户端（只读）"""
        return dict(self._clients)
    
    def get_client(self, client_id: str) -> Optional[WebSocketClient]:
        """获取指定客户端"""
        return self._clients.get(client_id)
    
    def is_client_connected(self, client_id: str) -> bool:
        """检查客户端是否已连接"""
        client = self._clients.get(client_id)
        return client is not None and client.is_alive
