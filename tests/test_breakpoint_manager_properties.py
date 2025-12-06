"""
BreakpointManager 属性测试

测试断点管理器的核心属性：
- Property 5: 断点保存完整性
- Property 6: 断点删除完整性
- Property 12: 单音频断点清除
- Property 14: 断点存储独立性
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime

from src.core.breakpoint_manager import BreakpointManager
from src.models.breakpoint import Breakpoint


# 定义生成策略
audio_id_strategy = st.text(
    min_size=1, 
    max_size=30, 
    alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='_-')
)

position_strategy = st.floats(
    min_value=0.0, 
    max_value=36000.0,  # 最大 10 小时
    allow_nan=False, 
    allow_infinity=False
)

label_strategy = st.text(min_size=0, max_size=100)


class TestBreakpointSaveIntegrity:
    """
    **Feature: multi-audio-player, Property 5: 断点保存完整性**
    
    *对于任意* 音频和播放位置，保存断点后，该音频的断点列表应包含该位置的断点记录
    **Validates: Requirements 2.4, 5.1**
    """

    @given(
        audio_id=audio_id_strategy,
        position=position_strategy,
        label=label_strategy,
        auto_saved=st.booleans()
    )
    @settings(max_examples=100)
    def test_save_breakpoint_adds_to_list(
        self, 
        audio_id: str, 
        position: float, 
        label: str,
        auto_saved: bool
    ):
        """
        属性测试：保存断点后，断点列表应包含该断点
        
        对于任意有效的音频 ID 和播放位置：
        1. 创建新的断点管理器
        2. 保存断点
        3. 获取该音频的断点列表
        4. 列表应包含刚保存的断点，且位置正确
        """
        manager = BreakpointManager()
        
        # 保存断点
        bp_id = manager.save_breakpoint(audio_id, position, label, auto_saved)
        
        # 获取断点列表
        breakpoints = manager.get_breakpoints(audio_id)
        
        # 验证断点存在
        assert len(breakpoints) >= 1
        
        # 查找刚保存的断点
        saved_bp = None
        for bp in breakpoints:
            if bp.id == bp_id:
                saved_bp = bp
                break
        
        # 验证断点属性
        assert saved_bp is not None, "保存的断点应该在列表中"
        assert saved_bp.audio_id == audio_id
        assert saved_bp.position == position
        assert saved_bp.label == label
        assert saved_bp.auto_saved == auto_saved


    @given(
        audio_id=audio_id_strategy,
        positions=st.lists(position_strategy, min_size=1, max_size=20)
    )
    @settings(max_examples=100)
    def test_multiple_breakpoints_all_saved(self, audio_id: str, positions: list):
        """
        属性测试：多次保存断点后，所有断点都应存在
        
        对于任意音频 ID 和多个播放位置：
        1. 依次保存所有断点
        2. 获取断点列表
        3. 列表应包含所有保存的断点
        """
        manager = BreakpointManager()
        saved_ids = []
        
        # 保存所有断点
        for pos in positions:
            bp_id = manager.save_breakpoint(audio_id, pos)
            saved_ids.append(bp_id)
        
        # 获取断点列表
        breakpoints = manager.get_breakpoints(audio_id)
        
        # 验证数量
        assert len(breakpoints) == len(positions)
        
        # 验证所有 ID 都存在
        bp_ids_in_list = {bp.id for bp in breakpoints}
        for saved_id in saved_ids:
            assert saved_id in bp_ids_in_list

    @given(
        audio_id=audio_id_strategy,
        position=position_strategy
    )
    @settings(max_examples=100)
    def test_get_breakpoint_by_id(self, audio_id: str, position: float):
        """
        属性测试：通过 ID 获取断点应返回正确的断点
        
        对于任意音频 ID 和播放位置：
        1. 保存断点
        2. 通过 ID 获取断点
        3. 返回的断点应与保存的一致
        """
        manager = BreakpointManager()
        
        # 保存断点
        bp_id = manager.save_breakpoint(audio_id, position, "test_label")
        
        # 通过 ID 获取
        bp = manager.get_breakpoint(audio_id, bp_id)
        
        # 验证
        assert bp is not None
        assert bp.id == bp_id
        assert bp.audio_id == audio_id
        assert bp.position == position
        assert bp.label == "test_label"



class TestBreakpointDeleteIntegrity:
    """
    **Feature: multi-audio-player, Property 6: 断点删除完整性**
    
    *对于任意* 选中的断点集合，执行批量删除后，断点列表不应包含任何已删除的断点
    **Validates: Requirements 2.5, 5.4**
    """

    @given(
        audio_id=audio_id_strategy,
        positions=st.lists(position_strategy, min_size=1, max_size=20)
    )
    @settings(max_examples=100)
    def test_delete_single_breakpoint(self, audio_id: str, positions: list):
        """
        属性测试：删除单个断点后，该断点不应存在于列表中
        
        对于任意音频和断点列表：
        1. 保存多个断点
        2. 删除其中一个
        3. 该断点不应再存在于列表中
        4. 其他断点应保持不变
        """
        manager = BreakpointManager()
        saved_ids = []
        
        # 保存所有断点
        for pos in positions:
            bp_id = manager.save_breakpoint(audio_id, pos)
            saved_ids.append(bp_id)
        
        # 删除第一个断点
        deleted_id = saved_ids[0]
        result = manager.delete_breakpoint(audio_id, deleted_id)
        
        # 验证删除成功
        assert result is True
        
        # 获取断点列表
        breakpoints = manager.get_breakpoints(audio_id)
        bp_ids = {bp.id for bp in breakpoints}
        
        # 验证已删除的断点不存在
        assert deleted_id not in bp_ids
        
        # 验证其他断点仍存在
        for bp_id in saved_ids[1:]:
            assert bp_id in bp_ids

    @given(
        audio_id=audio_id_strategy,
        positions=st.lists(position_strategy, min_size=2, max_size=20),
        delete_indices=st.data()
    )
    @settings(max_examples=100)
    def test_batch_delete_breakpoints(self, audio_id: str, positions: list, delete_indices):
        """
        属性测试：批量删除断点后，所有选中的断点都不应存在
        
        对于任意音频和断点列表：
        1. 保存多个断点
        2. 随机选择一些断点进行批量删除
        3. 所有被删除的断点都不应存在于列表中
        4. 未被删除的断点应保持不变
        """
        manager = BreakpointManager()
        saved_ids = []
        
        # 保存所有断点
        for pos in positions:
            bp_id = manager.save_breakpoint(audio_id, pos)
            saved_ids.append(bp_id)
        
        # 随机选择要删除的断点数量（至少1个，最多全部）
        num_to_delete = delete_indices.draw(
            st.integers(min_value=1, max_value=len(saved_ids))
        )
        
        # 随机选择要删除的断点
        indices_to_delete = delete_indices.draw(
            st.lists(
                st.integers(min_value=0, max_value=len(saved_ids)-1),
                min_size=num_to_delete,
                max_size=num_to_delete,
                unique=True
            )
        )
        
        ids_to_delete = [saved_ids[i] for i in indices_to_delete]
        ids_to_keep = [saved_ids[i] for i in range(len(saved_ids)) if i not in indices_to_delete]
        
        # 批量删除
        deleted_count = manager.clear_selected(ids_to_delete)
        
        # 验证删除数量
        assert deleted_count == len(ids_to_delete)
        
        # 获取断点列表
        breakpoints = manager.get_breakpoints(audio_id)
        bp_ids = {bp.id for bp in breakpoints}
        
        # 验证已删除的断点都不存在
        for deleted_id in ids_to_delete:
            assert deleted_id not in bp_ids
        
        # 验证未删除的断点仍存在
        for kept_id in ids_to_keep:
            assert kept_id in bp_ids

    @given(audio_id=audio_id_strategy)
    @settings(max_examples=100)
    def test_delete_nonexistent_breakpoint(self, audio_id: str):
        """
        属性测试：删除不存在的断点应返回 False
        """
        manager = BreakpointManager()
        
        # 尝试删除不存在的断点
        result = manager.delete_breakpoint(audio_id, "nonexistent_id")
        
        # 验证返回 False
        assert result is False



class TestSingleAudioBreakpointClear:
    """
    **Feature: multi-audio-player, Property 12: 单音频断点清除**
    
    *对于任意* 音频，执行一键清除断点后，该音频的断点列表应为空，其他音频断点不受影响
    **Validates: Requirements 5.3**
    """

    @given(
        audio_id=audio_id_strategy,
        positions=st.lists(position_strategy, min_size=1, max_size=20)
    )
    @settings(max_examples=100)
    def test_clear_audio_breakpoints_empties_list(self, audio_id: str, positions: list):
        """
        属性测试：清除单个音频的断点后，该音频断点列表应为空
        
        对于任意音频和断点列表：
        1. 保存多个断点
        2. 执行一键清除
        3. 该音频的断点列表应为空
        """
        manager = BreakpointManager()
        
        # 保存断点
        for pos in positions:
            manager.save_breakpoint(audio_id, pos)
        
        # 验证断点已保存
        assert len(manager.get_breakpoints(audio_id)) == len(positions)
        
        # 清除断点
        manager.clear_audio_breakpoints(audio_id)
        
        # 验证断点列表为空
        assert len(manager.get_breakpoints(audio_id)) == 0

    @given(
        audio_id_1=audio_id_strategy,
        audio_id_2=audio_id_strategy,
        positions_1=st.lists(position_strategy, min_size=1, max_size=10),
        positions_2=st.lists(position_strategy, min_size=1, max_size=10)
    )
    @settings(max_examples=100)
    def test_clear_one_audio_preserves_others(
        self, 
        audio_id_1: str, 
        audio_id_2: str, 
        positions_1: list, 
        positions_2: list
    ):
        """
        属性测试：清除一个音频的断点不影响其他音频
        
        对于任意两个不同的音频：
        1. 分别为两个音频保存断点
        2. 清除第一个音频的断点
        3. 第一个音频断点列表应为空
        4. 第二个音频断点列表应保持不变
        """
        # 确保两个音频 ID 不同
        assume(audio_id_1 != audio_id_2)
        
        manager = BreakpointManager()
        
        # 为两个音频保存断点
        ids_1 = []
        for pos in positions_1:
            bp_id = manager.save_breakpoint(audio_id_1, pos)
            ids_1.append(bp_id)
        
        ids_2 = []
        for pos in positions_2:
            bp_id = manager.save_breakpoint(audio_id_2, pos)
            ids_2.append(bp_id)
        
        # 清除第一个音频的断点
        manager.clear_audio_breakpoints(audio_id_1)
        
        # 验证第一个音频断点列表为空
        assert len(manager.get_breakpoints(audio_id_1)) == 0
        
        # 验证第二个音频断点列表保持不变
        breakpoints_2 = manager.get_breakpoints(audio_id_2)
        assert len(breakpoints_2) == len(positions_2)
        
        bp_ids_2 = {bp.id for bp in breakpoints_2}
        for bp_id in ids_2:
            assert bp_id in bp_ids_2

    @given(audio_id=audio_id_strategy)
    @settings(max_examples=100)
    def test_clear_empty_audio_is_safe(self, audio_id: str):
        """
        属性测试：清除没有断点的音频应该是安全的（不抛出异常）
        """
        manager = BreakpointManager()
        
        # 清除不存在的音频断点（不应抛出异常）
        manager.clear_audio_breakpoints(audio_id)
        
        # 验证断点列表为空
        assert len(manager.get_breakpoints(audio_id)) == 0



class TestBreakpointStorageIndependence:
    """
    **Feature: multi-audio-player, Property 14: 断点存储独立性**
    
    *对于任意* 两个不同的音频，修改一个音频的断点不应影响另一个音频的断点列表
    **Validates: Requirements 5.6**
    """

    @given(
        audio_id_1=audio_id_strategy,
        audio_id_2=audio_id_strategy,
        position_1=position_strategy,
        position_2=position_strategy
    )
    @settings(max_examples=100)
    def test_add_breakpoint_to_one_audio_preserves_other(
        self, 
        audio_id_1: str, 
        audio_id_2: str, 
        position_1: float, 
        position_2: float
    ):
        """
        属性测试：向一个音频添加断点不影响另一个音频
        
        对于任意两个不同的音频：
        1. 为第一个音频保存断点
        2. 为第二个音频保存断点
        3. 两个音频的断点列表应相互独立
        """
        assume(audio_id_1 != audio_id_2)
        
        manager = BreakpointManager()
        
        # 为第一个音频保存断点
        bp_id_1 = manager.save_breakpoint(audio_id_1, position_1)
        
        # 验证第二个音频断点列表为空
        assert len(manager.get_breakpoints(audio_id_2)) == 0
        
        # 为第二个音频保存断点
        bp_id_2 = manager.save_breakpoint(audio_id_2, position_2)
        
        # 验证两个音频的断点列表相互独立
        breakpoints_1 = manager.get_breakpoints(audio_id_1)
        breakpoints_2 = manager.get_breakpoints(audio_id_2)
        
        assert len(breakpoints_1) == 1
        assert len(breakpoints_2) == 1
        assert breakpoints_1[0].id == bp_id_1
        assert breakpoints_2[0].id == bp_id_2
        assert breakpoints_1[0].audio_id == audio_id_1
        assert breakpoints_2[0].audio_id == audio_id_2

    @given(
        audio_id_1=audio_id_strategy,
        audio_id_2=audio_id_strategy,
        positions_1=st.lists(position_strategy, min_size=2, max_size=10),
        positions_2=st.lists(position_strategy, min_size=1, max_size=10)
    )
    @settings(max_examples=100)
    def test_delete_from_one_audio_preserves_other(
        self, 
        audio_id_1: str, 
        audio_id_2: str, 
        positions_1: list, 
        positions_2: list
    ):
        """
        属性测试：从一个音频删除断点不影响另一个音频
        
        对于任意两个不同的音频：
        1. 分别为两个音频保存断点
        2. 从第一个音频删除一个断点
        3. 第二个音频的断点列表应保持不变
        """
        assume(audio_id_1 != audio_id_2)
        
        manager = BreakpointManager()
        
        # 为两个音频保存断点
        ids_1 = []
        for pos in positions_1:
            bp_id = manager.save_breakpoint(audio_id_1, pos)
            ids_1.append(bp_id)
        
        ids_2 = []
        for pos in positions_2:
            bp_id = manager.save_breakpoint(audio_id_2, pos)
            ids_2.append(bp_id)
        
        # 记录第二个音频的断点状态
        original_breakpoints_2 = manager.get_breakpoints(audio_id_2)
        original_ids_2 = {bp.id for bp in original_breakpoints_2}
        
        # 从第一个音频删除断点
        manager.delete_breakpoint(audio_id_1, ids_1[0])
        
        # 验证第二个音频断点列表保持不变
        current_breakpoints_2 = manager.get_breakpoints(audio_id_2)
        current_ids_2 = {bp.id for bp in current_breakpoints_2}
        
        assert current_ids_2 == original_ids_2
        assert len(current_breakpoints_2) == len(positions_2)

    @given(
        audio_ids=st.lists(
            audio_id_strategy, 
            min_size=2, 
            max_size=5, 
            unique=True
        ),
        positions_per_audio=st.lists(
            st.lists(position_strategy, min_size=1, max_size=5),
            min_size=2,
            max_size=5
        )
    )
    @settings(max_examples=100)
    def test_multiple_audios_independent_storage(
        self, 
        audio_ids: list, 
        positions_per_audio: list
    ):
        """
        属性测试：多个音频的断点存储完全独立
        
        对于任意多个不同的音频：
        1. 为每个音频保存不同数量的断点
        2. 每个音频的断点列表应只包含该音频的断点
        3. 断点数量应与保存的数量一致
        """
        # 确保音频数量和位置列表数量匹配
        num_audios = min(len(audio_ids), len(positions_per_audio))
        assume(num_audios >= 2)
        
        manager = BreakpointManager()
        saved_ids = {}
        
        # 为每个音频保存断点
        for i in range(num_audios):
            audio_id = audio_ids[i]
            positions = positions_per_audio[i]
            saved_ids[audio_id] = []
            
            for pos in positions:
                bp_id = manager.save_breakpoint(audio_id, pos)
                saved_ids[audio_id].append(bp_id)
        
        # 验证每个音频的断点列表独立
        for i in range(num_audios):
            audio_id = audio_ids[i]
            expected_count = len(positions_per_audio[i])
            
            breakpoints = manager.get_breakpoints(audio_id)
            
            # 验证数量
            assert len(breakpoints) == expected_count
            
            # 验证所有断点都属于该音频
            for bp in breakpoints:
                assert bp.audio_id == audio_id
            
            # 验证所有保存的 ID 都存在
            bp_ids = {bp.id for bp in breakpoints}
            for saved_id in saved_ids[audio_id]:
                assert saved_id in bp_ids
