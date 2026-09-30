#!/usr/bin/env python3
"""Módulo de visualización de evolución temporal de personajes en campaña — Spec 20.

Genera gráficas interactivas cronológicas (por episodio) de la participación,
cuota de protagonismo, intervenciones de diálogo, cordura y pistas de cada investigador.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

import plotly.graph_objects as go

# Paleta distintiva y contrastada para tema oscuro Lovecraftian
INVESTIGATOR_PALETTE = [
    "#38bdf8",  # Azul celeste
    "#a78bfa",  # Violeta arcano
    "#34d399",  # Verde esmeralda
    "#fb923c",  # Ámbar cálido
    "#f472b6",  # Rosa
    "#818cf8",  # Índigo
    "#2dd4bf",  # Turquesa
    "#e879f9",  # Fucsia místico
    "#fbbf24",  # Dorado antiguo
    "#4ade80",  # Verde brillante
]

METRIC_CONFIG = {
    "speaking_minutes": {
        "label": "⏱️ Minutos de Habla (Tiempo en mesa)",
        "short_label": "Minutos de Habla",
        "unit": "min",
        "format": ".1f",
    },
    "relative_share_pct": {
        "label": "📊 Cuota de Protagonismo (% de Investigadores)",
        "short_label": "Cuota de Protagonismo",
        "unit": "%",
        "format": ".1f",
    },
    "turn_count": {
        "label": "🗣️ Turnos de Diálogo (Intervenciones)",
        "short_label": "Turnos de Diálogo",
        "unit": "turnos",
        "format": "d",
    },
    "sanity_loss": {
        "label": "🧠 Pérdida de Cordura (-SAN)",
        "short_label": "Cordura Perdida",
        "unit": "SAN",
        "format": "d",
    },
    "clues_found": {
        "label": "🔍 Pistas Descubiertas",
        "short_label": "Pistas Halladas",
        "unit": "pistas",
        "format": "d",
    },
    "fumbles": {
        "label": "💀 Pifias y Fallos Críticos",
        "short_label": "Pifias",
        "unit": "pifias",
        "format": "d",
    },
    "critical_successes": {
        "label": "🎯 Éxitos Críticos y Extremos",
        "short_label": "Éxitos Críticos",
        "unit": "críticos",
        "format": "d",
    },
}


def clean_episode_title(raw_title: str | None, ep_order: int | None, index: int) -> tuple[str, str]:
    """Genera una etiqueta corta y limpia para el eje X y tooltips.

    Retorna: (label_corta, titulo_limpio)
    Ejemplo: ("Ep 01", "Ep 01: Mondariz")
    """
    order = ep_order if ep_order is not None else index
    short_label = f"Ep {order:02d}"

    if not raw_title:
        return short_label, short_label

    # Limpiar títulos típicos como "Horror en el Orient Express #1: Mondariz | Campaña..."
    t = str(raw_title)
    # Quitar sufijos comunes
    t = re.sub(r"\s*\|\s*Campaña.*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"^\s*\(CORRECTO\)\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"^\s*\(RESUBIDO\)\s*", "", t, flags=re.IGNORECASE)

    # Extraer subtítulo si tiene "#X: Subtítulo"
    m = re.search(r"#\d+\s*:\s*(.+)$", t)
    if m:
        sub = m.group(1).strip()
        full_label = f"{short_label}: {sub}"
    else:
        full_label = f"{short_label}: {t[:30]}"

    return short_label, full_label


def build_campaign_evolution_series(
    campaign_sessions: list[dict[str, Any]],
    session_stats_map: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Construye las series temporales por personaje a lo largo de los capítulos de la campaña.

    Args:
        campaign_sessions: Lista de sesiones de la campaña con id, title, episode_order, etc.
        session_stats_map: Mapeo de session_id a lista de stats de investigadores (build_session_investigator_stats).

    Returns:
        dict con metadatos de episodios, personajes y series por métrica.
    """
    if not campaign_sessions:
        return {
            "episodes": [],
            "characters": [],
            "character_meta": {},
            "series": {m: {} for m in METRIC_CONFIG},
        }

    # 1. Ordenar sesiones cronológicamente
    sorted_sessions = sorted(
        campaign_sessions,
        key=lambda s: (
            s.get("episode_order") if s.get("episode_order") is not None else 9999,
            s.get("analyzed_at") or "",
        ),
    )

    # 2. Descubrir todos los personajes únicos y asociar metadatos
    character_totals: dict[str, float] = {}
    character_meta: dict[str, dict[str, Any]] = {}

    for s_idx, session in enumerate(sorted_sessions):
        sid = session.get("id") or ""
        s_stats = session_stats_map.get(sid, [])
        for char_stat in s_stats:
            c_name = char_stat.get("character") or "Investigador"
            p_name = char_stat.get("player") or "Jugador"
            airtime = float(char_stat.get("speaking_seconds") or 0.0)

            character_totals[c_name] = character_totals.get(c_name, 0.0) + airtime
            if c_name not in character_meta:
                character_meta[c_name] = {
                    "character": c_name,
                    "player": p_name,
                    "color": "#38bdf8",  # asignado luego
                }

    # Ordenar personajes por tiempo total de habla
    sorted_characters = sorted(character_totals.keys(), key=lambda c: character_totals[c], reverse=True)
    for i, c_name in enumerate(sorted_characters):
        color = INVESTIGATOR_PALETTE[i % len(INVESTIGATOR_PALETTE)]
        character_meta[c_name]["color"] = color

    # 3. Construir lista de episodios
    episodes: list[dict[str, Any]] = []
    for idx, s in enumerate(sorted_sessions, start=1):
        sid = s.get("id") or ""
        order = s.get("episode_order")
        short_lbl, full_lbl = clean_episode_title(s.get("title"), order, idx)
        dur_sec = float(s.get("duration_seconds") or 0.0)
        episodes.append({
            "index": idx,
            "session_id": sid,
            "episode_order": order if order is not None else idx,
            "short_label": short_lbl,
            "full_label": full_lbl,
            "raw_title": s.get("title") or "",
            "duration_minutes": round(dur_sec / 60.0, 1),
        })

    # 4. Inicializar matrices de series temporales
    series: dict[str, dict[str, list[Any]]] = {m: {c: [] for c in sorted_characters} for m in METRIC_CONFIG}

    for ep in episodes:
        sid = ep["session_id"]
        stats_list = session_stats_map.get(sid, [])
        char_map = {st.get("character"): st for st in stats_list}

        # Calcular tiempo total de investigadores en este episodio para la cuota relativa (%)
        total_inv_sec = sum(float(st.get("speaking_seconds") or 0.0) for st in stats_list)

        for c_name in sorted_characters:
            st = char_map.get(c_name)
            if st:
                sec = float(st.get("speaking_seconds") or 0.0)
                mins = round(sec / 60.0, 1)
                share = round((sec / total_inv_sec * 100.0), 1) if total_inv_sec > 0 else 0.0
                turns = int(st.get("turn_count") or 0)
                san = int(st.get("sanity_loss") or 0)
                clues = int(st.get("clues_found") or 0)
                fumbles = int(st.get("fumbles") or 0)
                crits = int(st.get("critical_successes") or 0)
            else:
                mins = 0.0
                share = 0.0
                turns = 0
                san = 0
                clues = 0
                fumbles = 0
                crits = 0

            series["speaking_minutes"][c_name].append(mins)
            series["relative_share_pct"][c_name].append(share)
            series["turn_count"][c_name].append(turns)
            series["sanity_loss"][c_name].append(san)
            series["clues_found"][c_name].append(clues)
            series["fumbles"][c_name].append(fumbles)
            series["critical_successes"][c_name].append(crits)

    return {
        "episodes": episodes,
        "characters": sorted_characters,
        "character_meta": character_meta,
        "series": series,
    }


def render_campaign_evolution_chart(
    evolution_data: dict[str, Any],
    selected_metric: str = "speaking_minutes",
    selected_characters: list[str] | None = None,
    is_cumulative: bool = False,
) -> go.Figure:
    """Genera la figura interactiva de líneas Plotly con la evolución por episodio.

    Args:
        evolution_data: Diccionario producido por build_campaign_evolution_series.
        selected_metric: Clave de la métrica (speaking_minutes, relative_share_pct, etc.).
        selected_characters: Lista de personajes a visualizar (None o vacío = todos).
        is_cumulative: Si es True, grafica la suma acumulada a lo largo del tiempo.

    Returns:
        plotly.graph_objects.Figure configurada con diseño Lovecraftian.
    """
    episodes = evolution_data.get("episodes", [])
    if not episodes:
        fig = go.Figure()
        fig.update_layout(title="Sin episodios disponibles")
        return fig

    all_chars = evolution_data.get("characters", [])
    char_meta = evolution_data.get("character_meta", {})
    metric_series = evolution_data.get("series", {}).get(selected_metric, {})
    config = METRIC_CONFIG.get(selected_metric, METRIC_CONFIG["speaking_minutes"])

    active_chars = [c for c in all_chars if selected_characters is None or c in selected_characters]
    if not active_chars:
        active_chars = all_chars

    x_labels = [ep["short_label"] for ep in episodes]
    x_titles = [ep["full_label"] for ep in episodes]

    fig = go.Figure()

    for c_name in active_chars:
        raw_values = metric_series.get(c_name, [0.0] * len(episodes))
        if is_cumulative:
            values = []
            curr_total = 0.0
            for v in raw_values:
                curr_total += v
                values.append(round(curr_total, 1) if isinstance(v, float) else int(curr_total))
        else:
            values = raw_values

        meta = char_meta.get(c_name, {})
        player = meta.get("player", "")
        color = meta.get("color", "#38bdf8")

        # Custom data para tooltip enriquecido: [titulo_episodio, nombre_personaje, jugador, unidad, val_puntual, val_acum]
        custom_data = [
            [x_titles[i], c_name, player, config["unit"], raw_values[i], values[i]]
            for i in range(len(episodes))
        ]

        if is_cumulative:
            hover_template = (
                "<b>%{customdata[0]}</b><br>"
                "👤 <b>%{customdata[1]}</b> (%{customdata[2]})<br>"
                f"📈 Total Acumulado: <b>%{{y}} %{{customdata[3]}}</b><br>"
                f"📍 En este capítulo: <i>+{{customdata[4]}} %{{customdata[3]}}</i>"
                "<extra></extra>"
            )
        else:
            hover_template = (
                "<b>%{customdata[0]}</b><br>"
                "👤 <b>%{customdata[1]}</b> (%{customdata[2]})<br>"
                f"📊 {config['short_label']}: <b>%{{y}} %{{customdata[3]}}</b>"
                "<extra></extra>"
            )

        fig.add_trace(
            go.Scatter(
                x=x_labels,
                y=values,
                mode="lines+markers",
                name=f"{c_name} ({player})",
                line=dict(color=color, width=2.5),
                marker=dict(size=7, color=color, symbol="circle"),
                customdata=custom_data,
                hovertemplate=hover_template,
            )
        )

    chart_title = (
        f"<b>Progresión Acumulada en Campaña: {config['label']}</b>"
        if is_cumulative
        else f"<b>Evolución por Capítulo: {config['label']}</b>"
    )
    y_axis_title = (
        f"{config['short_label']} Acumulado ({config['unit']})"
        if is_cumulative
        else f"{config['short_label']} ({config['unit']})"
    )

    fig.update_layout(
        title=dict(
            text=chart_title,
            font=dict(size=15, color="#e6edf3"),
            x=0.01,
            y=0.96,
        ),
        xaxis=dict(
            title="Capítulo de la Campaña",
            gridcolor="rgba(255, 255, 255, 0.08)",
            tickangle=-45,
            tickfont=dict(size=11, color="#8b949e"),
        ),
        yaxis=dict(
            title=f"{config['short_label']} ({config['unit']})",
            gridcolor="rgba(255, 255, 255, 0.08)",
            zerolinecolor="rgba(255, 255, 255, 0.15)",
            tickfont=dict(size=11, color="#8b949e"),
        ),
        plot_bgcolor="rgba(14, 17, 23, 0.6)",
        paper_bgcolor="rgba(0, 0, 0, 0)",
        margin=dict(l=45, r=20, t=55, b=65),
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1.0,
            font=dict(size=11, color="#c9d1d9"),
            bgcolor="rgba(14, 17, 23, 0.8)",
            bordercolor="rgba(255, 255, 255, 0.1)",
            borderwidth=1,
        ),
    )

    return fig


def render_campaign_relative_share_chart(
    evolution_data: dict[str, Any],
    selected_characters: list[str] | None = None,
) -> go.Figure:
    """Genera la figura interactiva de barras apiladas 100% que muestra la cuota de protagonismo relativa.

    Args:
        evolution_data: Diccionario producido por build_campaign_evolution_series.
        selected_characters: Lista opcional para aislar personajes.

    Returns:
        plotly.graph_objects.Figure configurada como stacked 100% bar.
    """
    episodes = evolution_data.get("episodes", [])
    if not episodes:
        fig = go.Figure()
        fig.update_layout(title="Sin episodios disponibles")
        return fig

    all_chars = evolution_data.get("characters", [])
    char_meta = evolution_data.get("character_meta", {})
    share_series = evolution_data.get("series", {}).get("relative_share_pct", {})
    minutes_series = evolution_data.get("series", {}).get("speaking_minutes", {})

    active_chars = [c for c in all_chars if selected_characters is None or c in selected_characters]
    if not active_chars:
        active_chars = all_chars

    x_labels = [ep["short_label"] for ep in episodes]
    x_titles = [ep["full_label"] for ep in episodes]

    fig = go.Figure()

    for c_name in active_chars:
        shares = share_series.get(c_name, [0.0] * len(episodes))
        mins = minutes_series.get(c_name, [0.0] * len(episodes))
        meta = char_meta.get(c_name, {})
        player = meta.get("player", "")
        color = meta.get("color", "#38bdf8")

        custom_data = [
            [x_titles[i], c_name, player, mins[i]]
            for i in range(len(episodes))
        ]

        fig.add_trace(
            go.Bar(
                x=x_labels,
                y=shares,
                name=f"{c_name} ({player})",
                marker=dict(color=color),
                customdata=custom_data,
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "👤 <b>%{customdata[1]}</b> (%{customdata[2]})<br>"
                    "📊 Cuota: <b>%{y:.1f}%</b> (%{customdata[3]:.1f} min)"
                    "<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        barmode="stack",
        title=dict(
            text="<b>Reparto Relativo de Protagonismo en Mesa (100% Investigadores)</b>",
            font=dict(size=15, color="#e6edf3"),
            x=0.01,
            y=0.96,
        ),
        xaxis=dict(
            title="Capítulo de la Campaña",
            gridcolor="rgba(255, 255, 255, 0.08)",
            tickangle=-45,
            tickfont=dict(size=11, color="#8b949e"),
        ),
        yaxis=dict(
            title="Cuota de Habla (%)",
            range=[0, 100],
            gridcolor="rgba(255, 255, 255, 0.08)",
            tickfont=dict(size=11, color="#8b949e"),
        ),
        plot_bgcolor="rgba(14, 17, 23, 0.6)",
        paper_bgcolor="rgba(0, 0, 0, 0)",
        margin=dict(l=45, r=20, t=55, b=65),
        hovermode="x",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1.0,
            font=dict(size=11, color="#c9d1d9"),
            bgcolor="rgba(14, 17, 23, 0.8)",
            bordercolor="rgba(255, 255, 255, 0.1)",
            borderwidth=1,
        ),
    )

    return fig


def render_campaign_evolution_section(
    st: Any,
    campaign_sessions: list[dict[str, Any]],
    session_stats_map: dict[str, list[dict[str, Any]]],
) -> None:
    """Renderiza el bloque completo de evolución temporal de investigadores en la vista de campaña.

    Args:
        st: Módulo de Streamlit.
        campaign_sessions: Lista de sesiones de la campaña ordenadas.
        session_stats_map: Diccionario session_id -> lista de estadísticas de investigadores.
    """
    if not campaign_sessions:
        return

    evolution_data = build_campaign_evolution_series(campaign_sessions, session_stats_map)
    all_chars = evolution_data.get("characters", [])
    if not all_chars:
        return

    st.markdown("---")
    st.markdown("### 📈 Evolución Temporal de los Investigadores")
    st.caption(
        "Analiza la trayectoria de cada personaje a lo largo de los capítulos: quién lideró la mesa en cada fase, "
        "dónde se concentró la pérdida de cordura y cómo evolucionó el reparto del tiempo."
    )

    # 1. Controles superiores (Métrica, Modo Temporal, Tipo de Gráfico y Filtro)
    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([1.4, 1.1, 1.1])

    metric_keys = list(METRIC_CONFIG.keys())
    metric_labels = [METRIC_CONFIG[k]["label"] for k in metric_keys]

    with ctrl_col1:
        selected_label = st.selectbox(
            "Seleccionar Métrica a Visualizar",
            options=metric_labels,
            index=0,
            key="camp_evo_metric_select",
        )
        selected_metric = metric_keys[metric_labels.index(selected_label)]

    with ctrl_col2:
        calc_mode = st.radio(
            "Cálculo Temporal",
            options=["📍 Por Capítulo", "📈 Acumulado"],
            horizontal=True,
            key="camp_evo_calc_mode",
            help="Elige si ver el valor de cada episodio individual o la suma acumulada que muestra el progreso a lo largo de la campaña.",
        )
        is_cumulative = calc_mode == "📈 Acumulado"

    with ctrl_col3:
        chart_mode = st.radio(
            "Modo de Gráfico",
            options=["📈 Curva de Líneas", "📊 Reparto 100%"],
            horizontal=True,
            key="camp_evo_mode_select",
            help="Curva temporal de evolución o barras apiladas de cuota entre investigadores.",
        )

    # Filtro multiselección de personajes
    char_options = all_chars
    selected_chars = st.multiselect(
        "Filtrar Investigadores a Comparar (Vacío = Todos)",
        options=char_options,
        default=char_options,
        key="camp_evo_chars_filter",
        help="Permite aislar dos o más personajes para comparar sus trayectorias directamente (ej. Álex Coxen vs Lily Bennett).",
    )

    active_chars = selected_chars if selected_chars else all_chars

    # 2. Renderizado del Gráfico
    if chart_mode.startswith("📈"):
        fig = render_campaign_evolution_chart(
            evolution_data,
            selected_metric=selected_metric,
            selected_characters=active_chars,
            is_cumulative=is_cumulative,
        )
    else:
        fig = render_campaign_relative_share_chart(
            evolution_data,
            selected_characters=active_chars,
        )

    st.plotly_chart(fig, width="stretch")

    # 3. Bloque de Insights y Resumen para la métrica seleccionada
    metric_info = METRIC_CONFIG.get(selected_metric, METRIC_CONFIG["speaking_minutes"])
    series_data = evolution_data.get("series", {}).get(selected_metric, {})
    episodes = evolution_data.get("episodes", [])

    if is_cumulative and chart_mode.startswith("📈"):
        # Insight de líder acumulado
        lead_char = ""
        lead_total = -1.0
        for c in active_chars:
            vals = series_data.get(c, [])
            tot = sum(vals)
            if tot > lead_total:
                lead_total = tot
                lead_char = c

        if lead_total > 0 and lead_char:
            lead_player = evolution_data.get("character_meta", {}).get(lead_char, {}).get("player", "")
            fmt_val = f"{lead_total:.1f}" if isinstance(lead_total, float) else f"{int(lead_total)}"
            st.info(
                f"📈 **Líder Acumulado en Campaña ({metric_info['short_label']}):** "
                f"**{lead_char}** ({lead_player}) con un total acumulado de **{fmt_val} {metric_info['unit']}** "
                f"al cierre del capítulo {len(episodes)}."
            )
    else:
        # Encontrar el récord individual en un solo capítulo
        max_val = -1.0
        max_char = ""
        max_ep_label = ""

        for c in active_chars:
            vals = series_data.get(c, [])
            for i, v in enumerate(vals):
                if v > max_val:
                    max_val = v
                    max_char = c
                    max_ep_label = episodes[i]["full_label"] if i < len(episodes) else f"Ep {i+1}"

        if max_val > 0 and max_char:
            c_player = evolution_data.get("character_meta", {}).get(max_char, {}).get("player", "")
            formatted_val = f"{max_val:.1f}" if isinstance(max_val, float) else f"{int(max_val)}"
            st.info(
                f"💡 **Pico Máximo en un Capítulo ({metric_info['short_label']}):** "
                f"**{max_char}** ({c_player}) con **{formatted_val} {metric_info['unit']}** en **{max_ep_label}**."
            )

