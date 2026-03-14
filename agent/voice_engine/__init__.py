"""Voice Engine Abstraction Layer — Facade Pattern.

Ses calma islemini soyutlar. player.py hicbir zaman alt seviye
ses motorunu (LibVLC, TTS vb.) bilmez — sadece bu katmanin
play/pause/resume/stop/set_volume/close metodlarini cagirir.

MVP: LibVLCBackend (python-vlc)
Faz 2: TTSBackend (Coqui XTTS v2 stub)

Blueprint Bolum 3D.4 — voice_engine Modulu.
"""

import asyncio
import logging
import math
import os
import platform
import subprocess
from abc import ABC, abstractmethod
from typing import Any

from agent.core.settings import agent_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ABC — Sozlesme
# ---------------------------------------------------------------------------
class VoiceEngine(ABC):
    """Ses motoru soyut arayuzu. Tum backend'ler bunu uygular."""

    @abstractmethod
    async def play(self, path: str) -> None:
        """Verilen dosyayi calar."""

    @abstractmethod
    async def pause(self) -> None:
        """Calmayi duraklatir."""

    @abstractmethod
    async def resume(self) -> None:
        """Duraklatilmis calmayi devam ettirir."""

    @abstractmethod
    async def stop(self) -> None:
        """Calmayi durdurur."""

    @abstractmethod
    async def set_volume(self, volume: int) -> None:
        """Ses seviyesini ayarlar (0-100)."""

    @abstractmethod
    async def close(self) -> None:
        """Kaynaklari serbest birakir. Guard 2: Memory Safety."""


# ---------------------------------------------------------------------------
# LibVLCBackend — MVP
# ---------------------------------------------------------------------------
class LibVLCBackend(VoiceEngine):
    """python-vlc ile ses calma backend'i.

    VLC instance argumanlari:
      --no-video : Sadece ses (gereksiz video codec yuklenmez)
      --quiet    : VLC kendi log spam'ini kapatir
      --no-xlib  : Headless Pi4'te X11 bagimliligi olmaz
    """

    _instance: Any  # vlc.Instance — __init__ sonrasi her zaman non-None
    _player: Any    # vlc.MediaPlayer — __init__ sonrasi her zaman non-None

    def __init__(self) -> None:
        import vlc  # type: ignore[import-untyped]

        self._instance = vlc.Instance("--no-video", "--quiet", "--no-xlib")
        if self._instance is None:
            raise RuntimeError("VLC baslatilamadi: vlc.Instance() None dondurdu")

        self._player = self._instance.media_player_new()
        if self._player is None:
            self._instance.release()
            raise RuntimeError(
                "MediaPlayer olusturulamadi: media_player_new() None dondurdu"
            )

        self._op_lock = asyncio.Lock()
        self._closed = False

        logger.info(
            "LibVLCBackend baslatildi",
            extra={"vlc_args": ["--no-video", "--quiet", "--no-xlib"]},
        )

    # -- Playback ---------------------------------------------------------

    async def play(self, path: str) -> None:
        async with self._op_lock:
            self._raise_if_closed()
            exists = await asyncio.to_thread(os.path.isfile, path)
            if not exists:
                raise FileNotFoundError(f"Ses dosyasi bulunamadi: {path}")

            await asyncio.to_thread(self._play_sync, path)

    async def pause(self) -> None:
        async with self._op_lock:
            self._raise_if_closed()
            await asyncio.to_thread(self._pause_sync)

    async def resume(self) -> None:
        async with self._op_lock:
            self._raise_if_closed()
            await asyncio.to_thread(self._resume_sync)

    async def stop(self) -> None:
        async with self._op_lock:
            self._raise_if_closed()
            await asyncio.to_thread(self._stop_sync)

    # -- Volume -----------------------------------------------------------

    async def set_volume(self, volume: int) -> None:
        volume = max(0, min(100, volume))

        async with self._op_lock:
            self._raise_if_closed()

            # Katman 1: LibVLC software volume
            await asyncio.to_thread(self._set_volume_sync, volume)

            # Katman 2: Pi4 ALSA hardware calibration (legacy pattern)
            if platform.system() == "Linux" and agent_settings.ENABLE_HW_VOLUME:
                await asyncio.to_thread(self._set_hardware_volume, volume)

            logger.info("Volume set", extra={"volume": volume})

    def _play_sync(self, path: str) -> None:
        media = self._instance.media_new(path)
        if media is None:
            logger.error(
                "media_new() None dondurdu, dosya calinamiyor",
                extra={"file": os.path.basename(path)},
            )
            return

        try:
            self._player.set_media(media)
            self._player.play()
            logger.info("Playing", extra={"file": os.path.basename(path)})
        finally:
            release = getattr(media, "release", None)
            if callable(release):
                release()

    def _pause_sync(self) -> None:
        # LibVLC pause() toggle'dir — sadece caliyorsa duraklat
        if self._player.is_playing():
            self._player.pause()
            logger.info("Paused")

    def _resume_sync(self) -> None:
        # LibVLC pause() toggle'dir — sadece duraklatilmissa devam ettir
        if not self._player.is_playing():
            self._player.pause()
            logger.info("Resumed")

    def _stop_sync(self) -> None:
        self._player.stop()
        logger.info("Stopped")

    def _set_volume_sync(self, volume: int) -> None:
        self._player.audio_set_volume(volume)

    def _set_hardware_volume(self, volume: int) -> None:
        """Pi4 ALSA hardware volume — senkron (asyncio.to_thread ile cagrilir).

        Legacy calibration curve (player.py:657-708):
        Pi4 analog (3.5mm) cikisi berbat logaritmik egriye sahip.
        HW 100% = +4dB, HW 90% = -6dB, HW 80% = -15dB, HW 70% = -25dB
        Cozum: UI 0-9% = mute, UI 10-100% -> HW 70-100%
        """
        success = False
        if volume < 10:
            success = self._run_amixer(["mute"])
            if success:
                logger.info(
                    "HW volume muted",
                    extra={"ui_volume": volume, "hw_volume": 0},
                )
        else:
            hw_volume = int(round(70 + math.sqrt((volume - 10) / 90.0) * 30))
            success = self._run_amixer([f"{hw_volume}%", "unmute"])
            if success:
                logger.info(
                    "HW volume calibrated",
                    extra={"ui_volume": volume, "hw_volume": hw_volume},
                )

        if not success:
            logger.warning("amixer failed for all card/control candidates")

    def _run_amixer(self, value_args: list[str]) -> bool:
        """amixer calistir, PCM -> Master fallback, card fallback zinciri.

        Legacy pattern: player.py:147-173
        """
        cards = self._build_alsa_card_candidates()

        for control in ("PCM", "Master"):
            for card in cards:
                try:
                    result = subprocess.run(
                        ["amixer", "-c", card, "set", control, *value_args],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if result.returncode == 0:
                        return True
                except (subprocess.SubprocessError, OSError):
                    continue

            # Fallback: default card
            try:
                result = subprocess.run(
                    ["amixer", "set", control, *value_args],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    return True
            except (subprocess.SubprocessError, OSError):
                continue

        return False

    def _build_alsa_card_candidates(self) -> list[str]:
        """ALSA card fallback zinciri.

        Legacy pattern: player.py:123-145
        """
        candidates: list[str] = []

        if agent_settings.ALSA_CARD:
            card = agent_settings.ALSA_CARD
            if card.startswith(("plughw:", "hw:")):
                # hw:2,0 -> "2"
                tail = card.split(":", 1)[1]
                card_idx = tail.split(",", 1)[0]
                if card_idx:
                    candidates.append(card_idx)
            else:
                candidates.append(card)

        candidates.extend(["2", "0", "1"])

        # Dedupe while preserving order
        seen: set[str] = set()
        deduped: list[str] = []
        for item in candidates:
            if item and item not in seen:
                seen.add(item)
                deduped.append(item)
        return deduped

    # -- Cleanup ----------------------------------------------------------

    async def close(self) -> None:
        async with self._op_lock:
            if self._closed:
                return

            await asyncio.to_thread(self._close_sync)
            self._closed = True
            logger.info("LibVLCBackend kapatildi")

    def _close_sync(self) -> None:
        self._player.stop()
        self._player.release()
        self._instance.release()

    def _raise_if_closed(self) -> None:
        if self._closed:
            raise RuntimeError("Voice engine kapatildi")


# ---------------------------------------------------------------------------
# TTSBackend — Faz 2 Stub
# ---------------------------------------------------------------------------
class TTSBackend(VoiceEngine):
    """TTS backend stub'i. Faz 2'de Coqui XTTS v2 ile doldurulacak."""

    async def play(self, path: str) -> None:
        raise NotImplementedError("TTS: Faz 2")

    async def pause(self) -> None:
        raise NotImplementedError("TTS: Faz 2")

    async def resume(self) -> None:
        raise NotImplementedError("TTS: Faz 2")

    async def stop(self) -> None:
        raise NotImplementedError("TTS: Faz 2")

    async def set_volume(self, volume: int) -> None:
        raise NotImplementedError("TTS: Faz 2")

    async def close(self) -> None:
        raise NotImplementedError("TTS: Faz 2")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def get_voice_engine() -> VoiceEngine:
    """Konfigurasyona gore uygun ses backend'ini dondurur.

    settings.VOICE_BACKEND: 'libvlc' | 'tts'
    """
    if agent_settings.VOICE_BACKEND == "libvlc":
        return LibVLCBackend()
    return TTSBackend()
