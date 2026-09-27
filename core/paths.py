#!/usr/bin/env python3
"""Módulo centralizado de rutas del sistema para Miskatonic Scribe (Spec 06).

Desacopla el código fuente de los datos generados y encapsula cada partida
en su propio directorio independiente bajo data/sessions/{video_id}/.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Raíz del repositorio y directorios principales
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SESSIONS_DIR = DATA_DIR / "sessions"

# Recursos globales de datos
DB_PATH = DATA_DIR / "partidas.db"
URLS_FILE = DATA_DIR / "urls.txt"
PROCESSED_FILE = DATA_DIR / "procesados.txt"


def get_session_dir(video_id: str) -> Path:
    """Devuelve la ruta absoluta del directorio raíz de una sesión."""
    return SESSIONS_DIR / video_id


def get_download_dir(video_id: str) -> Path:
    """Devuelve la ruta del directorio de descargas y medios de la sesión."""
    return get_session_dir(video_id) / "download"


def get_transcript_provider(provider: str | None = None) -> str:
    """Normaliza y devuelve el identificador de subcarpeta del proveedor ('whisperx' o 'deepgram')."""
    if provider:
        p = provider.lower().strip()
        return "deepgram" if "deepgram" in p else "whisperx"
    try:
        from core import config
        backend = config.get_transcription_backend()
        return "deepgram" if "deepgram" in backend else "whisperx"
    except Exception:
        return "whisperx"


def get_transcript_dir(video_id: str, provider: str | None = None) -> Path:
    """Devuelve la ruta del directorio de transcripciones para una sesión y proveedor."""
    prov = get_transcript_provider(provider)
    prov_dir = get_session_dir(video_id) / "transcript" / prov
    if prov_dir.exists():
        return prov_dir

    # Fallback retrocompatible para sesiones previas sin subcarpetas
    legacy_dir = get_session_dir(video_id) / "transcript"
    if prov == "deepgram" and (legacy_dir / "dialogs.json").exists() and not (legacy_dir / "whisperx").exists():
        return legacy_dir

    return prov_dir


def get_analysis_dir(video_id: str) -> Path:
    """Devuelve la ruta del directorio de análisis e inteligencia NLP."""
    return get_session_dir(video_id) / "analysis"


def get_audio_path(video_id: str) -> Path:
    """Ruta al archivo de audio principal (.m4a)."""
    return get_download_dir(video_id) / "audio.m4a"


def get_thumbnail_path(video_id: str) -> Path:
    """Ruta a la miniatura local de YouTube (.jpg)."""
    return get_download_dir(video_id) / "thumbnail.jpg"


def get_metadata_path(video_id: str) -> Path:
    """Ruta al archivo de metadatos brutos de YouTube (metadata.json)."""
    return get_download_dir(video_id) / "metadata.json"


def get_clips_dir(video_id: str, provider: str | None = None) -> Path:
    """Ruta al directorio de fragmentos de audio por orador para el mapper."""
    return get_transcript_dir(video_id, provider=provider) / ".clips"


def get_clip_path(video_id: str, speaker: str, provider: str | None = None) -> Path:
    """Ruta a la muestra de audio individual de un orador."""
    return get_clips_dir(video_id, provider=provider) / f"{speaker}.m4a"


def get_raw_transcript_path(video_id: str, provider: str | None = None) -> Path:
    """Ruta al volcado JSON crudo devuelto por la API de transcripción (raw.json)."""
    return get_transcript_dir(video_id, provider=provider) / "raw.json"


def get_dialogs_path(video_id: str, provider: str | None = None) -> Path:
    """Ruta a la lista ordenada de intervenciones con timestamps (dialogs.json)."""
    return get_transcript_dir(video_id, provider=provider) / "dialogs.json"


def get_mapping_path(video_id: str, provider: str | None = None) -> Path:
    """Ruta al archivo de mapeo manual de identidades (mapping.json)."""
    return get_transcript_dir(video_id, provider=provider) / "mapping.json"


def get_normalized_mapping_path(video_id: str, provider: str | None = None) -> Path:
    """Ruta al archivo de mapeo con colisiones unificadas (mapping_normalized.json)."""
    return get_transcript_dir(video_id, provider=provider) / "mapping_normalized.json"


def get_normalized_dialogs_path(video_id: str, provider: str | None = None) -> Path:
    """Ruta a los diálogos normalizados con identidades fusionadas (dialogs_normalized.json)."""
    return get_transcript_dir(video_id, provider=provider) / "dialogs_normalized.json"


def get_analysis_path(video_id: str) -> Path:
    """Ruta al resultado estructurado del análisis cualitativo LLM (analysis.json)."""
    return get_analysis_dir(video_id) / "analysis.json"


def ensure_session_dirs(video_id: str, provider: str | None = None) -> None:
    """Crea los subdirectorios estructurados para una sesión si no existen."""
    get_download_dir(video_id).mkdir(parents=True, exist_ok=True)
    get_transcript_dir(video_id, provider=provider).mkdir(parents=True, exist_ok=True)
    get_clips_dir(video_id, provider=provider).mkdir(parents=True, exist_ok=True)
    get_analysis_dir(video_id).mkdir(parents=True, exist_ok=True)


def list_available_session_ids() -> list[str]:
    """Devuelve los IDs de todas las sesiones presentes en data/sessions/."""
    if not SESSIONS_DIR.exists():
        return []
    return sorted(
        [d.name for d in SESSIONS_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")]
    )


def parse_url_entry(
    line: str,
    default_min: int = 5,
    default_max: int = 6,
) -> tuple[str, int, int] | None:
    """Parsea una línea de urls.txt extrayendo la URL y los límites opcionales de oradores.

    Formatos admitidos:
    - Líneas en blanco o comentarios (# ...) -> None
    - '<URL>' -> (url, default_min, default_max)
    - '<URL> <N>' -> (url, N, N)
    - '<URL> <MIN> <MAX>' -> (url, MIN, MAX)
    """
    raw = line.split("#", 1)[0].strip()
    if not raw:
        return None

    tokens = raw.split()
    url = tokens[0]

    min_s = default_min
    max_s = default_max

    if len(tokens) == 2:
        try:
            val = int(tokens[1])
            min_s, max_s = val, val
        except ValueError:
            pass
    elif len(tokens) >= 3:
        try:
            min_s = int(tokens[1])
            max_s = int(tokens[2])
        except ValueError:
            pass

    if min_s <= 0:
        min_s = default_min
    if max_s < min_s:
        max_s = min_s

    return url, min_s, max_s


def read_urls_entries(file_path: Path | None = None) -> list[dict[str, Any]]:
    """Lee todas las entradas de URLs con sus límites de oradores asociados."""
    target_path = file_path or URLS_FILE
    if not target_path.exists():
        return []

    try:
        from core import config
        default_min, default_max = config.get_default_speakers_range()
    except Exception:
        default_min, default_max = 5, 6

    entries: list[dict[str, Any]] = []
    with open(target_path, "r", encoding="utf-8") as f:
        for line in f:
            parsed = parse_url_entry(line, default_min=default_min, default_max=default_max)
            if parsed is not None:
                url, min_s, max_s = parsed
                entries.append(
                    {
                        "raw": url,
                        "min_speakers": min_s,
                        "max_speakers": max_s,
                    }
                )
    return entries

