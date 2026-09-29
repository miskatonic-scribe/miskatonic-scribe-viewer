#!/usr/bin/env python3
"""Módulo de visualización de la Curva de Tensión Dramática Enriquecida (Spec 17 / US1).

Genera el gráfico interactivo de Plotly con la curva de tensión continua
y capas superpuestas de eventos narrativos (cordura, pistas, dados, combate).
"""

from __future__ import annotations

import textwrap
from typing import Any
import pandas as pd
import plotly.graph_objects as go

from dashboard.visualizations.timeline_stream import parse_timestamp_seconds


def wrap_text(text: str, width: int = 55) -> str:
    """Envuelve texto largo con saltos de línea HTML para cuadros de diálogo Plotly."""
    if not text:
        return ""
    paragraphs = str(text).split("\n")
    wrapped_paras = ["<br>".join(textwrap.wrap(p, width=width)) for p in paragraphs if p]
    return "<br>".join(wrapped_paras)


def render_tension_chart(
    metrics: list[dict[str, Any]],
    sanity_events: list[dict[str, Any]] | None = None,
    clues: list[dict[str, Any]] | None = None,
    milestones: list[dict[str, Any]] | None = None,
    critical_rolls: list[dict[str, Any]] | None = None,
    combat_events: list[dict[str, Any]] | None = None,
) -> go.Figure:
    """Genera la Curva de Tensión Dramática con Plotly con capas de eventos superpuestas."""
    if not metrics:
        fig = go.Figure()
        fig.update_layout(title="Sin métricas de tensión disponibles.")
        return fig

    df = pd.DataFrame(metrics)
    time_labels = list(df["time_label"])

    # Paleta de colores para tensión según severidad
    def get_color(val: int) -> str:
        if val <= 0:
            return "#8b949e"
        elif val <= 3:
            return "#26a69a"
        elif val <= 6:
            return "#ffa726"
        elif val <= 8:
            return "#ff7043"
        return "#e53935"

    point_colors = [get_color(t) for t in df["tension"]]
    wrapped_just = [wrap_text(t, width=55) for t in df.get("tension_justification", [])]
    wrapped_story = [wrap_text(s, width=55) for s in df.get("story_state", [])]
    off_pcts = df.get("off_topic_pct", [0] * len(df))

    fig = go.Figure()

    # 1. Líneas de umbral de referencia
    fig.add_hline(
        y=7,
        line_dash="dash",
        line_color="rgba(255, 112, 67, 0.4)",
        annotation_text="Peligro / Tiradas Críticas (7)",
        annotation_position="bottom right",
    )
    fig.add_hline(
        y=9,
        line_dash="dash",
        line_color="rgba(229, 57, 53, 0.4)",
        annotation_text="Horror Cósmico / Clímax (9)",
        annotation_position="top right",
    )

    # 2. Línea y Área de tensión continua
    fig.add_trace(
        go.Scatter(
            x=time_labels,
            y=df["tension"],
            mode="lines+markers",
            name="Tensión Dramática",
            line=dict(color="#58a6ff", width=3, shape="spline", smoothing=0.7),
            marker=dict(size=12, color=point_colors, line=dict(color="#ffffff", width=1.5)),
            customdata=list(zip(wrapped_just, wrapped_story, off_pcts)),
            hovertemplate=(
                "<b>Intervalo:</b> %{x}<br>"
                "<b>Tensión:</b> %{y}/10<br>"
                "<b>Off-Topic:</b> %{customdata[2]}%<br>"
                "<span style='color:#8b949e;'>──────────────────────────────</span><br>"
                "<b>Justificación:</b><br>%{customdata[0]}<br><br>"
                "<b>Estado de la Trama:</b><br>%{customdata[1]}"
                "<extra></extra>"
            ),
        )
    )

    # Helper para asignar eventos al time_label correspondiente
    def find_block_label_and_tension(t_sec: float) -> tuple[str, float]:
        for b in metrics:
            if b.get("start_time", 0) <= t_sec < b.get("end_time", 999999):
                return b["time_label"], float(b.get("tension", 5))
        last_b = metrics[-1]
        return last_b["time_label"], float(last_b.get("tension", 5))

    # 3. Capa de Cordura (🐙)
    if sanity_events:
        s_x, s_y, s_hover, s_custom = [], [], [], []
        for e in sanity_events:
            t_sec = parse_timestamp_seconds(e.get("timestamp_seconds"), e.get("timestamp_str"))
            lbl, t_val = find_block_label_and_tension(t_sec)
            s_x.append(lbl)
            s_y.append(min(10.2, t_val + 0.35))
            who = e.get("character_name") or e.get("player_name") or "Investigador"
            loss = e.get("sanity_loss", 0)
            s_custom.append((
                "🐙 Pérdida de Cordura",
                e.get("timestamp_str", "N/D"),
                f"{who} (-{loss} COR)",
                wrap_text(e.get("description", ""), width=45),
            ))

        fig.add_trace(
            go.Scatter(
                x=s_x,
                y=s_y,
                mode="markers",
                name="Cordura & Traumas (🐙)",
                marker=dict(symbol="diamond", size=13, color="#ff4d4f", line=dict(color="#ffffff", width=1.5)),
                customdata=s_custom,
                hovertemplate=(
                    "<b>%{customdata[0]}</b> [%{customdata[1]}]<br>"
                    "<b>Afectado:</b> %{customdata[2]}<br>"
                    "<span style='color:#8b949e;'>──────────────────────────────</span><br>"
                    "%{customdata[3]}<extra></extra>"
                ),
            )
        )

    # 4. Capa de Pistas e Hitos (🔍 / 🚩)
    all_clues_milestones = (clues or []) + (milestones or [])
    if all_clues_milestones:
        c_x, c_y, c_custom = [], [], []
        for item in all_clues_milestones:
            t_sec = parse_timestamp_seconds(item.get("timestamp_seconds"), item.get("timestamp_str"))
            lbl, t_val = find_block_label_and_tension(t_sec)
            c_x.append(lbl)
            c_y.append(min(10.2, t_val + 0.35))

            is_clue = "clue_name" in item
            tag = "🔍 Pista Clave" if is_clue else "🚩 Hito Narrativo"
            name = item.get("clue_name") or item.get("title") or "Descubrimiento"
            detail = item.get("discovered_by") or item.get("milestone_type") or "Trama"

            c_custom.append((
                tag,
                item.get("timestamp_str", "N/D"),
                f"{name} ({detail})",
                wrap_text(item.get("description", ""), width=45),
            ))

        fig.add_trace(
            go.Scatter(
                x=c_x,
                y=c_y,
                mode="markers",
                name="Pistas & Hitos (🔍/🚩)",
                marker=dict(symbol="star", size=13, color="#faad14", line=dict(color="#ffffff", width=1.5)),
                customdata=c_custom,
                hovertemplate=(
                    "<b>%{customdata[0]}</b> [%{customdata[1]}]<br>"
                    "<b>Elemento:</b> %{customdata[2]}<br>"
                    "<span style='color:#8b949e;'>──────────────────────────────</span><br>"
                    "%{customdata[3]}<extra></extra>"
                ),
            )
        )

    # 5. Capa de Tiradas Críticas y Combate (🎲 / ⚔️)
    all_dice_combats = (critical_rolls or []) + (combat_events or [])
    if all_dice_combats:
        d_x, d_y, d_custom = [], [], []
        for item in all_dice_combats:
            t_sec = parse_timestamp_seconds(item.get("timestamp_seconds"), item.get("timestamp_str"))
            lbl, t_val = find_block_label_and_tension(t_sec)
            d_x.append(lbl)
            d_y.append(min(10.2, t_val + 0.35))

            is_combat = "combat_type" in item
            tag = "⚔️ Combate" if is_combat else "🎲 Tirada Crítica/Pifia"
            subject = item.get("combatants") or item.get("character_name") or item.get("player_name") or "Mesa"
            desc = item.get("description") or item.get("consequence") or item.get("outcome") or ""

            d_custom.append((
                tag,
                item.get("timestamp_str", "N/D"),
                str(subject),
                wrap_text(str(desc), width=45),
            ))

        fig.add_trace(
            go.Scatter(
                x=d_x,
                y=d_y,
                mode="markers",
                name="Tiradas & Combates (🎲/⚔️)",
                marker=dict(symbol="cross", size=12, color="#ff7a45", line=dict(color="#ffffff", width=1.5)),
                customdata=d_custom,
                hovertemplate=(
                    "<b>%{customdata[0]}</b> [%{customdata[1]}]<br>"
                    "<b>Involucrados:</b> %{customdata[2]}<br>"
                    "<span style='color:#8b949e;'>──────────────────────────────</span><br>"
                    "%{customdata[3]}<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        title="<b>Evolución del Ritmo y Tensión Dramática (con Hitos Clave)</b>",
        xaxis_title="Intervalo Temporal (Minutos)",
        yaxis_title="Nivel de Tensión (1-10)",
        yaxis=dict(range=[0, 10.8], dtick=1, gridcolor="#21262d"),
        xaxis=dict(gridcolor="#21262d"),
        paper_bgcolor="#0d1117",
        plot_bgcolor="#0d1117",
        font=dict(color="#c9d1d9"),
        hoverlabel=dict(
            bgcolor="#161b22",
            font_size=12,
            font_family="sans-serif",
            bordercolor="#30363d",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(13, 17, 23, 0.7)",
            bordercolor="#30363d",
            borderwidth=1,
        ),
        height=480,
        margin=dict(l=40, r=40, t=60, b=40),
    )

    return fig
