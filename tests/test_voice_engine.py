"""Voice Engine Abstraction Layer testleri.

python-vlc tamamen mock'lanir — CI/CD'de VLC kurulu olmayabilir.
asyncio_mode = auto (pytest.ini) — async testler otomatik calisir.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers: VLC mock factory
# ---------------------------------------------------------------------------
def _make_vlc_mock():
    """python-vlc modulu icin mock olusturur."""
    vlc = MagicMock()

    instance = MagicMock()
    player = MagicMock()

    vlc.Instance.return_value = instance
    instance.media_player_new.return_value = player

    player.is_playing.return_value = False
    player.audio_set_volume.return_value = 0  # VLC returns 0 on success

    return vlc, instance, player


def _create_backend(vlc_mock=None):
    """LibVLCBackend olusturur, vlc modulu mock ile."""
    if vlc_mock is None:
        vlc_mock, _, _ = _make_vlc_mock()

    with patch.dict("sys.modules", {"vlc": vlc_mock}):
        from agent.voice_engine import LibVLCBackend

        return LibVLCBackend()


def _same_bound_method(left, right) -> bool:
    return (
        getattr(left, "__self__", None) is getattr(right, "__self__", None)
        and getattr(left, "__func__", None) is getattr(right, "__func__", None)
    )


# ---------------------------------------------------------------------------
# 1. ABC Tests
# ---------------------------------------------------------------------------
class TestVoiceEngineABC:
    def test_abc_not_instantiable(self):
        from agent.voice_engine import VoiceEngine

        with pytest.raises(TypeError):
            VoiceEngine()


# ---------------------------------------------------------------------------
# 2. LibVLCBackend Tests
# ---------------------------------------------------------------------------
class TestLibVLCBackend:
    # -- play -------------------------------------------------------------

    async def test_libvlc_play_success(self, tmp_path):
        vlc_mock, instance, player = _make_vlc_mock()
        media = MagicMock()
        instance.media_new.return_value = media

        backend = _create_backend(vlc_mock)

        test_file = tmp_path / "test.mp3"
        test_file.write_bytes(b"\x00" * 100)

        await backend.play(str(test_file))

        instance.media_new.assert_called_once_with(str(test_file))
        player.set_media.assert_called_once_with(media)
        player.play.assert_called_once()
        media.release.assert_called_once()

    async def test_libvlc_play_missing_file(self):
        backend = _create_backend()

        with pytest.raises(FileNotFoundError):
            await backend.play("/nonexistent/file.mp3")

    async def test_libvlc_play_media_none(self, tmp_path):
        """Guard 4: media_new() None donerse crash olmaz, log + return."""
        vlc_mock, instance, player = _make_vlc_mock()
        instance.media_new.return_value = None

        backend = _create_backend(vlc_mock)

        test_file = tmp_path / "bad.mp3"
        test_file.write_bytes(b"\x00" * 100)

        # Crash olmamali, sessiz hata
        await backend.play(str(test_file))

        # set_media ve play cagrilmamali
        player.set_media.assert_not_called()
        player.play.assert_not_called()

    async def test_libvlc_play_uses_to_thread(self, tmp_path):
        vlc_mock, instance, player = _make_vlc_mock()
        media = MagicMock()
        instance.media_new.return_value = media
        backend = _create_backend(vlc_mock)

        test_file = tmp_path / "threaded.mp3"
        test_file.write_bytes(b"\x00" * 100)

        async def passthrough(func, *args, **kwargs):
            return func(*args, **kwargs)

        with patch(
            "agent.voice_engine.asyncio.to_thread",
            new_callable=AsyncMock,
        ) as mock_to_thread:
            mock_to_thread.side_effect = passthrough
            await backend.play(str(test_file))

        called_funcs = [call.args[0] for call in mock_to_thread.call_args_list]
        assert os.path.isfile in called_funcs
        assert any(
            _same_bound_method(func, backend._play_sync)
            for func in called_funcs
        )
        player.play.assert_called_once()

    # -- pause / resume ---------------------------------------------------

    async def test_libvlc_pause(self):
        vlc_mock, _, player = _make_vlc_mock()
        player.is_playing.return_value = True

        backend = _create_backend(vlc_mock)
        await backend.pause()

        player.pause.assert_called_once()

    async def test_libvlc_pause_uses_to_thread(self):
        vlc_mock, _, _ = _make_vlc_mock()
        backend = _create_backend(vlc_mock)

        with patch(
            "agent.voice_engine.asyncio.to_thread",
            new_callable=AsyncMock,
        ) as mock_to_thread:
            await backend.pause()

        mock_to_thread.assert_called_once_with(backend._pause_sync)

    async def test_libvlc_pause_when_not_playing(self):
        vlc_mock, _, player = _make_vlc_mock()
        player.is_playing.return_value = False

        backend = _create_backend(vlc_mock)
        await backend.pause()

        player.pause.assert_not_called()

    async def test_libvlc_resume(self):
        vlc_mock, _, player = _make_vlc_mock()
        player.is_playing.return_value = False  # Paused state

        backend = _create_backend(vlc_mock)
        await backend.resume()

        player.pause.assert_called_once()  # Toggle to resume

    async def test_libvlc_resume_uses_to_thread(self):
        vlc_mock, _, _ = _make_vlc_mock()
        backend = _create_backend(vlc_mock)

        with patch(
            "agent.voice_engine.asyncio.to_thread",
            new_callable=AsyncMock,
        ) as mock_to_thread:
            await backend.resume()

        mock_to_thread.assert_called_once_with(backend._resume_sync)

    # -- stop -------------------------------------------------------------

    async def test_libvlc_stop(self):
        vlc_mock, _, player = _make_vlc_mock()

        backend = _create_backend(vlc_mock)
        await backend.stop()

        player.stop.assert_called_once()

    async def test_libvlc_stop_uses_to_thread(self):
        vlc_mock, _, _ = _make_vlc_mock()
        backend = _create_backend(vlc_mock)

        with patch(
            "agent.voice_engine.asyncio.to_thread",
            new_callable=AsyncMock,
        ) as mock_to_thread:
            await backend.stop()

        mock_to_thread.assert_called_once_with(backend._stop_sync)

    # -- set_volume -------------------------------------------------------

    async def test_libvlc_set_volume_clamp(self):
        vlc_mock, _, player = _make_vlc_mock()
        backend = _create_backend(vlc_mock)

        # Patch out hardware volume for isolation
        with patch.object(backend, "_set_hardware_volume"):
            await backend.set_volume(-5)
            player.audio_set_volume.assert_called_with(0)

            await backend.set_volume(150)
            player.audio_set_volume.assert_called_with(100)

            await backend.set_volume(50)
            player.audio_set_volume.assert_called_with(50)

    @patch("agent.voice_engine.platform")
    async def test_libvlc_set_volume_hw_linux(self, mock_platform):
        """Linux'ta ALSA hardware volume cagrilir, calibration dogrulugu."""
        mock_platform.system.return_value = "Linux"

        vlc_mock, _, player = _make_vlc_mock()
        backend = _create_backend(vlc_mock)

        with patch.object(backend, "_set_hardware_volume") as mock_hw:
            with patch("agent.voice_engine.agent_settings") as mock_settings:
                mock_settings.ENABLE_HW_VOLUME = True
                await backend.set_volume(50)

            mock_hw.assert_called_once_with(50)

    @patch("agent.voice_engine.platform")
    async def test_libvlc_set_volume_hw_skip_macos(self, mock_platform):
        """macOS'ta ALSA hardware volume cagrilmaz."""
        mock_platform.system.return_value = "Darwin"

        vlc_mock, _, player = _make_vlc_mock()
        backend = _create_backend(vlc_mock)

        with patch.object(backend, "_set_hardware_volume") as mock_hw:
            await backend.set_volume(50)

        mock_hw.assert_not_called()

    @patch("agent.voice_engine.platform")
    async def test_libvlc_set_volume_hw_uses_to_thread(self, mock_platform):
        """Guard 1: amixer asyncio.to_thread ile cagrilir."""
        mock_platform.system.return_value = "Linux"

        vlc_mock, _, _ = _make_vlc_mock()
        backend = _create_backend(vlc_mock)

        with patch("agent.voice_engine.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            with patch("agent.voice_engine.agent_settings") as mock_settings:
                mock_settings.ENABLE_HW_VOLUME = True
                await backend.set_volume(70)

            assert mock_to_thread.call_count == 2
            called_funcs = [call.args[0] for call in mock_to_thread.call_args_list]
            assert any(
                _same_bound_method(func, backend._set_volume_sync)
                for func in called_funcs
            )
            assert any(
                _same_bound_method(func, backend._set_hardware_volume)
                for func in called_funcs
            )

    # -- close ------------------------------------------------------------

    async def test_libvlc_close(self):
        vlc_mock, instance, player = _make_vlc_mock()

        backend = _create_backend(vlc_mock)
        await backend.close()

        player.stop.assert_called_once()
        player.release.assert_called_once()
        instance.release.assert_called_once()

    async def test_libvlc_close_uses_to_thread(self):
        vlc_mock, _, _ = _make_vlc_mock()
        backend = _create_backend(vlc_mock)

        with patch(
            "agent.voice_engine.asyncio.to_thread",
            new_callable=AsyncMock,
        ) as mock_to_thread:
            await backend.close()

        mock_to_thread.assert_called_once_with(backend._close_sync)

    async def test_libvlc_close_idempotent(self):
        vlc_mock, instance, player = _make_vlc_mock()

        backend = _create_backend(vlc_mock)
        await backend.close()
        await backend.close()  # Ikinci cagri hata vermemeli

        # release sadece 1 kez cagrilmali
        assert player.release.call_count == 1
        assert instance.release.call_count == 1

    async def test_libvlc_operation_after_close_raises(self):
        backend = _create_backend()
        await backend.close()

        with pytest.raises(RuntimeError, match="Voice engine kapatildi"):
            await backend.stop()

    # -- init guard -------------------------------------------------------

    def test_libvlc_init_instance_none(self):
        """Guard 4: Instance() None donerse RuntimeError."""
        vlc_mock = MagicMock()
        vlc_mock.Instance.return_value = None

        with patch.dict("sys.modules", {"vlc": vlc_mock}):
            from agent.voice_engine import LibVLCBackend

            with pytest.raises(RuntimeError, match="VLC baslatilamadi"):
                LibVLCBackend()

    # -- VLC args ---------------------------------------------------------

    def test_vlc_instance_args(self):
        vlc_mock, _, _ = _make_vlc_mock()

        _create_backend(vlc_mock)

        vlc_mock.Instance.assert_called_once_with(
            "--no-video", "--quiet", "--no-xlib"
        )


# ---------------------------------------------------------------------------
# 3. TTSBackend Tests
# ---------------------------------------------------------------------------
class TestTTSBackend:
    async def test_tts_backend_not_implemented(self):
        from agent.voice_engine import TTSBackend

        backend = TTSBackend()

        with pytest.raises(NotImplementedError, match="TTS: Faz 2"):
            await backend.play("/dummy.mp3")

        with pytest.raises(NotImplementedError, match="TTS: Faz 2"):
            await backend.pause()

        with pytest.raises(NotImplementedError, match="TTS: Faz 2"):
            await backend.resume()

        with pytest.raises(NotImplementedError, match="TTS: Faz 2"):
            await backend.stop()

        with pytest.raises(NotImplementedError, match="TTS: Faz 2"):
            await backend.set_volume(50)

        with pytest.raises(NotImplementedError, match="TTS: Faz 2"):
            await backend.close()


# ---------------------------------------------------------------------------
# 4. Factory Tests
# ---------------------------------------------------------------------------
class TestFactory:
    def test_factory_libvlc(self):
        vlc_mock, _, _ = _make_vlc_mock()

        with patch.dict("sys.modules", {"vlc": vlc_mock}):
            with patch("agent.voice_engine.agent_settings") as mock_settings:
                mock_settings.VOICE_BACKEND = "libvlc"

                from agent.voice_engine import LibVLCBackend, get_voice_engine

                engine = get_voice_engine()
                assert isinstance(engine, LibVLCBackend)

    def test_factory_tts(self):
        with patch("agent.voice_engine.agent_settings") as mock_settings:
            mock_settings.VOICE_BACKEND = "tts"

            from agent.voice_engine import TTSBackend, get_voice_engine

            engine = get_voice_engine()
            assert isinstance(engine, TTSBackend)
