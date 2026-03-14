import json
from pathlib import Path
from typing import Any, NoReturn

from backend.core.settings import settings


class VoiceProfileResolutionError(ValueError):
    """Raised when voice profile resolution fails with a stable reason code."""

    def __init__(
        self,
        reason_code: str,
        detail: str,
        registry_path: str | None = None,
    ) -> None:
        super().__init__(detail)
        self.reason_code = reason_code
        self.registry_path = registry_path


def _raise_resolution_error(
    reason_code: str,
    detail: str,
    registry_path: str,
) -> NoReturn:
    raise VoiceProfileResolutionError(
        reason_code=reason_code,
        detail=detail,
        registry_path=registry_path,
    )


def load_registry(path: str) -> dict[str, Any]:
    """Load and minimally validate the voice profile registry JSON."""
    registry_path = str(Path(path).expanduser())
    registry_file = Path(registry_path)

    if not registry_file.exists():
        _raise_resolution_error(
            "REGISTRY_NOT_FOUND",
            f"Registry file not found: {registry_path}",
            registry_path,
        )
    if not registry_file.is_file() or registry_file.suffix.lower() != ".json":
        _raise_resolution_error(
            "REGISTRY_INVALID_SCHEMA",
            f"Registry path must point to a JSON file: {registry_path}",
            registry_path,
        )

    try:
        with registry_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        _raise_resolution_error(
            "REGISTRY_INVALID_JSON",
            f"Registry JSON parse failed: {exc}",
            registry_path,
        )
    except OSError as exc:
        _raise_resolution_error(
            "REGISTRY_NOT_FOUND",
            f"Registry file cannot be read: {exc}",
            registry_path,
        )

    if not isinstance(data, dict):
        _raise_resolution_error(
            "REGISTRY_INVALID_SCHEMA",
            "Registry root must be an object",
            registry_path,
        )

    default_profile = data.get("default_profile")
    profiles = data.get("profiles")
    if not isinstance(default_profile, str) or not default_profile.strip():
        _raise_resolution_error(
            "REGISTRY_INVALID_SCHEMA",
            "default_profile must be a non-empty string",
            registry_path,
        )
    if not isinstance(profiles, dict):
        _raise_resolution_error(
            "REGISTRY_INVALID_SCHEMA",
            "profiles must be an object",
            registry_path,
        )
    if default_profile not in profiles:
        _raise_resolution_error(
            "REGISTRY_INVALID_SCHEMA",
            "default_profile must exist in profiles",
            registry_path,
        )

    for profile_id, profile in profiles.items():
        if not isinstance(profile_id, str) or not profile_id.strip():
            _raise_resolution_error(
                "REGISTRY_INVALID_SCHEMA",
                "profile keys must be non-empty strings",
                registry_path,
            )
        if not isinstance(profile, dict):
            _raise_resolution_error(
                "REGISTRY_INVALID_SCHEMA",
                f"profile '{profile_id}' must be an object",
                registry_path,
            )
        profile_type = profile.get("type")
        if not isinstance(profile_type, str) or not profile_type.strip():
            _raise_resolution_error(
                "REGISTRY_INVALID_SCHEMA",
                f"profile '{profile_id}' must define type",
                registry_path,
            )
        enabled = profile.get("enabled")
        if not isinstance(enabled, bool):
            _raise_resolution_error(
                "REGISTRY_INVALID_SCHEMA",
                f"profile '{profile_id}' must define enabled as bool",
                registry_path,
            )
        if profile_type == "xtts_builtin":
            speaker_id = profile.get("speaker_id")
            if not isinstance(speaker_id, str) or not speaker_id.strip():
                _raise_resolution_error(
                    "REGISTRY_INVALID_SCHEMA",
                    f"profile '{profile_id}' must define speaker_id",
                    registry_path,
                )

    return data


def _get_available_model_speakers(model: Any, registry_path: str) -> set[str]:
    try:
        speakers = model.synthesizer.tts_model.speaker_manager.speakers
    except AttributeError as exc:
        _raise_resolution_error(
            "SPEAKER_NOT_IN_MODEL",
            f"Model speaker list is not available: {exc}",
            registry_path,
        )

    if not hasattr(speakers, "keys"):
        _raise_resolution_error(
            "SPEAKER_NOT_IN_MODEL",
            "Model speaker list is invalid",
            registry_path,
        )

    return {str(name) for name in speakers.keys()}


def resolve_builtin_speaker(voice_profile: str, model: Any) -> str:
    """Resolve friendly voice profile alias to XTTS builtin speaker id."""
    registry_path = settings.TTS_VOICE_PROFILE_REGISTRY_PATH
    registry = load_registry(registry_path)

    requested_profile = (voice_profile or "").strip()
    if requested_profile in {"", "default"}:
        requested_profile = registry["default_profile"]

    profiles = registry["profiles"]
    if requested_profile not in profiles:
        _raise_resolution_error(
            "PROFILE_NOT_FOUND",
            f"Voice profile '{requested_profile}' is not defined",
            registry_path,
        )

    profile = profiles[requested_profile]
    if not profile["enabled"]:
        _raise_resolution_error(
            "PROFILE_DISABLED",
            f"Voice profile '{requested_profile}' is disabled",
            registry_path,
        )
    if profile["type"] != "xtts_builtin":
        _raise_resolution_error(
            "UNSUPPORTED_PROFILE_TYPE",
            f"Profile type '{profile['type']}' is not supported",
            registry_path,
        )

    speaker_id = profile["speaker_id"]
    available_speakers = _get_available_model_speakers(model, registry_path)
    if speaker_id not in available_speakers:
        _raise_resolution_error(
            "SPEAKER_NOT_IN_MODEL",
            f"Speaker '{speaker_id}' is not available in current model",
            registry_path,
        )

    return speaker_id
