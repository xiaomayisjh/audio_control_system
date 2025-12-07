"""HTTP API 服务器模块

提供 RESTful API 接口用于远程控制音效系统。

功能：
- 播放控制端点 (play, pause, stop, next, seek)
- 音量控制端点
- 状态查询端点
- Cue 列表管理端点
- 断点管理端点
- 音频上传端点
- 静态文件服务 (Web UI)
"""
import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Optional, Set, Callable, Any

from aiohttp import web

from src.core.controller import CoreController, PlayMode, EventType
from src.models.audio_track import AudioTrack
from src.models.cue import Cue


class APIServer:
    """HTTP API + WebSocket 服务器
    
    提供完整的 HTTP API 接口和 WebSocket 实时状态推送。
    """
    
    def __init__(
        self,
        controller: CoreController,
        host: str = "0.0.0.0",
        port: int = 8080,
        audio_dir: str = "audio_files"
    ):
        """初始化 API 服务器
        
        Args:
            controller: 核心控制器实例
            host: 监听地址
            port: 监听端口
            audio_dir: 音频文件存储目录
        """
        self._controller = controller
        self._host = host
        self._port = port
        self._audio_dir = Path(audio_dir)
        self._audio_dir.mkdir(parents=True, exist_ok=True)
        
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
        
        # WebSocket 连接集合
        self._websockets: Set[web.WebSocketResponse] = set()
        
        # 事件循环引用（用于跨线程调用）
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
        # 设置控制器事件监听
        self._setup_controller_listeners()
    
    def _setup_controller_listeners(self) -> None:
        """设置控制器事件监听器"""
        self._controller.add_listener(
            EventType.STATE_CHANGED,
            self._on_state_changed
        )
    
    def _on_state_changed(self, event_type: EventType, data: dict) -> None:
        """状态变化回调"""
        # 广播状态变化到所有 WebSocket 客户端
        # 使用线程安全的方式调用异步方法
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.broadcast_state(event_type.value, data),
                self._loop
            )
    
    async def start(self) -> None:
        """启动 API 服务器"""
        # 保存事件循环引用
        self._loop = asyncio.get_running_loop()
        
        self._app = web.Application(middlewares=[self._cors_middleware])
        self._setup_routes()
        
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        
        self._site = web.TCPSite(self._runner, self._host, self._port)
        await self._site.start()
    
    @web.middleware
    async def _cors_middleware(self, request: web.Request, handler):
        """CORS 中间件"""
        # 处理预检请求
        if request.method == "OPTIONS":
            response = web.Response()
        else:
            try:
                response = await handler(request)
            except web.HTTPException as ex:
                response = ex
        
        # 添加 CORS 头
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response
    
    async def stop(self) -> None:
        """停止 API 服务器"""
        # 关闭所有 WebSocket 连接
        for ws in list(self._websockets):
            try:
                await ws.close()
            except Exception:
                pass
        self._websockets.clear()
        
        # 先停止站点
        if self._site:
            try:
                await self._site.stop()
            except Exception:
                pass
        
        # 再清理 runner
        if self._runner:
            try:
                await self._runner.cleanup()
            except Exception:
                pass
    
    def _setup_routes(self) -> None:
        """设置 API 路由"""
        # 静态文件服务 - Web UI
        static_dir = Path(__file__).parent / "static"
        if static_dir.exists():
            # 添加静态文件路由
            self._app.router.add_static("/static/", static_dir, name="static")
            # 根路径返回 index.html
            self._app.router.add_get("/", self._handle_index)
        
        # API 路由
        self._app.router.add_post("/api/play", self._handle_play)
        self._app.router.add_post("/api/pause", self._handle_pause)
        self._app.router.add_post("/api/resume", self._handle_resume)
        self._app.router.add_post("/api/stop", self._handle_stop)
        self._app.router.add_post("/api/next", self._handle_next)
        self._app.router.add_post("/api/seek", self._handle_seek)
        self._app.router.add_post("/api/replay", self._handle_replay)
        
        # 音量控制
        self._app.router.add_post("/api/volume/bgm", self._handle_bgm_volume)
        self._app.router.add_post("/api/volume/sfx", self._handle_sfx_volume)
        self._app.router.add_get("/api/volume", self._handle_get_volume)
        
        # 状态查询
        self._app.router.add_get("/api/state", self._handle_get_state)
        
        # Cue 列表管理
        self._app.router.add_get("/api/cues", self._handle_get_cues)
        self._app.router.add_post("/api/cues", self._handle_update_cues)
        self._app.router.add_post("/api/cues/add", self._handle_add_cue)
        self._app.router.add_delete("/api/cues/{cue_id}", self._handle_delete_cue)
        
        # 音频管理
        self._app.router.add_get("/api/audio", self._handle_get_audio_list)
        self._app.router.add_post("/api/audio/upload", self._handle_upload_audio)
        self._app.router.add_delete("/api/audio/{audio_id}", self._handle_delete_audio)
        
        # 断点管理
        self._app.router.add_get(
            "/api/breakpoints/{audio_id}",
            self._handle_get_breakpoints
        )
        self._app.router.add_post(
            "/api/breakpoints/{audio_id}",
            self._handle_save_breakpoint
        )
        self._app.router.add_delete(
            "/api/breakpoints/{audio_id}/{bp_id}",
            self._handle_delete_breakpoint
        )
        self._app.router.add_delete(
            "/api/breakpoints/{audio_id}",
            self._handle_clear_breakpoints
        )
        
        # 模式切换
        self._app.router.add_post("/api/mode", self._handle_switch_mode)
        self._app.router.add_get("/api/mode", self._handle_get_mode)
        
        # 音效控制
        self._app.router.add_post("/api/sfx/play/{sfx_id}", self._handle_play_sfx)
        self._app.router.add_post("/api/sfx/stop/{sfx_id}", self._handle_stop_sfx)
        self._app.router.add_post("/api/sfx/toggle/{sfx_id}", self._handle_toggle_sfx)
        
        # WebSocket
        self._app.router.add_get("/ws", self._handle_websocket)
    
    # ==================== 静态文件端点 ====================
    
    async def _handle_index(self, request: web.Request) -> web.Response:
        """返回 Web UI 首页"""
        static_dir = Path(__file__).parent / "static"
        index_path = static_dir / "index.html"
        
        if index_path.exists():
            return web.FileResponse(index_path)
        else:
            return web.Response(
                text="Web UI not available. Static files not found.",
                status=404
            )
    
    # ==================== 播放控制端点 ====================
    
    async def _handle_play(self, request: web.Request) -> web.Response:
        """处理播放请求"""
        result = await self._controller.play(source="remote")
        return self._json_response({"success": result})
    
    async def _handle_pause(self, request: web.Request) -> web.Response:
        """处理暂停请求"""
        result = await self._controller.pause(source="remote")
        return self._json_response({"success": result})
    
    async def _handle_resume(self, request: web.Request) -> web.Response:
        """处理继续播放请求"""
        result = await self._controller.resume(source="remote")
        return self._json_response({"success": result})
    
    async def _handle_stop(self, request: web.Request) -> web.Response:
        """处理停止请求"""
        result = await self._controller.stop(source="remote")
        return self._json_response({"success": result})
    
    async def _handle_next(self, request: web.Request) -> web.Response:
        """处理跳至下一段请求"""
        result = await self._controller.next_cue(source="remote")
        return self._json_response({"success": result})
    
    async def _handle_seek(self, request: web.Request) -> web.Response:
        """处理跳转请求"""
        try:
            data = await request.json()
            position = float(data.get("position", 0))
            result = await self._controller.seek(position, source="remote")
            return self._json_response({"success": result})
        except (json.JSONDecodeError, ValueError) as e:
            return self._error_response(f"Invalid request: {e}", 400)
    
    async def _handle_replay(self, request: web.Request) -> web.Response:
        """处理重播请求"""
        result = await self._controller.replay(source="remote")
        return self._json_response({"success": result})
    
    # ==================== 音量控制端点 ====================
    
    async def _handle_bgm_volume(self, request: web.Request) -> web.Response:
        """处理 BGM 音量调节请求"""
        try:
            data = await request.json()
            volume = float(data.get("volume", 1.0))
            if not 0.0 <= volume <= 3.0:
                return self._error_response("Volume must be between 0.0 and 3.0 (0%-300%)", 400)
            
            self._controller.set_bgm_volume(volume)
            return self._json_response({
                "success": True,
                "volume": self._controller.get_bgm_volume()
            })
        except (json.JSONDecodeError, ValueError) as e:
            return self._error_response(f"Invalid request: {e}", 400)
    
    async def _handle_sfx_volume(self, request: web.Request) -> web.Response:
        """处理音效音量调节请求"""
        try:
            data = await request.json()
            volume = float(data.get("volume", 1.0))
            if not 0.0 <= volume <= 3.0:
                return self._error_response("Volume must be between 0.0 and 3.0 (0%-300%)", 400)
            
            self._controller.set_sfx_volume(volume)
            return self._json_response({
                "success": True,
                "volume": self._controller.get_sfx_volume()
            })
        except (json.JSONDecodeError, ValueError) as e:
            return self._error_response(f"Invalid request: {e}", 400)
    
    async def _handle_get_volume(self, request: web.Request) -> web.Response:
        """获取当前音量"""
        return self._json_response({
            "bgm_volume": self._controller.get_bgm_volume(),
            "sfx_volume": self._controller.get_sfx_volume()
        })
    
    # ==================== 状态查询端点 ====================
    
    async def _handle_get_state(self, request: web.Request) -> web.Response:
        """获取当前播放状态"""
        state = self._controller.get_state_dict()
        return self._json_response(state)
    
    # ==================== Cue 列表管理端点 ====================
    
    async def _handle_get_cues(self, request: web.Request) -> web.Response:
        """获取 Cue 列表"""
        cue_manager = self._controller.cue_manager
        cues = [cue.to_dict() for cue in cue_manager.cue_list]
        return self._json_response({
            "cues": cues,
            "current_index": cue_manager.current_index,
            "config_name": cue_manager.get_config_name()
        })
    
    async def _handle_update_cues(self, request: web.Request) -> web.Response:
        """更新 Cue 列表"""
        try:
            data = await request.json()
            cues_data = data.get("cues", [])
            
            cue_manager = self._controller.cue_manager
            cue_manager.clear_cues()
            
            for cue_data in cues_data:
                cue = Cue.from_dict(cue_data)
                cue_manager.add_cue(cue)
            
            if "config_name" in data:
                cue_manager.set_config_name(data["config_name"])
            
            return self._json_response({"success": True})
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            return self._error_response(f"Invalid request: {e}", 400)
    
    async def _handle_add_cue(self, request: web.Request) -> web.Response:
        """添加单个 Cue"""
        try:
            data = await request.json()
            cue = Cue.from_dict(data)
            self._controller.cue_manager.add_cue(cue)
            return self._json_response({"success": True, "cue_id": cue.id})
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            return self._error_response(f"Invalid request: {e}", 400)
    
    async def _handle_delete_cue(self, request: web.Request) -> web.Response:
        """删除 Cue"""
        cue_id = request.match_info["cue_id"]
        result = self._controller.cue_manager.remove_cue(cue_id)
        return self._json_response({"success": result})
    
    # ==================== 音频管理端点 ====================
    
    async def _handle_get_audio_list(self, request: web.Request) -> web.Response:
        """获取音频文件列表"""
        audio_files = self._controller.cue_manager.audio_files
        return self._json_response({
            "audio_files": [audio.to_dict() for audio in audio_files]
        })
    
    async def _handle_upload_audio(self, request: web.Request) -> web.Response:
        """处理音频文件上传"""
        try:
            reader = await request.multipart()
            
            audio_id = None
            title = None
            track_type = "bgm"
            file_path = None
            duration = 0.0
            
            async for field in reader:
                if field.name == "file":
                    # 保存文件
                    filename = field.filename
                    if not filename:
                        return self._error_response("No filename provided", 400)
                    
                    # 生成唯一文件名
                    ext = Path(filename).suffix
                    audio_id = str(uuid.uuid4())
                    safe_filename = f"{audio_id}{ext}"
                    file_path = self._audio_dir / safe_filename
                    
                    # 写入文件
                    with open(file_path, "wb") as f:
                        while True:
                            chunk = await field.read_chunk()
                            if not chunk:
                                break
                            f.write(chunk)
                    
                    title = filename
                    
                elif field.name == "title":
                    title = (await field.read()).decode("utf-8")
                elif field.name == "track_type":
                    track_type = (await field.read()).decode("utf-8")
                elif field.name == "duration":
                    duration = float((await field.read()).decode("utf-8"))
            
            if not file_path or not audio_id:
                return self._error_response("No file uploaded", 400)
            
            # 创建音频轨道对象
            audio = AudioTrack(
                id=audio_id,
                file_path=str(file_path),
                duration=duration,
                title=title or "Unknown",
                track_type=track_type
            )
            
            # 添加到 Cue 管理器
            self._controller.cue_manager.add_audio_file(audio)
            
            return self._json_response({
                "success": True,
                "audio": audio.to_dict()
            })
            
        except Exception as e:
            return self._error_response(f"Upload failed: {e}", 500)
    
    async def _handle_delete_audio(self, request: web.Request) -> web.Response:
        """删除音频文件"""
        audio_id = request.match_info["audio_id"]
        
        # 获取音频信息
        audio = self._controller.cue_manager.get_audio_file(audio_id)
        if audio:
            # 删除文件
            try:
                file_path = Path(audio.file_path)
                if file_path.exists():
                    file_path.unlink()
            except Exception:
                pass
        
        # 从管理器中移除
        result = self._controller.cue_manager.remove_audio_file(audio_id)
        return self._json_response({"success": result})
    
    # ==================== 断点管理端点 ====================
    
    async def _handle_get_breakpoints(self, request: web.Request) -> web.Response:
        """获取指定音频的断点列表"""
        audio_id = request.match_info["audio_id"]
        breakpoints = self._controller.breakpoint_manager.get_breakpoints(audio_id)
        return self._json_response({
            "breakpoints": [bp.to_dict() for bp in breakpoints]
        })
    
    async def _handle_save_breakpoint(self, request: web.Request) -> web.Response:
        """保存断点"""
        audio_id = request.match_info["audio_id"]
        try:
            data = await request.json()
            position = float(data.get("position", 0))
            label = data.get("label", "")
            
            bp_id = self._controller.breakpoint_manager.save_breakpoint(
                audio_id, position, label
            )
            return self._json_response({"success": True, "bp_id": bp_id})
        except (json.JSONDecodeError, ValueError) as e:
            return self._error_response(f"Invalid request: {e}", 400)
    
    async def _handle_delete_breakpoint(self, request: web.Request) -> web.Response:
        """删除断点"""
        audio_id = request.match_info["audio_id"]
        bp_id = request.match_info["bp_id"]
        result = self._controller.breakpoint_manager.delete_breakpoint(audio_id, bp_id)
        return self._json_response({"success": result})
    
    async def _handle_clear_breakpoints(self, request: web.Request) -> web.Response:
        """清除指定音频的所有断点"""
        audio_id = request.match_info["audio_id"]
        self._controller.breakpoint_manager.clear_audio_breakpoints(audio_id)
        return self._json_response({"success": True})
    
    # ==================== 模式切换端点 ====================
    
    async def _handle_switch_mode(self, request: web.Request) -> web.Response:
        """切换播放模式"""
        try:
            data = await request.json()
            mode_str = data.get("mode", "auto")
            mode = PlayMode.AUTO if mode_str == "auto" else PlayMode.MANUAL
            result = await self._controller.switch_mode(mode)
            return self._json_response({
                "success": result,
                "mode": self._controller.mode.value
            })
        except (json.JSONDecodeError, ValueError) as e:
            return self._error_response(f"Invalid request: {e}", 400)
    
    async def _handle_get_mode(self, request: web.Request) -> web.Response:
        """获取当前播放模式"""
        return self._json_response({"mode": self._controller.mode.value})
    
    # ==================== 音效控制端点 ====================
    
    async def _handle_play_sfx(self, request: web.Request) -> web.Response:
        """播放音效"""
        sfx_id = request.match_info["sfx_id"]
        
        # 获取音效轨道
        audio = self._controller.cue_manager.get_audio_file(sfx_id)
        if not audio:
            return self._error_response(f"Audio not found: {sfx_id}", 404)
        
        result = self._controller.play_sfx(sfx_id, audio)
        return self._json_response({"success": result})
    
    async def _handle_stop_sfx(self, request: web.Request) -> web.Response:
        """停止音效"""
        sfx_id = request.match_info["sfx_id"]
        result = self._controller.stop_sfx(sfx_id)
        return self._json_response({"success": result})
    
    async def _handle_toggle_sfx(self, request: web.Request) -> web.Response:
        """切换音效状态"""
        sfx_id = request.match_info["sfx_id"]
        
        # 获取音效轨道
        audio = self._controller.cue_manager.get_audio_file(sfx_id)
        if not audio:
            return self._error_response(f"Audio not found: {sfx_id}", 404)
        
        is_playing = self._controller.toggle_sfx(sfx_id, audio)
        return self._json_response({"success": True, "is_playing": is_playing})
    
    # ==================== WebSocket 端点 ====================
    
    async def _handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """处理 WebSocket 连接"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        self._websockets.add(ws)
        
        try:
            # 发送当前状态
            state = self._controller.get_state_dict()
            await ws.send_json({"type": "state", "data": state})
            
            # 处理消息
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self._handle_ws_message(ws, data)
                    except json.JSONDecodeError:
                        await ws.send_json({"type": "error", "message": "Invalid JSON"})
                elif msg.type == web.WSMsgType.ERROR:
                    break
        finally:
            self._websockets.discard(ws)
        
        return ws
    
    async def _handle_ws_message(
        self,
        ws: web.WebSocketResponse,
        data: dict
    ) -> None:
        """处理 WebSocket 消息"""
        msg_type = data.get("type")
        
        if msg_type == "ping":
            await ws.send_json({"type": "pong"})
        elif msg_type == "get_state":
            state = self._controller.get_state_dict()
            await ws.send_json({"type": "state", "data": state})
    
    async def broadcast_state(self, event: str, data: dict) -> None:
        """广播状态变化到所有 WebSocket 客户端
        
        Args:
            event: 事件类型
            data: 事件数据
        """
        if not self._websockets:
            return
        
        message = {
            "type": "event",
            "event": event,
            "data": data,
            "state": self._controller.get_state_dict()
        }
        
        # 并发发送到所有客户端
        tasks = []
        for ws in list(self._websockets):
            if not ws.closed:
                tasks.append(ws.send_json(message))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    # ==================== 工具方法 ====================
    
    def _json_response(self, data: dict, status: int = 200) -> web.Response:
        """创建 JSON 响应"""
        return web.json_response(data, status=status)
    
    def _error_response(self, message: str, status: int = 400) -> web.Response:
        """创建错误响应"""
        return web.json_response({"error": message}, status=status)
    
    @property
    def host(self) -> str:
        """获取监听地址"""
        return self._host
    
    @property
    def port(self) -> int:
        """获取监听端口"""
        return self._port
    
    @property
    def url(self) -> str:
        """获取服务器 URL"""
        return f"http://{self._host}:{self._port}"
    
    @property
    def websocket_count(self) -> int:
        """获取当前 WebSocket 连接数"""
        return len(self._websockets)
