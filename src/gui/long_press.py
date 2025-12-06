"""
长按处理器模块

实现高危操作的长按确认机制，防止演出中的误操作。

**Requirements: 12.1-12.5**
"""
import time
from typing import Callable, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class LongPressState(Enum):
    """长按状态枚举"""
    IDLE = "idle"           # 空闲状态
    PRESSING = "pressing"   # 按压中
    COMPLETED = "completed" # 已完成
    CANCELLED = "cancelled" # 已取消


@dataclass
class LongPressResult:
    """长按操作结果"""
    success: bool           # 是否成功触发
    duration_ms: float      # 实际按压时长（毫秒）
    state: LongPressState   # 最终状态
    
    @property
    def was_cancelled(self) -> bool:
        """是否被取消"""
        return self.state == LongPressState.CANCELLED


class LongPressHandler:
    """
    长按确认处理器
    
    用于处理高危操作的长按确认，防止演出中的误操作。
    支持 Tkinter 控件的按压事件绑定。
    
    **Requirements: 12.1-12.5**
    
    使用示例:
        handler = LongPressHandler(button, duration_ms=500)
        handler.bind(
            callback=lambda: print("执行操作"),
            progress_callback=lambda p: print(f"进度: {p:.0%}")
        )
    """
    
    DEFAULT_DURATION_MS = 500  # 默认长按阈值（毫秒）
    
    def __init__(self, widget: Any = None, duration_ms: int = DEFAULT_DURATION_MS):
        """
        初始化长按处理器
        
        Args:
            widget: Tkinter 控件（可选，可后续通过 bind 方法绑定）
            duration_ms: 长按阈值（毫秒），默认 500ms
        """
        self.widget = widget
        self.duration_ms = duration_ms
        self._press_start: Optional[float] = None
        self._callback: Optional[Callable[[], None]] = None
        self._progress_callback: Optional[Callable[[float], None]] = None
        self._cancel_callback: Optional[Callable[[], None]] = None
        self._state: LongPressState = LongPressState.IDLE
        self._progress_timer_id: Optional[str] = None
        self._last_result: Optional[LongPressResult] = None

    @property
    def state(self) -> LongPressState:
        """获取当前状态"""
        return self._state
    
    @property
    def is_pressing(self) -> bool:
        """是否正在按压中"""
        return self._state == LongPressState.PRESSING
    
    @property
    def last_result(self) -> Optional[LongPressResult]:
        """获取上次操作结果"""
        return self._last_result
    
    def bind(
        self,
        callback: Callable[[], None],
        progress_callback: Optional[Callable[[float], None]] = None,
        cancel_callback: Optional[Callable[[], None]] = None,
        widget: Any = None
    ) -> None:
        """
        绑定回调函数
        
        Args:
            callback: 长按成功后执行的回调函数
            progress_callback: 进度回调函数，参数为 0.0-1.0 的进度值
            cancel_callback: 取消时的回调函数（可选）
            widget: Tkinter 控件（可选，覆盖构造函数中的控件）
        """
        self._callback = callback
        self._progress_callback = progress_callback
        self._cancel_callback = cancel_callback
        
        if widget is not None:
            self.widget = widget
        
        # 如果有控件，绑定事件
        if self.widget is not None:
            self._bind_events()
    
    def _bind_events(self) -> None:
        """绑定 Tkinter 事件"""
        if self.widget is None:
            return
        
        # 绑定鼠标按下和释放事件
        self.widget.bind("<ButtonPress-1>", self.on_press)
        self.widget.bind("<ButtonRelease-1>", self.on_release)
        # 绑定鼠标离开事件（视为取消）
        self.widget.bind("<Leave>", self._on_leave)
    
    def unbind(self) -> None:
        """解除事件绑定"""
        if self.widget is not None:
            try:
                self.widget.unbind("<ButtonPress-1>")
                self.widget.unbind("<ButtonRelease-1>")
                self.widget.unbind("<Leave>")
            except Exception:
                pass  # 忽略解绑错误
        
        self._callback = None
        self._progress_callback = None
        self._cancel_callback = None
    
    def on_press(self, event: Any = None) -> None:
        """
        处理按压开始事件
        
        Args:
            event: Tkinter 事件对象（可选）
        """
        self._press_start = time.time()
        self._state = LongPressState.PRESSING
        
        # 开始进度更新
        if self._progress_callback is not None:
            self._progress_callback(0.0)
            self._start_progress_timer()
    
    def _start_progress_timer(self) -> None:
        """启动进度更新定时器"""
        if self.widget is None or self._progress_callback is None:
            return
        
        def update_progress():
            if self._state != LongPressState.PRESSING:
                return
            
            progress = self.get_progress()
            if progress < 1.0:
                self._progress_callback(progress)
                # 每 50ms 更新一次进度
                self._progress_timer_id = self.widget.after(50, update_progress)
            else:
                self._progress_callback(1.0)
        
        # 延迟 50ms 后开始更新
        self._progress_timer_id = self.widget.after(50, update_progress)
    
    def _stop_progress_timer(self) -> None:
        """停止进度更新定时器"""
        if self._progress_timer_id is not None and self.widget is not None:
            try:
                self.widget.after_cancel(self._progress_timer_id)
            except Exception:
                pass
            self._progress_timer_id = None

    def on_release(self, event: Any = None) -> LongPressResult:
        """
        处理按压释放事件
        
        Args:
            event: Tkinter 事件对象（可选）
            
        Returns:
            LongPressResult: 操作结果
        """
        self._stop_progress_timer()
        
        if self._state != LongPressState.PRESSING:
            # 不在按压状态，返回取消结果
            result = LongPressResult(
                success=False,
                duration_ms=0.0,
                state=LongPressState.CANCELLED
            )
            self._last_result = result
            return result
        
        # 计算按压时长
        duration_ms = self.get_elapsed_ms()
        
        # 检查是否达到阈值
        if self.check_duration():
            # 长按成功
            self._state = LongPressState.COMPLETED
            result = LongPressResult(
                success=True,
                duration_ms=duration_ms,
                state=LongPressState.COMPLETED
            )
            self._last_result = result
            
            # 执行回调
            if self._callback is not None:
                self._callback()
        else:
            # 长按时间不足，取消操作
            self._state = LongPressState.CANCELLED
            result = LongPressResult(
                success=False,
                duration_ms=duration_ms,
                state=LongPressState.CANCELLED
            )
            self._last_result = result
            
            # 执行取消回调
            if self._cancel_callback is not None:
                self._cancel_callback()
        
        # 重置按压开始时间
        self._press_start = None
        
        return result
    
    def _on_leave(self, event: Any = None) -> None:
        """
        处理鼠标离开事件（视为取消）
        
        Args:
            event: Tkinter 事件对象（可选）
        """
        if self._state == LongPressState.PRESSING:
            self.cancel()
    
    def cancel(self) -> LongPressResult:
        """
        取消当前按压操作
        
        Returns:
            LongPressResult: 取消结果
        """
        self._stop_progress_timer()
        
        duration_ms = self.get_elapsed_ms() if self._press_start else 0.0
        
        self._state = LongPressState.CANCELLED
        self._press_start = None
        
        result = LongPressResult(
            success=False,
            duration_ms=duration_ms,
            state=LongPressState.CANCELLED
        )
        self._last_result = result
        
        # 执行取消回调
        if self._cancel_callback is not None:
            self._cancel_callback()
        
        return result
    
    def get_elapsed_ms(self) -> float:
        """
        获取当前按压时长（毫秒）
        
        Returns:
            float: 按压时长（毫秒），未按压时返回 0
        """
        if self._press_start is None:
            return 0.0
        return (time.time() - self._press_start) * 1000
    
    def get_progress(self) -> float:
        """
        获取当前进度（0.0-1.0）
        
        Returns:
            float: 进度值，0.0 表示刚开始，1.0 表示达到阈值
        """
        elapsed = self.get_elapsed_ms()
        if self.duration_ms <= 0:
            return 1.0
        return min(1.0, elapsed / self.duration_ms)
    
    def check_duration(self) -> bool:
        """
        检查按压时长是否达到阈值
        
        Returns:
            bool: True 表示达到阈值，False 表示未达到
        """
        return self.get_elapsed_ms() >= self.duration_ms
    
    def reset(self) -> None:
        """重置处理器状态"""
        self._stop_progress_timer()
        self._press_start = None
        self._state = LongPressState.IDLE
        self._last_result = None
    
    def set_duration(self, duration_ms: int) -> None:
        """
        设置长按阈值
        
        Args:
            duration_ms: 长按阈值（毫秒）
        """
        self.duration_ms = duration_ms


# 便捷函数：模拟长按操作（用于测试）
def simulate_long_press(
    handler: LongPressHandler,
    press_duration_ms: float
) -> LongPressResult:
    """
    模拟长按操作（用于测试）
    
    Args:
        handler: 长按处理器
        press_duration_ms: 模拟的按压时长（毫秒）
        
    Returns:
        LongPressResult: 操作结果
    """
    # 模拟按下
    handler.on_press()
    
    # 模拟时间流逝（通过直接设置 _press_start）
    handler._press_start = time.time() - (press_duration_ms / 1000)
    
    # 模拟释放
    return handler.on_release()
