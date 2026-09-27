#!/usr/bin/env python3
"""Dashboard analítico interactivo para Miskatonic Scribe (Fase 8).

Aplicación web en Streamlit que lee desde partidas.db y renderiza
gráficos interactivos con Plotly para la Curva de Tensión Dramática,
el Airtime Ratio (Guardián vs Investigadores) y el Índice de Off-Topic.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

# Asegurar que la raíz del proyecto esté en sys.path (compatible tanto en dev como en dist/viewer)
_PARENT = Path(__file__).resolve().parent
_PROJECT_ROOT = _PARENT if (_PARENT / "core").exists() else _PARENT.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

try:
    from dashboard.visualizations.swimlane import (
        build_speaker_metadata,
        get_participant_label,
        render_swimlane_chart,
    )
except ImportError:
    from visualizations.swimlane import (
        build_speaker_metadata,
        get_participant_label,
        render_swimlane_chart,
    )

from core import paths

ROOT = paths.ROOT
DB_PATH = paths.DB_PATH

st.set_page_config(
    page_title="Miskatonic Scribe — Analíticas de Partidas",
    page_icon="🐙",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Estilo visual inmersivo (Lovecraftian theme)
st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #e0e6ed;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #8b9bb4;
        margin-bottom: 1.5rem;
    }
    .kpi-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }
    .kpi-val {
        font-size: 1.8rem;
        font-weight: bold;
        color: #58a6ff;
    }
    .kpi-label {
        font-size: 0.9rem;
        color: #8b949e;
    }
    img {
        border-radius: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_db_connection() -> sqlite3.Connection:
    """Conexión a la base de datos SQLite."""
    conn = sqlite3.connect(f"file:{DB_PATH.resolve()}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@st.cache_data
def load_available_sessions() -> list[dict[str, Any]]:
    """Obtiene la lista de sesiones disponibles en partidas.db con sus metadatos."""
    if not DB_PATH.exists():
        return []
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, title, channel, url, thumbnail_path, like_count, comment_count,
               duration_seconds, analyzed_at, model
        FROM sessions
        ORDER BY analyzed_at DESC
        """
    )
    rows = cursor.fetchall()
    return [dict(r) for r in rows]


@st.cache_data
def load_session_details(session_id: str) -> dict[str, Any] | None:
    """Carga todos los datos de una partida: sesión, participantes y métricas."""
    if not DB_PATH.exists():
        return None
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Sesión
    cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
    s_row = cursor.fetchone()
    if not s_row:
        return None
    session = dict(s_row)

    # 2. Personajes / Participantes
    cursor.execute("SELECT * FROM characters WHERE session_id = ? ORDER BY airtime_pct DESC", (session_id,))
    characters = [dict(r) for r in cursor.fetchall()]

    # 3. Métricas por bloque temporal
    cursor.execute("SELECT * FROM scene_metrics WHERE session_id = ? ORDER BY block_index ASC", (session_id,))
    scene_metrics = [dict(r) for r in cursor.fetchall()]

    return {
        "session": session,
        "characters": characters,
        "metrics": scene_metrics,
    }


@st.cache_data
def load_session_dialogs(session_id: str) -> list[dict[str, Any]]:
    """Carga los diálogos normalizados con marcas de tiempo para la sesión."""
    dialogs_file = paths.get_normalized_dialogs_path(session_id)
    if not dialogs_file.exists():
        return []
    with open(dialogs_file, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_sanity_events(session_id: str) -> list[dict[str, Any]]:
    """Carga los eventos de cordura registrados para una partida ordenados cronológicamente."""
    if not DB_PATH.exists():
        return []
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT session_id, block_index, timestamp_seconds, timestamp_str,
               character_name, player_name, trigger_cause, sanity_loss, consequence
        FROM sanity_events
        WHERE session_id = ?
        ORDER BY timestamp_seconds ASC, id ASC
        """,
        (session_id,),
    )
    return [dict(r) for r in cursor.fetchall()]


@st.cache_data
def load_clues(session_id: str) -> list[dict[str, Any]]:
    """Carga las pistas descubiertas registradas para una partida ordenadas cronológicamente."""
    if not DB_PATH.exists():
        return []
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT session_id, block_index, timestamp_seconds, timestamp_str,
               character_name, player_name, clue_text, source_skill, importance
        FROM clues
        WHERE session_id = ?
        ORDER BY timestamp_seconds ASC, id ASC
        """,
        (session_id,),
    )
    return [dict(r) for r in cursor.fetchall()]


@st.cache_data
def load_milestones(session_id: str) -> list[dict[str, Any]]:
    """Carga los hitos narrativos registrados para una partida ordenados cronológicamente."""
    if not DB_PATH.exists():
        return []
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT session_id, block_index, timestamp_seconds, timestamp_str,
               title, description, phase
        FROM narrative_milestones
        WHERE session_id = ?
        ORDER BY timestamp_seconds ASC, id ASC
        """,
        (session_id,),
    )
    return [dict(r) for r in cursor.fetchall()]


@st.cache_data
def load_critical_rolls(session_id: str) -> list[dict[str, Any]]:
    """Carga las tiradas críticas, forzadas y pifias registradas para una partida ordenadas cronológicamente."""
    if not DB_PATH.exists():
        return []
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT session_id, block_index, timestamp_seconds, timestamp_str,
               character_name, player_name, skill, roll_type, outcome, consequence
        FROM critical_rolls
        WHERE session_id = ?
        ORDER BY timestamp_seconds ASC, id ASC
        """,
        (session_id,),
    )
    return [dict(r) for r in cursor.fetchall()]


@st.cache_data
def load_combat_events(session_id: str) -> list[dict[str, Any]]:
    """Carga los eventos de combate y letalidad física registrados para una partida ordenados cronológicamente."""
    if not DB_PATH.exists():
        return []
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT session_id, block_index, timestamp_seconds, timestamp_str,
               character_name, player_name, source, severity, details
        FROM combat_events
        WHERE session_id = ?
        ORDER BY timestamp_seconds ASC, id ASC
        """,
        (session_id,),
    )
    return [dict(r) for r in cursor.fetchall()]


import textwrap

def wrap_text(text: str, width: int = 55) -> str:
    """Ajusta un texto largo insertando etiquetas <br> para tooltips elegantes."""
    if not text:
        return ""
    lines = textwrap.wrap(str(text), width=width)
    return "<br>".join(lines)


def render_tension_chart(metrics: list[dict[str, Any]]) -> go.Figure:
    """Genera la Curva de Tensión Dramática con Plotly con tooltips enriquecidos."""
    df = pd.DataFrame(metrics)
    df["minute_mark"] = df["start_time"] / 60

    # Paleta de colores para tensión según severidad
    def get_color(val: int) -> str:
        if val <= 0:
            return "#8b949e"  # Gris ceniza (Error de análisis LLM / no evaluado)
        elif val <= 3:
            return "#26a69a"  # Verde (Baja)
        elif val <= 6:
            return "#ffa726"  # Ámbar (Media)
        elif val <= 8:
            return "#ff7043"  # Naranja intenso (Peligro)
        return "#e53935"      # Rojo Carmesí (Horror Cósmico)

    point_colors = [get_color(t) for t in df["tension"]]

    # Textos formateados con ancho fijo para evitar cuadros gigantescos
    wrapped_just = [wrap_text(t, width=55) for t in df["tension_justification"]]
    wrapped_story = [wrap_text(s, width=55) for s in df["story_state"]]

    fig = go.Figure()

    # Líneas de umbral de referencia
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

    # Línea de tensión continua
    fig.add_trace(
        go.Scatter(
            x=df["time_label"],
            y=df["tension"],
            mode="lines+markers",
            name="Tensión Dramática",
            line=dict(color="#58a6ff", width=3, shape="spline", smoothing=0.7),
            marker=dict(size=12, color=point_colors, line=dict(color="#ffffff", width=1.5)),
            customdata=list(zip(wrapped_just, wrapped_story, df["off_topic_pct"])),
            hovertemplate=(
                "<b>Bloque:</b> %{x}<br>"
                "<b>Tensión:</b> %{y}/10<br>"
                "<b>Off-Topic:</b> %{customdata[2]}%<br>"
                "<span style='color:#8b949e;'>──────────────────────────────</span><br>"
                "<b>Justificación:</b><br>%{customdata[0]}<br><br>"
                "<b>Estado de la Trama:</b><br>%{customdata[1]}"
                "<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title="<b>Evolución del Ritmo y Tensión Dramática</b>",
        xaxis_title="Intervalo Temporal (Minutos)",
        yaxis_title="Nivel de Tensión (1-10)",
        yaxis=dict(range=[0, 10.5], dtick=1, gridcolor="#21262d"),
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
        margin=dict(l=40, r=40, t=50, b=40),
        height=450,
    )

    return fig


def render_airtime_charts(session: dict[str, Any], characters: list[dict[str, Any]]) -> tuple[go.Figure, go.Figure]:
    """Genera el gráfico de dona Guardián vs Investigadores y barras por jugador."""
    # 1. Gráfico de dona (Guardián vs Investigadores)
    donut_fig = go.Figure(
        data=[
            go.Pie(
                labels=["Guardián", "Investigadores"],
                values=[session["guardian_pct"], session["investigators_pct"]],
                hole=0.55,
                marker=dict(colors=["#9c27b0", "#00bcd4"]),
                textinfo="label+percent",
                hoverinfo="label+percent+value",
            )
        ]
    )
    donut_fig.update_layout(
        title="<b>Reparto Global de Habla</b>",
        paper_bgcolor="#0d1117",
        plot_bgcolor="#0d1117",
        font=dict(color="#c9d1d9"),
        margin=dict(l=20, r=20, t=50, b=20),
        height=320,
        showlegend=False,
    )

    # 2. Gráfico de barras horizontal por participante
    df_chars = pd.DataFrame(characters).sort_values("speaking_seconds", ascending=True)
    df_chars["minutes"] = (df_chars["speaking_seconds"] / 60).round(1)
    df_chars["display_name"] = df_chars["player"] + " (" + df_chars["character"] + ")"

    bar_colors = ["#9c27b0" if r == "guardian" else "#00bcd4" for r in df_chars["role"]]

    bar_fig = go.Figure(
        go.Bar(
            x=df_chars["airtime_pct"],
            y=df_chars["display_name"],
            orientation="h",
            marker=dict(color=bar_colors),
            text=df_chars.apply(lambda row: f"{row['airtime_pct']}% ({row['minutes']} min)", axis=1),
            textposition="auto",
            hovertemplate="<b>%{y}</b><br>Porcentaje: %{x}%<br>Minutos: %{customdata} min<extra></extra>",
            customdata=df_chars["minutes"],
        )
    )
    bar_fig.update_layout(
        title="<b>Participación por Jugador</b>",
        xaxis_title="Porcentaje de Habla (%)",
        paper_bgcolor="#0d1117",
        plot_bgcolor="#0d1117",
        font=dict(color="#c9d1d9"),
        xaxis=dict(gridcolor="#21262d"),
        margin=dict(l=20, r=20, t=50, b=20),
        height=320,
    )

    return donut_fig, bar_fig


def render_offtopic_chart(metrics: list[dict[str, Any]]) -> go.Figure:
    """Genera el gráfico de área interactivo de evolución de Off-Topic."""
    df = pd.DataFrame(metrics)
    wrapped_off_just = [wrap_text(t, width=50) for t in df["off_topic_justification"]]

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
            customdata=wrapped_off_just,
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
        line_color="rgba(255, 152, 0, 0.5)",
        annotation_text="Alerta Distracción (>20%)",
        annotation_position="top left",
    )

    fig.update_layout(
        title="<b>Evolución del Índice de Off-Topic (Distracción vs Inmersión)</b>",
        xaxis_title="Intervalo Temporal",
        yaxis_title="Off-Topic (%)",
        yaxis=dict(range=[0, max(50, df["off_topic_pct"].max() + 10)], gridcolor="#21262d"),
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
        margin=dict(l=40, r=40, t=50, b=40),
        height=380,
    )

    return fig


def main() -> None:
    st.markdown('<div class="main-title">🐙 Miskatonic Scribe — Analíticas de Partidas</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Plataforma empírica de ritmo dramático, inmersión y dinámicas de mesa para <i>La Llamada de Cthulhu</i>.</div>', unsafe_allow_html=True)

    sessions = load_available_sessions()
    if not sessions:
        st.warning("⚠️ No se encontraron partidas en `partidas.db`. Asegúrate de ejecutar `python db_manager.py import`.")
        return

    # Barra lateral
    with st.sidebar:
        st.header("🗂️ Selección de Partida")
        session_map = {s["id"]: s for s in sessions}

        def format_session_label(session_id: str) -> str:
            s_info = session_map.get(session_id, {})
            title = s_info.get("title") or ""
            if title and title != session_id:
                short_title = (title[:26] + "...") if len(title) > 28 else title
                return f"{session_id} — {short_title}"
            return session_id

        selected_id = st.selectbox(
            "Elige la partida a consultar:",
            options=[s["id"] for s in sessions],
            format_func=format_session_label,
            index=0,
        )

        # Botón de refresco
        if st.button("🔄 Recargar Base de Datos"):
            st.cache_data.clear()
            st.rerun()

        st.divider()
        st.caption("Miskatonic Scribe MVP • SQLite + Ollama (qwen2.5:32b)")

    data = load_session_details(selected_id)
    if not data:
        st.error(f"No se pudieron cargar los datos de la sesión {selected_id}.")
        return

    session = data["session"]
    characters = data["characters"]
    metrics = data["metrics"]

    # Ficha de Sesión (Hero Card - Spec 05)
    title = session.get("title") or f"Sesión {session['id']}"
    channel = session.get("channel") or ""
    yt_url = session.get("url") or f"https://www.youtube.com/watch?v={session['id']}"
    thumb_path = session.get("thumbnail_path")
    likes = session.get("like_count")
    comments = session.get("comment_count")
    duration_min = f"{session['duration_seconds']/60:.1f} min"
    block_count = len(metrics)

    with st.container(border=True):
        col_thumb, col_info = st.columns([1, 2.5], gap="large", vertical_alignment="center")
        with col_thumb:
            thumb_file = Path(thumb_path) if thumb_path else paths.get_thumbnail_path(session["id"])
            if thumb_file.exists():
                st.image(str(thumb_file), width="stretch")
            else:
                st.markdown(
                    """
                    <div style="background-color: #161b22; border: 1px dashed #30363d; border-radius: 8px; height: 130px; display: flex; align-items: center; justify-content: center; color: #8b949e;">
                        🎬 <i>Sin miniatura local</i>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        with col_info:
            st.markdown(f"<h3 style='margin-top: 0; margin-bottom: 0.25rem; color: #e0e6ed;'>🎬 {title}</h3>", unsafe_allow_html=True)

            sub_meta = []
            if channel:
                sub_meta.append(f"<b>Canal:</b> {channel}")
            sub_meta.append(f'<a href="{yt_url}" target="_blank" style="color: #58a6ff; text-decoration: none; font-weight: 500;">🔗 Ver en YouTube ↗</a>')
            st.markdown(" • ".join(sub_meta), unsafe_allow_html=True)

            st.markdown("<div style='margin: 8px 0; border-bottom: 1px solid #21262d;'></div>", unsafe_allow_html=True)

            # Fila 1: Métricas de YouTube y duración
            social_badges = [f"⏱️ `{duration_min}`"]
            if likes is not None:
                social_badges.append(f"👍 `{likes:,} likes`")
            if comments is not None:
                social_badges.append(f"💬 `{comments:,} comentarios`")
            st.markdown(" • ".join(social_badges), unsafe_allow_html=True)

            # Fila 2: Metadatos técnicos de análisis
            tech_badges = [
                f"🆔 `{session['id']}`",
                f"🤖 `{session['model']}`",
                f"📊 `{block_count} bloques analizados`",
            ]
            st.markdown(" • ".join(tech_badges), unsafe_allow_html=True)

    st.markdown("<div style='margin-top: 0.8rem;'></div>", unsafe_allow_html=True)

    # Fila de KPIs superiores
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric(
            label="📈 Tensión Media",
            value=f"{session['average_tension']:.1f} / 10",
            help="Puntuación media de atmósfera y peligro evaluada por el LLM.",
        )
    with kpi2:
        st.metric(
            label="🎲 Off-Topic Medio",
            value=f"{session['average_off_topic_pct']:.1f}%",
            help="Porcentaje medio de tiempo fuera de rol (chistes, reglas, cotidianidad).",
        )
    with kpi3:
        st.metric(
            label="🎙️ Airtime Guardián",
            value=f"{session['guardian_pct']:.1f}%",
            delta=f"{session['guardian_seconds']/60:.1f} min",
        )
    with kpi4:
        st.metric(
            label="👥 Airtime Investigadores",
            value=f"{session['investigators_pct']:.1f}%",
            delta=f"{session['investigators_seconds']/60:.1f} min",
        )

    st.divider()

    # Pestañas analíticas principales
    tab_tension, tab_swimlane, tab_airtime, tab_offtopic, tab_chronicle = st.tabs([
        "📈 Curva de Tensión Dramática",
        "🏊‍♂️ Carriles de Habla (Swimlane)",
        "🎙️ Gestión de Mesa (Airtime)",
        "🎲 Inmersión y Off-Topic",
        "📖 Crónica Narrativa y Desglose",
    ])

    # PESTAÑA 1: Tensión Dramática
    with tab_tension:
        fig_tension = render_tension_chart(metrics)
        st.plotly_chart(fig_tension)

        error_blocks = [b for b in metrics if b["tension"] <= 0]
        if error_blocks:
            st.warning(
                f"⚠️ **{len(error_blocks)} bloque(s)** registraron un fallo en el LLM durante el análisis (tensión = 0). "
                f"Consulta el detalle en la crónica temporal o re-analiza la sesión con `python analyzer.py <ID> --force`."
            )

        # Destacar los picos de mayor tensión
        high_tension_blocks = [b for b in metrics if b["tension"] >= 7]
        if high_tension_blocks:
            st.subheader("🔥 Momentos Clave de Tensión / Terror")
            cols = st.columns(len(high_tension_blocks))
            for i, b in enumerate(high_tension_blocks):
                with cols[i]:
                    st.info(
                        f"**{b['time_label']} — Tensión {b['tension']}/10**\n\n"
                        f"{b['tension_justification']}"
                    )

        # Crónica Directa de Cordura y Shocks Psicológicos (Spec 02)
        sanity_events = load_sanity_events(selected_id)
        st.markdown("---")
        st.subheader("🧠 Crónica de Cordura y Shocks Psicológicos")

        if not sanity_events:
            st.caption("No se detectaron pérdidas de cordura ni tiradas de crisis en esta sesión.")
        else:
            for ev in sanity_events:
                player = ev.get("player_name", "").strip()
                char = ev.get("character_name", "").strip()
                if player and char and player.lower() != char.lower():
                    who = f"**{player}** (*{char}*)"
                else:
                    who = f"**{player or char or 'Investigador'}**"

                loss = ev.get("sanity_loss", "").strip() or "Pérdida no especificada"
                trigger = ev.get("trigger_cause", "").strip() or "Estímulo perturbador"
                consequence = ev.get("consequence", "").strip()

                time_badge = f"`[{ev.get('timestamp_str', '')}]`"
                consequence_txt = f" · **Efecto:** *{consequence}*" if consequence and consequence.lower() != "ninguna" else ""

                st.markdown(
                    f"{time_badge} 🧠 {who} · **Pérdida:** `{loss}` · **Detonante:** {trigger}{consequence_txt}"
                )

        # Pistas Clave Descubiertas (Spec 03)
        clues = load_clues(selected_id)
        st.markdown("---")
        st.subheader("🔍 Pistas Clave Descubiertas")

        if not clues:
            st.caption("No se registraron pistas formales descubiertas en esta sesión.")
        else:
            for c in clues:
                player = c.get("player_name", "").strip()
                char = c.get("character_name", "").strip()
                if player and char and player.lower() != char.lower():
                    who = f"**{player}** (*{char}*)"
                else:
                    who = f"**{player or char or 'Investigador'}**"

                skill = c.get("source_skill", "").strip() or "Deducción"
                importance = c.get("importance", "clave").strip().lower()
                imp_badge = ":red-background[Clave]" if importance == "clave" else ":gray-background[Contexto]"
                clue_txt = c.get("clue_text", "").strip()
                time_badge = f"`[{c.get('timestamp_str', '')}]`"

                st.markdown(
                    f"{time_badge} 🔍 {who} · **Habilidad:** `{skill}` · {imp_badge} {clue_txt}"
                )

        # Hitos Narrativos y Puntos de Inflexión (Spec 03)
        milestones = load_milestones(selected_id)
        st.markdown("---")
        st.subheader("🚩 Hitos y Puntos de Inflexión de la Trama")

        if not milestones:
            st.caption("No se registraron hitos narrativos destacados en esta sesión.")
        else:
            for m in milestones:
                time_badge = f"`[{m.get('timestamp_str', '')}]`"
                title = m.get("title", "").strip()
                phase = m.get("phase", "investigación").strip()
                desc = m.get("description", "").strip()
                phase_badge = f"*{phase.capitalize()}*"

                st.markdown(
                    f"{time_badge} 🚩 **{title}** ({phase_badge}) — {desc}"
                )

        # Tiradas Críticas y Forzadas (Spec 04)
        critical_rolls = load_critical_rolls(selected_id)
        st.markdown("---")
        st.subheader("🎲 Tiradas Críticas y Forzadas")

        if not critical_rolls:
            st.caption("No se registraron tiradas forzadas ni resultados críticos/pifias en esta sesión.")
        else:
            for r in critical_rolls:
                player = r.get("player_name", "").strip()
                char = r.get("character_name", "").strip()
                if player and char and player.lower() != char.lower():
                    who = f"**{player}** (*{char}*)"
                else:
                    who = f"**{player or char or 'Investigador'}**"

                time_badge = f"`[{r.get('timestamp_str', '')}]`"
                skill = r.get("skill", "General").strip()
                roll_type = r.get("roll_type", "pushed_roll").strip().lower()
                outcome = r.get("outcome", "failure").strip().lower()
                consequence = r.get("consequence", "").strip()

                # Badge temático
                if roll_type == "fumble":
                    badge = ":red-background[💥 Pifia]"
                elif roll_type == "critical":
                    badge = ":green-background[⭐ Éxito Crítico]"
                elif roll_type == "pushed_roll":
                    badge = ":orange-background[🎲 Tirada Forzada]"
                else:
                    badge = f":blue-background[{roll_type.capitalize()}]"

                outcome_icon = "✅" if outcome == "success" else "❌"
                consequence_txt = f" — *{consequence}*" if consequence else ""

                st.markdown(
                    f"{time_badge} 🎲 {who} · **Habilidad:** `{skill}` · {badge} {outcome_icon}{consequence_txt}"
                )

        # Combate y Letalidad Física (Spec 04)
        combat_events = load_combat_events(selected_id)
        st.markdown("---")
        st.subheader("🩸 Combate y Letalidad Física")

        if not combat_events:
            st.caption("No se registraron enfrentamientos físicos ni heridas graves en esta sesión.")
        else:
            for ev in combat_events:
                player = ev.get("player_name", "").strip()
                char = ev.get("character_name", "").strip()
                if player and char and player.lower() != char.lower():
                    who = f"**{player}** (*{char}*)"
                else:
                    who = f"**{player or char or 'Víctima'}**"

                time_badge = f"`[{ev.get('timestamp_str', '')}]`"
                source = ev.get("source", "").strip() or "Amenaza física"
                severity = ev.get("severity", "herida_leve").strip().lower()
                details = ev.get("details", "").strip()

                # Badges de severidad
                if severity == "muerte":
                    sev_badge = ":red-background[💀 Muerte]"
                elif severity == "inconsciente":
                    sev_badge = ":red-background[😵 Inconsciente]"
                elif severity == "herida_grave":
                    sev_badge = ":red-background[🩸 Herida Grave]"
                else:
                    sev_badge = ":orange-background[🩹 Herida Leve]"

                details_txt = f" — *{details}*" if details else ""

                st.markdown(
                    f"{time_badge} 🩸 {who} · **Origen:** `{source}` · {sev_badge}{details_txt}"
                )

    # PESTAÑA 2: Carriles de Habla (Swimlane)
    with tab_swimlane:
        dialogs = load_session_dialogs(selected_id)
        if not dialogs:
            st.info("ℹ️ No se encontraron turnos de diálogo normalizados para esta partida.")
        else:
            speaker_map = build_speaker_metadata(characters)
            available_labels = []
            for d in dialogs:
                lbl, _ = get_participant_label(d.get("speaker", ""), speaker_map)
                if lbl not in available_labels:
                    available_labels.append(lbl)

            col_filter, col_stats = st.columns([3, 1])
            with col_filter:
                selected_speakers = st.multiselect(
                    "Filtrar participantes:",
                    options=available_labels,
                    default=available_labels,
                    help="Selecciona los oradores a visualizar en los carriles de habla.",
                )
            with col_stats:
                st.metric("Total Intervenciones", f"{len(dialogs)} turnos")

            fig_swimlane = render_swimlane_chart(
                dialogs=dialogs,
                characters=characters,
                selected_speakers=selected_speakers,
            )
            st.plotly_chart(fig_swimlane)

            with st.expander("💡 Cómo interpretar el Diagrama de Carriles"):
                st.markdown(
                    """
                    - **Eje X (Tiempo de Partida):** Muestra el progreso cronológico (`HH:MM:SS`). Puedes hacer zoom y paneo horizontal con el ratón.
                    - **Eje Y (Participantes):** El **Guardián (👑)** se ubica en el carril superior con distinción dorada. Los **Investigadores (🕵️)** tienen colores individuales asignados.
                    - **Patrones de Habla:**
                      - *Bloques continuos largos:* Monólogos y descripciones narrativas del Guardián.
                      - *Bloques breves alternados:* Diálogos rápidos, discusiones de pistas o escenas de tensión entre investigadores.
                      - *Espacios vacíos:* Pausas dramáticas, silencios tensos o consultas mecánicas de dados y fichas.
                    """
                )

    # PESTAÑA 3: Airtime y Participación
    with tab_airtime:
        c1, c2 = st.columns([1, 1.5])
        fig_donut, fig_bar = render_airtime_charts(session, characters)
        with c1:
            st.plotly_chart(fig_donut)
        with c2:
            st.plotly_chart(fig_bar)

        st.subheader("Desglose de Participantes")
        df_display = pd.DataFrame(characters)[["player", "character", "role", "speaking_seconds", "airtime_pct"]]
        df_display.columns = ["Jugador", "Personaje", "Rol", "Segundos Habla", "Airtime %"]
        df_display["Minutos Habla"] = (df_display["Segundos Habla"] / 60).round(1)
        st.dataframe(df_display[["Jugador", "Personaje", "Rol", "Minutos Habla", "Airtime %"]], hide_index=True)

    # PESTAÑA 3: Off-Topic e Inmersión
    with tab_offtopic:
        fig_offtopic = render_offtopic_chart(metrics)
        st.plotly_chart(fig_offtopic)

        immersion_pct = 100.0 - session["average_off_topic_pct"]
        st.markdown(
            f"**Índice de Inmersión Global:** La mesa pasó el **{immersion_pct:.1f}%** del tiempo completamente "
            f"sumergida en el rol y la ficción de la partida."
        )

    # PESTAÑA 4: Crónica y Desglose
    with tab_chronicle:
        st.subheader("Sinopsis Global de la Partida")
        if session.get("narrative_synopsis"):
            st.write(session["narrative_synopsis"])
        else:
            st.info("No se ha registrado sinopsis global para esta sesión.")

        st.subheader("Desglose Cronológico por Intervalos")
        for b in metrics:
            tension_badge = f":red-background[Tensión {b['tension']}/10]" if b["tension"] >= 7 else f"Tensión {b['tension']}/10"
            off_badge = f":orange-background[Off-Topic {b['off_topic_pct']}%]" if b["off_topic_pct"] >= 20 else f"Off-Topic {b['off_topic_pct']}%"

            with st.expander(f"⏱️ **Bloque {b['block_index']} ({b['time_label']})** — {tension_badge} | {off_badge}"):
                col_left, col_right = st.columns([1, 1])
                with col_left:
                    st.markdown("**🎭 Análisis de Tensión:**")
                    st.write(b["tension_justification"])
                    st.markdown(f"**🗣️ Habla:** Guardián {b['guardian_pct']:.1f}% | Investigadores {b['investigators_pct']:.1f}%")
                with col_right:
                    st.markdown("**🎲 Análisis de Off-Topic:**")
                    st.write(b["off_topic_justification"])
                    st.markdown("**📖 Estado de la Trama:**")
                    st.write(b["story_state"])


if __name__ == "__main__":
    main()
