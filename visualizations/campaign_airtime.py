#!/usr/bin/env python3
"""Módulo de visualización de Balance de Mesa y Protagonismo de Campaña (Spec 15 / US3).

Genera gráficos interactivos con Plotly para:
1. Donut de reparto global: Tiempo acumulado de Guardián vs Investigadores en la campaña.
2. Ranking horizontal de participación de la mesa por jugador, personaje y episodios presentes.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go


def render_campaign_airtime_charts(
    airtime_data: list[dict[str, Any]],
    campaign_name: str = "La mansión de la locura",
) -> tuple[go.Figure, go.Figure]:
    """Genera los gráficos de balance de mesa multi-sesión (Dona + Barras).

    Args:
        airtime_data: Lista de registros agregados por participante (de load_campaign_airtime):
            - player: Nombre del jugador real.
            - character: Nombre del personaje.
            - role: 'guardian' o 'investigator'.
            - total_speaking_seconds: Segundos totales hablados en la campaña.
            - episodes_present: Número de episodios en los que participó.
        campaign_name: Nombre público de la campaña.

    Returns:
        tuple[go.Figure, go.Figure]: (donut_fig, bar_fig)
    """
    if not airtime_data:
        empty_donut = go.Figure()
        empty_donut.update_layout(
            title="Sin datos de balance de mesa",
            template="plotly_dark",
            paper_bgcolor="#0d1117",
            plot_bgcolor="#161b22",
        )
        return empty_donut, empty_donut

    df = pd.DataFrame(airtime_data)
    total_campaign_seconds = df["total_speaking_seconds"].sum()
    if total_campaign_seconds <= 0:
        total_campaign_seconds = 1.0

    df["minutes"] = (df["total_speaking_seconds"] / 60.0).round(1)
    df["hours"] = (df["total_speaking_seconds"] / 3600.0).round(2)
    df["airtime_pct"] = ((df["total_speaking_seconds"] / total_campaign_seconds) * 100.0).round(1)

    # 1. Gráfico Donut: Guardián vs Investigadores
    guardian_secs = df[df["role"] == "guardian"]["total_speaking_seconds"].sum()
    investigators_secs = df[df["role"] != "guardian"]["total_speaking_seconds"].sum()

    guardian_pct = round((guardian_secs / total_campaign_seconds) * 100.0, 1)
    investigators_pct = round((investigators_secs / total_campaign_seconds) * 100.0, 1)

    donut_fig = go.Figure(
        data=[
            go.Pie(
                labels=["Guardián (DJ)", "Investigadores"],
                values=[guardian_secs, investigators_secs],
                hole=0.58,
                marker=dict(colors=["#9c27b0", "#00bcd4"], line=dict(color="#0d1117", width=2)),
                textinfo="label+percent",
                hoverinfo="label+percent+text",
                text=[
                    f"{guardian_secs / 3600:.1f}h de narración",
                    f"{investigators_secs / 3600:.1f}h de intervenciones",
                ],
                hovertemplate="<b>%{label}</b><br>Participación: %{percent}<br>Tiempo acumulado: %{text}<extra></extra>",
            )
        ]
    )

    donut_fig.update_layout(
        title=dict(
            text="<b>⚖️ Reparto Acumulado de Mesa</b><br><span style='font-size:12px; color:#8b949e;'>Guardián vs Investigadores (Campaña Completa)</span>",
            font=dict(color="#e0e6ed", size=15),
        ),
        paper_bgcolor="#0d1117",
        plot_bgcolor="#161b22",
        font=dict(color="#c9d1d9"),
        margin=dict(l=20, r=20, t=60, b=20),
        height=350,
        showlegend=False,
    )

    # 2. Gráfico de Barras Horizontal: Ranking por Participante
    df_sorted = df.sort_values("total_speaking_seconds", ascending=True)

    labels = []
    for _, row in df_sorted.iterrows():
        p = row["player"]
        c = row["character"]
        if c and c.lower() != p.lower() and c.lower() != "guardián":
            labels.append(f"{p} ({c})")
        else:
            labels.append(p)

    df_sorted["display_label"] = labels
    bar_colors = ["#9c27b0" if r == "guardian" else "#00bcd4" for r in df_sorted["role"]]

    bar_fig = go.Figure(
        go.Bar(
            x=df_sorted["airtime_pct"],
            y=df_sorted["display_label"],
            orientation="h",
            marker=dict(
                color=bar_colors,
                line=dict(color="#0d1117", width=1),
            ),
            text=df_sorted.apply(
                lambda r: f"{r['airtime_pct']}% ({r['minutes']} min • {r['episodes_present']} eps)",
                axis=1,
            ),
            textposition="auto",
            customdata=list(
                zip(
                    df_sorted["hours"],
                    df_sorted["minutes"],
                    df_sorted["episodes_present"],
                    df_sorted["role"],
                )
            ),
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Porcentaje global: <b>%{x}%</b><br>"
                "Tiempo acumulado: %{customdata[0]:.2f} horas (%{customdata[1]:.0f} min)<br>"
                "Presencia en campaña: %{customdata[2]} episodios<br>"
                "<extra></extra>"
            ),
        )
    )

    bar_fig.update_layout(
        title=dict(
            text="<b>🎙️ Protagonismo por Participante en la Campaña</b><br><span style='font-size:12px; color:#8b949e;'>Porcentaje de tiempo de habla global y minutos totales</span>",
            font=dict(color="#e0e6ed", size=15),
        ),
        xaxis=dict(
            title="Porcentaje de Habla Acumulado (%)",
            gridcolor="#21262d",
            zerolinecolor="#30363d",
            ticksuffix="%",
        ),
        yaxis=dict(
            gridcolor="#21262d",
        ),
        paper_bgcolor="#0d1117",
        plot_bgcolor="#161b22",
        font=dict(color="#c9d1d9"),
        margin=dict(l=20, r=20, t=60, b=20),
        height=350,
    )

    return donut_fig, bar_fig
