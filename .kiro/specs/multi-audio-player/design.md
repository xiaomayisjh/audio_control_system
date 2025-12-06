# 设计文档

## 概述

本系统是一个舞台剧音乐音效控制系统，采用 Python + Tkinter 构建本地控制台，同时提供 HTTP API 和 WebSocket 服务支持远程控制。系统分为三个主要组件：本地控制台（服务器）、Tkinter 远程客户端、Web UI 客户端。

### 核心设计原则

1. **异步非阻塞**: 所有 I/O 操作使用异步处理，音频播放在独立线程
2. **本地优先**: 本地 GUI 操作优先级高于远程 API 请求
3. **状态同步**: 所有客户端实时同步控制台状态
4. **演出安全**: 高危操作需长按确认，防止误操作

## 架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        本地控制台 (Server)                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  Tkinter    │  │   HTTP      │  │      WebSocket          │  │
│  │    GUI      │  │   API       │  │      Server             │  │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │
│         │                │                     │                │
│         └────────────────┼─────────────────────┘                │
│                          ▼                                      │
│              ┌───────────────────────┐                          │
│              │    Core Controller    │                          │
│              │   (状态管理 + 调度)    │                          │
│              └───────────┬───────────┘                          │
│                          │                                      │
│         ┌────────────────┼────────────────┐                     │
│         ▼                ▼                ▼                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ Audio Engine│  │ Cue Manager │  │  Breakpoint │              │
│  │ (pygame)    │  │             │  │   Manager   │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    Config & Storage                         ││
│  │              (JSON 配置文件 + 断点持久化)                     ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
   │  Tkinter    │     │   Web UI    │     │   Web UI    │
   │   Client    │     │  (Desktop)  │     │  (Mobile)   │
   └─────────────┘     └─────────────┘     └─────────────┘
```

## 组件和接口

### 1. Core Controller (核心控制器)

负责协调所有操作，管理播放状态，处理优先级调度。

```python
class CoreController:
    """核心控制器 - 单例模式"""
    
    def __init__(self):
        self.audio_engine: AudioEngine
        self.cue_manager: CueManager
        self.breakpoint_manager: BreakpointManager
        self.state: PlaybackState
        self.mode: PlayMode  # AUTO / MANUAL
        self.operation_lock: threading.Lock
        self.local_priority: bool = True
    
    # 播放控制
    async def play(self, source: str = "local") -> bool: ...
    async def pause(self, source: str = "local") -> bool: ...
    async def stop(self, source: str = "local") -> bool: ...
    async def next_cue(self, source: str = "local") -> bool: ...
    async def seek(self, position: float, source: str = "local") -> bool: ...
    
    # 音量控制
    def set_bgm_volume(self, volume: float) -> None: ...
    def set_sfx_volume(self, volume: float) -> None: ...
    
    # 模式切换
    async def switch_mode(self, mode: PlayMode) -> bool: ...
    
    # 状态查询
    def get_state(self) -> dict: ...
    
    # 事件通知
    def add_listener(self, callback: Callable) -> None: ...
    def notify_listeners(self, event: str, data: dict) -> None: ...
```

### 2. Audio Engine (音频引擎)

基于 pygame.mixer 实现，支持多通道播放。

```python
class AudioEngine:
    """音频引擎 - 多通道播放"""
    
    def __init__(self):
        self.bgm_channel: pygame.mixer.Channel  # BGM 专用通道
        self.sfx_channels: List[pygame.mixer.Channel]  # 音效通道池
        self.current_bgm: Optional[AudioTrack]
        self.playing_sfx: Dict[str, pygame.mixer.Channel]
    
    # BGM 控制
    def play_bgm(self, track: AudioTrack, start_pos: float = 0) -> None: ...
    def pause_bgm(self) -> None: ...
    def resume_bgm(self) -> None: ...
    def stop_bgm(self) -> float: ...  # 返回当前位置
    def get_bgm_position(self) -> float: ...
    
    # 音效控制
    def play_sfx(self, sfx_id: str, track: AudioTrack) -> None: ...
    def stop_sfx(self, sfx_id: str) -> None: ...
    def stop_all_sfx(self) -> None: ...
    
    # 音量控制
    def set_bgm_volume(self, volume: float) -> None: ...
    def set_sfx_volume(self, volume: float) -> None: ...
```

### 3. Cue Manager (Cue 列表管理器)

管理自动模式的播放序列。

```python
class CueManager:
    """Cue 列表管理器"""
    
    def __init__(self):
        self.cue_list: List[Cue]
        self.current_index: int
        self.is_playing: bool
    
    def load_config(self, config_path: str) -> None: ...
    def save_config(self, config_path: str) -> None: ...
    def get_current_cue(self) -> Optional[Cue]: ...
    def get_next_cue(self) -> Optional[Cue]: ...
    def advance(self) -> Optional[Cue]: ...
    def reset(self) -> None: ...
    def set_index(self, index: int) -> None: ...
```

### 4. Breakpoint Manager (断点管理器)

管理各音频的独立断点。

```python
class BreakpointManager:
    """断点管理器 - 各音频独立存储"""
    
    def __init__(self):
        self.breakpoints: Dict[str, List[Breakpoint]]  # audio_id -> breakpoints
    
    def save_breakpoint(self, audio_id: str, position: float, label: str = "") -> str: ...
    def get_breakpoints(self, audio_id: str) -> List[Breakpoint]: ...
    def delete_breakpoint(self, audio_id: str, bp_id: str) -> bool: ...
    def clear_audio_breakpoints(self, audio_id: str) -> None: ...
    def clear_selected(self, bp_ids: List[str]) -> None: ...
    def load_from_file(self, path: str) -> None: ...
    def save_to_file(self, path: str) -> None: ...
```

### 5. API Server (API 服务器)

基于 aiohttp 实现 HTTP API 和 WebSocket。

```python
class APIServer:
    """HTTP API + WebSocket 服务器"""
    
    def __init__(self, controller: CoreController, host: str, port: int):
        self.controller = controller
        self.app: aiohttp.web.Application
        self.websockets: Set[aiohttp.web.WebSocketResponse]
    
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    
    # HTTP API 路由
    # POST /api/play
    # POST /api/pause
    # POST /api/stop
    # POST /api/next
    # POST /api/seek
    # POST /api/volume
    # GET  /api/state
    # GET  /api/cues
    # POST /api/cues
    # GET  /api/audio
    # POST /api/audio/upload
    # GET  /api/breakpoints/{audio_id}
    # POST /api/breakpoints/{audio_id}
    # DELETE /api/breakpoints/{audio_id}/{bp_id}
    
    # WebSocket
    # /ws - 实时状态推送
    
    async def broadcast_state(self, event: str, data: dict) -> None: ...
```

### 6. Long Press Handler (长按处理器)

处理高危操作的长按确认。

```python
class LongPressHandler:
    """长按确认处理器"""
    
    def __init__(self, widget, duration_ms: int = 500):
        self.widget = widget
        self.duration_ms = duration_ms
        self.press_start: Optional[float]
        self.callback: Optional[Callable]
        self.progress_callback: Optional[Callable]
    
    def bind(self, callback: Callable, progress_callback: Callable = None) -> None: ...
    def on_press(self, event) -> None: ...
    def on_release(self, event) -> None: ...
    def check_duration(self) -> bool: ...
```

## 数据模型

### AudioTrack (音频轨道)

```python
@dataclass
class AudioTrack:
    id: str
    file_path: str
    duration: float  # 总时长（秒）
    title: str
    track_type: str  # "bgm" | "sfx"
```

### Cue (播放提示)

```python
@dataclass
class Cue:
    id: str
    audio_id: str
    start_time: float  # 入点（秒）
    end_time: Optional[float]  # 出点（秒），None 表示播放到结束
    silence_before: float  # 前置静音（秒）
    silence_after: float  # 后置静音（秒）
    volume: float  # 0.0 - 1.0
    label: str  # 显示标签
```

### Breakpoint (断点)

```python
@dataclass
class Breakpoint:
    id: str
    audio_id: str
    position: float  # 位置（秒）
    label: str
    created_at: datetime
    auto_saved: bool  # 是否为自动保存（被打断时）
```

### PlaybackState (播放状态)

```python
@dataclass
class PlaybackState:
    mode: str  # "auto" | "manual"
    is_playing: bool
    is_paused: bool
    current_audio_id: Optional[str]
    current_position: float
    current_cue_index: int
    bgm_volume: float
    sfx_volume: float
    in_silence: bool  # 是否在静音间隔中
    silence_remaining: float
```

### CueListConfig (Cue 列表配置)

```python
@dataclass
class CueListConfig:
    version: str
    name: str
    created_at: datetime
    cues: List[Cue]
    audio_files: List[AudioTrack]
```

## 配置文件格式

### cue_config.json

```json
{
  "version": "1.0",
  "name": "舞台剧第一幕",
  "created_at": "2025-12-06T10:00:00",
  "audio_files": [
    {
      "id": "bgm_01",
      "file_path": "0-上课铃-纯音乐.mp3",
      "title": "上课铃",
      "track_type": "bgm"
    }
  ],
  "cues": [
    {
      "id": "cue_001",
      "audio_id": "bgm_01",
      "start_time": 0,
      "end_time": 30,
      "silence_before": 0,
      "silence_after": 2,
      "volume": 0.8,
      "label": "开场铃声"
    }
  ]
}
```

### breakpoints.json

```json
{
  "bgm_01": [
    {
      "id": "bp_001",
      "position": 15.5,
      "label": "第一段结束",
      "created_at": "2025-12-06T10:30:00",
      "auto_saved": false
    }
  ]
}
```


## 正确性属性

*属性是系统在所有有效执行中应保持为真的特征或行为——本质上是关于系统应该做什么的形式化陈述。属性是人类可读规范与机器可验证正确性保证之间的桥梁。*

### Property 1: Cue 播放顺序一致性
*对于任意* Cue 列表配置，自动模式播放时，Cue 的播放顺序应与配置中定义的顺序完全一致
**Validates: Requirements 1.1**

### Property 2: 播放范围约束
*对于任意* 带有入点和出点的 Cue，播放位置应始终在 [start_time, end_time] 范围内
**Validates: Requirements 1.2**

### Property 3: 暂停/继续位置保持
*对于任意* 播放状态，暂停后继续播放，播放位置应与暂停时的位置一致（允许 ±0.1 秒误差）
**Validates: Requirements 2.2**

### Property 4: 跳转后索引递增
*对于任意* 自动模式播放状态，执行跳至下一段操作后，当前 Cue 索引应递增 1（除非已是最后一个）
**Validates: Requirements 2.3**

### Property 5: 断点保存完整性
*对于任意* 音频和播放位置，保存断点后，该音频的断点列表应包含该位置的断点记录
**Validates: Requirements 2.4, 5.1**

### Property 6: 断点删除完整性
*对于任意* 选中的断点集合，执行批量删除后，断点列表不应包含任何已删除的断点
**Validates: Requirements 2.5, 5.4**

### Property 7: 音效切换状态
*对于任意* 正在播放的音效，再次触发该音效按钮后，该音效应停止播放
**Validates: Requirements 3.2**

### Property 8: BGM/音效独立播放
*对于任意* BGM 播放状态，播放或停止音效不应改变 BGM 的播放状态和位置
**Validates: Requirements 3.3, 3.4, 10.1, 10.5**

### Property 9: 手动模式入点播放
*对于任意* 指定的入点位置，手动模式播放后，初始播放位置应等于指定的入点
**Validates: Requirements 4.2**

### Property 10: 静音跳过状态转换
*对于任意* 处于静音等待状态的播放，执行跳过操作后，应立即进入播放状态
**Validates: Requirements 4.4**

### Property 11: 断点恢复位置
*对于任意* 已保存的断点，选择该断点恢复播放后，播放位置应等于断点记录的位置
**Validates: Requirements 5.2, 10.4**

### Property 12: 单音频断点清除
*对于任意* 音频，执行一键清除断点后，该音频的断点列表应为空，其他音频断点不受影响
**Validates: Requirements 5.3**

### Property 13: 重播位置归零
*对于任意* 音频，执行重播操作后，播放位置应为 0
**Validates: Requirements 5.5**

### Property 14: 断点存储独立性
*对于任意* 两个不同的音频，修改一个音频的断点不应影响另一个音频的断点列表
**Validates: Requirements 5.6**

### Property 15: 音量调节不中断播放
*对于任意* 播放状态，调节音量后，播放状态（is_playing）应保持不变
**Validates: Requirements 6.2**

### Property 16: 音量设置一致性
*对于任意* 音量值 v（0.0-1.0），设置音量后立即获取，返回值应等于 v
**Validates: Requirements 6.3**

### Property 17: BGM/音效音量独立
*对于任意* BGM 音量调节操作，音效音量应保持不变；反之亦然
**Validates: Requirements 6.4**

### Property 18: 模式切换位置保持
*对于任意* 播放状态和当前位置，在自动/手动模式之间切换后，播放位置应保持不变
**Validates: Requirements 7.1, 7.2**

### Property 19: 模式切换状态同步
*对于任意* 模式切换操作，切换完成后两种模式的播放状态应一致
**Validates: Requirements 7.4**

### Property 20: 播放状态序列化往返
*对于任意* 有效的 PlaybackState 对象，序列化后反序列化应得到等价的对象
**Validates: Requirements 8.2**

### Property 21: 断点数据序列化往返
*对于任意* 有效的断点数据集合，保存到文件后加载应得到等价的数据
**Validates: Requirements 8.3**

### Property 22: Cue 添加完整性
*对于任意* 新 Cue 配置，添加到 Cue 列表后，列表应包含该 Cue 且属性完整
**Validates: Requirements 9.2**

### Property 23: 配置序列化往返
*对于任意* 有效的 CueListConfig 对象，保存为 JSON 后加载应得到等价的配置
**Validates: Requirements 9.4, 9.5**

### Property 24: BGM 互斥与自动断点
*对于任意* 正在播放的 BGM，播放新 BGM 后，旧 BGM 应停止且其播放位置应被保存为断点
**Validates: Requirements 10.2, 10.3**

### Property 25: 长按时间不足取消
*对于任意* 长按操作，如果按压时间小于阈值（500ms），操作应被取消不执行
**Validates: Requirements 12.5**

### Property 26: API 状态查询一致性
*对于任意* 控制台状态，API 状态查询返回的数据应与实际状态一致
**Validates: Requirements 14.5**

### Property 27: 音频列表一致性
*对于任意* 已上传的音频文件集合，API 获取音频列表应返回所有已上传的文件
**Validates: Requirements 15.2**

## 错误处理

### 音频加载错误
- 文件不存在：显示错误提示，跳过该音频
- 格式不支持：显示错误提示，建议转换格式
- 文件损坏：显示错误提示，标记为不可用

### 网络错误
- API 请求超时：重试 3 次后显示错误
- WebSocket 断开：自动重连，最多 5 次
- 文件上传失败：显示进度和错误信息

### 播放错误
- 音频设备不可用：显示错误，尝试重新初始化
- 内存不足：释放未使用资源，显示警告

### 配置错误
- JSON 解析失败：显示错误，使用默认配置
- 配置版本不兼容：尝试迁移，失败则提示

## 测试策略

### 单元测试
使用 pytest 进行单元测试：
- 数据模型的创建和验证
- 断点管理器的 CRUD 操作
- Cue 管理器的列表操作
- 配置文件的解析和生成
- 长按处理器的时间判断

### 属性测试
使用 hypothesis 进行属性测试：
- 每个属性测试运行至少 100 次迭代
- 使用智能生成器约束输入空间
- 测试标注格式：`**Feature: multi-audio-player, Property {number}: {property_text}**`

属性测试重点：
1. 序列化/反序列化往返（Property 20, 21, 23）
2. 状态一致性（Property 18, 19, 26）
3. 数据完整性（Property 5, 6, 12, 14）
4. 播放控制（Property 3, 4, 7, 8）

### 集成测试
- API 端点测试
- WebSocket 通信测试
- 多客户端同步测试

### 测试工具
- pytest: 单元测试框架
- hypothesis: 属性测试库
- pytest-asyncio: 异步测试支持
- aiohttp.test_utils: API 测试工具
