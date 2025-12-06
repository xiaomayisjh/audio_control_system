"""
PlaybackState 属性测试

**Feature: multi-audio-player, Property 20: 播放状态序列化往返**
**Validates: Requirements 8.2**
"""
import pytest
from hypothesis import given, strategies as st, settings

from src.models.playback_state import PlaybackState


# 定义 PlaybackState 的生成策略
playback_state_strategy = st.builds(
    PlaybackState,
    mode=st.sampled_from(["auto", "manual"]),
    is_playing=st.booleans(),
    is_paused=st.booleans(),
    current_audio_id=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
    current_position=st.floats(min_value=0.0, max_value=36000.0, allow_nan=False, allow_infinity=False),
    current_cue_index=st.integers(min_value=0, max_value=1000),
    bgm_volume=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    sfx_volume=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    in_silence=st.booleans(),
    silence_remaining=st.floats(min_value=0.0, max_value=3600.0, allow_nan=False, allow_infinity=False),
)


class TestPlaybackStateRoundTrip:
    """
    **Feature: multi-audio-player, Property 20: 播放状态序列化往返**
    
    *对于任意* 有效的 PlaybackState 对象，序列化后反序列化应得到等价的对象
    **Validates: Requirements 8.2**
    """

    @given(state=playback_state_strategy)
    @settings(max_examples=100)
    def test_json_round_trip(self, state: PlaybackState):
        """
        属性测试：JSON 序列化往返一致性
        
        对于任意有效的 PlaybackState 对象：
        1. 序列化为 JSON 字符串
        2. 从 JSON 字符串反序列化
        3. 结果应与原始对象等价
        """
        # 序列化
        json_str = state.to_json()
        
        # 反序列化
        restored = PlaybackState.from_json(json_str)
        
        # 验证所有字段一致
        assert restored.mode == state.mode
        assert restored.is_playing == state.is_playing
        assert restored.is_paused == state.is_paused
        assert restored.current_audio_id == state.current_audio_id
        assert restored.current_position == state.current_position
        assert restored.current_cue_index == state.current_cue_index
        assert restored.bgm_volume == state.bgm_volume
        assert restored.sfx_volume == state.sfx_volume
        assert restored.in_silence == state.in_silence
        assert restored.silence_remaining == state.silence_remaining

    @given(state=playback_state_strategy)
    @settings(max_examples=100)
    def test_dict_round_trip(self, state: PlaybackState):
        """
        属性测试：字典序列化往返一致性
        
        对于任意有效的 PlaybackState 对象：
        1. 转换为字典
        2. 从字典创建新实例
        3. 结果应与原始对象等价
        """
        # 转换为字典
        data = state.to_dict()
        
        # 从字典创建
        restored = PlaybackState.from_dict(data)
        
        # 验证所有字段一致
        assert restored.mode == state.mode
        assert restored.is_playing == state.is_playing
        assert restored.is_paused == state.is_paused
        assert restored.current_audio_id == state.current_audio_id
        assert restored.current_position == state.current_position
        assert restored.current_cue_index == state.current_cue_index
        assert restored.bgm_volume == state.bgm_volume
        assert restored.sfx_volume == state.sfx_volume
        assert restored.in_silence == state.in_silence
        assert restored.silence_remaining == state.silence_remaining
