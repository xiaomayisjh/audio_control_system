# 实现计划

- [x] 1. 项目初始化和核心数据模型
  - [x] 1.1 创建项目结构和依赖配置
    - 创建 `requirements.txt` 包含 pygame, aiohttp, hypothesis, pytest, qrcode, pillow
    - 创建项目目录结构: `src/`, `src/models/`, `src/core/`, `src/gui/`, `src/api/`, `src/client/`, `tests/`
    - _Requirements: 8.1_
  - [x] 1.2 实现数据模型类
    - 创建 `src/models/audio_track.py` - AudioTrack 数据类
    - 创建 `src/models/cue.py` - Cue 数据类
    - 创建 `src/models/breakpoint.py` - Breakpoint 数据类
    - 创建 `src/models/playback_state.py` - PlaybackState 数据类
    - 创建 `src/models/cue_config.py` - CueListConfig 数据类
    - _Requirements: 8.2, 8.3_
  - [x] 1.3 编写属性测试：播放状态序列化往返







    - **Property 20: 播放状态序列化往返**
    - **Validates: Requirements 8.2**

  - [x] 1.4 编写属性测试：断点数据序列化往返












    - **Property 21: 断点数据序列化往返**
    - **Validates: Requirements 8.3**
  - [x] 1.5 编写属性测试：配置序列化往返









    - **Property 23: 配置序列化往返**
    - **Validates: Requirements 9.4, 9.5**

- [x] 2. 断点管理器实现






  - [x] 2.1 实现 BreakpointManager 类

    - 创建 `src/core/breakpoint_manager.py`
    - 实现断点的增删改查操作
    - 实现各音频独立存储逻辑
    - 实现持久化到 JSON 文件
    - _Requirements: 2.4, 2.5, 5.1-5.6_
  - [x] 2.2 编写属性测试：断点保存完整性



    - **Property 5: 断点保存完整性**
    - **Validates: Requirements 2.4, 5.1**

  - [x] 2.3 编写属性测试：断点删除完整性


    - **Property 6: 断点删除完整性**
    - **Validates: Requirements 2.5, 5.4**
  - [x] 2.4 编写属性测试：单音频断点清除



    - **Property 12: 单音频断点清除**
    - **Validates: Requirements 5.3**


  - [x] 2.5 编写属性测试：断点存储独立性



    - **Property 14: 断点存储独立性**
    - **Validates: Requirements 5.6**

- [x] 3. Checkpoint - 确保所有测试通过










  - 确保所有测试通过，如有问题请询问用户


- [x] 4. Cue 管理器实现






  - [x] 4.1 实现 CueManager 类
    - 创建 `src/core/cue_manager.py`

    - 实现 Cue 列表的加载和保存
    - 实现当前/下一个 Cue 的获取
    - 实现索引管理和重置
    - _Requirements: 1.1, 9.2, 9.4, 9.5_
  - [x] 4.2 编写属性测试：Cue 添加完整性




    - **Property 22: Cue 添加完整性**
    - **Validates: Requirements 9.2**

- [x] 5. 音频引擎实现





  - [x] 5.1 实现 AudioEngine 类


    - 创建 `src/core/audio_engine.py`
    - 初始化 pygame.mixer 多通道
    - 实现 BGM 播放/暂停/停止/定位
    - 实现音效播放/停止（多通道并行）
    - 实现 BGM 和音效独立音量控制
    - _Requirements: 1.2, 1.4, 3.1-3.4, 4.2, 6.1-6.4_
  - [x] 5.2 编写属性测试：音量设置一致性



    - **Property 16: 音量设置一致性**
    - **Validates: Requirements 6.3**

  - [x] 5.3 编写属性测试：BGM/音效音量独立






    - **Property 17: BGM/音效音量独立**
    - **Validates: Requirements 6.4**

- [x] 6. 核心控制器实现






  - [x] 6.1 实现 CoreController 类

    - 创建 `src/core/controller.py`
    - 整合 AudioEngine, CueManager, BreakpointManager
    - 实现播放/暂停/停止/跳转控制
    - 实现自动模式播放逻辑（静音间隔处理）
    - 实现手动模式播放逻辑
    - 实现模式切换（位置保持）
    - 实现本地优先级调度
    - 实现事件监听器机制
    - _Requirements: 1.1-1.4, 2.1-2.5, 4.1-4.6, 7.1-7.4, 10.2-10.3_

  - [x] 6.2 编写属性测试：暂停/继续位置保持


    - **Property 3: 暂停/继续位置保持**
    - **Validates: Requirements 2.2**
  - [x] 6.3 编写属性测试：跳转后索引递增


    - **Property 4: 跳转后索引递增**
    - **Validates: Requirements 2.3**

  - [x] 6.4 编写属性测试：音效切换状态


    - **Property 7: 音效切换状态**
    - **Validates: Requirements 3.2**

  - [x] 6.5 编写属性测试：BGM/音效独立播放

    - **Property 8: BGM/音效独立播放**
    - **Validates: Requirements 3.3, 3.4, 10.1, 10.5**


  - [x] 6.6 编写属性测试：断点恢复位置






    - **Property 11: 断点恢复位置**
    - **Validates: Requirements 5.2, 10.4**

  - [x] 6.7 编写属性测试：重播位置归零


    - **Property 13: 重播位置归零**
    - **Validates: Requirements 5.5**

  - [x] 6.8 编写属性测试：音量调节不中断播放

    - **Property 15: 音量调节不中断播放**
    - **Validates: Requirements 6.2**

  - [x] 6.9 编写属性测试：模式切换位置保持

    - **Property 18: 模式切换位置保持**
    - **Validates: Requirements 7.1, 7.2**
  - [x] 6.10 编写属性测试：模式切换状态同步


    - **Property 19: 模式切换状态同步**
    - **Validates: Requirements 7.4**

  - [x] 6.11 编写属性测试：BGM 互斥与自动断点


    - **Property 24: BGM 互斥与自动断点**
    - **Validates: Requirements 10.2, 10.3**

- [ ] 7. Checkpoint - 确保所有测试通过




  - 确保所有测试通过，如有问题请询问用户

- [x] 8. 长按处理器实现




  - [x] 8.1 实现 LongPressHandler 类

    - 创建 `src/gui/long_press.py`
    - 实现按压开始/释放事件处理
    - 实现时间阈值判断（500ms）
    - 实现进度回调支持
    - _Requirements: 12.1-12.5_

  - [x] 8.2 编写属性测试：长按时间不足取消



    - **Property 25: 长按时间不足取消**
    - **Validates: Requirements 12.5**

- [x] 9. 本地控制台 GUI 实现





  - [x] 9.1 实现主窗口框架
    - 创建 `src/gui/main_window.py`
    - 垂直布局，区分自动/手动模式区域
    - 实现模式切换 Tab
    - 实现关闭确认对话框

    - _Requirements: 11.1, 11.6_
  - [x] 9.2 实现自动模式面板

    - 创建 `src/gui/auto_mode_panel.py`
    - Cue 列表显示（当前高亮，下一个预览）
    - 播放控制按钮（长按确认）
    - 进度条和剩余时间显示
    - 断点管理界面
    - _Requirements: 1.1-1.4, 2.1-2.5, 11.2, 11.4, 12.1-12.3_

  - [x] 9.3 实现手动模式面板

    - 创建 `src/gui/manual_mode_panel.py`
    - 音频列表和选择
    - 入点设置和静音设置
    - 播放控制（长按确认）
    - 断点管理（独立存储）
    - 下一条提示按钮
    - _Requirements: 4.1-4.6, 5.1-5.6, 10.1-10.5, 12.1-12.3_
  - [x] 9.4 实现音效面板


    - 创建 `src/gui/sfx_panel.py`
    - 音效按钮网格
    - 点击播放/再点停止
    - _Requirements: 3.1-3.4_

  - [x] 9.5 实现音量控制面板


    - 创建 `src/gui/volume_panel.py`
    - BGM 音量滑块
    - 音效音量滑块
    - 实时无延迟调节
    - _Requirements: 6.1-6.4_

- [x] 10. API 服务器实现




  - [x] 10.1 实现 HTTP API 路由

    - 创建 `src/api/server.py`
    - 实现播放控制端点 (play, pause, stop, next, seek)
    - 实现音量控制端点
    - 实现状态查询端点
    - 实现 Cue 列表管理端点
    - 实现断点管理端点
    - 实现音频上传端点
    - _Requirements: 14.1-14.7, 15.1-15.5_


  - [x] 10.2 实现 WebSocket 服务
    - 创建 `src/api/websocket.py`
    - 实现客户端连接管理
    - 实现状态变化广播

    - _Requirements: 17.4_

  - [x] 10.3 编写属性测试：API 状态查询一致性

    - **Property 26: API 状态查询一致性**

    - **Validates: Requirements 14.5**
  - [x] 10.4 编写属性测试：音频列表一致性


    - **Property 27: 音频列表一致性**
    - **Validates: Requirements 15.2**

- [x] 11. Web UI 实现




  - [x] 11.1 实现静态文件服务

    - 创建 `src/api/static/` 目录
    - 配置 aiohttp 静态文件路由
    - _Requirements: 17.1_

  - [x] 11.2 实现响应式 Web UI
    - 创建 `src/api/static/index.html`
    - 创建 `src/api/static/style.css` - 移动端适配
    - 创建 `src/api/static/app.js` - WebSocket 通信和 UI 控制
    - 实现与桌面客户端相同的核心功能
    - _Requirements: 17.1-17.7_

  - [x] 11.3 实现二维码显示窗口


    - 创建 `src/gui/qrcode_window.py`
    - 生成 Web UI URL 二维码
    - 独立窗口显示，不干扰主界面
    - 控制台打印 URL
    - _Requirements: 17.8-17.10_



- [x] 12. Tkinter 远程客户端实现



  - [x] 12.1 实现远程客户端主窗口


    - 创建 `src/client/remote_client.py`
    - 复用本地 GUI 组件
    - 添加 API 地址配置组件
    - _Requirements: 16.1-16.2_
  - [x] 12.2 实现 API 通信层


    - 创建 `src/client/api_client.py`
    - 实现所有 API 调用封装
    - 实现 WebSocket 状态同步
    - 实现断线重连

    - _Requirements: 16.3-16.6_
  - [x] 12.3 实现文件上传功能


    - 实现音频文件选择和上传
    - 显示上传进度
    - _Requirements: 16.5_

- [ ] 13. Checkpoint - 确保所有测试通过




  - 确保所有测试通过，如有问题请询问用户



- [x] 14. 配置工具实现




  - [x] 14.1 实现配置工具主窗口


    - 创建 `src/tools/config_editor.py`
    - Cue 列表可视化编辑
    - 音频文件添加和管理
    - _Requirements: 9.1-9.4_


  - [x] 14.2 实现 Cue 编辑功能





    - 入点、出点、静音间隔设置
    - Cue 顺序调整（上移/下移按钮）
    - JSON 导入/导出
    - _Requirements: 9.2-9.4_

- [x] 15. 应用入口和集成






  - [x] 15.1 实现主程序入口

    - 创建 `src/main.py`
    - 初始化所有组件
    - 启动 GUI 和 API 服务器
    - 加载上次保存的配置和断点
    - _Requirements: 8.4, 14.1_


  - [x] 15.2 实现配置工具入口





    - 创建 `src/config_tool.py`
    - 独立启动配置编辑器
    - _Requirements: 9.1_

- [ ] 16. 最终 Checkpoint - 确保所有测试通过
  - 确保所有测试通过，如有问题请询问用户
