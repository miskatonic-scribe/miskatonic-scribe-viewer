#!/usr/bin/env python3
"""Módulo de navegación jerárquica y gestión de estado de vista para Miskatonic Scribe (Spec 16).

Centraliza el estado semántico de navegación (Global, Campaña, Episodio)
y desacopla la lógica de selección de los widgets visuales de Streamlit.
"""

from __future__ import annotations

from typing import Any, Mapping

# Constantes de niveles de navegación
NAV_GLOBAL = "global"
NAV_CAMPAIGN = "campaign"
NAV_EPISODE = "episode"

VALID_LEVELS = {NAV_GLOBAL, NAV_CAMPAIGN, NAV_EPISODE}
STATE_KEY = "nav_target"


def normalize_nav_target(target: Mapping[str, Any] | None) -> dict[str, Any]:
    """Valida y normaliza un diccionario de destino de navegación."""
    if not isinstance(target, Mapping):
        return {
            "level": NAV_GLOBAL,
            "campaign_id": None,
            "session_id": None,
        }

    level = str(target.get("level", NAV_GLOBAL)).lower().strip()
    if level not in VALID_LEVELS:
        level = NAV_GLOBAL

    campaign_id = target.get("campaign_id")
    session_id = target.get("session_id")

    # Reglas de integridad de estado
    if level == NAV_GLOBAL:
        campaign_id = None
        session_id = None
    elif level == NAV_CAMPAIGN:
        session_id = None
        if not campaign_id:
            level = NAV_GLOBAL
    elif level == NAV_EPISODE:
        if not session_id:
            level = NAV_CAMPAIGN if campaign_id else NAV_GLOBAL

    return {
        "level": level,
        "campaign_id": str(campaign_id).strip() if campaign_id else None,
        "session_id": str(session_id).strip() if session_id else None,
    }


def get_nav_target(session_state: Any) -> dict[str, Any]:
    """Obtiene el destino de navegación actual desde session_state garantizando su validez."""
    raw = getattr(session_state, STATE_KEY, None) if not isinstance(session_state, dict) else session_state.get(STATE_KEY)
    normalized = normalize_nav_target(raw)
    # Sincronizar en el estado si hubo normalización
    if isinstance(session_state, dict):
        session_state[STATE_KEY] = normalized
    else:
        setattr(session_state, STATE_KEY, normalized)
    return normalized


def set_nav_target(
    session_state: Any,
    level: str,
    campaign_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Establece un nuevo destino de navegación válido en session_state."""
    new_target = normalize_nav_target({
        "level": level,
        "campaign_id": campaign_id,
        "session_id": session_id,
    })
    if isinstance(session_state, dict):
        session_state[STATE_KEY] = new_target
    else:
        setattr(session_state, STATE_KEY, new_target)
    return new_target


def init_navigation(
    session_state: Any,
    default_campaign_id: str | None = None,
    default_session_id: str | None = None,
) -> dict[str, Any]:
    """Inicializa el estado de navegación si no existe previamente."""
    has_key = (
        STATE_KEY in session_state
        if isinstance(session_state, dict)
        else hasattr(session_state, STATE_KEY)
    )

    if not has_key:
        if default_session_id:
            return set_nav_target(
                session_state,
                NAV_EPISODE,
                campaign_id=default_campaign_id,
                session_id=default_session_id,
            )
        elif default_campaign_id:
            return set_nav_target(
                session_state,
                NAV_CAMPAIGN,
                campaign_id=default_campaign_id,
            )
        else:
            return set_nav_target(session_state, NAV_GLOBAL)

    return get_nav_target(session_state)


def format_duration(seconds: float | None) -> str:
    """Convierte segundos a formato amigable como '01:01h' o '59m'."""
    if not seconds or seconds <= 0:
        return ""
    total_min = int(seconds // 60)
    hrs = total_min // 60
    mins = total_min % 60
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}h"
    return f"{mins:02d}m"


def build_navigation_tree(
    campaigns: list[dict[str, Any]],
    all_sessions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Construye la estructura de árbol jerárquica para la navegación."""
    # Indexar sesiones por campaign_id
    sessions_by_camp: dict[str, list[dict[str, Any]]] = {}
    orphan_sessions: list[dict[str, Any]] = []

    for s in all_sessions:
        cid = s.get("campaign_id")
        if cid:
            sessions_by_camp.setdefault(str(cid).strip(), []).append(s)
        else:
            orphan_sessions.append(s)

    # Ordenar episodios dentro de cada campaña por episode_order
    campaign_nodes: list[dict[str, Any]] = []
    for c in campaigns:
        cid = str(c["id"]).strip()
        raw_eps = sessions_by_camp.get(cid, [])
        # Ordenar por episode_order ascendente
        sorted_eps = sorted(
            raw_eps,
            key=lambda x: (
                x.get("episode_order") if x.get("episode_order") is not None else 9999,
                x.get("analyzed_at") or "",
            ),
        )
        campaign_nodes.append({
            "id": cid,
            "name": c.get("name", cid),
            "system": c.get("system", ""),
            "description": c.get("description", ""),
            "episode_count": len(sorted_eps),
            "episodes": sorted_eps,
        })

    return {
        "total_sessions": len(all_sessions),
        "campaigns": campaign_nodes,
        "orphan_sessions": orphan_sessions,
    }


def format_episode_button_label(
    session: dict[str, Any],
    is_active: bool = False,
) -> str:
    """Genera la etiqueta para el botón de episodio en el árbol."""
    order = session.get("episode_order")
    order_prefix = f"[Ep. {order}] " if order is not None else ""
    raw_title = session.get("title") or session.get("id") or "Sesión"

    # Acortar título para no saturar la barra lateral
    max_len = 24
    short_title = (raw_title[:max_len] + "…") if len(raw_title) > max_len else raw_title

    dur_str = format_duration(session.get("duration_seconds"))
    dur_suffix = f" ({dur_str})" if dur_str else ""

    if is_active:
        return f"▶ {order_prefix}{short_title}{dur_suffix}"
    return f"🎬 {order_prefix}{short_title}{dur_suffix}"


def render_navigation_tree(
    st_module: Any,
    tree: dict[str, Any],
    current_target: dict[str, Any],
) -> dict[str, Any] | None:
    """Renderiza el árbol de navegación jerárquico en la barra lateral de Streamlit.

    Retorna un nuevo target dict si el usuario hizo clic en algún nodo, o None si no hubo cambio.
    """
    st = st_module
    cur_level = current_target.get("level", NAV_GLOBAL)
    cur_camp = current_target.get("campaign_id")
    cur_sess = current_target.get("session_id")

    new_selection: dict[str, Any] | None = None

    with st.sidebar:
        st.markdown("### 🗂️ Explorador de Archivo")

        # 1. Nodo Raíz: Archivo General
        is_global_active = cur_level == NAV_GLOBAL
        global_label = "▶ 🌐 Archivo General (Catálogo)" if is_global_active else "🌐 Archivo General (Catálogo)"
        if st.button(
            global_label,
            key="nav_btn_global_archive",
            type="primary" if is_global_active else "secondary",
            width="stretch",
        ):
            new_selection = {"level": NAV_GLOBAL, "campaign_id": None, "session_id": None}

        st.markdown("---")

        # 2. Carpetas de Campañas
        campaigns = tree.get("campaigns", [])
        for c in campaigns:
            cid = c["id"]
            cname = c["name"]
            ep_count = c["episode_count"]
            is_active_camp = (cur_camp == cid)

            expander_title = f"🏰 {cname} ({ep_count} eps)"
            with st.expander(expander_title, expanded=is_active_camp):
                # Botón de Visión Global de la Campaña
                is_camp_overview_active = (cur_level == NAV_CAMPAIGN and is_active_camp)
                camp_btn_label = "▶ 🗺️ Visión Global" if is_camp_overview_active else "🗺️ Visión Global"
                if st.button(
                    camp_btn_label,
                    key=f"nav_btn_camp_{cid}",
                    type="primary" if is_camp_overview_active else "secondary",
                    width="stretch",
                ):
                    new_selection = {"level": NAV_CAMPAIGN, "campaign_id": cid, "session_id": None}

                # Lista de Episodios
                for ep in c.get("episodes", []):
                    sid = ep["id"]
                    is_active_ep = (cur_level == NAV_EPISODE and cur_sess == sid)
                    ep_label = format_episode_button_label(ep, is_active=is_active_ep)
                    if st.button(
                        ep_label,
                        key=f"nav_btn_ep_{cid}_{sid}",
                        type="primary" if is_active_ep else "secondary",
                        width="stretch",
                    ):
                        new_selection = {"level": NAV_EPISODE, "campaign_id": cid, "session_id": sid}

        # 3. Partidas Sueltas / One-Shots (solo si existen)
        orphans = tree.get("orphan_sessions", [])
        if orphans:
            is_orphan_active = (cur_camp == "__oneshots__" or (cur_level == NAV_EPISODE and not cur_camp))
            with st.expander(f"🎲 Partidas Sueltas ({len(orphans)})", expanded=is_orphan_active):
                for ep in orphans:
                    sid = ep["id"]
                    is_active_ep = (cur_level == NAV_EPISODE and cur_sess == sid)
                    ep_label = format_episode_button_label(ep, is_active=is_active_ep)
                    if st.button(
                        ep_label,
                        key=f"nav_btn_orphan_{sid}",
                        type="primary" if is_active_ep else "secondary",
                        width="stretch",
                    ):
                        new_selection = {"level": NAV_EPISODE, "campaign_id": None, "session_id": sid}

    return new_selection


def build_breadcrumbs(
    current_target: dict[str, Any],
    tree: dict[str, Any],
) -> str:
    """Construye la cadena de texto HTML/Markdown para las migas de pan (Breadcrumbs)."""
    cur_level = current_target.get("level", NAV_GLOBAL)
    cur_camp = current_target.get("campaign_id")
    cur_sess = current_target.get("session_id")

    if cur_level == NAV_GLOBAL:
        return "🌐 **Archivo Miskatonic** &nbsp;›&nbsp; 📊 *Resumen General del Catálogo*"

    # Buscar datos de campaña en el árbol
    camp_match = next((c for c in tree.get("campaigns", []) if c["id"] == cur_camp), None)
    camp_name = camp_match["name"] if camp_match else (cur_camp or "Partida Suelta")

    if cur_level == NAV_CAMPAIGN:
        return f"🌐 **Archivo Miskatonic** &nbsp;›&nbsp; 🏰 **{camp_name}** &nbsp;›&nbsp; 🗺️ *Visión Global*"

    # Buscar datos de sesión
    ep_title = cur_sess
    ep_order_str = ""
    if camp_match:
        sess_match = next((s for s in camp_match.get("episodes", []) if s["id"] == cur_sess), None)
        if sess_match:
            raw_title = sess_match.get("title") or cur_sess
            ep_title = (raw_title[:35] + "…") if len(raw_title) > 37 else raw_title
            order = sess_match.get("episode_order")
            if order is not None:
                ep_order_str = f"[Ep. {order}] "
    else:
        # Partida huérfana
        orphans = tree.get("orphan_sessions", [])
        sess_match = next((s for s in orphans if s["id"] == cur_sess), None)
        if sess_match:
            ep_title = sess_match.get("title") or cur_sess

    return f"🌐 **Archivo Miskatonic** &nbsp;›&nbsp; 🏰 **{camp_name}** &nbsp;›&nbsp; 🎬 *{ep_order_str}{ep_title}*"


def get_adjacent_episodes(
    current_session_id: str,
    campaign_id: str | None,
    tree: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Determina los episodios anterior y siguiente dentro de la misma campaña."""
    if not campaign_id:
        return None, None

    camp_match = next((c for c in tree.get("campaigns", []) if c["id"] == campaign_id), None)
    if not camp_match:
        return None, None

    eps = camp_match.get("episodes", [])
    current_idx = next((i for i, ep in enumerate(eps) if ep["id"] == current_session_id), None)
    if current_idx is None:
        return None, None

    prev_ep = eps[current_idx - 1] if current_idx > 0 else None
    next_ep = eps[current_idx + 1] if current_idx < len(eps) - 1 else None
    return prev_ep, next_ep


def render_episode_pagination_footer(
    st_module: Any,
    current_session_id: str,
    campaign_id: str | None,
    tree: dict[str, Any],
) -> dict[str, Any] | None:
    """Renderiza la botonera de navegación secuencial al pie de un episodio."""
    st = st_module
    prev_ep, next_ep = get_adjacent_episodes(current_session_id, campaign_id, tree)

    new_target: dict[str, Any] | None = None

    st.markdown("---")
    c_prev, c_camp, c_next = st.columns([2, 2, 2])

    with c_prev:
        if prev_ep:
            order_p = prev_ep.get("episode_order")
            pref_p = f"Ep. {order_p}" if order_p is not None else "Anterior"
            if st.button(f"⬅ {pref_p}", key=f"foot_prev_{current_session_id}", width="stretch"):
                new_target = {"level": NAV_EPISODE, "campaign_id": campaign_id, "session_id": prev_ep["id"]}
        else:
            st.button("⬅ Episodio 1 (Inicio)", key=f"foot_prev_{current_session_id}", disabled=True, width="stretch")

    with c_camp:
        if campaign_id:
            if st.button("🏰 Visión de Campaña", key=f"foot_camp_{current_session_id}", width="stretch"):
                new_target = {"level": NAV_CAMPAIGN, "campaign_id": campaign_id, "session_id": None}

    with c_next:
        if next_ep:
            order_n = next_ep.get("episode_order")
            pref_n = f"Ep. {order_n}" if order_n is not None else "Siguiente"
            if st.button(f"{pref_n} ➡", key=f"foot_next_{current_session_id}", type="primary", width="stretch"):
                new_target = {"level": NAV_EPISODE, "campaign_id": campaign_id, "session_id": next_ep["id"]}
        else:
            st.button("🎉 Fin de Campaña", key=f"foot_next_{current_session_id}", disabled=True, width="stretch")

    return new_target


def load_global_archive_kpis(db_path: Any = None) -> dict[str, Any]:
    """Calcula las métricas consolidadas de todo el catálogo histórico de partidas."""
    import sqlite3
    from core import paths

    target_db = db_path or paths.DB_PATH
    if not target_db.exists():
        return {
            "total_sessions": 0,
            "total_duration_hours": 0.0,
            "average_tension": 0.0,
            "total_sanity_events": 0,
            "total_sanity_loss": 0,
            "total_clues": 0,
            "total_milestones": 0,
            "total_critical_rolls": 0,
            "total_combat_events": 0,
            "total_campaigns": 0,
        }

    with sqlite3.connect(target_db) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT 
                (SELECT COUNT(*) FROM sessions) AS total_sessions,
                (SELECT COALESCE(SUM(duration_seconds), 0) FROM sessions) AS total_duration_seconds,
                (SELECT COALESCE(AVG(average_tension), 0) FROM sessions) AS average_tension,
                (SELECT COUNT(*) FROM sanity_events) AS total_sanity_events,
                (SELECT COALESCE(SUM(sanity_loss), 0) FROM sanity_events) AS total_sanity_loss,
                (SELECT COUNT(*) FROM clues) AS total_clues,
                (SELECT COUNT(*) FROM narrative_milestones) AS total_milestones,
                (SELECT COUNT(*) FROM critical_rolls) AS total_critical_rolls,
                (SELECT COUNT(*) FROM combat_events) AS total_combat_events,
                (SELECT COUNT(*) FROM campaigns) AS total_campaigns
            """
        ).fetchone()

        total_secs = float(row["total_duration_seconds"] or 0)
        return {
            "total_sessions": int(row["total_sessions"] or 0),
            "total_duration_hours": round(total_secs / 3600.0, 1),
            "average_tension": round(float(row["average_tension"] or 0), 1),
            "total_sanity_events": int(row["total_sanity_events"] or 0),
            "total_sanity_loss": int(row["total_sanity_loss"] or 0),
            "total_clues": int(row["total_clues"] or 0),
            "total_milestones": int(row["total_milestones"] or 0),
            "total_critical_rolls": int(row["total_critical_rolls"] or 0),
            "total_combat_events": int(row["total_combat_events"] or 0),
            "total_campaigns": int(row["total_campaigns"] or 0),
        }


def render_global_archive_view(
    st_module: Any,
    kpis: dict[str, Any],
    campaigns: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Renderiza la portada del Archivo General con los KPIs macro y tarjetas de campaña."""
    st = st_module
    new_selection: dict[str, Any] | None = None

    st.markdown(
        """
        <div style="background: linear-gradient(135deg, #121820 0%, #1e2638 100%); 
                    border: 1px solid #2d3748; border-radius: 12px; padding: 24px; margin-bottom: 24px;">
            <h1 style="color: #64ffda; margin-top: 0; margin-bottom: 8px;">🏛️ Archivo Miskatonic</h1>
            <p style="color: #a0aec0; font-size: 1.1rem; margin-bottom: 0;">
                Catálogo histórico consolidado de partidas y campañas de horror cósmico analizadas por IA.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Fila de KPIs Principales
    st.markdown("### 📊 Macro-Estadísticas del Repositorio")
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric(
            "⏳ Tiempo de Juego",
            f"{kpis.get('total_duration_hours', 0)} h",
            f"{kpis.get('total_sessions', 0)} sesiones analizadas",
        )
    with k2:
        st.metric(
            "🐙 Cordura Sacrificada",
            f"{kpis.get('total_sanity_loss', 0)} pts",
            f"{kpis.get('total_sanity_events', 0)} traumas registrados",
        )
    with k3:
        st.metric(
            "🔍 Pistas e Hitos",
            f"{kpis.get('total_clues', 0)} pistas",
            f"{kpis.get('total_milestones', 0)} momentos clave",
        )
    with k4:
        st.metric(
            "🎲 Tensión y Letalidad",
            f"{kpis.get('average_tension', 0)} / 10",
            f"{kpis.get('total_critical_rolls', 0)} tiradas críticas · {kpis.get('total_combat_events', 0)} combates",
        )

    st.markdown("---")
    st.markdown("### 🏰 Campañas Disponibles")
    st.caption("Selecciona una campaña para explorar su cronología, curva de tensión continua y balance de protagonismo.")

    cols = st.columns(len(campaigns) if campaigns else 1)
    for idx, c in enumerate(campaigns):
        col = cols[idx % len(cols)]
        with col:
            with st.container(border=True):
                st.subheader(f"🏰 {c.get('name', 'Campaña')}")
                st.caption(f"**Sistema:** {c.get('system', 'La Llamada de Cthulhu')}")
                desc = c.get("description") or "Sin sinopsis registrada."
                st.markdown(f"*{desc[:120] + '…' if len(desc) > 120 else desc}*")
                st.markdown(f"**Episodios:** {c.get('episode_count', 0)} capítulos")

                if st.button(
                    "🗺️ Explorar Campaña",
                    key=f"card_camp_btn_{c['id']}",
                    type="primary",
                    width="stretch",
                ):
                    new_selection = {"level": NAV_CAMPAIGN, "campaign_id": c["id"], "session_id": None}

    return new_selection



