#!/usr/bin/env python3
"""Módulo de consolidación y renderizado de la Línea de Tiempo Narrativa (Spec 17).

Unifica eventos heterogéneos (cordura, pistas, hitos, dados y combates)
en un único flujo cronológico continuo, filtrable y legible.
"""

from __future__ import annotations

from typing import Any

# Categorías normalizadas para filtros
CAT_ALL = "all"
CAT_SANITY = "cordura"
CAT_CLUES = "pistas"
CAT_DICE_COMBAT = "dados_combate"

CATEGORY_LABELS = {
    CAT_ALL: "🌟 Todos",
    CAT_SANITY: "🐙 Cordura y Traumas",
    CAT_CLUES: "🔍 Pistas e Hitos",
    CAT_DICE_COMBAT: "🎲 Dados y Combate",
}


def parse_timestamp_seconds(raw_seconds: Any, raw_str: str | None = None) -> float:
    """Extrae o calcula los segundos de un evento de forma tolerante."""
    if raw_seconds is not None:
        try:
            val = float(raw_seconds)
            if val >= 0:
                return val
        except (ValueError, TypeError):
            pass

    if raw_str:
        # Formatos tipo "MM:SS" o "HH:MM:SS"
        parts = str(raw_str).strip().split(":")
        try:
            if len(parts) == 2:
                return float(parts[0]) * 60 + float(parts[1])
            elif len(parts) == 3:
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        except (ValueError, TypeError):
            pass

    return 0.0


def format_seconds_to_hhmmss(seconds: float) -> str:
    """Formatea segundos en formato 'MM:SS' o 'HH:MM:SS'."""
    s = int(max(0.0, seconds))
    hrs = s // 3600
    mins = (s % 3600) // 60
    secs = s % 60
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


def consolidate_event_stream(
    sanity_events: list[dict[str, Any]] | None = None,
    clues: list[dict[str, Any]] | None = None,
    milestones: list[dict[str, Any]] | None = None,
    critical_rolls: list[dict[str, Any]] | None = None,
    combat_events: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Unifica y ordena cronológicamente todas las categorías de eventos narrativos."""
    stream: list[dict[str, Any]] = []

    # 1. Eventos de Cordura (🐙)
    for e in sanity_events or []:
        t_sec = parse_timestamp_seconds(e.get("timestamp_seconds"), e.get("timestamp_str"))
        t_str = e.get("timestamp_str") or format_seconds_to_hhmmss(t_sec)
        loss = e.get("sanity_loss")
        loss_str = f"-{loss} COR" if loss is not None and str(loss).strip() else "Pérdida de Cordura"
        ev_type = (e.get("event_type") or "Pérdida").capitalize()
        p_name = str(e.get("player_name") or "").strip()
        c_name = str(e.get("character_name") or "").strip()
        if p_name and c_name and p_name.lower() != c_name.lower():
            who = f"{p_name} ({c_name})"
        else:
            who = p_name or c_name or "Investigador"

        trigger = str(e.get("trigger_cause") or e.get("trigger_context") or e.get("description") or "").strip()
        consequence = str(e.get("consequence") or "").strip()
        context_parts = []
        if loss is not None and str(loss).strip():
            context_parts.append(f"Pérdida: {loss_str}")
        if consequence and consequence.lower() != "ninguna":
            context_parts.append(f"Consecuencia: {consequence}")

        stream.append({
            "id": f"sanity_{e.get('id', len(stream))}",
            "timestamp_seconds": t_sec,
            "timestamp_str": t_str,
            "category": CAT_SANITY,
            "icon": "🐙",
            "title": f"Cordura: {loss_str} ({ev_type})",
            "entity": who,
            "summary": trigger,
            "context": " · ".join(context_parts) if context_parts else "Shock psicológico",
            "badge_color": "#ff4d4f",
            "type_tag": "Cordura / Trauma",
        })

    # 2. Pistas Clave (🔍)
    for c in clues or []:
        t_sec = parse_timestamp_seconds(c.get("timestamp_seconds"), c.get("timestamp_str"))
        t_str = c.get("timestamp_str") or format_seconds_to_hhmmss(t_sec)
        clue_txt = str(c.get("clue_text") or c.get("description") or "").strip()
        name = c.get("clue_name") or (clue_txt[:45] + "..." if len(clue_txt) > 45 else clue_txt) or "Pista descubierta"
        p_name = str(c.get("player_name") or "").strip()
        c_name = str(c.get("character_name") or "").strip()
        if p_name and c_name and p_name.lower() != c_name.lower():
            who = f"{p_name} ({c_name})"
        else:
            who = str(c.get("discovered_by") or p_name or c_name or "Investigadores").strip()

        importance = str(c.get("importance") or c.get("relevance") or "clave").strip().capitalize()
        skill = str(c.get("source_skill") or "").strip()
        context_parts = [f"Relevancia: {importance}"]
        if skill:
            context_parts.append(f"Habilidad: {skill}")

        stream.append({
            "id": f"clue_{c.get('id', len(stream))}",
            "timestamp_seconds": t_sec,
            "timestamp_str": t_str,
            "category": CAT_CLUES,
            "icon": "🔍",
            "title": f"Pista: {name}",
            "entity": who,
            "summary": clue_txt,
            "context": " · ".join(context_parts),
            "badge_color": "#faad14",
            "type_tag": "Pista Clave",
        })

    # 3. Hitos Narrativos (🚩)
    for m in milestones or []:
        t_sec = parse_timestamp_seconds(m.get("timestamp_seconds"), m.get("timestamp_str"))
        t_str = m.get("timestamp_str") or format_seconds_to_hhmmss(t_sec)
        title = m.get("title") or "Momento clave"
        m_type = str(m.get("phase") or m.get("milestone_type") or "Giro de trama").capitalize()
        desc = str(m.get("description") or "").strip()

        stream.append({
            "id": f"milestone_{m.get('id', len(stream))}",
            "timestamp_seconds": t_sec,
            "timestamp_str": t_str,
            "category": CAT_CLUES,
            "icon": "🚩",
            "title": f"Hito: {title}",
            "entity": m_type,
            "summary": desc,
            "context": f"Fase narrativa: {m_type}",
            "badge_color": "#1890ff",
            "type_tag": "Hito Narrativo",
        })

    # 4. Tiradas Críticas y Forzadas (🎲 / 💥 / ⭐)
    for r in critical_rolls or []:
        t_sec = parse_timestamp_seconds(r.get("timestamp_seconds"), r.get("timestamp_str"))
        t_str = r.get("timestamp_str") or format_seconds_to_hhmmss(t_sec)
        skill = r.get("skill") or "Tirada"
        r_type = str(r.get("roll_type") or "pushed_roll").lower()
        p_name = str(r.get("player_name") or "").strip()
        c_name = str(r.get("character_name") or "").strip()
        if p_name and c_name and p_name.lower() != c_name.lower():
            who = f"{p_name} ({c_name})"
        else:
            who = p_name or c_name or "Investigador"

        if r_type == "fumble":
            icon = "💥"
            label = "Pifia"
            b_color = "#f5222d"
        elif r_type == "critical":
            icon = "⭐"
            label = "Éxito Crítico"
            b_color = "#52c41a"
        else:
            icon = "🎲"
            label = "Tirada Forzada"
            b_color = "#fa8c16"

        consequence = str(r.get("consequence") or "").strip()
        outcome = str(r.get("outcome") or "").strip()
        context_parts = [f"Habilidad: {skill}", f"Tipo: {label}"]
        if outcome:
            context_parts.append(f"Resultado: {outcome.capitalize()}")

        stream.append({
            "id": f"roll_{r.get('id', len(stream))}",
            "timestamp_seconds": t_sec,
            "timestamp_str": t_str,
            "category": CAT_DICE_COMBAT,
            "icon": icon,
            "title": f"{label}: {skill}",
            "entity": who,
            "summary": consequence or f"Resultado: {outcome or 'Fallo'}",
            "context": " · ".join(context_parts),
            "badge_color": b_color,
            "type_tag": label,
        })

    # 5. Combate y Letalidad (⚔️)
    for b in combat_events or []:
        t_sec = parse_timestamp_seconds(b.get("timestamp_seconds"), b.get("timestamp_str"))
        t_str = b.get("timestamp_str") or format_seconds_to_hhmmss(t_sec)
        c_source = str(b.get("source") or b.get("combat_type") or "Amenaza física").capitalize()
        p_name = str(b.get("player_name") or "").strip()
        c_name = str(b.get("character_name") or "").strip()
        if p_name and c_name and p_name.lower() != c_name.lower():
            who = f"{p_name} ({c_name})"
        else:
            who = str(b.get("combatants") or p_name or c_name or "Personajes").strip()

        severity = str(b.get("severity") or b.get("damage_dealt") or "herida_leve").strip()
        details = str(b.get("details") or b.get("description") or "").strip()
        outcome = str(b.get("outcome") or "").strip()

        context_parts = [f"Origen: {c_source}", f"Severidad: {severity.capitalize()}"]
        if outcome:
            context_parts.append(f"Desenlace: {outcome.capitalize()}")

        stream.append({
            "id": f"combat_{b.get('id', len(stream))}",
            "timestamp_seconds": t_sec,
            "timestamp_str": t_str,
            "category": CAT_DICE_COMBAT,
            "icon": "⚔️",
            "title": f"Combate: {c_source}",
            "entity": who,
            "summary": details or f"Enfrentamiento físico con {c_source}",
            "context": " · ".join(context_parts),
            "badge_color": "#d4380d",
            "type_tag": "Combate",
        })

    # Ordenar por timestamp_seconds ascendente
    return sorted(stream, key=lambda x: x["timestamp_seconds"])


def filter_event_stream(
    stream: list[dict[str, Any]],
    active_category: str = CAT_ALL,
) -> list[dict[str, Any]]:
    """Filtra la lista de eventos según la categoría seleccionada."""
    if not active_category or active_category == CAT_ALL:
        return stream
    return [e for e in stream if e.get("category") == active_category]


def render_timeline_stream(
    st: Any,
    event_stream: list[dict[str, Any]],
    current_session_id: str | None = None,
) -> None:
    """Renderiza el flujo cronológico de eventos con selector de chips y tarjetas."""
    st.markdown("---")
    st.subheader("📜 Línea de Tiempo Narrativa y Eventos Clave")

    if not event_stream:
        st.info("ℹ️ No se registraron eventos narrativos clave (cordura, pistas, hitos o combates) para esta sesión.")
        return

    # Contadores por categoría
    count_all = len(event_stream)
    count_sanity = sum(1 for e in event_stream if e.get("category") == CAT_SANITY)
    count_clues = sum(1 for e in event_stream if e.get("category") == CAT_CLUES)
    count_dice = sum(1 for e in event_stream if e.get("category") == CAT_DICE_COMBAT)

    opt_all = f"🌟 Todos ({count_all})"
    opt_sanity = f"🐙 Cordura ({count_sanity})"
    opt_clues = f"🔍 Pistas e Hitos ({count_clues})"
    opt_dice = f"🎲 Dados y Combate ({count_dice})"

    options = [opt_all, opt_sanity, opt_clues, opt_dice]
    label_to_cat = {
        opt_all: CAT_ALL,
        opt_sanity: CAT_SANITY,
        opt_clues: CAT_CLUES,
        opt_dice: CAT_DICE_COMBAT,
    }

    # Chips de filtrado interactivo
    key_filter = f"timeline_filter_{current_session_id or 'default'}"
    if hasattr(st, "pills"):
        selected = st.pills(
            "Filtrar eventos por categoría:",
            options=options,
            default=opt_all,
            key=key_filter,
            label_visibility="collapsed",
        )
    else:
        selected = st.radio(
            "Filtrar eventos por categoría:",
            options=options,
            index=0,
            horizontal=True,
            key=key_filter,
            label_visibility="collapsed",
        )

    active_category = label_to_cat.get(selected or opt_all, CAT_ALL)
    filtered = filter_event_stream(event_stream, active_category)

    if not filtered:
        st.caption("No hay eventos que coincidan con la categoría seleccionada.")
        return

    st.caption(f"Mostrando **{len(filtered)}** de **{count_all}** eventos narrativos ordenados cronológicamente.")

    # Renderizar tarjetas visuales de eventos
    for ev in filtered:
        with st.container(border=True):
            col_head, col_badge = st.columns([0.80, 0.20])
            with col_head:
                badge_time = f":gray-background[⏱️ {ev.get('timestamp_str', '00:00')}]"
                icon = ev.get("icon", "📌")
                title = ev.get("title", "Evento")
                entity = ev.get("entity", "")
                who_txt = f" · *{entity}*" if entity else ""
                st.markdown(f"{badge_time} **{icon} {title}**{who_txt}")
            with col_badge:
                cat = ev.get("category", "")
                tag = ev.get("type_tag", "")
                if cat == CAT_SANITY:
                    st.markdown(f":red-background[{tag}]")
                elif cat == CAT_CLUES:
                    st.markdown(f":orange-background[{tag}]")
                else:
                    st.markdown(f":blue-background[{tag}]")

            summary = ev.get("summary", "").strip()
            if summary:
                st.markdown(summary)

            context = ev.get("context", "").strip()
            if context:
                st.caption(f"ℹ️ {context}")

