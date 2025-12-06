"""
CueListConfig 属性测试

**Feature: multi-audio-player, Property 23: 配置序列化往返**
**Validates: Requirements 9.4, 9.5**
"""
import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timezone

from src.models.cue_config import CueListConfig
from src.models.cue import Cue
from src.models.audio_track import AudioTrack


# 定义 AudioTrack 的生成策略
audio_track_strategy = st.builds(
    AudioTrack,
    id=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='_-')),
    file_path=st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='_-./\\')),
    duration=st.floats(min_value=0.1, max_value=36000.0, allow_nan=False, allow_infinity=False),
    title=st.text(min_size=0, max_size=100),
    track_type=st.sampled_from(["bgm", "sfx"]),
)


# 定义 Cue 的生成策略
cue_strategy = st.builds(
    Cue,
    id=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='_-')),
    audio_id=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='_-')),
    start_time=st.floats(min_value=0.0, max_value=36000.0, allow_nan=False, allow_infinity=False),
    end_time=st.one_of(st.none(), st.floats(min_value=0.0, max_value=36000.0, allow_nan=False, allow_infinity=False)),
    silence_before=st.floats(min_value=0.0, max_value=60.0, allow_nan=False, allow_infinity=False),
    silence_after=st.floats(min_value=0.0, max_value=60.0, allow_nan=False, allow_infinity=False),
    volume=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    label=st.text(min_size=0, max_size=100),
)


# 定义 datetime 的生成策略（使用 naive datetime 避免时区问题）
datetime_strategy = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2100, 12, 31),
)


# 定义 CueListConfig 的生成策略
cue_list_config_strategy = st.builds(
    CueListConfig,
    version=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='.')),
    name=st.text(min_size=0, max_size=100),
    created_at=datetime_strategy,
    cues=st.lists(cue_strategy, min_size=0, max_size=20),
    audio_files=st.lists(audio_track_strategy, min_size=0, max_size=20),
)



class TestCueListConfigRoundTrip:
    """
    **Feature: multi-audio-player, Property 23: 配置序列化往返**
    
    *对于任意* 有效的 CueListConfig 对象，保存为 JSON 后加载应得到等价的配置
    **Validates: Requirements 9.4, 9.5**
    """

    @given(config=cue_list_config_strategy)
    @settings(max_examples=100)
    def test_json_round_trip(self, config: CueListConfig):
        """
        属性测试：JSON 序列化往返一致性
        
        对于任意有效的 CueListConfig 对象：
        1. 序列化为 JSON 字符串
        2. 从 JSON 字符串反序列化
        3. 结果应与原始对象等价
        """
        # 序列化
        json_str = config.to_json()
        
        # 反序列化
        restored = CueListConfig.from_json(json_str)
        
        # 验证基本字段
        assert restored.version == config.version
        assert restored.name == config.name
        assert restored.created_at == config.created_at
        
        # 验证 cues 列表
        assert len(restored.cues) == len(config.cues)
        for orig_cue, rest_cue in zip(config.cues, restored.cues):
            assert rest_cue.id == orig_cue.id
            assert rest_cue.audio_id == orig_cue.audio_id
            assert rest_cue.start_time == orig_cue.start_time
            assert rest_cue.end_time == orig_cue.end_time
            assert rest_cue.silence_before == orig_cue.silence_before
            assert rest_cue.silence_after == orig_cue.silence_after
            assert rest_cue.volume == orig_cue.volume
            assert rest_cue.label == orig_cue.label
        
        # 验证 audio_files 列表
        assert len(restored.audio_files) == len(config.audio_files)
        for orig_track, rest_track in zip(config.audio_files, restored.audio_files):
            assert rest_track.id == orig_track.id
            assert rest_track.file_path == orig_track.file_path
            assert rest_track.duration == orig_track.duration
            assert rest_track.title == orig_track.title
            assert rest_track.track_type == orig_track.track_type

    @given(config=cue_list_config_strategy)
    @settings(max_examples=100)
    def test_dict_round_trip(self, config: CueListConfig):
        """
        属性测试：字典序列化往返一致性
        
        对于任意有效的 CueListConfig 对象：
        1. 转换为字典
        2. 从字典创建新实例
        3. 结果应与原始对象等价
        """
        # 转换为字典
        data = config.to_dict()
        
        # 从字典创建
        restored = CueListConfig.from_dict(data)
        
        # 验证基本字段
        assert restored.version == config.version
        assert restored.name == config.name
        assert restored.created_at == config.created_at
        
        # 验证 cues 列表长度和内容
        assert len(restored.cues) == len(config.cues)
        for orig_cue, rest_cue in zip(config.cues, restored.cues):
            assert rest_cue.id == orig_cue.id
            assert rest_cue.audio_id == orig_cue.audio_id
            assert rest_cue.start_time == orig_cue.start_time
            assert rest_cue.end_time == orig_cue.end_time
            assert rest_cue.silence_before == orig_cue.silence_before
            assert rest_cue.silence_after == orig_cue.silence_after
            assert rest_cue.volume == orig_cue.volume
            assert rest_cue.label == orig_cue.label
        
        # 验证 audio_files 列表长度和内容
        assert len(restored.audio_files) == len(config.audio_files)
        for orig_track, rest_track in zip(config.audio_files, restored.audio_files):
            assert rest_track.id == orig_track.id
            assert rest_track.file_path == orig_track.file_path
            assert rest_track.duration == orig_track.duration
            assert rest_track.title == orig_track.title
            assert rest_track.track_type == orig_track.track_type
