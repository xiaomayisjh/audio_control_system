"""
长按处理器属性测试

**Feature: multi-audio-player, Property 25: 长按时间不足取消**
**Validates: Requirements 12.5**
"""
import pytest
from hypothesis import given, strategies as st, settings, assume

from src.gui.long_press import (
    LongPressHandler,
    LongPressState,
    LongPressResult,
    simulate_long_press,
)


# 定义测试策略
# 长按阈值策略：100ms - 2000ms 的合理范围
duration_threshold_strategy = st.integers(min_value=100, max_value=2000)

# 按压时长策略：0ms - 3000ms
press_duration_strategy = st.floats(min_value=0.0, max_value=3000.0, allow_nan=False, allow_infinity=False)


class TestLongPressInsufficientDuration:
    """
    **Feature: multi-audio-player, Property 25: 长按时间不足取消**
    
    *对于任意* 长按操作，如果按压时间小于阈值（500ms），操作应被取消不执行
    **Validates: Requirements 12.5**
    """

    @given(
        threshold_ms=duration_threshold_strategy,
        press_ms=press_duration_strategy
    )
    @settings(max_examples=100)
    def test_insufficient_duration_cancels_operation(
        self,
        threshold_ms: int,
        press_ms: float
    ):
        """
        属性测试：长按时间不足时操作被取消
        
        对于任意长按阈值和按压时长：
        - 如果按压时长 < 阈值，操作应被取消（success=False）
        - 如果按压时长 >= 阈值，操作应成功（success=True）
        """
        # 创建处理器
        handler = LongPressHandler(duration_ms=threshold_ms)
        
        # 记录回调是否被执行
        callback_executed = False
        
        def on_success():
            nonlocal callback_executed
            callback_executed = True
        
        handler.bind(callback=on_success)
        
        # 模拟长按
        result = simulate_long_press(handler, press_ms)
        
        # 验证属性
        if press_ms < threshold_ms:
            # 时间不足，操作应被取消
            assert result.success is False, \
                f"按压时长 {press_ms}ms < 阈值 {threshold_ms}ms，操作应被取消"
            assert result.state == LongPressState.CANCELLED, \
                f"按压时长不足时状态应为 CANCELLED，实际为 {result.state}"
            assert callback_executed is False, \
                "按压时长不足时回调不应被执行"
        else:
            # 时间足够，操作应成功
            assert result.success is True, \
                f"按压时长 {press_ms}ms >= 阈值 {threshold_ms}ms，操作应成功"
            assert result.state == LongPressState.COMPLETED, \
                f"按压时长足够时状态应为 COMPLETED，实际为 {result.state}"
            assert callback_executed is True, \
                "按压时长足够时回调应被执行"

    @given(threshold_ms=duration_threshold_strategy)
    @settings(max_examples=100)
    def test_zero_duration_always_cancels(self, threshold_ms: int):
        """
        属性测试：零时长按压总是被取消
        
        对于任意长按阈值，零时长的按压应总是被取消
        """
        handler = LongPressHandler(duration_ms=threshold_ms)
        
        callback_executed = False
        handler.bind(callback=lambda: None)
        
        # 模拟零时长按压
        result = simulate_long_press(handler, 0.0)
        
        assert result.success is False, "零时长按压应被取消"
        assert result.state == LongPressState.CANCELLED

    @given(
        threshold_ms=duration_threshold_strategy,
        press_ms=st.floats(min_value=0.0, max_value=99.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_very_short_press_always_cancels(self, threshold_ms: int, press_ms: float):
        """
        属性测试：极短按压总是被取消
        
        对于任意阈值 >= 100ms，小于 100ms 的按压应总是被取消
        """
        # 阈值至少 100ms，所以 < 100ms 的按压一定不足
        assume(threshold_ms >= 100)
        
        handler = LongPressHandler(duration_ms=threshold_ms)
        handler.bind(callback=lambda: None)
        
        result = simulate_long_press(handler, press_ms)
        
        assert result.success is False, \
            f"按压时长 {press_ms}ms 应被取消（阈值 {threshold_ms}ms）"

    @given(threshold_ms=duration_threshold_strategy)
    @settings(max_examples=100)
    def test_exact_threshold_succeeds(self, threshold_ms: int):
        """
        属性测试：恰好达到阈值时操作成功
        
        对于任意长按阈值，恰好达到阈值的按压应成功
        """
        handler = LongPressHandler(duration_ms=threshold_ms)
        
        callback_executed = False
        def on_success():
            nonlocal callback_executed
            callback_executed = True
        
        handler.bind(callback=on_success)
        
        # 模拟恰好达到阈值的按压
        result = simulate_long_press(handler, float(threshold_ms))
        
        assert result.success is True, \
            f"恰好达到阈值 {threshold_ms}ms 的按压应成功"
        assert callback_executed is True, \
            "达到阈值时回调应被执行"

    @given(
        threshold_ms=duration_threshold_strategy,
        extra_ms=st.floats(min_value=0.1, max_value=1000.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_exceeding_threshold_succeeds(self, threshold_ms: int, extra_ms: float):
        """
        属性测试：超过阈值时操作成功
        
        对于任意长按阈值，超过阈值的按压应成功
        """
        handler = LongPressHandler(duration_ms=threshold_ms)
        
        callback_executed = False
        def on_success():
            nonlocal callback_executed
            callback_executed = True
        
        handler.bind(callback=on_success)
        
        # 模拟超过阈值的按压
        press_ms = threshold_ms + extra_ms
        result = simulate_long_press(handler, press_ms)
        
        assert result.success is True, \
            f"超过阈值的按压 {press_ms}ms > {threshold_ms}ms 应成功"
        assert callback_executed is True, \
            "超过阈值时回调应被执行"

    @given(
        threshold_ms=duration_threshold_strategy,
        deficit_ms=st.floats(min_value=0.1, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_just_below_threshold_cancels(self, threshold_ms: int, deficit_ms: float):
        """
        属性测试：略低于阈值时操作被取消
        
        对于任意长按阈值，略低于阈值的按压应被取消
        """
        press_ms = max(0.0, threshold_ms - deficit_ms)
        
        # 确保按压时长确实小于阈值
        assume(press_ms < threshold_ms)
        
        handler = LongPressHandler(duration_ms=threshold_ms)
        
        callback_executed = False
        handler.bind(callback=lambda: setattr(handler, '_test_executed', True))
        
        result = simulate_long_press(handler, press_ms)
        
        assert result.success is False, \
            f"略低于阈值的按压 {press_ms}ms < {threshold_ms}ms 应被取消"


class TestLongPressCancelCallback:
    """
    测试取消回调功能
    """

    @given(
        threshold_ms=duration_threshold_strategy,
        press_ms=st.floats(min_value=0.0, max_value=99.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_cancel_callback_invoked_on_insufficient_duration(
        self,
        threshold_ms: int,
        press_ms: float
    ):
        """
        属性测试：时间不足时取消回调被调用
        """
        assume(threshold_ms >= 100)  # 确保阈值大于按压时长
        
        handler = LongPressHandler(duration_ms=threshold_ms)
        
        cancel_callback_executed = False
        def on_cancel():
            nonlocal cancel_callback_executed
            cancel_callback_executed = True
        
        handler.bind(
            callback=lambda: None,
            cancel_callback=on_cancel
        )
        
        result = simulate_long_press(handler, press_ms)
        
        assert result.success is False
        assert cancel_callback_executed is True, \
            "时间不足时取消回调应被调用"


class TestLongPressResultDuration:
    """
    测试结果中的时长记录
    """

    @given(
        threshold_ms=duration_threshold_strategy,
        press_ms=press_duration_strategy
    )
    @settings(max_examples=100)
    def test_result_contains_actual_duration(
        self,
        threshold_ms: int,
        press_ms: float
    ):
        """
        属性测试：结果包含实际按压时长
        
        对于任意按压操作，结果中的 duration_ms 应接近实际按压时长
        """
        handler = LongPressHandler(duration_ms=threshold_ms)
        handler.bind(callback=lambda: None)
        
        result = simulate_long_press(handler, press_ms)
        
        # 允许 1ms 的误差（由于浮点数精度）
        assert abs(result.duration_ms - press_ms) < 1.0, \
            f"结果时长 {result.duration_ms}ms 应接近实际按压时长 {press_ms}ms"
