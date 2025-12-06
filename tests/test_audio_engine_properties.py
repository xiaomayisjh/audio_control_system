"""
AudioEngine 属性测试

**Feature: multi-audio-player, Property 16: 音量设置一致性**
**Validates: Requirements 6.3**
"""
import pytest
from hypothesis import given, strategies as st, settings

from src.core.audio_engine import AudioEngine


# 定义音量值的生成策略 (0.0 - 1.0)
volume_strategy = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)


# 模块级别的引擎实例，避免重复初始化 pygame.mixer
_engine = None


def get_engine() -> AudioEngine:
    """获取或创建音频引擎实例"""
    global _engine
    if _engine is None:
        _engine = AudioEngine()
    return _engine


@pytest.fixture(scope="module", autouse=True)
def cleanup_engine():
    """模块结束时清理引擎"""
    yield
    global _engine
    if _engine is not None:
        _engine.shutdown()
        _engine = None


class TestVolumeConsistency:
    """
    **Feature: multi-audio-player, Property 16: 音量设置一致性**
    
    *对于任意* 音量值 v（0.0-1.0），设置音量后立即获取，返回值应等于 v
    **Validates: Requirements 6.3**
    """
    
    @given(volume=volume_strategy)
    @settings(max_examples=100)
    def test_bgm_volume_consistency(self, volume: float):
        """
        属性测试：BGM 音量设置一致性
        
        对于任意有效的音量值 v (0.0-1.0)：
        1. 设置 BGM 音量为 v
        2. 获取 BGM 音量
        3. 返回值应等于 v
        """
        engine = get_engine()
        
        # 设置音量
        engine.set_bgm_volume(volume)
        
        # 获取音量
        result = engine.get_bgm_volume()
        
        # 验证一致性
        assert result == volume, f"Expected BGM volume {volume}, got {result}"
    
    @given(volume=volume_strategy)
    @settings(max_examples=100)
    def test_sfx_volume_consistency(self, volume: float):
        """
        属性测试：音效音量设置一致性
        
        对于任意有效的音量值 v (0.0-1.0)：
        1. 设置音效音量为 v
        2. 获取音效音量
        3. 返回值应等于 v
        """
        engine = get_engine()
        
        # 设置音量
        engine.set_sfx_volume(volume)
        
        # 获取音量
        result = engine.get_sfx_volume()
        
        # 验证一致性
        assert result == volume, f"Expected SFX volume {volume}, got {result}"
    
    @given(bgm_vol=volume_strategy, sfx_vol=volume_strategy)
    @settings(max_examples=100)
    def test_volume_independence(self, bgm_vol: float, sfx_vol: float):
        """
        属性测试：BGM 和音效音量独立性
        
        对于任意有效的音量值组合：
        1. 设置 BGM 音量
        2. 设置音效音量
        3. 两者应保持独立，互不影响
        """
        engine = get_engine()
        
        # 设置两种音量
        engine.set_bgm_volume(bgm_vol)
        engine.set_sfx_volume(sfx_vol)
        
        # 验证两者独立
        assert engine.get_bgm_volume() == bgm_vol
        assert engine.get_sfx_volume() == sfx_vol
        
        # 再次修改 BGM 音量，音效音量不应改变
        new_bgm_vol = 1.0 - bgm_vol  # 使用不同的值
        engine.set_bgm_volume(new_bgm_vol)
        assert engine.get_sfx_volume() == sfx_vol, "SFX volume changed when BGM volume was modified"
        
        # 再次修改音效音量，BGM 音量不应改变
        new_sfx_vol = 1.0 - sfx_vol
        engine.set_sfx_volume(new_sfx_vol)
        assert engine.get_bgm_volume() == new_bgm_vol, "BGM volume changed when SFX volume was modified"


class TestBgmSfxVolumeIndependence:
    """
    **Feature: multi-audio-player, Property 17: BGM/音效音量独立**
    
    *对于任意* BGM 音量调节操作，音效音量应保持不变；反之亦然
    **Validates: Requirements 6.4**
    """
    
    @given(
        initial_sfx_vol=volume_strategy,
        new_bgm_vol=volume_strategy
    )
    @settings(max_examples=100)
    def test_bgm_volume_change_does_not_affect_sfx(
        self, 
        initial_sfx_vol: float,
        new_bgm_vol: float
    ):
        """
        属性测试：调节 BGM 音量不影响音效音量
        
        **Feature: multi-audio-player, Property 17: BGM/音效音量独立**
        **Validates: Requirements 6.4**
        
        对于任意有效的音量值组合：
        1. 设置音效音量
        2. 修改 BGM 音量
        3. 音效音量应保持不变
        """
        engine = get_engine()
        
        # 设置初始音效音量
        engine.set_sfx_volume(initial_sfx_vol)
        
        # 修改 BGM 音量
        engine.set_bgm_volume(new_bgm_vol)
        
        # 验证音效音量保持不变
        assert engine.get_sfx_volume() == initial_sfx_vol, \
            f"SFX volume changed from {initial_sfx_vol} when BGM volume was set to {new_bgm_vol}"
    
    @given(
        initial_bgm_vol=volume_strategy,
        new_sfx_vol=volume_strategy
    )
    @settings(max_examples=100)
    def test_sfx_volume_change_does_not_affect_bgm(
        self, 
        initial_bgm_vol: float,
        new_sfx_vol: float
    ):
        """
        属性测试：调节音效音量不影响 BGM 音量
        
        **Feature: multi-audio-player, Property 17: BGM/音效音量独立**
        **Validates: Requirements 6.4**
        
        对于任意有效的音量值组合：
        1. 设置 BGM 音量
        2. 修改音效音量
        3. BGM 音量应保持不变
        """
        engine = get_engine()
        
        # 设置初始 BGM 音量
        engine.set_bgm_volume(initial_bgm_vol)
        
        # 修改音效音量
        engine.set_sfx_volume(new_sfx_vol)
        
        # 验证 BGM 音量保持不变
        assert engine.get_bgm_volume() == initial_bgm_vol, \
            f"BGM volume changed from {initial_bgm_vol} when SFX volume was set to {new_sfx_vol}"
