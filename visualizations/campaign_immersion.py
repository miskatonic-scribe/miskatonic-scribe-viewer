#!/usr/bin/env python3
"""Módulo de macro-métricas de inmersión y atmósfera de campaña (Spec 18).

Calcula y visualiza la evolución del clima de mesa y metajuego a lo largo de
todos los capítulos de una aventura, integrando franjas semafóricas y comparativas.
"""

from __future__ import annotations

import textwrap
from typing import Any

import plotly.graph_objects as go


def get_immersion_semaphore(offtopic_pct: float) -> tuple[str, str, str]:
    """Clasifica el nivel de off-topic según el semáforo de clima de mesa.

    Retorna: (label, color_hex, category)
    - Verde (< 10%): Inmersión Profunda
    - Amarillo (10% - 25%): Atmósfera Equilibrada
    - Rojo (> 25%): Sesión Distendida / Metajuego
    """
    if offtopic_pct < 10.0:
        return "Inmersión Profunda", "#10b981", "verde"
    elif offtopic_pct <= 25.0:
        return "Atmósfera Equilibrada", "#f59e0b", "amarillo"
    else:
        return "Sesión Distendida", "#ef4444", "rojo"


def build_campaign_immersion_data(
    campaign_sessions: list[dict[str, Any]],
    continuous_blocks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Calcula las métricas de inmersión agregadas y la serie temporal de campaña.

    Args:
        campaign_sessions: Lista de diccionarios de sesiones con episode_order,
                           duration_seconds, average_off_topic_pct y title.
        continuous_blocks: Lista opcional de bloques de escenas concatenados
                           con start_time, end_time y off_topic_pct.

    Returns:
        dict con métricas por episodio, agregados globales y límites temporales.
    """
    if not campaign_sessions:
        return {
            "episodes": [],
            "overall_immersion_pct": 0.0,
            "overall_offtopic_pct": 0.0,
            "semaphore_label": "Sin Datos",
            "semaphore_color": "#8b949e",
            "semaphore_category": "desconocido",
            "most_immersive": None,
            "most_distracted": None,
            "counts": {"verde": 0, "amarillo": 0, "rojo": 0},
            "total_duration_hours": 0.0,
            "blocks": [],
            "boundaries": [],
        }

    # Ordenar sesiones cronológicamente por episode_order
    sorted_sessions = sorted(
        campaign_sessions,
        key=lambda s: (
            s.get("episode_order") if s.get("episode_order") is not None else 9999,
            s.get("analyzed_at") or "",
        ),
    )

    episodes_data: list[dict[str, Any]] = []
    boundaries: list[dict[str, Any]] = []
    cum_seconds = 0.0
    total_offtopic_weighted = 0.0
    total_duration = 0.0

    counts = {"verde": 0, "amarillo": 0, "rojo": 0}

    for idx, s in enumerate(sorted_sessions):
        ep_order = s.get("episode_order") or (idx + 1)
        dur = float(s.get("duration_seconds") or 0.0)
        off_pct = float(s.get("average_off_topic_pct") or 0.0)
        imm_pct = max(0.0, min(100.0, 100.0 - off_pct))

        label, color, category = get_immersion_semaphore(off_pct)
        counts[category] += 1

        start_h = cum_seconds / 3600.0
        end_h = (cum_seconds + dur) / 3600.0

        ep_info = {
            "session_id": s.get("id"),
            "episode_order": ep_order,
            "title": s.get("title") or f"Episodio {ep_order}",
            "duration_seconds": dur,
            "duration_hours": dur / 3600.0,
            "start_hours": start_h,
            "end_hours": end_h,
            "offtopic_pct": off_pct,
            "immersion_pct": imm_pct,
            "semaphore_label": label,
            "semaphore_color": color,
            "semaphore_category": category,
        }
        episodes_data.append(ep_info)

        boundaries.append({
            "episode_order": ep_order,
            "session_id": s.get("id"),
            "title": ep_info["title"],
            "start_hours": start_h,
            "end_hours": end_h,
            "semaphore_color": color,
            "semaphore_category": category,
            "offtopic_pct": off_pct,
        })

        total_offtopic_weighted += off_pct * dur
        total_duration += dur
        cum_seconds += dur

    # Agregados globales ponderados
    overall_offtopic = (total_offtopic_weighted / total_duration) if total_duration > 0 else 0.0
    overall_immersion = max(0.0, min(100.0, 100.0 - overall_offtopic))
    g_label, g_color, g_cat = get_immersion_semaphore(overall_offtopic)

    # Identificar episodios extremos
    most_immersive = min(episodes_data, key=lambda e: e["offtopic_pct"]) if episodes_data else None
    most_distracted = max(episodes_data, key=lambda e: e["offtopic_pct"]) if episodes_data else None

    # Procesar bloques continuos si se proporcionan
    processed_blocks = []
    if continuous_blocks:
        processed_blocks = continuous_blocks

    return {
        "episodes": episodes_data,
        "overall_immersion_pct": round(overall_immersion, 1),
        "overall_offtopic_pct": round(overall_offtopic, 1),
        "semaphore_label": g_label,
        "semaphore_color": g_color,
        "semaphore_category": g_cat,
        "most_immersive": most_immersive,
        "most_distracted": most_distracted,
        "counts": counts,
        "total_duration_hours": round(total_duration / 3600.0, 1),
        "boundaries": boundaries,
        "blocks": processed_blocks,
    }


def render_campaign_immersion_timeline(
    immersion_data: dict[str, Any],
    campaign_name: str = "Aventura",
) -> go.Figure:
    """Construye la macro-gráfica continua de inmersión con franjas de semáforo.

    Args:
        immersion_data: Diccionario retornado por build_campaign_immersion_data.
        campaign_name: Nombre de la campaña para el encabezado.

    Returns:
        go.Figure: Gráfico Plotly listo para renderizar.
    """
    boundaries = immersion_data.get("boundaries", [])
    episodes = immersion_data.get("episodes", [])
    blocks = immersion_data.get("blocks", [])

    fig = go.Figure()

    if not boundaries and not episodes:
        fig.update_layout(
            title="Sin datos de inmersión disponibles para esta campaña",
            paper_bgcolor="#0e1117",
            plot_bgcolor="#0e1117",
            font_color="#8b949e",
        )
        return fig

    # 1. Franjas verticales de semáforo por capítulo
    for b in boundaries:
        start_h = b["start_hours"]
        end_h = b["end_hours"]
        cat = b["semaphore_category"]

        # Color de fondo traslúcido para no molestar la visibilidad
        if cat == "verde":
            bg_color = "rgba(16, 185, 129, 0.09)"
        elif cat == "amarillo":
            bg_color = "rgba(245, 158, 11, 0.09)"
        else:
            bg_color = "rgba(239, 68, 68, 0.09)"

        fig.add_vrect(
            x0=start_h,
            x1=end_h,
            fillcolor=bg_color,
            layer="below",
            line_width=0,
        )

        # Línea divisoria al final de cada episodio
        fig.add_vline(
            x=end_h,
            line_width=1,
            line_dash="dot",
            line_color="rgba(255, 255, 255, 0.15)",
        )

    # 2. Curva continua: si hay bloques de escenas detallados se trazan
    if blocks:
        x_vals = [b.get("global_mid_hours", 0.0) for b in blocks]
        y_offtopic = [float(b.get("off_topic_pct", 0.0)) for b in blocks]
        y_immersion = [max(0.0, 100.0 - val) for val in y_offtopic]
        labels = [b.get("time_label", "") for b in blocks]

        hover_texts = [
            f"<b>{lbl}</b><br>Inmersión: <b>{imm:.1f}%</b><br>Off-Topic: {off:.1f}%"
            for lbl, imm, off in zip(labels, y_immersion, y_offtopic)
        ]

        fig.add_trace(
            go.Scatter(
                x=x_vals,
                y=y_immersion,
                mode="lines",
                name="Inmersión en Escena",
                line=dict(color="#64ffda", width=2, shape="spline"),
                hoverinfo="text",
                hovertext=hover_texts,
            )
        )
    else:
        # Fallback: puntos centrales por episodio conectados suavemente
        x_pts = [(e["start_hours"] + e["end_hours"]) / 2.0 for e in episodes]
        y_pts = [e["immersion_pct"] for e in episodes]
        hover_texts = [
            f"<b>Ep. {e['episode_order']}: {e['title']}</b><br>Inmersión: <b>{e['immersion_pct']:.1f}%</b> ({e['semaphore_label']})<br>Off-Topic: {e['offtopic_pct']:.1f}%"
            for e in episodes
        ]

        fig.add_trace(
            go.Scatter(
                x=x_pts,
                y=y_pts,
                mode="lines+markers",
                name="Inmersión por Capítulo",
                line=dict(color="#64ffda", width=2.5, shape="spline"),
                marker=dict(
                    size=10,
                    color=[e["semaphore_color"] for e in episodes],
                    line=dict(color="#ffffff", width=1.5),
                ),
                hoverinfo="text",
                hovertext=hover_texts,
            )
        )

    # 3. Líneas de referencia horizontales
    fig.add_hline(
        y=90.0,
        line_dash="dash",
        line_color="rgba(16, 185, 129, 0.4)",
        annotation_text="Umbral Inmersión Profunda (≥90%)",
        annotation_position="top right",
        annotation_font=dict(color="#10b981", size=10),
    )
    fig.add_hline(
        y=75.0,
        line_dash="dash",
        line_color="rgba(239, 68, 68, 0.4)",
        annotation_text="Alerta Metajuego (<75%)",
        annotation_position="bottom right",
        annotation_font=dict(color="#ef4444", size=10),
    )

    # 4. Anotaciones de encabezado de episodio en el eje superior
    for b in boundaries:
        mid_x = (b["start_hours"] + b["end_hours"]) / 2.0
        fig.add_annotation(
            x=mid_x,
            y=105,
            text=f"<b>Ep. {b['episode_order']}</b>",
            showarrow=False,
            font=dict(size=11, color="#94a3b8"),
            yanchor="bottom",
        )

    max_hours = max((b["end_hours"] for b in boundaries), default=1.0)
    fig.update_layout(
        title=dict(
            text=f"🎭 Evolución Continua de Inmersión — {campaign_name}",
            font=dict(size=16, color="#e0e6ed"),
        ),
        xaxis=dict(
            title="Línea Temporal de la Aventura (Horas acumuladas)",
            gridcolor="#21262d",
            zerolinecolor="#21262d",
            range=[0, max_hours * 1.02],
        ),
        yaxis=dict(
            title="Índice de Inmersión (%)",
            gridcolor="#21262d",
            zerolinecolor="#21262d",
            range=[0, 115],
            tickmode="linear",
            tick0=0,
            dtick=20,
        ),
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        font=dict(family="sans-serif", color="#8b949e"),
        height=420,
        margin=dict(l=50, r=30, t=75, b=45),
        showlegend=False,
    )

    return fig


def render_campaign_immersion_bars(immersion_data: dict[str, Any]) -> go.Figure:
    """Genera la comparativa en barras del % de Off-Topic por episodio con semáforo.

    Args:
        immersion_data: Diccionario con la lista de 'episodes'.

    Returns:
        go.Figure: Gráfico de barras interactivo de Plotly.
    """
    episodes = immersion_data.get("episodes", [])
    fig = go.Figure()

    if not episodes:
        fig.update_layout(
            title="Sin episodios disponibles para comparar",
            paper_bgcolor="#0e1117",
            plot_bgcolor="#0e1117",
            font_color="#8b949e",
        )
        return fig

    x_labels = [f"Ep. {e['episode_order']}" for e in episodes]
    y_vals = [e["offtopic_pct"] for e in episodes]
    colors = [e["semaphore_color"] for e in episodes]
    text_labels = [f"{val:.1f}%" for val in y_vals]

    hover_texts = [
        f"<b>Ep. {e['episode_order']}: {e['title']}</b><br>"
        f"Off-Topic: <b>{e['offtopic_pct']:.1f}%</b><br>"
        f"Inmersión: <b>{e['immersion_pct']:.1f}%</b><br>"
        f"Clima: <i>{e['semaphore_label']}</i>"
        for e in episodes
    ]

    fig.add_trace(
        go.Bar(
            x=x_labels,
            y=y_vals,
            text=text_labels,
            textposition="outside",
            textfont=dict(color="#e0e6ed", size=11),
            marker=dict(
                color=colors,
                line=dict(color="rgba(255, 255, 255, 0.15)", width=1),
                opacity=0.88,
            ),
            hoverinfo="text",
            hovertext=hover_texts,
            name="Off-Topic (%)",
        )
    )

    # Líneas de referencia
    fig.add_hline(
        y=10.0,
        line_dash="dot",
        line_color="#10b981",
        annotation_text="Límite Inmersión Profunda (10%)",
        annotation_position="top left",
        annotation_font=dict(color="#10b981", size=10),
    )
    fig.add_hline(
        y=25.0,
        line_dash="dot",
        line_color="#ef4444",
        annotation_text="Límite Metajuego Elevado (25%)",
        annotation_position="top left",
        annotation_font=dict(color="#ef4444", size=10),
    )

    max_y = max(y_vals) if y_vals else 20.0
    fig.update_layout(
        title=dict(
            text="⚖️ Desconexión / Off-Topic por Capítulo (% de tiempo fuera de rol)",
            font=dict(size=15, color="#e0e6ed"),
        ),
        xaxis=dict(
            gridcolor="#21262d",
            zerolinecolor="#21262d",
        ),
        yaxis=dict(
            title="Off-Topic (%)",
            gridcolor="#21262d",
            zerolinecolor="#21262d",
            range=[0, max(30.0, max_y * 1.25)],
        ),
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        font=dict(family="sans-serif", color="#8b949e"),
        height=360,
        margin=dict(l=45, r=30, t=55, b=40),
        showlegend=False,
    )

    return fig


def render_campaign_immersion_tab(
    st_module: Any,
    immersion_data: dict[str, Any],
    campaign_name: str = "Aventura",
) -> None:
    """Renderiza el contenido visual completo de la pestaña de atmósfera en Streamlit.

    Args:
        st_module: Módulo streamlit ('st').
        immersion_data: Diccionario retornado por build_campaign_immersion_data.
        campaign_name: Nombre público de la campaña.
    """
    st = st_module

    if not immersion_data.get("episodes"):
        st.info("No hay datos analíticos de atmósfera disponibles para esta aventura.")
        return

    # Callout pedagógico
    st.markdown(
        """
        <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.08); padding: 12px 16px; border-radius: 8px; margin-bottom: 20px;">
            <b style="color: #64ffda;">🎭 ¿Cómo se evalúa la Atmósfera de la Aventura?</b>
            <p style="color: #94a3b8; margin: 4px 0 0 0; font-size: 0.92rem; line-height: 1.45;">
                El <b>Índice de Inmersión</b> mide el porcentaje de tiempo que la mesa permanece concentrada en el universo de juego vs. interrupciones de metajuego (chistes, reglas, anécdotas personales o pausas operativas).
                El semáforo clasifica cada capítulo en 
                <span style="color: #10b981; font-weight: 600;">🟢 Inmersión Profunda (&lt;10% off-topic)</span>, 
                <span style="color: #f59e0b; font-weight: 600;">🟡 Atmósfera Equilibrada (10-25%)</span> o 
                <span style="color: #ef4444; font-weight: 600;">🔴 Sesión Distendida (&gt;25%)</span>.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Fila de KPIs de Campaña
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    ov_imm = immersion_data.get("overall_immersion_pct", 0.0)
    ov_off = immersion_data.get("overall_offtopic_pct", 0.0)
    sem_label = immersion_data.get("semaphore_label", "")
    sem_color = immersion_data.get("semaphore_color", "#8b949e")

    with kpi1:
        st.metric(
            label="🎭 Inmersión Media Global",
            value=f"{ov_imm:.1f}%",
            delta=f"{ov_off:.1f}% off-topic",
            delta_color="inverse",
            help="Promedio ponderado por la duración de todos los episodios.",
        )
        st.markdown(
            f"<div style='font-size: 0.85rem; color: {sem_color}; font-weight: 600; margin-top: -8px;'>● {sem_label}</div>",
            unsafe_allow_html=True,
        )

    most_imm = immersion_data.get("most_immersive")
    with kpi2:
        if most_imm:
            st.metric(
                label="🕯️ Capítulo Más Inmersivo",
                value=f"Ep. {most_imm['episode_order']}",
                delta=f"{most_imm['immersion_pct']:.1f}% inmersión",
                help=f"{most_imm['title']} con solo {most_imm['offtopic_pct']:.1f}% de metajuego.",
            )
            st.caption(f"_{most_imm['title'][:28]}…_" if len(most_imm['title']) > 28 else f"_{most_imm['title']}_")
        else:
            st.metric(label="🕯️ Capítulo Más Inmersivo", value="—")

    most_dist = immersion_data.get("most_distracted")
    with kpi3:
        if most_dist:
            st.metric(
                label="🎪 Capítulo Más Distendido",
                value=f"Ep. {most_dist['episode_order']}",
                delta=f"{most_dist['offtopic_pct']:.1f}% off-topic",
                delta_color="inverse",
                help=f"{most_dist['title']} con {most_dist['offtopic_pct']:.1f}% de tiempo fuera de rol.",
            )
            st.caption(f"_{most_dist['title'][:28]}…_" if len(most_dist['title']) > 28 else f"_{most_dist['title']}_")
        else:
            st.metric(label="🎪 Capítulo Más Distendido", value="—")

    counts = immersion_data.get("counts", {})
    with kpi4:
        st.metric(
            label="🚥 Balance de Sesiones",
            value=f"{counts.get('verde', 0)} / {len(immersion_data.get('episodes', []))}",
            help="Episodios con Inmersión Profunda (verde) sobre el total.",
        )
        st.markdown(
            f"<div style='font-size: 0.85rem; color: #94a3b8; margin-top: -6px;'>"
            f"<span style='color: #10b981;'>● {counts.get('verde', 0)}</span> &nbsp; "
            f"<span style='color: #f59e0b;'>● {counts.get('amarillo', 0)}</span> &nbsp; "
            f"<span style='color: #ef4444;'>● {counts.get('rojo', 0)}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)

    # Visualización 1: Macro-gráfica continua con bandas semafóricas
    st.subheader("📈 Macro-Evolución Temporal del Clima de Juego")
    fig_timeline = render_campaign_immersion_timeline(immersion_data, campaign_name)
    st.plotly_chart(fig_timeline, width="stretch")

    # Visualización 2: Comparativa de barras
    st.subheader("📊 Comparativa de Desconexión por Capítulo")
    fig_bars = render_campaign_immersion_bars(immersion_data)
    st.plotly_chart(fig_bars, width="stretch")
