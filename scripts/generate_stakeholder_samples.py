import asyncio
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("COQUI_TOS_AGREED", "1")

from backend.services import tts_service

LANGUAGE = "tr"
OUTPUT_DIR = Path("data/media/stakeholder_samples/xtts_v2")

# Stakeholder demosunda kullandigimiz tum ornek sesler (sirali)
SPEAKERS = [
    "Alexandra Hisakawa",
    "Suad Qasim",
    "Ilkin Urbano",
    "Asya Anara",
    "Eugenio Mataracı",
    "Alma María",
    "Claribel Dervla",
    "Aaron Dreschner",
]

# XTTS v2 icin noktalama kaynakli artefact riskini azaltacak nihai metin.
FINAL_TEXT = (
    "Sayın misafirlerimiz, akıllı mağaza anons sistemimize hoş geldiniz. "
    "Bugün kaliteyi ve avantajı bir arada sunuyoruz, manav reyonumuzda günün taze ürün fırsatları başladı. "
    "Seçili domates, salatalık ve biber çeşitlerinde, kasada anında özel indirim uygulanmaktadır. "
    "Ekibimiz, meyve ve sebze reyonunda size en taze ürünleri seçmeniz için memnuniyetle yardımcı olacaktır. "
    "Şarküteri ve fırın bölümümüzde, akşam servisine özel yeni hazırlanmış ürünler sizleri bekliyor. "
    "Nazik bir hatırlatma yapmak isteriz, mağazamızın kapanışına on beş dakika kalmıştır. "
    "Lütfen son alışverişlerinizi tamamlayarak kasalarımıza yöneliniz. "
    "Bizi tercih ettiğiniz için teşekkür eder, sağlıklı ve huzurlu bir akşam dileriz."
)

SOURCES = [
    "https://docs.coqui.ai/en/latest/models/xtts.html",
    "https://github.com/coqui-ai/TTS/issues/3236",
    "https://github.com/coqui-ai/TTS/issues/3516",
    "https://github.com/coqui-ai/TTS/issues/3964",
]


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = "_".join(ascii_only.lower().split())
    return slug or "voice"


def _normalize_text_for_xtts(text: str) -> str:
    normalized = " ".join(text.split())
    normalized = re.sub(r"\s+([,.;:!?])", r"\1", normalized)
    normalized = re.sub(r"([,.;:!?])\1+", r"\1", normalized)
    return normalized.strip()


def _write_metadata_files(text: str, outputs: list[dict[str, str]]) -> None:
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_name": "tts_models/multilingual/multi-dataset/xtts_v2",
        "language": LANGUAGE,
        "text": text,
        "sources": SOURCES,
        "samples": outputs,
    }
    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUTPUT_DIR / "final_text.txt").write_text(text + "\n", encoding="utf-8")
    (OUTPUT_DIR / "sources.txt").write_text("\n".join(SOURCES) + "\n", encoding="utf-8")


async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for old_file in OUTPUT_DIR.glob("*.wav"):
        old_file.unlink(missing_ok=True)

    model = await tts_service.get_model()
    available_speakers = set(model.synthesizer.tts_model.speaker_manager.speakers.keys())

    missing = [speaker for speaker in SPEAKERS if speaker not in available_speakers]
    if missing:
        raise RuntimeError(f"Missing speakers in XTTS model: {missing}")

    text = _normalize_text_for_xtts(FINAL_TEXT)

    outputs: list[dict[str, str]] = []
    for idx, speaker in enumerate(SPEAKERS, start=1):
        output_file = OUTPUT_DIR / f"{idx:02d}_{_slugify(speaker)}.wav"
        await asyncio.to_thread(
            model.tts_to_file,
            text=text,
            language=LANGUAGE,
            speaker=speaker,
            file_path=str(output_file),
        )
        outputs.append({"speaker": speaker, "file": str(output_file)})
        print(f"Generated: {output_file.resolve()}")

    _write_metadata_files(text, outputs)
    print(f"All stakeholder samples generated under: {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    asyncio.run(main())
