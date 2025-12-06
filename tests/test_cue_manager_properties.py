"""
CueManager 属性测试

**Feature: multi-audio-player, Property 22: Cue 添加完整性**
**Validates: Requirements 9.2**
"""
import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime

from src.core.cue_manager import CueManager
from src.models.cue import Cue
from src.models.audio_track import AudioTrack


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


class TestCueAddIntegrity:
    """
    **Feature: multi-audio-player, Property 22: Cue 添加完整性**
    
    *对于任意* 新 Cue 配置，添加到 Cue 列表后，列表应包含该 Cue 且属性完整
    **Validates: Requirements 9.2**
    """

    @given(cue=cue_strategy)
    @settings(max_examples=100)
    def test_add_cue_contains_cue(self, cue: Cue):
        """
        属性测试：添加 Cue 后列表应包含该 Cue
        
        对于任意有效的 Cue 对象：
        1. 创建空的 CueManager
        2. 添加 Cue
        3. 列表应包含该 Cue
        """
        manager = CueManager()
        
        # 添加 Cue
        manager.add_cue(cue)
        
        # 验证列表包含该 Cue
        assert manager.contains_cue(cue.id)
        assert manager.get_cue_count() == 1


    @given(cue=cue_strategy)
    @settings(max_examples=100)
    def test_add_cue_preserves_attributes(self, cue: Cue):
        """
        属性测试：添加 Cue 后属性应完整保留
        
        对于任意有效的 Cue 对象：
        1. 创建空的 CueManager
        2. 添加 Cue
        3. 获取该 Cue 并验证所有属性完整
        """
        manager = CueManager()
        
        # 添加 Cue
        manager.add_cue(cue)
        
        # 获取添加的 Cue
        retrieved = manager.get_cue_by_id(cue.id)
        
        # 验证 Cue 存在
        assert retrieved is not None
        
        # 验证所有属性完整
        assert retrieved.id == cue.id
        assert retrieved.audio_id == cue.audio_id
        assert retrieved.start_time == cue.start_time
        assert retrieved.end_time == cue.end_time
        assert retrieved.silence_before == cue.silence_before
        assert retrieved.silence_after == cue.silence_after
        assert retrieved.volume == cue.volume
        assert retrieved.label == cue.label

    @given(cues=st.lists(cue_strategy, min_size=1, max_size=20, unique_by=lambda c: c.id))
    @settings(max_examples=100)
    def test_add_multiple_cues_all_present(self, cues: list):
        """
        属性测试：添加多个 Cue 后所有 Cue 都应存在
        
        对于任意有效的 Cue 列表：
        1. 创建空的 CueManager
        2. 依次添加所有 Cue
        3. 所有 Cue 都应存在于列表中
        """
        manager = CueManager()
        
        # 添加所有 Cue
        for cue in cues:
            manager.add_cue(cue)
        
        # 验证数量正确
        assert manager.get_cue_count() == len(cues)
        
        # 验证所有 Cue 都存在
        for cue in cues:
            assert manager.contains_cue(cue.id)
            retrieved = manager.get_cue_by_id(cue.id)
            assert retrieved is not None
            assert retrieved.id == cue.id
            assert retrieved.audio_id == cue.audio_id

    @given(cues=st.lists(cue_strategy, min_size=1, max_size=20, unique_by=lambda c: c.id))
    @settings(max_examples=100)
    def test_add_cues_preserves_order(self, cues: list):
        """
        属性测试：添加 Cue 后顺序应保持一致
        
        对于任意有效的 Cue 列表：
        1. 创建空的 CueManager
        2. 依次添加所有 Cue
        3. 获取的 Cue 列表顺序应与添加顺序一致
        """
        manager = CueManager()
        
        # 添加所有 Cue
        for cue in cues:
            manager.add_cue(cue)
        
        # 获取 Cue 列表
        cue_list = manager.cue_list
        
        # 验证顺序一致
        assert len(cue_list) == len(cues)
        for i, (original, retrieved) in enumerate(zip(cues, cue_list)):
            assert retrieved.id == original.id, f"Cue at index {i} has wrong id"
