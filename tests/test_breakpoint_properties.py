"""
Breakpoint 属性测试

**Feature: multi-audio-player, Property 21: 断点数据序列化往返**
**Validates: Requirements 8.3**
"""
import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timezone

from src.models.breakpoint import Breakpoint


# 定义 Breakpoint 的生成策略
# 使用有效的 datetime 范围，避免序列化问题
datetime_strategy = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2100, 12, 31),
)

breakpoint_strategy = st.builds(
    Breakpoint,
    id=st.text(min_size=1, max_size=50, alphabet=st.characters(
        whitelist_categories=('L', 'N'),
        whitelist_characters='_-'
    )),
    audio_id=st.text(min_size=1, max_size=50, alphabet=st.characters(
        whitelist_categories=('L', 'N'),
        whitelist_characters='_-'
    )),
    position=st.floats(min_value=0.0, max_value=36000.0, allow_nan=False, allow_infinity=False),
    label=st.text(min_size=0, max_size=100),
    created_at=datetime_strategy,
    auto_saved=st.booleans(),
)


class TestBreakpointRoundTrip:
    """
    **Feature: multi-audio-player, Property 21: 断点数据序列化往返**
    
    *对于任意* 有效的断点数据集合，保存到文件后加载应得到等价的数据
    **Validates: Requirements 8.3**
    """

    @given(bp=breakpoint_strategy)
    @settings(max_examples=100)
    def test_json_round_trip(self, bp: Breakpoint):
        """
        属性测试：JSON 序列化往返一致性
        
        对于任意有效的 Breakpoint 对象：
        1. 序列化为 JSON 字符串
        2. 从 JSON 字符串反序列化
        3. 结果应与原始对象等价
        """
        # 序列化
        json_str = bp.to_json()
        
        # 反序列化
        restored = Breakpoint.from_json(json_str)
        
        # 验证所有字段一致
        assert restored.id == bp.id
        assert restored.audio_id == bp.audio_id
        assert restored.position == bp.position
        assert restored.label == bp.label
        assert restored.created_at == bp.created_at
        assert restored.auto_saved == bp.auto_saved

    @given(bp=breakpoint_strategy)
    @settings(max_examples=100)
    def test_dict_round_trip(self, bp: Breakpoint):
        """
        属性测试：字典序列化往返一致性
        
        对于任意有效的 Breakpoint 对象：
        1. 转换为字典
        2. 从字典创建新实例
        3. 结果应与原始对象等价
        """
        # 转换为字典
        data = bp.to_dict()
        
        # 从字典创建
        restored = Breakpoint.from_dict(data)
        
        # 验证所有字段一致
        assert restored.id == bp.id
        assert restored.audio_id == bp.audio_id
        assert restored.position == bp.position
        assert restored.label == bp.label
        assert restored.created_at == bp.created_at
        assert restored.auto_saved == bp.auto_saved

    @given(breakpoints=st.lists(breakpoint_strategy, min_size=0, max_size=20))
    @settings(max_examples=100)
    def test_breakpoint_collection_round_trip(self, breakpoints: list):
        """
        属性测试：断点集合序列化往返一致性
        
        对于任意有效的断点数据集合：
        1. 将所有断点转换为字典列表
        2. 从字典列表恢复所有断点
        3. 结果应与原始集合等价
        """
        import json
        
        # 序列化为字典列表
        data_list = [bp.to_dict() for bp in breakpoints]
        
        # 序列化为 JSON 字符串（模拟保存到文件）
        json_str = json.dumps(data_list, ensure_ascii=False)
        
        # 反序列化（模拟从文件加载）
        loaded_data = json.loads(json_str)
        restored_breakpoints = [Breakpoint.from_dict(d) for d in loaded_data]
        
        # 验证数量一致
        assert len(restored_breakpoints) == len(breakpoints)
        
        # 验证每个断点的所有字段一致
        for original, restored in zip(breakpoints, restored_breakpoints):
            assert restored.id == original.id
            assert restored.audio_id == original.audio_id
            assert restored.position == original.position
            assert restored.label == original.label
            assert restored.created_at == original.created_at
            assert restored.auto_saved == original.auto_saved

    @given(audio_breakpoints=st.dictionaries(
        keys=st.text(min_size=1, max_size=30, alphabet=st.characters(
            whitelist_categories=('L', 'N'),
            whitelist_characters='_-'
        )),
        values=st.lists(breakpoint_strategy, min_size=0, max_size=10),
        min_size=0,
        max_size=10
    ))
    @settings(max_examples=100)
    def test_audio_breakpoints_map_round_trip(self, audio_breakpoints: dict):
        """
        属性测试：音频断点映射序列化往返一致性
        
        对于任意有效的 audio_id -> breakpoints 映射：
        1. 将映射转换为可序列化的字典格式
        2. 序列化为 JSON
        3. 反序列化并恢复映射
        4. 结果应与原始映射等价
        
        这模拟了 breakpoints.json 文件的完整往返过程
        """
        import json
        
        # 转换为可序列化格式
        serializable = {
            audio_id: [bp.to_dict() for bp in bps]
            for audio_id, bps in audio_breakpoints.items()
        }
        
        # 序列化为 JSON（模拟保存到文件）
        json_str = json.dumps(serializable, ensure_ascii=False)
        
        # 反序列化（模拟从文件加载）
        loaded_data = json.loads(json_str)
        restored_map = {
            audio_id: [Breakpoint.from_dict(d) for d in bp_list]
            for audio_id, bp_list in loaded_data.items()
        }
        
        # 验证键集合一致
        assert set(restored_map.keys()) == set(audio_breakpoints.keys())
        
        # 验证每个音频的断点列表
        for audio_id in audio_breakpoints:
            original_list = audio_breakpoints[audio_id]
            restored_list = restored_map[audio_id]
            
            assert len(restored_list) == len(original_list)
            
            for original, restored in zip(original_list, restored_list):
                assert restored.id == original.id
                assert restored.audio_id == original.audio_id
                assert restored.position == original.position
                assert restored.label == original.label
                assert restored.created_at == original.created_at
                assert restored.auto_saved == original.auto_saved
