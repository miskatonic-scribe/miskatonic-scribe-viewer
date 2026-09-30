#!/usr/bin/env python3
"""Módulo de visualización y análisis de Inmersión y Clima de Mesa (Specs 17 y 21).

Analiza el clima de la mesa a escala de escena/bloque, integrando el semáforo
tricolor de atmósfera, franjas verticales cromáticas y el desglose de tiempo diegético.
"""

from __future__ import annotations

import textwrap
from typing import Any

import pandas as pd
import plotly.graph_objects as go


def get_immersion_semaphore(offtopic_pct: float) -> tuple[str, str, str]:
    """Clasifica el nivel de off-topic según el semáforo estándar de atmósfera de mesa.

    Retorna: (label, color_hex, category)
    - Verde (< 10% off-topic / > 90% inmersión): Inmersión Profunda
    - Amarillo (10% - 25% off-topic / 75% - 90% inmersión): Atmósfera Equilibrada
    - Rojo (> 25% off-topic / < 75% inmersión): Sesión Distendida
    """
    if offtopic_pct < 10.0:
        return "Inmersión Profunda", "#10b981", "verde"
    elif offtopic_pct <= 25.0:
        return "Atmósfera Equilibrada", "#f59e0b", "amarillo"
    else:
        return "Sesión Distendida", "#ef4444", "rojo"


def classify_immersion_climate(immersion_pct: float) -> tuple[str, str, str]:
    """Clasifica el clima y atmósfera de la mesa según el porcentaje de inmersión (compatibilidad).

    Retorna:
        tuple[badge_title, description, status_tone]
    """
    if immersion_pct >= 80.0:
        return (
            "🟢 Inmersión Profunda",
            "Concentración interpretativa sobresaliente. La ficción diegética y el suspense dominan absolutamente la mesa.",
            "success",
        )
    elif immersion_pct >= 65.0:
        return (
            "🟡 Atmósfera Equilibrada",
            "Partida fluida con un balance natural entre el drama de los investigadores y momentos puntuales de distensión.",
            "info",
        )
    else:
        return (
            "🔴 Sesión Distendida / Metajuego Frecuente",
            "Predominio de momentos cómicos, consultas extensas de reglas o interrupciones frecuentes fuera de personaje.",
            "warning",
        )


def get_high_offtopic_blocks(
    metrics: list[dict[str, Any]],
    threshold: float = 20.0,
) -> list[dict[str, Any]]:
    """Extrae y ordena los bloques temporales donde el off-topic supera el umbral."""
    blocks = [b for b in metrics if float(b.get("off_topic_pct", 0.0)) >= threshold]
    return sorted(blocks, key=lambda x: float(x.get("off_topic_pct", 0.0)), reverse=True)


def wrap_justification_text(text: str | None, width: int = 50) -> str:
    """Ajusta un texto largo insertando etiquetas <br> para tooltips elegantes."""
    if not text:
        return "<i>Sin justificación registrada.</i>"
    lines = textwrap.wrap(str(text).strip(), width=width)
    return "<br>".join(lines)


def render_session_immersion_chart(metrics: list[dict[str, Any]]) -> go.Figure:
    """Genera la figura interactiva de curva continua de inmersión con franjas semafóricas."""
    df = pd.DataFrame(metrics)
    if df.empty or "off_topic_pct" not in df.columns:
        fig = go.Figure()
        fig.update_layout(
            title="Sin datos de inmersión disponibles",
            paper_bgcolor="#0d1117",
            plot_bgcolor="#0d1117",
            font=dict(color="#8b949e"),
        )
        return fig

    labels = list(df["time_label"]) if "time_label" in df.columns else [f"Bloque {i+1}" for i in range(len(df))]
    off_vals = [float(v) for v in df["off_topic_pct"]] if "off_topic_pct" in df.columns else [0.0] * len(df)
    imm_vals = [max(0.0, min(100.0, 100.0 - v)) for v in off_vals]
    raw_justifications = list(df["off_topic_justification"]) if "off_topic_justification" in df.columns else [None] * len(df)
    justifications = [wrap_justification_text(j) for j in raw_justifications]

    # Clasificar cada bloque con el semáforo
    semaphores = [get_immersion_semaphore(v) for v in off_vals]
    marker_colors = [s[1] for s in semaphores]
    sem_labels = [s[0] for s in semaphores]

    custom_data = [
        [imm_vals[i], sem_labels[i], off_vals[i], justifications[i]]
        for i in range(len(df))
    ]

    fig = go.Figure()

    # 1. Franjas verticales translúcidas de semáforo por cada bloque
    for i, (_, _, cat) in enumerate(semaphores):
        if cat == "verde":
            bg_color = "rgba(16, 185, 129, 0.09)"
        elif cat == "amarillo":
            bg_color = "rgba(245, 158, 11, 0.09)"
        else:
            bg_color = "rgba(239, 68, 68, 0.09)"

        fig.add_vrect(
            x0=i - 0.5,
            x1=i + 0.5,
            fillcolor=bg_color,
            layer="below",
            line_width=0,
        )
        if i > 0:
            fig.add_vline(
                x=i - 0.5,
                line_width=1,
                line_dash="dot",
                line_color="rgba(255, 255, 255, 0.08)",
            )

    # 2. Curva continua de Inmersión Diegética (%)
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=imm_vals,
            mode="lines+markers",
            name="Inmersión Diegética",
            line=dict(color="#64ffda", width=3, shape="spline", smoothing=0.8),
            fill="tozeroy",
            fillcolor="rgba(100, 255, 218, 0.07)",
            marker=dict(
                size=10,
                color=marker_colors,
                symbol="circle",
                line=dict(color="#ffffff", width=1.5),
            ),
            customdata=custom_data,
            hovertemplate=(
                "<b>⏱️ Bloque: %{x}</b><br>"
                "🎭 Inmersión Diegética: <b>%{customdata[0]:.1f}%</b> (%{customdata[1]})<br>"
                "☕ Metajuego / Off-Topic: <b>%{customdata[2]:.1f}%</b><br>"
                "<span style='color:#8b949e;'>──────────────────────────────</span><br>"
                "<b>Contexto analizado:</b><br>%{customdata[3]}"
                "<extra></extra>"
            ),
        )
    )

    # 3. Líneas horizontales de referencia para umbrales semafóricos
    fig.add_hline(
        y=90,
        line_dash="dot",
        line_color="rgba(16, 185, 129, 0.5)",
        annotation_text="🟢 Inmersión Profunda (≥90%)",
        annotation_position="top left",
        annotation_font=dict(size=10, color="#10b981"),
    )
    fig.add_hline(
        y=75,
        line_dash="dot",
        line_color="rgba(245, 158, 11, 0.5)",
        annotation_text="🟡 Equilibrio (≥75%)",
        annotation_position="top left",
        annotation_font=dict(size=10, color="#f59e0b"),
    )

    fig.update_layout(
        title=dict(
            text="<b>Evolución del Clima de Mesa: Inmersión Diegética (%) por Escena</b>",
            font=dict(size=14, color="#e6edf3"),
            x=0.01,
            y=0.96,
        ),
        xaxis=dict(
            title="Intervalo Temporal",
            gridcolor="rgba(255, 255, 255, 0.06)",
            tickfont=dict(size=11, color="#8b949e"),
        ),
        yaxis=dict(
            title="Inmersión en la Ficción (%)",
            range=[0, 105],
            gridcolor="rgba(255, 255, 255, 0.06)",
            tickfont=dict(size=11, color="#8b949e"),
        ),
        paper_bgcolor="rgba(0, 0, 0, 0)",
        plot_bgcolor="rgba(14, 17, 23, 0.6)",
        font=dict(color="#c9d1d9"),
        hoverlabel=dict(
            bgcolor="#161b22",
            bordercolor="#30363d",
            font_size=12,
            align="left",
        ),
        margin=dict(l=40, r=40, t=55, b=45),
        height=340,
    )

    return fig


def render_session_immersion_bars(metrics: list[dict[str, Any]]) -> go.Figure:
    """Genera la figura interactiva de barras semafóricas discretas por bloque temporal."""
    df = pd.DataFrame(metrics)
    if df.empty or "off_topic_pct" not in df.columns:
        fig = go.Figure()
        fig.update_layout(title="Sin datos disponibles")
        return fig

    labels = list(df["time_label"]) if "time_label" in df.columns else [f"Bloque {i+1}" for i in range(len(df))]
    off_vals = [float(v) for v in df["off_topic_pct"]] if "off_topic_pct" in df.columns else [0.0] * len(df)
    imm_vals = [max(0.0, min(100.0, 100.0 - v)) for v in off_vals]
    raw_justifications = list(df["off_topic_justification"]) if "off_topic_justification" in df.columns else [None] * len(df)
    justifications = [wrap_justification_text(j) for j in raw_justifications]

    semaphores = [get_immersion_semaphore(v) for v in off_vals]
    bar_colors = [s[1] for s in semaphores]
    sem_labels = [s[0] for s in semaphores]

    custom_data = [
        [imm_vals[i], sem_labels[i], off_vals[i], justifications[i]]
        for i in range(len(df))
    ]

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=labels,
            y=imm_vals,
            name="Inmersión por Bloque",
            marker=dict(
                color=bar_colors,
                line=dict(color="rgba(255, 255, 255, 0.2)", width=1),
            ),
            customdata=custom_data,
            hovertemplate=(
                "<b>⏱️ Bloque: %{x}</b><br>"
                "🎭 Inmersión: <b>%{y:.1f}%</b> (%{customdata[1]})<br>"
                "☕ Off-Topic: <b>%{customdata[2]:.1f}%</b><br>"
                "<span style='color:#8b949e;'>──────────────────────────────</span><br>"
                "<b>Contexto:</b><br>%{customdata[3]}"
                "<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title=dict(
            text="<b>Distribución Semafórica de Inmersión por Bloque</b>",
            font=dict(size=14, color="#e6edf3"),
            x=0.01,
            y=0.96,
        ),
        xaxis=dict(
            title="Intervalo Temporal",
            gridcolor="rgba(255, 255, 255, 0.06)",
            tickfont=dict(size=11, color="#8b949e"),
        ),
        yaxis=dict(
            title="Inmersión (%)",
            range=[0, 105],
            gridcolor="rgba(255, 255, 255, 0.06)",
            tickfont=dict(size=11, color="#8b949e"),
        ),
        paper_bgcolor="rgba(0, 0, 0, 0)",
        plot_bgcolor="rgba(14, 17, 23, 0.6)",
        font=dict(color="#c9d1d9"),
        margin=dict(l=40, r=40, t=55, b=45),
        height=340,
    )

    return fig


# Alias para compatibilidad con código existente
render_offtopic_chart = render_session_immersion_chart


def render_immersion_tab(
    st: Any,
    session: dict[str, Any],
    metrics: list[dict[str, Any]],
) -> None:
    """Renderiza la pestaña completa de Inmersión y Atmósfera de Mesa (Spec 21)."""
    # 1. Banner Pedagógico
    st.info(
        "💡 **¿Qué mide el Índice de Inmersión?**\n\n"
        "Mide el porcentaje de tiempo que los participantes se mantienen dentro de la ficción diegética "
        "(interpretando a sus investigadores o narrando el mundo lovecraftiano). "
        "El **Metajuego y Off-Topic** agrupa conversaciones fuera de personaje: chistes, anécdotas, consultas mecánicas de reglas o pausas. "
        "Una buena mesa de rol equilibra el horror cósmico con momentos naturales de distensión."
    )

    # 2. Cálculos de Tiempos Netos y Semáforo
    duration_sec = float(session.get("duration_seconds") or 0.0)
    avg_off = float(session.get("average_off_topic_pct") or 0.0)
    immersion_pct = max(0.0, min(100.0, 100.0 - avg_off))

    badge_title, description, _ = classify_immersion_climate(immersion_pct)
    _, sem_color, _ = get_immersion_semaphore(avg_off)

    dieg_sec = duration_sec * (immersion_pct / 100.0)
    off_sec = duration_sec * (avg_off / 100.0)
    dieg_mins = round(dieg_sec / 60.0, 1)
    off_mins = round(off_sec / 60.0, 1)

    # Bloque de mayor inmersión
    best_block = None
    if metrics:
        best_block = min(metrics, key=lambda m: float(m.get("off_topic_pct", 100.0)))

    # 3. Panel Superior con Métricas y KPIs
    col_k1, col_k2, col_k3, col_k4 = st.columns([1.1, 1.1, 1.1, 1.5])
    with col_k1:
        st.metric(
            "Índice de Inmersión",
            f"{immersion_pct:.1f}%",
            help="Porcentaje medio de la sesión transcurrido dentro de la ficción interpretativa.",
        )
    with col_k2:
        st.metric(
            "Tiempo en Ficción",
            f"{dieg_mins} min",
            help="Minutos netos calculados dentro de personaje.",
        )
    with col_k3:
        st.metric(
            "Metajuego / Risas",
            f"{off_mins} min",
            help="Minutos netos dedicados a bromas, dudas de reglas o pausas informales.",
        )
    with col_k4:
        with st.container(border=True):
            st.markdown(f"**Clima de Mesa:** <span style='color:{sem_color}; font-weight:600;'>{badge_title}</span>", unsafe_allow_html=True)
            st.caption(description)

    st.markdown("---")

    # 4. Selector de Modo de Gráfico y Renderizado
    chart_col1, _ = st.columns([1.5, 1.0])
    with chart_col1:
        view_mode = st.radio(
            "Modo de Visualización de Atmósfera",
            options=["📈 Curva Continua con Franjas de Clima", "📊 Barras Semafóricas por Escena"],
            horizontal=True,
            key="session_immersion_view_mode",
            help="Elige si ver la curva suave con zonas de semáforo de fondo o las barras discretas coloreadas.",
        )

    if view_mode.startswith("📈"):
        fig = render_session_immersion_chart(metrics)
    else:
        fig = render_session_immersion_bars(metrics)

    st.plotly_chart(fig, width="stretch")

    # 5. Bloque de Clímax y Momentos de Mayor Distensión (>20%)
    high_blocks = get_high_offtopic_blocks(metrics, threshold=20.0)
    st.markdown("---")
    st.subheader("☕ Momentos de Mayor Distensión y Pausas de Mesa")

    if not high_blocks:
        st.success("✨ **¡Concentración sobresaliente!** Ningún bloque temporal superó el 20% de metajuego o distracción.")
    else:
        st.caption(
            f"Se detectaron **{len(high_blocks)} bloque(s)** donde el metajuego o distracción superó el umbral del 20%:"
        )
        for b in high_blocks:
            t_label = b.get("time_label", "Intervalo")
            pct = float(b.get("off_topic_pct", 0.0))
            just = str(b.get("off_topic_justification", "")).strip() or "Sin justificación registrada."
            _, b_color, _ = get_immersion_semaphore(pct)

            with st.expander(f"⏱️ Bloque **{t_label}** — Off-Topic: {pct:.0f}%"):
                st.markdown(
                    f"**Nivel de Distensión:** <span style='color:{b_color}; font-weight:600;'>{pct:.0f}% metajuego</span> • "
                    f"Inmersión restante: **{100 - pct:.0f}%**\n\n"
                    f"**Contexto y justificación analizada:**\n\n{just}",
                    unsafe_allow_html=True,
                )
