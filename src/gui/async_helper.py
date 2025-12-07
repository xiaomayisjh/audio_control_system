"""异步辅助模块

提供在 Tkinter 环境中安全调用异步函数的工具。
"""
import asyncio
import threading
from typing import Coroutine, Any, Callable


def run_async(coro: Coroutine[Any, Any, Any]) -> None:
    """在后台线程中运行异步协程
    
    用于在 Tkinter 回调中安全地调用异步函数。
    
    Args:
        coro: 要执行的协程
    
    Example:
        run_async(controller.play())
    """
    def run():
        try:
            asyncio.run(coro)
        except Exception as e:
            print(f"Async error: {e}")
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()


def run_async_callback(coro_func: Callable[[], Coroutine[Any, Any, Any]]) -> Callable[[], None]:
    """创建一个可以在 Tkinter 中使用的回调函数
    
    Args:
        coro_func: 返回协程的函数
        
    Returns:
        可以直接用作 Tkinter 回调的函数
    
    Example:
        button.config(command=run_async_callback(lambda: controller.play()))
    """
    def callback():
        run_async(coro_func())
    return callback
