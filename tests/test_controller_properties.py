"""CoreController 属性测试

使用 hypothesis 进行属性测试，验证核心控制器的正确性属性。
"""
import asyncio
import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
import time
import threading

from src.core.controller import CoreController, PlayMode, EventType
from src.core.cue_manager import CueManager
from src.core.breakpoint_manager import BreakpointManager
from src.models.audio_track import AudioTrack
from src.models.cue import Cue


# ==================== 测试策略 ====================

@st.composite
def volume_strategy(draw):
    """生成有效的音量值"""
    return draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))


# ==================== Mock 音频引擎 ====================

class MockAudioEngine:
    """模拟音频引擎，用于测试"""
    
    def __init__(self):
        self._bgm_playing = False
        self._bgm_paused = False
        self._bgm_position = 0.0
        self._bgm_start_pos = 0.0
        self._bgm_volume = 1.0
        self._sfx_volume = 1.0
        self._current_bgm = None
        self._playing_sfx = {}
        self._on_bgm_end = None
        self._play_start_time = None
    
    def play_bgm(self, track: AudioTrack, start_pos: float = 0.0) -> None:
        self._bgm_playing = True
        self._bgm_paused = False
        self._bgm_start_pos = start_pos
        self._bgm_position = start_pos
        self._current_bgm = track
        self._play_start_time = time.time()
    
    def pause_bgm(self) -> None:
        if self._bgm_playing:
            self._bgm_paused = True
            if self._play_start_time:
                elapsed = time.time() - self._play_start_time
                self._bgm_position = self._bgm_start_pos + elapsed
    
    def resume_bgm(self) -> None:
        if self._bgm_paused:
            self._bgm_paused = False
            self._play_start_time = time.time()
            self._bgm_start_pos = self._bgm_position
    
    def stop_bgm(self) -> float:
        pos = self._bgm_position
        self._bgm_playing = False
        self._bgm_paused = False
        self._bgm_position = 0.0
        self._current_bgm = None
        return pos
    
    def get_bgm_position(self) -> float:
        return self._bgm_position
    
    def is_bgm_playing(self) -> bool:
        return self._bgm_playing and not self._bgm_paused
    
    def is_bgm_paused(self) -> bool:
        return self._bgm_paused
    
    def get_current_bgm(self):
        return self._current_bgm
    
    def play_sfx(self, sfx_id: str, track: AudioTrack) -> bool:
        self._playing_sfx[sfx_id] = track
        return True
    
    def stop_sfx(self, sfx_id: str) -> bool:
        if sfx_id in self._playing_sfx:
            del self._playing_sfx[sfx_id]
            return True
        return False
    
    def stop_all_sfx(self) -> None:
        self._playing_sfx.clear()
    
    def is_sfx_playing(self, sfx_id: str) -> bool:
        return sfx_id in self._playing_sfx
    
    def get_playing_sfx_ids(self):
        return list(self._playing_sfx.keys())
    
    def set_bgm_volume(self, volume: float) -> None:
        self._bgm_volume = max(0.0, min(1.0, volume))
    
    def get_bgm_volume(self) -> float:
        return self._bgm_volume
    
    def set_sfx_volume(self, volume: float) -> None:
        self._sfx_volume = max(0.0, min(1.0, volume))
    
    def get_sfx_volume(self) -> float:
        return self._sfx_volume
    
    def set_on_bgm_end(self, callback) -> None:
        self._on_bgm_end = callback
    
    def check_bgm_end(self) -> bool:
        return False
    
    def shutdown(self) -> None:
        pass
    
    def is_initialized(self) -> bool:
        return True


# ==================== 工厂函数 ====================

def create_controller():
    """创建新的控制器实例"""
    # 重置单例
    CoreController._instance = None
    
    mock_engine = MockAudioEngine()
    cue_manager = CueManager()
    breakpoint_manager = BreakpointManager()
    
    # 创建新实例
    ctrl = CoreController.__new__(CoreController)
    ctrl._initialized = False
    ctrl._audio_engine = mock_engine
    ctrl._cue_manager = cue_manager
    ctrl._breakpoint_manager = breakpoint_manager
    
    # 初始化状态
    ctrl._mode = PlayMode.AUTO
    ctrl._is_playing = False
    ctrl._is_paused = False
    ctrl._current_audio_id = None
    ctrl._current_position = 0.0
    ctrl._bgm_volume = 1.0
    ctrl._sfx_volume = 1.0
    ctrl._in_silence = False
    ctrl._silence_remaining = 0.0
    ctrl._silence_start_time = None
    ctrl._silence_duration = 0.0
    ctrl._manual_audio = None
    ctrl._manual_start_pos = 0.0
    ctrl._manual_silence_before = 0.0
    ctrl._operation_lock = threading.Lock()
    ctrl._local_priority = True
    ctrl._pending_remote_ops = []
    ctrl._listeners = {event_type: [] for event_type in EventType}
    ctrl._playback_start_time = None
    ctrl._playback_start_position = 0.0
    ctrl._initialized = True
    
    return ctrl


def run_async(coro):
    """运行异步函数"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ==================== Property 3: 暂停/继续位置保持 ====================

class TestPauseResumePositionProperty:
    """
    **Feature: multi-audio-player, Property 3: 暂停/继续位置保持**
    
    *对于任意* 播放状态，暂停后继续播放，播放位置应与暂停时的位置一致（允许 ±0.1 秒误差）
    **Validates: Requirements 2.2**
    """
    
    @given(
        position=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_pause_resume_preserves_position(self, position):
        """暂停后继续播放，位置应保持不变"""
        controller = create_controller()
        
        # 创建测试音频
        audio = AudioTrack(
            id="test_audio",
            file_path="/fake/path/test.mp3",
            duration=200.0,
            title="Test Audio",
            track_type="bgm"
        )
        
        # 设置手动模式并配置音频
        controller._mode = PlayMode.MANUAL
        controller._manual_audio = audio
        controller._manual_start_pos = position
        controller._manual_silence_before = 0.0
        
        # 开始播放
        run_async(controller.play())
        
        # 验证正在播放
        assert controller._is_playing
        assert not controller._is_paused
        
        # 暂停
        run_async(controller.pause())
        
        # 验证已暂停
        assert controller._is_paused
        
        # 记录暂停时位置
        pos_at_pause = controller._get_current_position()
        
        # 继续播放
        run_async(controller.resume())
        
        # 验证继续播放
        assert not controller._is_paused
        
        # 获取继续后的位置
        pos_after_resume = controller._get_current_position()
        
        # 验证位置保持（允许 ±0.1 秒误差）
        assert abs(pos_at_pause - pos_after_resume) <= 0.1, \
            f"Position changed after resume: {pos_at_pause} -> {pos_after_resume}"


# ==================== Property 4: 跳转后索引递增 ====================

class TestNextCueIndexProperty:
    """
    **Feature: multi-audio-player, Property 4: 跳转后索引递增**
    
    *对于任意* 自动模式播放状态，执行跳至下一段操作后，当前 Cue 索引应递增 1（除非已是最后一个）
    **Validates: Requirements 2.3**
    """
    
    @given(
        num_cues=st.integers(min_value=2, max_value=10),
        initial_index=st.integers(min_value=0, max_value=8)
    )
    @settings(max_examples=100)
    def test_next_cue_increments_index(self, num_cues, initial_index):
        """跳至下一段后，索引应递增 1"""
        # 确保初始索引有效
        assume(initial_index < num_cues - 1)  # 不是最后一个
        
        controller = create_controller()
        
        # 创建测试音频和 Cue
        audio = AudioTrack(
            id="test_audio",
            file_path="/fake/path/test.mp3",
            duration=100.0,
            title="Test Audio",
            track_type="bgm"
        )
        controller._cue_manager.add_audio_file(audio)
        
        for i in range(num_cues):
            cue = Cue(
                id=f"cue_{i}",
                audio_id="test_audio",
                start_time=0.0,
                end_time=10.0,
                silence_before=0.0,
                silence_after=0.0,
                volume=1.0,
                label=f"Cue {i}"
            )
            controller._cue_manager.add_cue(cue)
        
        # 设置初始索引
        controller._cue_manager.set_index(initial_index)
        controller._mode = PlayMode.AUTO
        
        # 记录当前索引
        index_before = controller._cue_manager.current_index
        
        # 执行跳至下一段
        run_async(controller.next_cue())
        
        # 验证索引递增
        index_after = controller._cue_manager.current_index
        assert index_after == index_before + 1, \
            f"Index should increment by 1: {index_before} -> {index_after}"
    
    @given(
        num_cues=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=100)
    def test_next_cue_at_last_does_not_exceed(self, num_cues):
        """在最后一个 Cue 时，跳至下一段不应超出范围"""
        controller = create_controller()
        
        # 创建测试音频和 Cue
        audio = AudioTrack(
            id="test_audio",
            file_path="/fake/path/test.mp3",
            duration=100.0,
            title="Test Audio",
            track_type="bgm"
        )
        controller._cue_manager.add_audio_file(audio)
        
        for i in range(num_cues):
            cue = Cue(
                id=f"cue_{i}",
                audio_id="test_audio",
                start_time=0.0,
                end_time=10.0,
                silence_before=0.0,
                silence_after=0.0,
                volume=1.0,
                label=f"Cue {i}"
            )
            controller._cue_manager.add_cue(cue)
        
        # 设置到最后一个
        controller._cue_manager.set_index(num_cues - 1)
        controller._mode = PlayMode.AUTO
        
        # 执行跳至下一段
        result = run_async(controller.next_cue())
        
        # 验证返回 False（没有下一个）
        assert result == False
        
        # 验证索引没有超出
        assert controller._cue_manager.current_index <= num_cues - 1


# ==================== Property 7: 音效切换状态 ====================

class TestSfxToggleProperty:
    """
    **Feature: multi-audio-player, Property 7: 音效切换状态**
    
    *对于任意* 正在播放的音效，再次触发该音效按钮后，该音效应停止播放
    **Validates: Requirements 3.2**
    """
    
    @given(
        sfx_id=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('L', 'N')))
    )
    @settings(max_examples=100)
    def test_toggle_sfx_stops_playing(self, sfx_id):
        """再次触发正在播放的音效应停止"""
        controller = create_controller()
        
        # 创建测试音效
        sfx = AudioTrack(
            id=sfx_id,
            file_path=f"/fake/path/{sfx_id}.mp3",
            duration=5.0,
            title="Test SFX",
            track_type="sfx"
        )
        
        # 第一次触发 - 开始播放
        result1 = controller.toggle_sfx(sfx_id, sfx)
        assert result1 == True  # 返回 True 表示正在播放
        assert controller.is_sfx_playing(sfx_id)
        
        # 第二次触发 - 停止播放
        result2 = controller.toggle_sfx(sfx_id, sfx)
        assert result2 == False  # 返回 False 表示已停止
        assert not controller.is_sfx_playing(sfx_id)
    
    @given(
        sfx_id=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('L', 'N')))
    )
    @settings(max_examples=100)
    def test_toggle_sfx_starts_when_not_playing(self, sfx_id):
        """触发未播放的音效应开始播放"""
        controller = create_controller()
        
        # 创建测试音效
        sfx = AudioTrack(
            id=sfx_id,
            file_path=f"/fake/path/{sfx_id}.mp3",
            duration=5.0,
            title="Test SFX",
            track_type="sfx"
        )
        
        # 确保未播放
        assert not controller.is_sfx_playing(sfx_id)
        
        # 触发 - 开始播放
        result = controller.toggle_sfx(sfx_id, sfx)
        assert result == True
        assert controller.is_sfx_playing(sfx_id)


# ==================== Property 8: BGM/音效独立播放 ====================

class TestBgmSfxIndependentProperty:
    """
    **Feature: multi-audio-player, Property 8: BGM/音效独立播放**
    
    *对于任意* BGM 播放状态，播放或停止音效不应改变 BGM 的播放状态和位置
    **Validates: Requirements 3.3, 3.4, 10.1, 10.5**
    """
    
    @given(
        bgm_position=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        sfx_id=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('L', 'N')))
    )
    @settings(max_examples=100)
    def test_sfx_play_does_not_affect_bgm(self, bgm_position, sfx_id):
        """播放音效不应影响 BGM 状态"""
        controller = create_controller()
        
        # 创建测试音频
        bgm = AudioTrack(
            id="test_bgm",
            file_path="/fake/path/bgm.mp3",
            duration=200.0,
            title="Test BGM",
            track_type="bgm"
        )
        sfx = AudioTrack(
            id=sfx_id,
            file_path=f"/fake/path/{sfx_id}.mp3",
            duration=5.0,
            title="Test SFX",
            track_type="sfx"
        )
        
        # 设置手动模式并播放 BGM
        controller._mode = PlayMode.MANUAL
        controller._manual_audio = bgm
        controller._manual_start_pos = bgm_position
        controller._manual_silence_before = 0.0
        run_async(controller.play())
        
        # 记录 BGM 状态
        bgm_playing_before = controller._is_playing
        bgm_paused_before = controller._is_paused
        bgm_audio_id_before = controller._current_audio_id
        
        # 播放音效
        controller.play_sfx(sfx_id, sfx)
        
        # 验证 BGM 状态未变
        assert controller._is_playing == bgm_playing_before
        assert controller._is_paused == bgm_paused_before
        assert controller._current_audio_id == bgm_audio_id_before
    
    @given(
        bgm_position=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        sfx_id=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('L', 'N')))
    )
    @settings(max_examples=100)
    def test_sfx_stop_does_not_affect_bgm(self, bgm_position, sfx_id):
        """停止音效不应影响 BGM 状态"""
        controller = create_controller()
        
        # 创建测试音频
        bgm = AudioTrack(
            id="test_bgm",
            file_path="/fake/path/bgm.mp3",
            duration=200.0,
            title="Test BGM",
            track_type="bgm"
        )
        sfx = AudioTrack(
            id=sfx_id,
            file_path=f"/fake/path/{sfx_id}.mp3",
            duration=5.0,
            title="Test SFX",
            track_type="sfx"
        )
        
        # 设置手动模式并播放 BGM
        controller._mode = PlayMode.MANUAL
        controller._manual_audio = bgm
        controller._manual_start_pos = bgm_position
        controller._manual_silence_before = 0.0
        run_async(controller.play())
        
        # 播放音效
        controller.play_sfx(sfx_id, sfx)
        
        # 记录 BGM 状态
        bgm_playing_before = controller._is_playing
        bgm_paused_before = controller._is_paused
        bgm_audio_id_before = controller._current_audio_id
        
        # 停止音效
        controller.stop_sfx(sfx_id)
        
        # 验证 BGM 状态未变
        assert controller._is_playing == bgm_playing_before
        assert controller._is_paused == bgm_paused_before
        assert controller._current_audio_id == bgm_audio_id_before


# ==================== Property 13: 重播位置归零 ====================

class TestReplayPositionProperty:
    """
    **Feature: multi-audio-player, Property 13: 重播位置归零**
    
    *对于任意* 音频，执行重播操作后，播放位置应为 0（或 Cue 的 start_time）
    **Validates: Requirements 5.5**
    """
    
    @given(
        initial_position=st.floats(min_value=10.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_replay_resets_position_manual_mode(self, initial_position):
        """手动模式重播后位置应归零"""
        controller = create_controller()
        
        # 创建测试音频
        audio = AudioTrack(
            id="test_audio",
            file_path="/fake/path/test.mp3",
            duration=200.0,
            title="Test Audio",
            track_type="bgm"
        )
        
        # 设置手动模式
        controller._mode = PlayMode.MANUAL
        controller._manual_audio = audio
        controller._manual_start_pos = initial_position
        controller._manual_silence_before = 0.0
        
        # 开始播放
        run_async(controller.play())
        
        # 验证初始位置
        assert controller._current_position == initial_position
        
        # 执行重播
        run_async(controller.replay())
        
        # 验证位置归零
        assert controller._current_position == 0.0
    
    @given(
        cue_start_time=st.floats(min_value=0.0, max_value=50.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_replay_resets_to_cue_start_auto_mode(self, cue_start_time):
        """自动模式重播后位置应回到 Cue 的 start_time"""
        controller = create_controller()
        
        # 创建测试音频和 Cue
        audio = AudioTrack(
            id="test_audio",
            file_path="/fake/path/test.mp3",
            duration=200.0,
            title="Test Audio",
            track_type="bgm"
        )
        cue = Cue(
            id="test_cue",
            audio_id="test_audio",
            start_time=cue_start_time,
            end_time=100.0,
            silence_before=0.0,
            silence_after=0.0,
            volume=1.0,
            label="Test Cue"
        )
        
        controller._cue_manager.add_audio_file(audio)
        controller._cue_manager.add_cue(cue)
        controller._mode = PlayMode.AUTO
        
        # 开始播放
        run_async(controller.play())
        
        # 模拟播放一段时间后
        controller._current_position = cue_start_time + 30.0
        
        # 执行重播
        run_async(controller.replay())
        
        # 验证位置回到 Cue 的 start_time
        assert controller._current_position == cue_start_time


# ==================== Property 15: 音量调节不中断播放 ====================

class TestVolumeAdjustmentProperty:
    """
    **Feature: multi-audio-player, Property 15: 音量调节不中断播放**
    
    *对于任意* 播放状态，调节音量后，播放状态（is_playing）应保持不变
    **Validates: Requirements 6.2**
    """
    
    @given(
        initial_volume=volume_strategy(),
        new_volume=volume_strategy()
    )
    @settings(max_examples=100)
    def test_bgm_volume_change_preserves_playback(self, initial_volume, new_volume):
        """调节 BGM 音量不应中断播放"""
        controller = create_controller()
        
        # 创建测试音频
        audio = AudioTrack(
            id="test_audio",
            file_path="/fake/path/test.mp3",
            duration=200.0,
            title="Test Audio",
            track_type="bgm"
        )
        
        # 设置手动模式并播放
        controller._mode = PlayMode.MANUAL
        controller._manual_audio = audio
        controller._manual_start_pos = 0.0
        controller._manual_silence_before = 0.0
        controller.set_bgm_volume(initial_volume)
        run_async(controller.play())
        
        # 记录播放状态
        is_playing_before = controller._is_playing
        is_paused_before = controller._is_paused
        
        # 调节音量
        controller.set_bgm_volume(new_volume)
        
        # 验证播放状态未变
        assert controller._is_playing == is_playing_before
        assert controller._is_paused == is_paused_before
    
    @given(
        initial_volume=volume_strategy(),
        new_volume=volume_strategy()
    )
    @settings(max_examples=100)
    def test_sfx_volume_change_preserves_playback(self, initial_volume, new_volume):
        """调节音效音量不应中断 BGM 播放"""
        controller = create_controller()
        
        # 创建测试音频
        audio = AudioTrack(
            id="test_audio",
            file_path="/fake/path/test.mp3",
            duration=200.0,
            title="Test Audio",
            track_type="bgm"
        )
        
        # 设置手动模式并播放
        controller._mode = PlayMode.MANUAL
        controller._manual_audio = audio
        controller._manual_start_pos = 0.0
        controller._manual_silence_before = 0.0
        controller.set_sfx_volume(initial_volume)
        run_async(controller.play())
        
        # 记录播放状态
        is_playing_before = controller._is_playing
        is_paused_before = controller._is_paused
        
        # 调节音效音量
        controller.set_sfx_volume(new_volume)
        
        # 验证播放状态未变
        assert controller._is_playing == is_playing_before
        assert controller._is_paused == is_paused_before


# ==================== Property 18: 模式切换位置保持 ====================

class TestModeSwitchPositionProperty:
    """
    **Feature: multi-audio-player, Property 18: 模式切换位置保持**
    
    *对于任意* 播放状态和当前位置，在自动/手动模式之间切换后，播放位置应保持不变
    **Validates: Requirements 7.1, 7.2**
    """
    
    @given(
        position=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_auto_to_manual_preserves_position(self, position):
        """从自动模式切换到手动模式，位置应保持"""
        controller = create_controller()
        
        # 创建测试音频和 Cue
        audio = AudioTrack(
            id="test_audio",
            file_path="/fake/path/test.mp3",
            duration=200.0,
            title="Test Audio",
            track_type="bgm"
        )
        cue = Cue(
            id="test_cue",
            audio_id="test_audio",
            start_time=0.0,
            end_time=150.0,
            silence_before=0.0,
            silence_after=0.0,
            volume=1.0,
            label="Test Cue"
        )
        
        controller._cue_manager.add_audio_file(audio)
        controller._cue_manager.add_cue(cue)
        controller._mode = PlayMode.AUTO
        
        # 开始播放
        run_async(controller.play())
        
        # 设置当前位置
        controller._current_position = position
        controller._playback_start_position = position
        controller._playback_start_time = time.time()
        
        # 记录位置
        pos_before = controller._get_current_position()
        
        # 切换到手动模式
        run_async(controller.switch_mode(PlayMode.MANUAL))
        
        # 验证模式已切换
        assert controller._mode == PlayMode.MANUAL
        
        # 验证位置保持（允许小误差）
        pos_after = controller._get_current_position()
        assert abs(pos_before - pos_after) <= 0.2, \
            f"Position changed after mode switch: {pos_before} -> {pos_after}"
    
    @given(
        position=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_manual_to_auto_preserves_position(self, position):
        """从手动模式切换到自动模式，位置应保持"""
        controller = create_controller()
        
        # 创建测试音频和 Cue
        audio = AudioTrack(
            id="test_audio",
            file_path="/fake/path/test.mp3",
            duration=200.0,
            title="Test Audio",
            track_type="bgm"
        )
        cue = Cue(
            id="test_cue",
            audio_id="test_audio",
            start_time=0.0,
            end_time=150.0,
            silence_before=0.0,
            silence_after=0.0,
            volume=1.0,
            label="Test Cue"
        )
        
        controller._cue_manager.add_audio_file(audio)
        controller._cue_manager.add_cue(cue)
        
        # 设置手动模式并播放
        controller._mode = PlayMode.MANUAL
        controller._manual_audio = audio
        controller._manual_start_pos = position
        controller._manual_silence_before = 0.0
        run_async(controller.play())
        
        # 设置当前位置
        controller._current_position = position
        controller._playback_start_position = position
        controller._playback_start_time = time.time()
        
        # 记录位置
        pos_before = controller._get_current_position()
        
        # 切换到自动模式
        run_async(controller.switch_mode(PlayMode.AUTO))
        
        # 验证模式已切换
        assert controller._mode == PlayMode.AUTO
        
        # 验证位置保持（允许小误差）
        pos_after = controller._get_current_position()
        assert abs(pos_before - pos_after) <= 0.2, \
            f"Position changed after mode switch: {pos_before} -> {pos_after}"


# ==================== Property 19: 模式切换状态同步 ====================

class TestModeSwitchStateSyncProperty:
    """
    **Feature: multi-audio-player, Property 19: 模式切换状态同步**
    
    *对于任意* 模式切换操作，切换完成后两种模式的播放状态应一致
    **Validates: Requirements 7.4**
    """
    
    @given(
        is_playing=st.booleans(),
        is_paused=st.booleans()
    )
    @settings(max_examples=100)
    def test_mode_switch_syncs_state(self, is_playing, is_paused):
        """模式切换后状态应同步"""
        # 排除无效状态组合
        assume(not (is_paused and not is_playing))  # 暂停必须在播放中
        
        controller = create_controller()
        
        # 创建测试音频和 Cue
        audio = AudioTrack(
            id="test_audio",
            file_path="/fake/path/test.mp3",
            duration=200.0,
            title="Test Audio",
            track_type="bgm"
        )
        cue = Cue(
            id="test_cue",
            audio_id="test_audio",
            start_time=0.0,
            end_time=150.0,
            silence_before=0.0,
            silence_after=0.0,
            volume=1.0,
            label="Test Cue"
        )
        
        controller._cue_manager.add_audio_file(audio)
        controller._cue_manager.add_cue(cue)
        
        # 设置初始状态
        controller._mode = PlayMode.AUTO
        controller._is_playing = is_playing
        controller._is_paused = is_paused
        controller._current_audio_id = "test_audio" if is_playing else None
        
        # 记录状态
        playing_before = controller._is_playing
        paused_before = controller._is_paused
        
        # 切换模式
        run_async(controller.switch_mode(PlayMode.MANUAL))
        
        # 验证状态同步
        assert controller._is_playing == playing_before
        assert controller._is_paused == paused_before


# ==================== Property 24: BGM 互斥与自动断点 ====================

class TestBgmMutexAutoBreakpointProperty:
    """
    **Feature: multi-audio-player, Property 24: BGM 互斥与自动断点**
    
    *对于任意* 正在播放的 BGM，播放新 BGM 后，旧 BGM 应停止且其播放位置应被保存为断点
    **Validates: Requirements 10.2, 10.3**
    """
    
    @given(
        old_position=st.floats(min_value=1.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        new_position=st.floats(min_value=0.0, max_value=50.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_new_bgm_stops_old_and_saves_breakpoint(self, old_position, new_position):
        """播放新 BGM 时，旧 BGM 应停止并保存断点"""
        controller = create_controller()
        
        # 创建测试音频
        old_bgm = AudioTrack(
            id="old_bgm",
            file_path="/fake/path/old.mp3",
            duration=200.0,
            title="Old BGM",
            track_type="bgm"
        )
        new_bgm = AudioTrack(
            id="new_bgm",
            file_path="/fake/path/new.mp3",
            duration=200.0,
            title="New BGM",
            track_type="bgm"
        )
        
        # 设置手动模式并播放旧 BGM
        controller._mode = PlayMode.MANUAL
        controller._manual_audio = old_bgm
        controller._manual_start_pos = old_position
        controller._manual_silence_before = 0.0
        run_async(controller.play())
        
        # 设置当前位置
        controller._current_position = old_position
        controller._playback_start_position = old_position
        controller._playback_start_time = time.time()
        
        # 验证旧 BGM 正在播放
        assert controller._is_playing
        assert controller._current_audio_id == "old_bgm"
        
        # 记录旧 BGM 断点数量
        old_breakpoints_count = len(controller._breakpoint_manager.get_breakpoints("old_bgm"))
        
        # 播放新 BGM
        run_async(controller.play_new_bgm(new_bgm, new_position))
        
        # 验证新 BGM 正在播放
        assert controller._is_playing
        assert controller._current_audio_id == "new_bgm"
        
        # 验证旧 BGM 断点已保存
        new_breakpoints_count = len(controller._breakpoint_manager.get_breakpoints("old_bgm"))
        assert new_breakpoints_count == old_breakpoints_count + 1, \
            "Breakpoint should be saved for old BGM"
        
        # 验证断点位置
        breakpoints = controller._breakpoint_manager.get_breakpoints("old_bgm")
        latest_bp = breakpoints[-1]
        assert abs(latest_bp.position - old_position) <= 0.2, \
            f"Breakpoint position should match: expected ~{old_position}, got {latest_bp.position}"
        assert latest_bp.auto_saved == True, "Breakpoint should be marked as auto-saved"
    
    @given(
        position=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_new_bgm_when_not_playing_no_breakpoint(self, position):
        """未播放时播放新 BGM 不应创建断点"""
        controller = create_controller()
        
        # 创建测试音频
        new_bgm = AudioTrack(
            id="new_bgm",
            file_path="/fake/path/new.mp3",
            duration=200.0,
            title="New BGM",
            track_type="bgm"
        )
        
        # 确保未播放
        assert not controller._is_playing
        
        # 记录断点数量
        all_breakpoints_before = sum(
            len(bps) for bps in controller._breakpoint_manager.breakpoints.values()
        )
        
        # 播放新 BGM
        run_async(controller.play_new_bgm(new_bgm, position))
        
        # 验证新 BGM 正在播放
        assert controller._is_playing
        
        # 验证没有创建新断点
        all_breakpoints_after = sum(
            len(bps) for bps in controller._breakpoint_manager.breakpoints.values()
        )
        assert all_breakpoints_after == all_breakpoints_before, \
            "No breakpoint should be created when not playing"


# ==================== Property 11: 断点恢复位置 ====================

class TestBreakpointRestorePositionProperty:
    """
    **Feature: multi-audio-player, Property 11: 断点恢复位置**
    
    *对于任意* 已保存的断点，选择该断点恢复播放后，播放位置应等于断点记录的位置
    **Validates: Requirements 5.2, 10.4**
    """
    
    @given(
        breakpoint_position=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_restore_breakpoint_sets_correct_position(self, breakpoint_position):
        """从断点恢复播放后，播放位置应等于断点记录的位置"""
        controller = create_controller()
        
        # 创建测试音频
        audio = AudioTrack(
            id="test_audio",
            file_path="/fake/path/test.mp3",
            duration=200.0,
            title="Test Audio",
            track_type="bgm"
        )
        
        # 将音频添加到 cue_manager 以便 restore_breakpoint 能找到它
        controller._cue_manager.add_audio_file(audio)
        
        # 保存一个断点
        bp_id = controller._breakpoint_manager.save_breakpoint(
            audio_id="test_audio",
            position=breakpoint_position,
            label="Test Breakpoint"
        )
        
        # 从断点恢复播放
        result = run_async(controller.restore_breakpoint("test_audio", bp_id))
        
        # 验证恢复成功
        assert result == True, "restore_breakpoint should return True"
        
        # 验证正在播放
        assert controller._is_playing, "Should be playing after restore"
        assert not controller._is_paused, "Should not be paused after restore"
        
        # 验证播放位置等于断点位置
        current_pos = controller._get_current_position()
        assert abs(current_pos - breakpoint_position) <= 0.1, \
            f"Position should match breakpoint: expected {breakpoint_position}, got {current_pos}"
        
        # 验证当前音频 ID
        assert controller._current_audio_id == "test_audio", \
            "Current audio ID should match the breakpoint's audio"
    
    @given(
        bp_position=st.floats(min_value=1.0, max_value=50.0, allow_nan=False, allow_infinity=False),
        current_position=st.floats(min_value=10.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_restore_breakpoint_while_playing_saves_current_position(self, bp_position, current_position):
        """在播放中恢复断点时，应保存当前播放位置为断点"""
        controller = create_controller()
        
        # 创建两个测试音频
        audio1 = AudioTrack(
            id="audio_1",
            file_path="/fake/path/audio1.mp3",
            duration=200.0,
            title="Audio 1",
            track_type="bgm"
        )
        audio2 = AudioTrack(
            id="audio_2",
            file_path="/fake/path/audio2.mp3",
            duration=200.0,
            title="Audio 2",
            track_type="bgm"
        )
        
        # 将音频添加到 cue_manager
        controller._cue_manager.add_audio_file(audio1)
        controller._cue_manager.add_audio_file(audio2)
        
        # 设置手动模式并播放 audio1
        controller._mode = PlayMode.MANUAL
        controller._manual_audio = audio1
        controller._manual_start_pos = current_position
        controller._manual_silence_before = 0.0
        run_async(controller.play())
        
        # 设置当前位置
        controller._current_position = current_position
        controller._playback_start_position = current_position
        controller._playback_start_time = time.time()
        
        # 记录 audio1 的断点数量
        audio1_bp_count_before = len(controller._breakpoint_manager.get_breakpoints("audio_1"))
        
        # 为 audio2 保存一个断点
        bp_id = controller._breakpoint_manager.save_breakpoint(
            audio_id="audio_2",
            position=bp_position,
            label="Test Breakpoint"
        )
        
        # 从 audio2 的断点恢复播放
        result = run_async(controller.restore_breakpoint("audio_2", bp_id))
        
        # 验证恢复成功
        assert result == True
        
        # 验证 audio1 的断点被自动保存
        audio1_bp_count_after = len(controller._breakpoint_manager.get_breakpoints("audio_1"))
        assert audio1_bp_count_after == audio1_bp_count_before + 1, \
            "A breakpoint should be auto-saved for the interrupted audio"
        
        # 验证当前播放的是 audio2
        assert controller._current_audio_id == "audio_2"
        
        # 验证播放位置等于断点位置
        current_pos = controller._get_current_position()
        assert abs(current_pos - bp_position) <= 0.1, \
            f"Position should match breakpoint: expected {bp_position}, got {current_pos}"
    
    @given(
        bp_position=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_restore_nonexistent_breakpoint_fails(self, bp_position):
        """恢复不存在的断点应返回 False"""
        controller = create_controller()
        
        # 创建测试音频
        audio = AudioTrack(
            id="test_audio",
            file_path="/fake/path/test.mp3",
            duration=200.0,
            title="Test Audio",
            track_type="bgm"
        )
        controller._cue_manager.add_audio_file(audio)
        
        # 尝试恢复不存在的断点
        result = run_async(controller.restore_breakpoint("test_audio", "nonexistent_bp_id"))
        
        # 验证返回 False
        assert result == False, "Should return False for nonexistent breakpoint"
    
    @given(
        bp_position=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_restore_breakpoint_for_nonexistent_audio_fails(self, bp_position):
        """恢复不存在音频的断点应返回 False"""
        controller = create_controller()
        
        # 保存一个断点（但不添加对应的音频到 cue_manager）
        bp_id = controller._breakpoint_manager.save_breakpoint(
            audio_id="nonexistent_audio",
            position=bp_position,
            label="Test Breakpoint"
        )
        
        # 尝试恢复断点
        result = run_async(controller.restore_breakpoint("nonexistent_audio", bp_id))
        
        # 验证返回 False（因为音频不存在）
        assert result == False, "Should return False when audio doesn't exist"
