"""Módulo de visualización Swimlane (Carriles de Habla) para Miskatonic Scribe.

Renderiza un gráfico interactivo estilo Gantt/Timeline en Plotly donde cada
participante (Guardián e Investigadores) tiene su propio carril nominal
a lo largo de la línea temporal de la sesión.
"""

from __future__ import annotations

import textwrap
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Paleta de colores optimizada para tema oscuro Lovecraftian
GUARDIAN_COLOR = "#D4AF37"  # Oro arcano / Ámbar imperial
INVESTIGATOR_PALETTE = [
    "#38bdf8",  # Azul celeste
    "#a78bfa",  # Violeta arcano
    "#34d399",  # Verde esmeralda
    "#fb923c",  # Ámbar cálido
    "#f472b6",  # Rosa
    "#818cf8",  # Índigo
    "#2dd4bf",  # Turquesa
]


def format_seconds_to_hms(seconds: float) -> str:
    """Convierte segundos a formato HH:MM:SS o MM:SS legible."""
    total_sec = max(0, int(seconds))
    h = total_sec // 3600
    m = (total_sec % 3600) // 60
    s = total_sec % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def wrap_tooltip_text(text: str, width: int = 50) -> str:
    """Envuelve texto largo insertando etiquetas <br> para tooltips elegantes."""
    if not text:
        return "<i>(sin diálogo)</i>"
    clean = str(text).strip()
    lines = textwrap.wrap(clean, width=width)
    return "<br>".join(lines)


def build_speaker_metadata(characters: list[dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    """Construye un diccionario de metadatos por speaker_id."""
    if not characters:
        return {}
    speaker_map = {}
    for c in characters:
        spk_id = c.get("speaker_id") or c.get("canonical_speaker")
        if spk_id:
            speaker_map[spk_id] = {
                "player": c.get("player", spk_id),
                "character": c.get("character", ""),
                "role": c.get("role", "investigator"),
            }
    return speaker_map


def get_participant_label(speaker_id: str, speaker_map: dict[str, dict[str, Any]]) -> tuple[str, str]:
    """Genera la etiqueta formal con icono y rol (ej. '👑 Justo (Guardián)')."""
    info = speaker_map.get(speaker_id, {})
    player = info.get("player", speaker_id)
    character = info.get("character", "")
    role = info.get("role", "investigator")

    if role == "guardian":
        label = f"👑 {player} ({character})" if character else f"👑 {player}"
    else:
        label = f"🕵️ {player} ({character})" if character else f"🕵️ {player}"

    return label, role


def render_swimlane_chart(
    dialogs: list[dict[str, Any]],
    characters: list[dict[str, Any]] | None = None,
    selected_speakers: list[str] | None = None,
) -> go.Figure:
    """Genera la figura interactiva de Plotly con los carriles de habla.

    Args:
        dialogs: Lista de turnos normalizados con 'speaker', 'start', 'end', 'text'.
        characters: Metadatos de personajes desde la base de datos o mapping.
        selected_speakers: Filtro opcional de etiquetas de oradores a mostrar.

    Returns:
        Figura de Plotly lista para st.plotly_chart.
    """
    if not dialogs:
        fig = go.Figure()
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0d1117",
            plot_bgcolor="#161b22",
            annotations=[
                dict(
                    text="No hay turnos de diálogo disponibles para esta sesión.",
                    showarrow=False,
                    font=dict(size=14, color="#8b949e"),
                )
            ],
        )
        return fig

    speaker_map = build_speaker_metadata(characters)
    records = []

    # Fecha base arbitraria para convertir segundos a timestamps continuos en Plotly
    base_date = pd.to_datetime("2000-01-01")

    for d in dialogs:
        spk_id = d.get("speaker", "SPEAKER_UNKNOWN")
        label, role = get_participant_label(spk_id, speaker_map)

        # Si hay filtro activo de oradores y este orador no está incluido, omitir
        if selected_speakers is not None and label not in selected_speakers:
            continue

        start_s = float(d.get("start", d.get("start_time", 0.0)))
        end_s = float(d.get("end", d.get("end_time", start_s + 0.5)))
        duration = max(0.5, end_s - start_s)

        time_range = f"[{format_seconds_to_hms(start_s)} - {format_seconds_to_hms(end_s)}]"
        dur_str = f"{duration:.1f}s"
        text_wrapped = wrap_tooltip_text(d.get("text", ""))

        records.append({
            "speaker_id": spk_id,
            "label": label,
            "role": role,
            "start_s": start_s,
            "end_s": end_s,
            "duration": duration,
            "start_dt": base_date + pd.to_timedelta(start_s, unit="s"),
            "end_dt": base_date + pd.to_timedelta(end_s, unit="s"),
            "time_range": time_range,
            "dur_str": dur_str,
            "text_wrapped": text_wrapped,
        })

    if not records:
        fig = go.Figure()
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0d1117",
            plot_bgcolor="#161b22",
            annotations=[
                dict(
                    text="Ningún orador coincide con los filtros seleccionados.",
                    showarrow=False,
                    font=dict(size=14, color="#8b949e"),
                )
            ],
        )
        return fig

    df = pd.DataFrame(records)

    # Ordenar carriles de forma jerárquica: Guardián arriba, luego Investigadores
    unique_labels = list(df["label"].unique())
    guardian_labels = [l for l in unique_labels if l.startswith("👑")]
    investigator_labels = sorted([l for l in unique_labels if not l.startswith("👑")])
    ordered_lanes = guardian_labels + investigator_labels

    # Asignar paleta de colores fija y armónica
    color_map = {}
    for l in guardian_labels:
        color_map[l] = GUARDIAN_COLOR
    for idx, l in enumerate(investigator_labels):
        color_map[l] = INVESTIGATOR_PALETTE[idx % len(INVESTIGATOR_PALETTE)]

    fig = px.timeline(
        df,
        x_start="start_dt",
        x_end="end_dt",
        y="label",
        color="label",
        color_discrete_map=color_map,
        custom_data=["time_range", "dur_str", "text_wrapped"],
        category_orders={"label": ordered_lanes},
    )

    # Hover template detallado y estilizado
    fig.update_traces(
        hovertemplate=(
            "<b>%{y}</b><br>"
            "⏱️ <b>%{customdata[0]}</b> (%{customdata[1]})<br><br>"
            "%{customdata[2]}<extra></extra>"
        ),
        marker_line_width=0,
        opacity=0.92,
    )

    chart_height = max(340, len(ordered_lanes) * 75 + 100)

    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="#161b22",
        paper_bgcolor="#0d1117",
        showlegend=False,
        height=chart_height,
        margin=dict(l=20, r=20, t=25, b=40),
        xaxis=dict(
            tickformat="%H:%M:%S",
            showgrid=True,
            gridcolor="#21262d",
            gridwidth=1,
            title=dict(text="Tiempo de Partida (HH:MM:SS)", font=dict(color="#8b949e", size=12)),
            zeroline=False,
        ),
        yaxis=dict(
            title="",
            showgrid=True,
            gridcolor="#21262d",
            autorange="reversed",  # El primer elemento (Guardián) en la fila superior
            tickfont=dict(size=13, color="#e0e6ed"),
        ),
        hoverlabel=dict(
            bgcolor="#161b22",
            bordercolor="#30363d",
            font_size=12,
            align="left",
            font_family="monospace",
        ),
    )

    return fig
