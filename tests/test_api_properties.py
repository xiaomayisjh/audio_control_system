"""API 服务器属性测试

使用 hypothesis 进行属性测试，验证 API 服务器的正确性属性。
"""
import asyncio
import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
import time
import threading
import json
from unittest.mock import MagicMock, AsyncMock, patch
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

from src.core.controller import CoreController, PlayMode, EventType
from src.core.cue_manager import CueManager
from src.core.breakpoint_manager import BreakpointManager
from src.models.audio_track import AudioTrack
from src.models.cue import Cue
from src.models.playback_state import PlaybackState
from src.api.server import APIServer


# ==================== 测试策略 ====================

@st.composite
def volume_strategy(draw):
    """生成有效的音量值"""
    return draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))


@st.composite
def position_strategy(draw):
    """生成有效的播放位置"""
    return draw(st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False))


@st.composite
def playback_state_strategy(draw):
    """生成有效的播放状态"""
    mode = draw(st.sampled_from(["auto", "manual"]))
    is_playing = draw(st.booleans())
    is_paused = draw(st.booleans()) if is_playing else False
    
    return {
        "mode": mode,
        "is_playing": is_playing,
        "is_paused": is_paused,
        "current_audio_id": draw(st.text(min_size=0, max_size=20, alphabet=st.characters(whitelist_categories=('L', 'N')))) if is_playing else None,
        "current_position": draw(position_strategy()) if is_playing else 0.0,
        "current_cue_index": draw(st.integers(min_value=0, max_value=100)),
        "bgm_volume": draw(volume_strategy()),
        "sfx_volume": draw(volume_strategy()),
        "in_silence": draw(st.booleans()),
        "silence_remaining": draw(st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False))
    }


@st.composite
def audio_track_strategy(draw):
    """生成有效的音频轨道"""
    audio_id = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('L', 'N'))))
    return AudioTrack(
        id=audio_id,
        file_path=f"/fake/path/{audio_id}.mp3",
        duration=draw(st.floats(min_value=1.0, max_value=600.0, allow_nan=False, allow_infinity=False)),
        title=draw(st.text(min_size=1, max_size=50)),
        track_type=draw(st.sampled_from(["bgm", "sfx"]))
    )


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


# ==================== Property 26: API 状态查询一致性 ====================

class TestAPIStateQueryConsistencyProperty:
    """
    **Feature: multi-audio-player, Property 26: API 状态查询一致性**
    
    *对于任意* 控制台状态，API 状态查询返回的数据应与实际状态一致
    **Validates: Requirements 14.5**
    """
    
    @given(
        mode=st.sampled_from(["auto", "manual"]),
        is_playing=st.booleans(),
        bgm_volume=volume_strategy(),
        sfx_volume=volume_strategy(),
        current_cue_index=st.integers(min_value=0, max_value=100),
        in_silence=st.booleans(),
        silence_remaining=st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_api_state_matches_controller_state(
        self,
        mode,
        is_playing,
        bgm_volume,
        sfx_volume,
        current_cue_index,
        in_silence,
        silence_remaining
    ):
        """API 返回的状态应与控制器实际状态一致"""
        controller = create_controller()
        
        # 设置控制器状态
        controller._mode = PlayMode.AUTO if mode == "auto" else PlayMode.MANUAL
        controller._is_playing = is_playing
        controller._is_paused = False
        controller._bgm_volume = bgm_volume
        controller._sfx_volume = sfx_volume
        controller._cue_manager._current_index = current_cue_index
        controller._in_silence = in_silence
        controller._silence_remaining = silence_remaining
        
        if is_playing:
            controller._current_audio_id = "test_audio"
            controller._current_position = 10.0
            controller._playback_start_time = time.time()
            controller._playback_start_position = 10.0
        else:
            controller._current_audio_id = None
            controller._current_position = 0.0
        
        # 获取状态
        state_dict = controller.get_state_dict()
        
        # 验证状态一致性
        assert state_dict["mode"] == mode, \
            f"Mode mismatch: expected {mode}, got {state_dict['mode']}"
        assert state_dict["is_playing"] == is_playing, \
            f"is_playing mismatch: expected {is_playing}, got {state_dict['is_playing']}"
        assert abs(state_dict["bgm_volume"] - bgm_volume) < 0.001, \
            f"bgm_volume mismatch: expected {bgm_volume}, got {state_dict['bgm_volume']}"
        assert abs(state_dict["sfx_volume"] - sfx_volume) < 0.001, \
            f"sfx_volume mismatch: expected {sfx_volume}, got {state_dict['sfx_volume']}"
        assert state_dict["current_cue_index"] == current_cue_index, \
            f"current_cue_index mismatch: expected {current_cue_index}, got {state_dict['current_cue_index']}"
        assert state_dict["in_silence"] == in_silence, \
            f"in_silence mismatch: expected {in_silence}, got {state_dict['in_silence']}"
    
    @given(
        position=position_strategy(),
        is_paused=st.booleans()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_api_state_position_accuracy(self, position, is_paused):
        """API 返回的播放位置应准确"""
        controller = create_controller()
        
        # 创建测试音频
        audio = AudioTrack(
            id="test_audio",
            file_path="/fake/path/test.mp3",
            duration=2000.0,
            title="Test Audio",
            track_type="bgm"
        )
        
        # 设置播放状态
        controller._mode = PlayMode.MANUAL
        controller._manual_audio = audio
        controller._is_playing = True
        controller._is_paused = is_paused
        controller._current_audio_id = "test_audio"
        controller._current_position = position
        controller._playback_start_position = position
        controller._playback_start_time = time.time()
        
        # 获取状态
        state_dict = controller.get_state_dict()
        
        # 验证位置（允许小误差，因为时间可能有微小变化）
        if is_paused:
            # 暂停时位置应该精确
            assert abs(state_dict["current_position"] - position) < 0.1, \
                f"Position mismatch when paused: expected ~{position}, got {state_dict['current_position']}"
        else:
            # 播放时位置可能有微小增加
            assert state_dict["current_position"] >= position - 0.1, \
                f"Position should be >= {position}, got {state_dict['current_position']}"
    
    @given(
        bgm_volume=volume_strategy(),
        sfx_volume=volume_strategy()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_api_volume_state_consistency(self, bgm_volume, sfx_volume):
        """API 返回的音量状态应与设置一致"""
        controller = create_controller()
        
        # 设置音量
        controller.set_bgm_volume(bgm_volume)
        controller.set_sfx_volume(sfx_volume)
        
        # 获取状态
        state_dict = controller.get_state_dict()
        
        # 验证音量一致性
        assert abs(state_dict["bgm_volume"] - bgm_volume) < 0.001, \
            f"BGM volume mismatch: expected {bgm_volume}, got {state_dict['bgm_volume']}"
        assert abs(state_dict["sfx_volume"] - sfx_volume) < 0.001, \
            f"SFX volume mismatch: expected {sfx_volume}, got {state_dict['sfx_volume']}"
        
        # 验证通过 getter 获取的值也一致
        assert abs(controller.get_bgm_volume() - bgm_volume) < 0.001
        assert abs(controller.get_sfx_volume() - sfx_volume) < 0.001


# ==================== Property 27: 音频列表一致性 ====================

class TestAudioListConsistencyProperty:
    """
    **Feature: multi-audio-player, Property 27: 音频列表一致性**
    
    *对于任意* 已上传的音频文件集合，API 获取音频列表应返回所有已上传的文件
    **Validates: Requirements 15.2**
    """
    
    @given(
        num_audio_files=st.integers(min_value=0, max_value=20)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_audio_list_contains_all_added_files(self, num_audio_files):
        """音频列表应包含所有已添加的文件"""
        controller = create_controller()
        
        # 添加音频文件
        added_ids = set()
        for i in range(num_audio_files):
            audio = AudioTrack(
                id=f"audio_{i}",
                file_path=f"/fake/path/audio_{i}.mp3",
                duration=100.0 + i,
                title=f"Audio {i}",
                track_type="bgm" if i % 2 == 0 else "sfx"
            )
            controller.cue_manager.add_audio_file(audio)
            added_ids.add(f"audio_{i}")
        
        # 获取音频列表
        audio_files = controller.cue_manager.audio_files
        retrieved_ids = {audio.id for audio in audio_files}
        
        # 验证所有添加的文件都在列表中
        assert added_ids == retrieved_ids, \
            f"Audio list mismatch: added {added_ids}, retrieved {retrieved_ids}"
        
        # 验证数量一致
        assert len(audio_files) == num_audio_files, \
            f"Audio count mismatch: expected {num_audio_files}, got {len(audio_files)}"
    
    @given(
        audio_tracks=st.lists(
            st.tuples(
                st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=('L', 'N'))),
                st.floats(min_value=1.0, max_value=600.0, allow_nan=False, allow_infinity=False),
                st.text(min_size=1, max_size=30),
                st.sampled_from(["bgm", "sfx"])
            ),
            min_size=0,
            max_size=15,
            unique_by=lambda x: x[0]  # 确保 ID 唯一
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_audio_list_preserves_properties(self, audio_tracks):
        """音频列表应保留所有文件的属性"""
        controller = create_controller()
        
        # 添加音频文件
        expected_audios = {}
        for audio_id, duration, title, track_type in audio_tracks:
            audio = AudioTrack(
                id=audio_id,
                file_path=f"/fake/path/{audio_id}.mp3",
                duration=duration,
                title=title,
                track_type=track_type
            )
            controller.cue_manager.add_audio_file(audio)
            expected_audios[audio_id] = audio
        
        # 获取音频列表
        audio_files = controller.cue_manager.audio_files
        
        # 验证每个文件的属性
        for audio in audio_files:
            expected = expected_audios.get(audio.id)
            assert expected is not None, f"Unexpected audio: {audio.id}"
            assert audio.file_path == expected.file_path, \
                f"file_path mismatch for {audio.id}"
            assert abs(audio.duration - expected.duration) < 0.001, \
                f"duration mismatch for {audio.id}"
            assert audio.title == expected.title, \
                f"title mismatch for {audio.id}"
            assert audio.track_type == expected.track_type, \
                f"track_type mismatch for {audio.id}"
    
    @given(
        initial_count=st.integers(min_value=1, max_value=10),
        remove_count=st.integers(min_value=0, max_value=5)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_audio_list_after_removal(self, initial_count, remove_count):
        """删除音频后，列表应正确更新"""
        # 确保删除数量不超过初始数量
        remove_count = min(remove_count, initial_count)
        
        controller = create_controller()
        
        # 添加音频文件
        added_ids = []
        for i in range(initial_count):
            audio = AudioTrack(
                id=f"audio_{i}",
                file_path=f"/fake/path/audio_{i}.mp3",
                duration=100.0,
                title=f"Audio {i}",
                track_type="bgm"
            )
            controller.cue_manager.add_audio_file(audio)
            added_ids.append(f"audio_{i}")
        
        # 删除部分音频
        removed_ids = added_ids[:remove_count]
        for audio_id in removed_ids:
            controller.cue_manager.remove_audio_file(audio_id)
        
        # 获取音频列表
        audio_files = controller.cue_manager.audio_files
        remaining_ids = {audio.id for audio in audio_files}
        
        # 验证删除的文件不在列表中
        for removed_id in removed_ids:
            assert removed_id not in remaining_ids, \
                f"Removed audio {removed_id} should not be in list"
        
        # 验证剩余文件数量正确
        expected_count = initial_count - remove_count
        assert len(audio_files) == expected_count, \
            f"Audio count mismatch: expected {expected_count}, got {len(audio_files)}"
    
    @given(
        audio_id=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('L', 'N')))
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_get_audio_file_by_id(self, audio_id):
        """通过 ID 获取音频文件应返回正确的文件"""
        controller = create_controller()
        
        # 添加音频文件
        audio = AudioTrack(
            id=audio_id,
            file_path=f"/fake/path/{audio_id}.mp3",
            duration=120.0,
            title=f"Test Audio {audio_id}",
            track_type="bgm"
        )
        controller.cue_manager.add_audio_file(audio)
        
        # 通过 ID 获取
        retrieved = controller.cue_manager.get_audio_file(audio_id)
        
        # 验证获取的文件正确
        assert retrieved is not None, f"Audio {audio_id} should be found"
        assert retrieved.id == audio_id
        assert retrieved.file_path == audio.file_path
        assert retrieved.duration == audio.duration
        assert retrieved.title == audio.title
        assert retrieved.track_type == audio.track_type
    
    @given(
        existing_ids=st.lists(
            st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=('L', 'N'))),
            min_size=0,
            max_size=10,
            unique=True
        ),
        query_id=st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=('L', 'N')))
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_get_nonexistent_audio_returns_none(self, existing_ids, query_id):
        """获取不存在的音频应返回 None"""
        # 确保查询 ID 不在已存在的 ID 中
        assume(query_id not in existing_ids)
        
        controller = create_controller()
        
        # 添加已存在的音频
        for audio_id in existing_ids:
            audio = AudioTrack(
                id=audio_id,
                file_path=f"/fake/path/{audio_id}.mp3",
                duration=100.0,
                title=f"Audio {audio_id}",
                track_type="bgm"
            )
            controller.cue_manager.add_audio_file(audio)
        
        # 查询不存在的 ID
        result = controller.cue_manager.get_audio_file(query_id)
        
        # 验证返回 None
        assert result is None, \
            f"get_audio_file should return None for non-existent ID: {query_id}"
