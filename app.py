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
    from dashboard.visualizations.campaign_tension import render_campaign_tension_chart
    from dashboard.visualizations.campaign_airtime import render_campaign_airtime_charts
    from dashboard.visualizations.campaign_immersion import (
        build_campaign_immersion_data,
        render_campaign_immersion_tab,
    )
    from dashboard.visualizations.tension import render_tension_chart
    from dashboard.visualizations.timeline_stream import consolidate_event_stream, render_timeline_stream
    from dashboard.visualizations.offtopic import render_immersion_tab, render_offtopic_chart
    from dashboard.visualizations.investigator_stats import (
        build_session_investigator_stats,
        build_campaign_investigator_stats,
        render_session_investigator_table,
        render_campaign_investigator_scoreboard,
    )
    from dashboard import navigation
except ImportError:
    from visualizations.swimlane import (
        build_speaker_metadata,
        get_participant_label,
        render_swimlane_chart,
    )
    from visualizations.campaign_tension import render_campaign_tension_chart
    from visualizations.campaign_airtime import render_campaign_airtime_charts
    from visualizations.campaign_immersion import (
        build_campaign_immersion_data,
        render_campaign_immersion_tab,
    )
    from visualizations.tension import render_tension_chart
    from visualizations.timeline_stream import consolidate_event_stream, render_timeline_stream
    from visualizations.offtopic import render_immersion_tab, render_offtopic_chart
    from visualizations.investigator_stats import (
        build_session_investigator_stats,
        build_campaign_investigator_stats,
        render_session_investigator_table,
        render_campaign_investigator_scoreboard,
    )
    import navigation

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


def get_db_connection() -> sqlite3.Connection:
    """Conexión a la base de datos SQLite en modo lectura."""
    conn = sqlite3.connect(f"file:{DB_PATH.resolve()}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def get_db_mtime() -> float:
    """Devuelve el timestamp de modificación del fichero SQLite para auto-invalidar la caché."""
    try:
        return DB_PATH.stat().st_mtime if DB_PATH.exists() else 0.0
    except Exception:
        return 0.0


@st.cache_data(ttl=300)
def load_available_sessions(db_mtime: float = 0.0) -> list[dict[str, Any]]:
    """Obtiene la lista de sesiones disponibles en partidas.db con sus metadatos."""
    if not DB_PATH.exists():
        return []
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(sessions)")
        cols = {row[1] for row in cursor.fetchall()}
        has_camp = "campaign_id" in cols and "episode_order" in cols

        if has_camp:
            query = """
            SELECT id, title, channel, url, thumbnail_path, like_count, comment_count,
                   duration_seconds, analyzed_at, model, campaign_id, episode_order
            FROM sessions
            ORDER BY analyzed_at DESC
            """
        else:
            query = """
            SELECT id, title, channel, url, thumbnail_path, like_count, comment_count,
                   duration_seconds, analyzed_at, model
            FROM sessions
            ORDER BY analyzed_at DESC
            """
        cursor.execute(query)
        rows = cursor.fetchall()
        results: list[dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            if not has_camp:
                d["campaign_id"] = None
                d["episode_order"] = None
            results.append(d)
        return results
    finally:
        conn.close()


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


# ==============================================================================
# CARGADORES DE CAMPAÑA (Spec 15 / T001)
# ==============================================================================

@st.cache_data(ttl=300)
def load_campaigns(db_mtime: float = 0.0) -> list[dict[str, Any]]:
    """Obtiene todas las campañas registradas con conteo de episodios y duración."""
    if not DB_PATH.exists():
        return []
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='campaigns'")
        if not cursor.fetchone():
            return []
        cursor.execute(
            """
            SELECT c.id, c.name, c.system, c.description, c.order_index, c.created_at,
                   COUNT(s.id) AS episode_count,
                   COALESCE(SUM(s.duration_seconds), 0) AS total_duration_seconds
            FROM campaigns c
            LEFT JOIN sessions s ON s.campaign_id = c.id
            GROUP BY c.id
            ORDER BY c.order_index ASC, c.created_at ASC
            """
        )
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()


@st.cache_data
def load_campaign_sessions(campaign_id: str) -> list[dict[str, Any]]:
    """Obtiene las sesiones de una campaña ordenadas cronológicamente."""
    if not DB_PATH.exists():
        return []
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, title, channel, url, thumbnail_path, duration_seconds,
               campaign_id, episode_order, analyzed_at, like_count, average_off_topic_pct
        FROM sessions
        WHERE campaign_id = ?
        ORDER BY COALESCE(episode_order, 9999) ASC, analyzed_at ASC, id ASC
        """,
        (campaign_id,),
    )
    return [dict(r) for r in cursor.fetchall()]


@st.cache_data
def load_campaign_kpis(campaign_id: str) -> dict[str, Any]:
    """Calcula los KPIs acumulados de toda la campaña."""
    if not DB_PATH.exists():
        return {}
    conn = get_db_connection()
    cursor = conn.cursor()
    row = cursor.execute(
        """
        SELECT
            COUNT(DISTINCT s.id) AS total_episodes,
            COALESCE(SUM(s.duration_seconds), 0) AS total_duration_seconds,
            (SELECT COUNT(*) FROM sanity_events se JOIN sessions s2 ON se.session_id = s2.id WHERE s2.campaign_id = ?) AS total_sanity_events,
            (SELECT COALESCE(SUM(se.sanity_loss), 0) FROM sanity_events se JOIN sessions s2 ON se.session_id = s2.id WHERE s2.campaign_id = ?) AS total_sanity_loss,
            (SELECT COUNT(*) FROM clues cl JOIN sessions s2 ON cl.session_id = s2.id WHERE s2.campaign_id = ?) AS total_clues,
            (SELECT COUNT(*) FROM narrative_milestones nm JOIN sessions s2 ON nm.session_id = s2.id WHERE s2.campaign_id = ?) AS total_milestones,
            (SELECT COUNT(*) FROM critical_rolls cr JOIN sessions s2 ON cr.session_id = s2.id WHERE s2.campaign_id = ?) AS total_critical_rolls,
            (SELECT COUNT(*) FROM combat_events cb JOIN sessions s2 ON cb.session_id = s2.id WHERE s2.campaign_id = ?) AS total_combat_events
        FROM sessions s
        WHERE s.campaign_id = ?
        """,
        (campaign_id, campaign_id, campaign_id, campaign_id, campaign_id, campaign_id, campaign_id),
    ).fetchone()
    return dict(row) if row else {}


@st.cache_data
def load_campaign_airtime(campaign_id: str) -> list[dict[str, Any]]:
    """Calcula el tiempo de habla acumulado por participante en toda la campaña."""
    if not DB_PATH.exists():
        return []
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT ch.player, ch.character, ch.role,
               SUM(ch.speaking_seconds) AS total_speaking_seconds,
               COUNT(DISTINCT ch.session_id) AS episodes_present
        FROM characters ch
        JOIN sessions s ON ch.session_id = s.id
        WHERE s.campaign_id = ?
        GROUP BY ch.player, ch.character, ch.role
        ORDER BY total_speaking_seconds DESC
        """,
        (campaign_id,),
    )
    return [dict(r) for r in cursor.fetchall()]


@st.cache_data
def load_campaign_tension_continuous(campaign_id: str) -> dict[str, Any]:
    """Genera la serie temporal continua de tensión concatenando todos los episodios de la campaña."""
    if not DB_PATH.exists():
        return {"blocks": [], "boundaries": [], "total_duration_seconds": 0.0}
    conn = get_db_connection()
    cursor = conn.cursor()

    sessions = cursor.execute(
        """
        SELECT id, title, episode_order, duration_seconds
        FROM sessions
        WHERE campaign_id = ?
        ORDER BY COALESCE(episode_order, 9999) ASC, analyzed_at ASC, id ASC
        """,
        (campaign_id,),
    ).fetchall()

    cum_time = 0.0
    boundaries = []
    all_blocks = []

    for s in sessions:
        ep_num = s["episode_order"] or (len(boundaries) + 1)
        dur = float(s["duration_seconds"] or 0.0)
        boundaries.append({
            "episode_order": ep_num,
            "session_id": s["id"],
            "title": s["title"],
            "start_hour": cum_time / 3600.0,
            "duration_hours": dur / 3600.0,
        })
        blocks = cursor.execute(
            """
            SELECT block_index, start_time, end_time, time_label, tension, tension_justification, off_topic_pct
            FROM scene_metrics
            WHERE session_id = ?
            ORDER BY block_index ASC
            """,
            (s["id"],),
        ).fetchall()
        for b in blocks:
            b_start = float(b["start_time"] or 0.0)
            b_end = float(b["end_time"] or 0.0)
            g_start = cum_time + b_start
            g_end = cum_time + b_end
            all_blocks.append({
                "episode_order": ep_num,
                "session_id": s["id"],
                "block_index": b["block_index"],
                "global_start_hours": g_start / 3600.0,
                "global_end_hours": g_end / 3600.0,
                "global_mid_hours": (g_start + g_end) / 7200.0,
                "tension": float(b["tension"] or 0),
                "justification": b["tension_justification"] or "",
                "off_topic_pct": float(b["off_topic_pct"] or 0),
                "time_label": f"Ep. {ep_num} [{b['time_label']}]",
            })
        cum_time += dur

    return {
        "blocks": all_blocks,
        "boundaries": boundaries,
        "total_duration_seconds": cum_time,
    }


@st.cache_data
def load_campaign_sanity_traumas(campaign_id: str) -> list[dict[str, Any]]:
    """Carga todos los eventos de cordura y traumas ocurridos a lo largo de la campaña."""
    if not DB_PATH.exists():
        return []
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT s.episode_order, s.title AS session_title, se.session_id, se.block_index,
               se.timestamp_str, se.character_name, se.player_name, se.trigger_cause,
               se.sanity_loss, se.consequence
        FROM sanity_events se
        JOIN sessions s ON se.session_id = s.id
        WHERE s.campaign_id = ?
        ORDER BY COALESCE(s.episode_order, 9999) ASC, se.timestamp_seconds ASC, se.id ASC
        """,
        (campaign_id,),
    )
    return [dict(r) for r in cursor.fetchall()]


@st.cache_data
def load_campaign_clues(campaign_id: str) -> list[dict[str, Any]]:
    """Carga todas las pistas descubiertas en la campaña."""
    if not DB_PATH.exists():
        return []
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT s.episode_order, s.title AS session_title, cl.session_id, cl.timestamp_str,
               cl.character_name, cl.player_name, cl.clue_text, cl.source_skill, cl.importance
        FROM clues cl
        JOIN sessions s ON cl.session_id = s.id
        WHERE s.campaign_id = ?
        ORDER BY COALESCE(s.episode_order, 9999) ASC, cl.timestamp_seconds ASC, cl.id ASC
        """,
        (campaign_id,),
    )
    return [dict(r) for r in cursor.fetchall()]


@st.cache_data
def load_campaign_milestones(campaign_id: str) -> list[dict[str, Any]]:
    """Carga todos los hitos narrativos de la campaña."""
    if not DB_PATH.exists():
        return []
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT s.episode_order, s.title AS session_title, nm.session_id, nm.timestamp_str,
               nm.title, nm.description, nm.phase
        FROM narrative_milestones nm
        JOIN sessions s ON nm.session_id = s.id
        WHERE s.campaign_id = ?
        ORDER BY COALESCE(s.episode_order, 9999) ASC, nm.timestamp_seconds ASC, nm.id ASC
        """,
        (campaign_id,),
    )
    return [dict(r) for r in cursor.fetchall()]


@st.cache_data
def load_campaign_investigator_stats(campaign_id: str) -> dict[str, Any]:
    """Carga y agrega las métricas numéricas por investigador de toda la campaña (Spec 19)."""
    episodes = load_campaign_sessions(campaign_id)
    if not episodes:
        return {"investigators": {}, "awards": {}}

    session_stats_list: list[dict[str, Any]] = []
    for ep in episodes:
        sid = ep["id"]
        details = load_session_details(sid)
        if not details:
            continue
        chars = details.get("characters", [])
        se = load_sanity_events(sid)
        cl = load_clues(sid)
        cr = load_critical_rolls(sid)
        ce = load_combat_events(sid)
        s_stats = build_session_investigator_stats(chars, se, cl, cr, ce)
        session_stats_list.append(s_stats)

    return build_campaign_investigator_stats(session_stats_list)


import textwrap

def wrap_text(text: str, width: int = 55) -> str:
    """Ajusta un texto largo insertando etiquetas <br> para tooltips elegantes."""
    if not text:
        return ""
    lines = textwrap.wrap(str(text), width=width)
    return "<br>".join(lines)




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



def render_campaign_global_view(campaign_id: str) -> None:
    """Renderiza el tablero macro-analítico de la campaña completa (Spec 15 / US2, US3)."""
    campaigns = load_campaigns(get_db_mtime())
    camp_meta = next((c for c in campaigns if c["id"] == campaign_id), None)
    if not camp_meta:
        st.error(f"Campaña '{campaign_id}' no encontrada.")
        return

    camp_name = camp_meta["name"]
    system = camp_meta["system"]
    desc = camp_meta.get("description") or ""
    kpis = load_campaign_kpis(campaign_id)
    episodes = load_campaign_sessions(campaign_id)
    total_secs = float(kpis.get("total_duration_seconds", 0.0))
    total_hours = total_secs / 3600.0

    # 1. Hero Banner de Campaña con Miniatura del Episodio 1
    with st.container(border=True):
        col_banner_thumb, col_banner_info = st.columns([1, 2.8], gap="large", vertical_alignment="center")

        with col_banner_thumb:
            first_ep = episodes[0] if episodes else None
            first_thumb = paths.get_thumbnail_path(first_ep["id"]) if first_ep else None
            if first_thumb and first_thumb.exists():
                st.image(str(first_thumb), width="stretch")
            elif first_ep:
                yt_fallback = f"https://img.youtube.com/vi/{first_ep['id']}/hqdefault.jpg"
                st.image(yt_fallback, width="stretch")
            else:
                st.markdown(
                    """
                    <div style="background-color: #161b22; border: 1px dashed #30363d; border-radius: 8px; height: 130px; display: flex; align-items: center; justify-content: center; color: #8b949e;">
                        📜 <i>Aventura</i>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        with col_banner_info:
            st.markdown(f"<h2 style='margin-top: 0; margin-bottom: 0.25rem; color: #e0e6ed;'>📜 {camp_name}</h2>", unsafe_allow_html=True)
            meta_items = [
                f"<b>Sistema:</b> {system}",
                f"<b>Capítulos:</b> {len(episodes)} episodios",
                f"<b>Duración Total:</b> {total_hours:.1f} horas ({int(total_secs // 60)} min)",
                f"<b>Estado:</b> <span style='color: #26a69a;'>Completada</span>",
            ]
            st.markdown(" • ".join(meta_items), unsafe_allow_html=True)
            if desc:
                st.markdown(f"<p style='color: #8b949e; margin-top: 0.6rem; font-style: italic; line-height: 1.4;'>{desc}</p>", unsafe_allow_html=True)

    st.markdown("<div style='margin-top: 0.5rem;'></div>", unsafe_allow_html=True)

    # 2. Barra de KPIs Acumulados
    col_k1, col_k2, col_k3, col_k4, col_k5 = st.columns(5)
    with col_k1:
        st.metric("⏱️ Horas Totales", f"{total_hours:.1f} h", help="Suma de la duración de todos los episodios.")
    with col_k2:
        st.metric("🧠 Eventos de Cordura", f"{kpis.get('total_sanity_events', 0)}", help="Momentos de impacto psicológico y tiradas de Cordura sufridas.")
    with col_k3:
        st.metric("🔍 Pistas Halladas", f"{kpis.get('total_clues', 0)}", help="Pistas e indicios descubiertos a lo largo de la investigación.")
    with col_k4:
        st.metric("🎲 Críticos y Pifias", f"{kpis.get('total_critical_rolls', 0)}", help="Tiradas extremas registradas en momentos clave.")
    with col_k5:
        st.metric("📜 Hitos Clave", f"{kpis.get('total_milestones', 0)}", help="Hitos narrativos de progresión de la trama alcanzados.")

    st.divider()

    # 3. Pestañas Analíticas Multi-Episodio
    tab_tension, tab_immersion, tab_airtime, tab_scoreboard, tab_sanity, tab_clues, tab_episodes = st.tabs([
        "📈 La Gran Curva de Tensión",
        "🎭 Atmósfera & Inmersión",
        "⚖️ Balance de Mesa y Protagonismo",
        "🏆 Cuadro de Honor y Desgracia",
        "🧠 Desgaste Psicológico (Traumas)",
        "🗺️ Crónica de Pistas e Hitos",
        "🎬 Índice de Capítulos",
    ])

    with tab_tension:
        tension_data = load_campaign_tension_continuous(campaign_id)
        fig_tension = render_campaign_tension_chart(tension_data, camp_name)
        st.plotly_chart(fig_tension, width="stretch")

        blocks = tension_data.get("blocks", [])
        if blocks:
            max_block = max(blocks, key=lambda b: b["tension"])
            avg_tension = sum(b["tension"] for b in blocks) / len(blocks)
            st.caption(
                f"**Ritmo Narrativo:** Tensión media de la aventura: **{avg_tension:.1f}/10** • "
                f"Clímax dramático alcanzado en el **{max_block['time_label']}** con tensión **{max_block['tension']:.0f}/10**."
            )

    with tab_immersion:
        tension_data = load_campaign_tension_continuous(campaign_id)
        immersion_data = build_campaign_immersion_data(
            episodes,
            continuous_blocks=tension_data.get("blocks", []),
        )
        render_campaign_immersion_tab(st, immersion_data, camp_name)

    with tab_airtime:
        airtime_data = load_campaign_airtime(campaign_id)
        col_donut, col_bar = st.columns([1, 1.6], gap="medium")
        donut_fig, bar_fig = render_campaign_airtime_charts(airtime_data, camp_name)
        with col_donut:
            st.plotly_chart(donut_fig, width="stretch")
        with col_bar:
            st.plotly_chart(bar_fig, width="stretch")

    with tab_scoreboard:
        scoreboard_data = load_campaign_investigator_stats(campaign_id)
        render_campaign_investigator_scoreboard(st, scoreboard_data, camp_name)

    with tab_sanity:
        st.markdown("#### 🧠 Historial de Pérdidas de Cordura y Secuelas Mentales")
        st.caption("Registro de todos los impactos psicológicos, fobias y traumas adquiridos durante la aventura.")
        traumas = load_campaign_sanity_traumas(campaign_id)
        if traumas:
            df_traumas = pd.DataFrame(traumas)
            df_traumas_display = df_traumas[[
                "episode_order", "character_name", "player_name", "sanity_loss", "trigger_cause", "consequence"
            ]].rename(columns={
                "episode_order": "Episodio",
                "character_name": "Personaje",
                "player_name": "Jugador",
                "sanity_loss": "Pérdida COR",
                "trigger_cause": "Desencadenante",
                "consequence": "Secuela / Reacción",
            })
            st.dataframe(df_traumas_display, width="stretch", hide_index=True)
        else:
            st.info("No se registraron eventos de pérdida de cordura en esta campaña.")

    with tab_clues:
        st.markdown("#### 🗺️ Pistas Clave e Hitos Narrativos de la Aventura")
        sub_tab_clues, sub_tab_milestones = st.tabs(["🔍 Pistas Clave", "📜 Hitos Narrativos"])

        with sub_tab_clues:
            clues = load_campaign_clues(campaign_id)
            if clues:
                st.caption(f"{len(clues)} pistas e indicios encontrados por los investigadores:")
                for c in clues:
                    with st.container(border=True):
                        col_c_meta, col_c_desc = st.columns([1, 3])
                        with col_c_meta:
                            st.markdown(f"**Episodio {c.get('episode_order')}**")
                            st.caption(f"👤 `{c.get('character_name') or 'Investigador'}`")
                            st.caption(f"🏷️ `{c.get('source_skill') or 'Descubrimiento'}`")
                        with col_c_desc:
                            st.markdown(f"*{c.get('clue_text')}*")
                            imp = c.get("importance") or "Media"
                            st.caption(f"Importancia: `{imp}`")
            else:
                st.info("No se registraron pistas para esta campaña.")

        with sub_tab_milestones:
            milestones = load_campaign_milestones(campaign_id)
            if milestones:
                st.caption(f"{len(milestones)} hitos narrativos de progresión:")
                for m in milestones:
                    with st.container(border=True):
                        col_m_meta, col_m_desc = st.columns([1, 3])
                        with col_m_meta:
                            st.markdown(f"**Episodio {m.get('episode_order')}**")
                            st.caption(f"🚩 Fase: `{m.get('phase') or 'Desarrollo'}`")
                        with col_m_desc:
                            st.markdown(f"**{m.get('title')}**")
                            st.markdown(f"{m.get('description')}")
            else:
                st.info("No se registraron hitos narrativos para esta campaña.")

    with tab_episodes:
        st.markdown(f"#### 🎬 Catálogo de Episodios ({len(episodes)} capítulos)")
        st.caption("Acceso directo a las analíticas detalladas de cada sesión de la campaña.")

        for idx, ep in enumerate(episodes):
            ep_num = ep.get("episode_order") or (idx + 1)
            dur_mins = int((ep.get("duration_seconds") or 0) // 60)
            dur_str = f"{dur_mins // 60}h {dur_mins % 60}m" if dur_mins >= 60 else f"{dur_mins} min"
            vid_id = ep["id"]
            title = ep.get("title") or f"Episodio {ep_num}"

            with st.container(border=True):
                col_e_thumb, col_e_info, col_e_act = st.columns([1.2, 3, 1], vertical_alignment="center")

                with col_e_thumb:
                    thumb_p = paths.get_thumbnail_path(vid_id)
                    if thumb_p.exists():
                        st.image(str(thumb_p), width=180)
                    else:
                        yt_cdn = f"https://img.youtube.com/vi/{vid_id}/hqdefault.jpg"
                        st.image(yt_cdn, width=180)

                with col_e_info:
                    st.markdown(f"**Episodio {ep_num}: {title}**")
                    meta_bits = [f"⏱️ `{dur_str}`", f"🆔 `{vid_id}`"]
                    if ep.get("channel"):
                        meta_bits.append(f"📺 {ep['channel']}")
                    st.caption(" • ".join(meta_bits))

                with col_e_act:
                    if st.button("👁️ Ver Episodio", key=f"btn_jump_ep_{vid_id}", width="stretch", type="primary"):
                        st.session_state["dashboard_mode_radio"] = "🎬 Ver Episodio Específico"
                        st.session_state["dashboard_selected_episode_id"] = vid_id
                        st.rerun()



def render_session_view(
    selected_id: str,
    campaign_info: dict[str, Any] | None = None,
    all_campaign_sessions: list[dict[str, Any]] | None = None,
) -> None:
    """Renderiza el visor detallado para un episodio o sesión individual."""

    data = load_session_details(selected_id)
    if not data:
        st.error(f"No se pudieron cargar los datos de la sesión {selected_id}.")
        return

    session = data["session"]
    characters = data["characters"]
    metrics = data["metrics"]

    # 1. Barra de Navegación Contextual y Breadcrumbs (Spec 15 / US4)
    curr_idx = 0
    total_eps = len(all_campaign_sessions) if all_campaign_sessions else 0
    if campaign_info and all_campaign_sessions and total_eps > 1:
        camp_name = campaign_info.get("name", "Campaña")
        session_ids = [s["id"] for s in all_campaign_sessions]
        curr_idx = session_ids.index(selected_id) if selected_id in session_ids else 0
        ep_order = all_campaign_sessions[curr_idx].get("episode_order") or (curr_idx + 1)

        col_bcrumb, col_nav = st.columns([2.5, 2], vertical_alignment="center")

        with col_bcrumb:
            st.markdown(
                f"<div style='color: #8b949e; font-size: 0.95rem;'>"
                f"📜 <b style='color: #58a6ff;'>{camp_name}</b> &nbsp;›&nbsp; "
                f"<span style='color: #e0e6ed; font-weight: 500;'>Episodio {ep_order} de {total_eps}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        with col_nav:
            c_prev, c_home, c_next = st.columns([1.2, 1.4, 1.2])

            with c_prev:
                btn_prev_disabled = curr_idx == 0
                if st.button("⬅ Anterior", key=f"nav_prev_{selected_id}", disabled=btn_prev_disabled, width="stretch", help="Ir al episodio anterior"):
                    prev_sid = session_ids[curr_idx - 1]
                    navigation.set_nav_target(st.session_state, navigation.NAV_EPISODE, campaign_id=campaign_info.get("id"), session_id=prev_sid, query_params=st.query_params)
                    st.rerun()

            with c_home:
                if st.button("🗺️ Ver Aventura", key=f"nav_home_{selected_id}", width="stretch", help="Volver a la visión global de la aventura"):
                    navigation.set_nav_target(st.session_state, navigation.NAV_CAMPAIGN, campaign_id=campaign_info.get("id"), query_params=st.query_params)
                    st.rerun()

            with c_next:
                btn_next_disabled = curr_idx == total_eps - 1
                if st.button("Siguiente ➡", key=f"nav_next_{selected_id}", disabled=btn_next_disabled, width="stretch", help="Ir al episodio siguiente"):
                    next_sid = session_ids[curr_idx + 1]
                    navigation.set_nav_target(st.session_state, navigation.NAV_EPISODE, campaign_id=campaign_info.get("id"), session_id=next_sid, query_params=st.query_params)
                    st.rerun()

        st.markdown("<div style='margin-bottom: 0.4rem;'></div>", unsafe_allow_html=True)
    elif campaign_info:
        st.markdown(
            f"<div style='color: #8b949e; font-size: 0.95rem; margin-bottom: 0.6rem;'>"
            f"📜 <b style='color: #58a6ff;'>{campaign_info.get('name')}</b> &nbsp;›&nbsp; "
            f"<span style='color: #e0e6ed;'>Partida Independiente</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # Ficha de Sesión (Hero Card - Spec 05)
    raw_title = session.get("title") or f"Sesión {session['id']}"
    ep_num = session.get("episode_order")
    title = f"Episodio {ep_num}: {raw_title}" if ep_num is not None else raw_title
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
            thumb_file = paths.get_thumbnail_path(session["id"])
            if not thumb_file.exists() and thumb_path:
                alt = Path(thumb_path)
                if alt.exists():
                    thumb_file = alt

            if thumb_file.exists():
                st.image(str(thumb_file), width="stretch")
            else:
                # Fallback resiliente a la miniatura oficial de YouTube en CDN
                yt_fallback = f"https://img.youtube.com/vi/{session['id']}/hqdefault.jpg"
                st.image(yt_fallback, width="stretch")
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

    # Cargar eventos narrativos y mecánicos comunes (Spec 17 & 19)
    sanity_events = load_sanity_events(selected_id)
    clues = load_clues(selected_id)
    milestones = load_milestones(selected_id)
    critical_rolls = load_critical_rolls(selected_id)
    combat_events = load_combat_events(selected_id)

    # Pestañas analíticas principales
    tab_tension, tab_dynamics, tab_offtopic, tab_chronicle = st.tabs([
        "📈 Curva de Tensión Dramática",
        "👥 Dinámicas de Mesa & Participación",
        "🎭 Inmersión & Atmósfera",
        "📖 Crónica Narrativa y Desglose",
    ])

    # PESTAÑA 1: Tensión Dramática
    with tab_tension:
        fig_tension = render_tension_chart(
            metrics,
            sanity_events=sanity_events,
            clues=clues,
            milestones=milestones,
            critical_rolls=critical_rolls,
            combat_events=combat_events,
        )
        st.plotly_chart(fig_tension, width="stretch")

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

        # Línea de Tiempo Narrativa Consolidada y Filtrable (Spec 17 / US2 & US3)
        event_stream = consolidate_event_stream(
            sanity_events=sanity_events,
            clues=clues,
            milestones=milestones,
            critical_rolls=critical_rolls,
            combat_events=combat_events,
        )
        render_timeline_stream(st, event_stream, current_session_id=selected_id)

    # PESTAÑA 2: Dinámicas de Mesa & Participación (Swimlane First + Airtime)
    with tab_dynamics:
        # Nivel 1 (Superior): Carriles de Habla Interactivos (Swimlane Timeline)
        st.subheader("🎙️ Carriles de Habla en el Tiempo (Swimlane)")
        dialogs = load_session_dialogs(selected_id)
        if not dialogs:
            st.info("ℹ️ No se encontraron turnos de diálogo normalizados para los carriles de esta partida.")
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
                    "Filtrar participantes en el timeline:",
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
            st.plotly_chart(fig_swimlane, width="stretch")

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

        # Nivel 2 (Medio): Reparto y Balance Macro
        st.markdown("---")
        st.subheader("⚖️ Reparto y Balance de Voz en la Mesa")
        c1, c2 = st.columns([1.2, 1.8])
        fig_donut, fig_bar = render_airtime_charts(session, characters)
        with c1:
            st.plotly_chart(fig_donut, width="stretch")
        with c2:
            st.plotly_chart(fig_bar, width="stretch")

        # Nivel 3 (Inferior): Desglose Detallado
        st.caption("Desglose detallado de intervención por participante:")
        df_display = pd.DataFrame(characters)[["player", "character", "role", "speaking_seconds", "airtime_pct"]]
        df_display.columns = ["Jugador", "Personaje", "Rol", "Segundos Habla", "Airtime %"]
        df_display["Minutos Habla"] = (df_display["Segundos Habla"] / 60).round(1)
        st.dataframe(df_display[["Jugador", "Personaje", "Rol", "Minutos Habla", "Airtime %"]], hide_index=True, width="stretch")

        # Nivel 4: Métricas Numéricas por Investigador (Stats Puros - Spec 19)
        session_investigator_stats = build_session_investigator_stats(
            characters=characters,
            sanity_events=sanity_events,
            clues=clues,
            critical_rolls=critical_rolls,
            combat_events=combat_events,
        )
        render_session_investigator_table(st, session_investigator_stats)

    # PESTAÑA 3: Inmersión & Atmósfera de Mesa (Spec 17 / US4)
    with tab_offtopic:
        render_immersion_tab(st, session, metrics)

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

    # 2. Navegación Secuencial al pie del episodio (Spec 16 / US2)
    if campaign_info and all_campaign_sessions and total_eps > 1:
        foot_target = navigation.render_episode_pagination_footer(
            st,
            selected_id,
            campaign_info.get("id"),
            tree=navigation.build_navigation_tree([campaign_info], all_campaign_sessions),
        )
        if foot_target:
            navigation.set_nav_target(st.session_state, **foot_target, query_params=st.query_params)
            st.rerun()


def main() -> None:
    st.markdown('<div class="main-title">🐙 Miskatonic Scribe — Analíticas de Partidas</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Plataforma empírica de ritmo dramático, inmersión y dinámicas de mesa para <i>La Llamada de Cthulhu</i>.</div>', unsafe_allow_html=True)

    db_mtime = get_db_mtime()
    all_sessions = load_available_sessions(db_mtime)
    if not all_sessions:
        st.warning("⚠️ No se encontraron partidas en `partidas.db`. Asegúrate de ejecutar `python -m pipeline.cli run`.")
        return

    campaigns = load_campaigns(db_mtime)

    # Construcción de la jerarquía de navegación y gestión de estado (Spec 16 / US1)
    tree = navigation.build_navigation_tree(campaigns, all_sessions)
    default_camp = campaigns[0]["id"] if campaigns else None
    current_target = navigation.init_navigation(
        st.session_state,
        query_params=st.query_params,
        default_campaign_id=default_camp,
    )

    # 1. Árbol de navegación interactivo en la barra lateral
    new_selection = navigation.render_navigation_tree(st, tree, current_target)
    if new_selection:
        navigation.set_nav_target(st.session_state, **new_selection, query_params=st.query_params)
        st.rerun()

    with st.sidebar:
        is_local_dev = (ROOT / "pipeline").exists()
        if is_local_dev:
            st.divider()
            if st.button("🔄 Recargar Base de Datos", width="stretch"):
                st.cache_data.clear()
                st.rerun()
        st.caption("Miskatonic Scribe v2.0 • Archivo de Rol")

    # 2. Migas de Pan (Breadcrumbs) interactivas en la cabecera (Spec 16 / US2)
    navigation.render_breadcrumbs(st, current_target, tree)

    # 3. Enrutamiento del cuerpo principal por nivel de navegación
    cur_level = current_target.get("level", navigation.NAV_GLOBAL)
    cur_camp = current_target.get("campaign_id")
    cur_sess = current_target.get("session_id")

    if cur_level == navigation.NAV_GLOBAL:
        # Portada del Archivo General (Spec 16 / US3)
        archive_kpis = navigation.load_global_archive_kpis()
        camp_select = navigation.render_global_archive_view(st, archive_kpis, tree["campaigns"])
        if camp_select:
            navigation.set_nav_target(st.session_state, **camp_select, query_params=st.query_params)
            st.rerun()

    elif cur_level == navigation.NAV_CAMPAIGN:
        # Visión Global de la Campaña (Spec 15)
        if cur_camp:
            render_campaign_global_view(cur_camp)
        else:
            st.info("Selecciona una campaña en el árbol lateral.")

    elif cur_level == navigation.NAV_EPISODE:
        # Visión Detallada del Episodio
        if cur_sess:
            camp_info = next((c for c in campaigns if c["id"] == cur_camp), None) if cur_camp else None
            if cur_camp:
                camp_match = next((c for c in tree["campaigns"] if c["id"] == cur_camp), None)
                camp_episodes = camp_match["episodes"] if camp_match else []
            else:
                camp_episodes = tree["orphan_sessions"]

            render_session_view(cur_sess, camp_info, camp_episodes)
        else:
            st.info("Selecciona un episodio en el árbol lateral para ver sus analíticas.")


if __name__ == "__main__":
    main()
