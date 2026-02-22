import json
from pathlib import Path
from typing import Any

import pytest

from backend.core.settings import settings
from backend.services.voice_profile_resolver import (
    VoiceProfileResolutionError,
    load_registry,
    resolve_builtin_speaker,
)


def _build_model_with_speakers(names: list[str]) -> Any:
    class _SpeakerManager:
        def __init__(self, speakers: dict[str, dict[str, str]]) -> None:
            self.speakers = speakers

    class _TTSModel:
        def __init__(self, speakers: dict[str, dict[str, str]]) -> None:
            self.speaker_manager = _SpeakerManager(speakers)

    class _Synthesizer:
        def __init__(self, speakers: dict[str, dict[str, str]]) -> None:
            self.tts_model = _TTSModel(speakers)

    class _Model:
        def __init__(self, speakers: dict[str, dict[str, str]]) -> None:
            self.synthesizer = _Synthesizer(speakers)

    speakers_dict = {name: {"id": name} for name in names}
    return _Model(speakers_dict)


def _write_registry(tmp_path: Path, data: dict[str, Any]) -> Path:
    registry_path = tmp_path / "voice_profiles.json"
    registry_path.write_text(json.dumps(data), encoding="utf-8")
    return registry_path


def test_resolve_builtin_speaker_valid_alias(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    registry_path = _write_registry(
        tmp_path,
        {
            "version": 1,
            "default_profile": "tok_erkek_1",
            "profiles": {
                "tok_erkek_1": {
                    "type": "xtts_builtin",
                    "speaker_id": "Claribel Dervla",
                    "enabled": True,
                }
            },
        },
    )
    monkeypatch.setattr(settings, "TTS_VOICE_PROFILE_REGISTRY_PATH", str(registry_path))
    model = _build_model_with_speakers(["Claribel Dervla", "Ana Florence"])

    speaker = resolve_builtin_speaker("tok_erkek_1", model)

    assert speaker == "Claribel Dervla"


def test_resolve_builtin_speaker_profile_not_found(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    registry_path = _write_registry(
        tmp_path,
        {
            "version": 1,
            "default_profile": "tok_erkek_1",
            "profiles": {
                "tok_erkek_1": {
                    "type": "xtts_builtin",
                    "speaker_id": "Claribel Dervla",
                    "enabled": True,
                }
            },
        },
    )
    monkeypatch.setattr(settings, "TTS_VOICE_PROFILE_REGISTRY_PATH", str(registry_path))
    model = _build_model_with_speakers(["Claribel Dervla"])

    with pytest.raises(VoiceProfileResolutionError) as exc_info:
        resolve_builtin_speaker("missing_profile", model)

    assert exc_info.value.reason_code == "PROFILE_NOT_FOUND"


def test_resolve_builtin_speaker_missing_in_model(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    registry_path = _write_registry(
        tmp_path,
        {
            "version": 1,
            "default_profile": "tok_erkek_1",
            "profiles": {
                "tok_erkek_1": {
                    "type": "xtts_builtin",
                    "speaker_id": "Claribel Dervla",
                    "enabled": True,
                }
            },
        },
    )
    monkeypatch.setattr(settings, "TTS_VOICE_PROFILE_REGISTRY_PATH", str(registry_path))
    model = _build_model_with_speakers(["Ana Florence"])

    with pytest.raises(VoiceProfileResolutionError) as exc_info:
        resolve_builtin_speaker("tok_erkek_1", model)

    assert exc_info.value.reason_code == "SPEAKER_NOT_IN_MODEL"


def test_load_registry_invalid_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.json"
    monkeypatch.setattr(settings, "TTS_VOICE_PROFILE_REGISTRY_PATH", str(missing_path))

    with pytest.raises(VoiceProfileResolutionError) as exc_info:
        load_registry(str(missing_path))

    assert exc_info.value.reason_code == "REGISTRY_NOT_FOUND"


def test_load_registry_invalid_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    registry_path = tmp_path / "voice_profiles.json"
    registry_path.write_text("{ invalid json", encoding="utf-8")
    monkeypatch.setattr(settings, "TTS_VOICE_PROFILE_REGISTRY_PATH", str(registry_path))

    with pytest.raises(VoiceProfileResolutionError) as exc_info:
        load_registry(str(registry_path))

    assert exc_info.value.reason_code == "REGISTRY_INVALID_JSON"
