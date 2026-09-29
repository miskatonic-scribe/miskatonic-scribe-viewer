#!/usr/bin/env python3
"""Módulo de visualización y análisis de Inmersión y Off-Topic (Spec 17 / US4).

Analiza el clima de la mesa, el balance entre inmersión diegética y metajuego,
y destaca los momentos cualitativos de distensión y humor.
"""

from __future__ import annotations

from typing import Any
import pandas as pd
import plotly.graph_objects as go


def classify_immersion_climate(immersion_pct: float) -> tuple[str, str, str]:
    """Clasifica el clima y atmósfera de la mesa según el porcentaje de inmersión.

    Retorna:
        tuple[badge_title, description, status_tone]
    """
    if immersion_pct >= 80.0:
        return (
            "🟢 Atmósfera Inmersiva / Tensa",
            "Alta concentración interpretativa. El horror cósmico, la investigación y el suspense predominan sobre el metajuego.",
            "success",
        )
    elif immersion_pct >= 65.0:
        return (
            "🟡 Equilibrio Distendido",
            "Partida fluida y balanceada con alternancia orgánica entre suspense y momentos informales de distensión.",
            "info",
        )
    else:
        return (
            "🔴 Sesión Desenfadada / Metajuego Frecuente",
            "Predominio de momentos cómicos, consultas extensas de reglas o interrupciones frecuentes fuera de personaje.",
            "warning",
        )


def get_high_offtopic_blocks(
    metrics: list[dict[str, Any]],
    threshold: float = 20.0,
) -> list[dict[str, Any]]:
    """Extrae y ordena los bloques temporales donde el off-topic supera el umbral."""
    blocks = [b for b in metrics if b.get("off_topic_pct", 0.0) >= threshold]
    return sorted(blocks, key=lambda x: x.get("off_topic_pct", 0.0), reverse=True)


def render_offtopic_chart(metrics: list[dict[str, Any]]) -> go.Figure:
    """Genera el gráfico interactivo de área para la evolución de Off-Topic."""
    df = pd.DataFrame(metrics)
    if df.empty or "off_topic_pct" not in df.columns:
        fig = go.Figure()
        fig.update_layout(
            paper_bgcolor="#0d1117",
            plot_bgcolor="#0d1117",
            font=dict(color="#c9d1d9"),
        )
        return fig

    # Text wrap para las justificaciones en el tooltip
    wrapped_just = []
    for text in df.get("off_topic_justification", []):
        t = str(text or "")
        words = t.split(" ")
        lines = []
        cur_line: list[str] = []
        cur_len = 0
        for w in words:
            if cur_len + len(w) + 1 > 50:
                lines.append(" ".join(cur_line))
                cur_line = [w]
                cur_len = len(w)
            else:
                cur_line.append(w)
                cur_len += len(w) + 1
        if cur_line:
            lines.append(" ".join(cur_line))
        wrapped_just.append("<br>".join(lines))

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df["time_label"],
            y=df["off_topic_pct"],
            mode="lines+markers",
            fill="tozeroy",
            name="Off-Topic %",
            line=dict(color="#ffca28", width=2.5),
            fillcolor="rgba(255, 202, 40, 0.15)",
            marker=dict(size=8, color="#ffca28"),
            customdata=wrapped_just,
            hovertemplate=(
                "<b>Bloque:</b> %{x}<br>"
                "<b>Off-Topic:</b> %{y}%<br>"
                "<span style='color:#8b949e;'>──────────────────────────────</span><br>"
                "<b>Causa:</b><br>%{customdata}<extra></extra>"
            ),
        )
    )

    fig.add_hline(
        y=20,
        line_dash="dot",
        line_color="rgba(255, 152, 0, 0.6)",
        annotation_text="Alerta Distracción (>20%)",
        annotation_position="top left",
    )

    max_y = max(50.0, float(df["off_topic_pct"].max()) + 10.0) if not df.empty else 50.0

    fig.update_layout(
        title="<b>Evolución del Metajuego y Off-Topic (% por Bloque Temporal)</b>",
        xaxis_title="Intervalo Temporal",
        yaxis_title="Off-Topic (%)",
        yaxis=dict(range=[0, max_y], gridcolor="#21262d"),
        xaxis=dict(gridcolor="#21262d"),
        paper_bgcolor="#0d1117",
        plot_bgcolor="#0d1117",
        font=dict(color="#c9d1d9"),
        hoverlabel=dict(
            bgcolor="#161b22",
            bordercolor="#30363d",
            font_size=13,
            font_family="sans-serif",
            align="left",
        ),
        margin=dict(l=40, r=40, t=60, b=40),
        height=320,
    )

    return fig


def render_immersion_tab(
    st: Any,
    session: dict[str, Any],
    metrics: list[dict[str, Any]],
) -> None:
    """Renderiza la pestaña completa de Inmersión y Atmósfera de Mesa."""
    # 1. Banner Pedagógico
    st.info(
        "💡 **¿Qué mide el Índice de Inmersión?**\n\n"
        "Mide el porcentaje de tiempo que los participantes se mantienen dentro de la ficción diegética "
        "(interpretando a sus investigadores o narrando el mundo lovecraftiano). "
        "El **Off-Topic / Metajuego** agrupa conversaciones fuera de personaje: chistes, anécdotas externas, "
        "consultas mecánicas de reglas o pausas técnicas. Una buena mesa equilibra el horror cósmico con momentos naturales de distensión."
    )

    avg_off = float(session.get("average_off_topic_pct") or 0.0)
    immersion_pct = max(0.0, min(100.0, 100.0 - avg_off))
    badge_title, description, _ = classify_immersion_climate(immersion_pct)

    # 2. Métricas y Semáforo de Clima
    col_m1, col_m2, col_m3 = st.columns([1, 1, 2])
    with col_m1:
        st.metric("Índice de Inmersión", f"{immersion_pct:.1f}%")
    with col_m2:
        st.metric("Metajuego Medio", f"{avg_off:.1f}%")
    with col_m3:
        with st.container(border=True):
            st.markdown(f"**Clima de Mesa:** {badge_title}")
            st.caption(description)

    # 3. Gráfico de Evolución
    st.markdown("---")
    fig_off = render_offtopic_chart(metrics)
    st.plotly_chart(fig_off, width="stretch")

    # 4. Acordeón / Tarjetas de Momentos de Distensión y Metajuego (>20%)
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
            pct = b.get("off_topic_pct", 0)
            just = b.get("off_topic_justification", "").strip() or "Sin justificación registrada."
            with st.expander(f"⏱️ Bloque **{t_label}** — Off-Topic: {pct}%"):
                st.markdown(f"**Causa y contexto analizado:**\n\n{just}")
