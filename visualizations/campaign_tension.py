#!/usr/bin/env python3
"""Módulo de visualización de la Gran Curva de Tensión de Campaña (Spec 15 / US2).

Genera un gráfico continuo con Plotly que une los bloques dramáticos de todos
los episodios de una campaña, destacando los clímax y delimitando los episodios.
"""

from __future__ import annotations

import textwrap
from typing import Any

import pandas as pd
import plotly.graph_objects as go


def wrap_text(text: str, width: int = 50) -> str:
    """Ajusta un texto largo insertando saltos <br> para tooltips elegantes."""
    if not text:
        return ""
    lines = textwrap.wrap(str(text), width=width)
    return "<br>".join(lines)


def get_tension_color(val: float) -> str:
    """Devuelve el color semántico según el nivel de tensión dramática."""
    if val <= 0:
        return "#8b949e"  # Gris ceniza (no evaluado)
    elif val <= 3:
        return "#26a69a"  # Verde azulado (Tensión baja / investigación)
    elif val <= 6:
        return "#ffa726"  # Ámbar (Tensión media / sospecha)
    elif val <= 8:
        return "#ff7043"  # Naranja intenso (Peligro / amenaza)
    return "#e53935"      # Rojo Carmesí (Horror Cósmico / clímax)


def render_campaign_tension_chart(
    tension_data: dict[str, Any],
    campaign_name: str = "La mansión de la locura",
) -> go.Figure:
    """Construye la Gran Curva de Tensión Continua Multi-Episodio para una campaña.

    Args:
        tension_data: Diccionario retornado por load_campaign_tension_continuous con:
            - 'blocks': lista de bloques de tensión con timestamps continuos.
            - 'boundaries': lista de episodios con su tiempo de inicio y duración.
            - 'total_duration_seconds': duración total acumulada.
        campaign_name: Nombre público de la campaña.

    Returns:
        go.Figure: Gráfico interactivo de Plotly listo para renderizar con st.plotly_chart.
    """
    blocks = tension_data.get("blocks", [])
    boundaries = tension_data.get("boundaries", [])

    if not blocks:
        fig = go.Figure()
        fig.update_layout(
            title="Sin datos de tensión disponibles para esta campaña",
            template="plotly_dark",
            paper_bgcolor="#0d1117",
            plot_bgcolor="#161b22",
        )
        return fig

    df = pd.DataFrame(blocks)
    point_colors = [get_tension_color(t) for t in df["tension"]]
    point_sizes = [10 if t >= 8 else 7 for t in df["tension"]]

    wrapped_just = [wrap_text(j, width=50) for j in df["justification"]]

    fig = go.Figure()

    # 1. Bandas de alternancia por episodio en el fondo
    for idx, b in enumerate(boundaries):
        start_h = b["start_hour"]
        end_h = start_h + b["duration_hours"]
        # Alternar tinte de fondo muy sutil para delimitar visualmente cada sesión
        if idx % 2 == 1:
            fig.add_vrect(
                x0=start_h,
                x1=end_h,
                fillcolor="rgba(88, 166, 255, 0.03)",
                layer="below",
                line_width=0,
            )

    # 2. Área sombreada y línea continua de tensión
    fig.add_trace(
        go.Scatter(
            x=df["global_mid_hours"],
            y=df["tension"],
            mode="lines",
            line=dict(color="#ff7043", width=2.5, shape="spline", smoothing=0.7),
            fill="tozeroy",
            fillcolor="rgba(255, 112, 67, 0.08)",
            name="Tensión Dramática",
            hoverinfo="skip",
        )
    )

    # 3. Puntos de escena interactivos con tooltip detallado
    fig.add_trace(
        go.Scatter(
            x=df["global_mid_hours"],
            y=df["tension"],
            mode="markers",
            marker=dict(
                size=point_sizes,
                color=point_colors,
                line=dict(width=1.5, color="#0d1117"),
            ),
            name="Escenas",
            customdata=list(
                zip(
                    df["time_label"],
                    df["tension"],
                    wrapped_just,
                    df["off_topic_pct"],
                )
            ),
            hovertemplate=(
                "<b>🎬 %{customdata[0]}</b><br>"
                "⚡ <b>Tensión:</b> %{customdata[1]}/10<br>"
                "☕ <b>Off-Topic:</b> %{customdata[3]}%<br>"
                "⏱️ <b>Tiempo acumulado:</b> %{x:.2f}h<br>"
                "<hr style='margin:4px 0;'>"
                "<i>%{customdata[2]}</i>"
                "<extra></extra>"
            ),
        )
    )

    # 4. Líneas divisorias de episodios y etiquetas de cabecera
    for idx, b in enumerate(boundaries):
        start_h = b["start_hour"]
        ep_num = b["episode_order"]
        dur_h = b["duration_hours"]

        # Línea divisoria vertical entre episodios (excepto el inicio en 0)
        if start_h > 0:
            fig.add_vline(
                x=start_h,
                line_width=1.5,
                line_dash="dot",
                line_color="rgba(88, 166, 255, 0.4)",
            )

        # Etiqueta de episodio centrada en su tramo
        mid_ep_h = start_h + (dur_h / 2.0)
        fig.add_annotation(
            x=mid_ep_h,
            y=10.2,
            text=f"<b>Ep. {ep_num}</b>",
            showarrow=False,
            font=dict(size=11, color="#58a6ff"),
            bgcolor="rgba(22, 27, 34, 0.85)",
            bordercolor="rgba(48, 54, 61, 0.8)",
            borderwidth=1,
            borderpad=3,
        )

    # 5. Línea de referencia de peligro (Tensión = 7)
    fig.add_hline(
        y=7,
        line_dash="dash",
        line_color="rgba(255, 112, 67, 0.25)",
        annotation_text="Umbral de Peligro (7/10)",
        annotation_position="bottom right",
        annotation_font=dict(size=10, color="#ff7043"),
    )

    total_hours = tension_data.get("total_duration_seconds", 0.0) / 3600.0

    fig.update_layout(
        title=dict(
            text=f"📈 La Gran Curva de Tensión — {campaign_name} ({len(boundaries)} episodios • {total_hours:.1f}h totales)",
            font=dict(size=16, color="#e0e6ed"),
        ),
        xaxis=dict(
            title="Línea de Tiempo Continua de la Campaña (Horas acumuladas)",
            gridcolor="#21262d",
            zerolinecolor="#30363d",
            showline=True,
            linecolor="#30363d",
            tickformat=".1f",
            ticksuffix="h",
            range=[-0.1, total_hours + 0.2],
        ),
        yaxis=dict(
            title="Nivel de Tensión Dramática (1-10)",
            range=[0, 11],
            gridcolor="#21262d",
            zerolinecolor="#30363d",
            showline=True,
            linecolor="#30363d",
            tickmode="linear",
            tick0=1,
            dtick=2,
        ),
        template="plotly_dark",
        paper_bgcolor="#0d1117",
        plot_bgcolor="#161b22",
        hoverlabel=dict(
            bgcolor="#161b22",
            font_size=12,
            font_color="#e0e6ed",
            bordercolor="#30363d",
        ),
        margin=dict(l=50, r=30, t=60, b=50),
        height=450,
        showlegend=False,
    )

    return fig
