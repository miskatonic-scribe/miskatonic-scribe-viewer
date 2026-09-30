#!/usr/bin/env python3
"""Módulo de estadísticas cuantitativas e investigadoras (Stats Puros) — Spec 19.

Calcula y visualiza tablas y medalleros empíricos de personajes para episodios
y campañas (pérdida de cordura, dados, heridas, pistas y tiempo de habla).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

import pandas as pd


def normalize_name(text: str | None) -> str:
    """Normaliza un nombre eliminando tildes, signos y pasando a minúsculas."""
    if not text:
        return ""
    n = unicodedata.normalize("NFD", str(text))
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    n = re.sub(r"[^\w\s]", "", n)
    return n.lower().strip()


def parse_sanity_loss(val: Any) -> int:
    """Extrae el número entero de pérdida de cordura desde texto o valor numérico."""
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return max(0, int(val))
    s = str(val).strip()
    m = re.search(r"\d+", s)
    if m:
        return int(m.group(0))
    if "punto" in s.lower():
        return 1
    return 0


def matches_character(
    target_char: str,
    target_player: str,
    char_candidate: str,
    player_candidate: str,
) -> bool:
    """Determina si un evento pertenece a un personaje o jugador mediante coincidencia flexible."""
    cn = normalize_name(target_char)
    pn = normalize_name(target_player)
    cand_c = normalize_name(char_candidate)
    cand_p = normalize_name(player_candidate)

    if not cand_c and not cand_p:
        return False

    # 1. Coincidencia exacta o contenida por nombre de personaje
    if cn and (cn in cand_c or cand_c in cn):
        return True

    # 2. Coincidencia por primer nombre del personaje (ej. 'Alex' en 'Álex Coxen')
    first_name = cn.split()[0] if cn else ""
    if first_name and len(first_name) >= 3 and first_name in cand_c:
        return True

    # 3. Coincidencia por jugador (ej. 'Chemi' o 'Lucia')
    if pn and len(pn) >= 3 and (pn in cand_p or pn in cand_c or cand_p in pn):
        return True

    return False


def build_session_investigator_stats(
    characters: list[dict[str, Any]],
    sanity_events: list[dict[str, Any]],
    critical_rolls: list[dict[str, Any]],
    combat_events: list[dict[str, Any]],
    clues: list[dict[str, Any]],
    dialogs: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Genera la lista de estadísticas puras por investigador para un episodio.

    Excluye al Guardián de la lista para centrarse en los personajes investigadores.
    """
    stats_list: list[dict[str, Any]] = []

    # Filtrar solo investigadores (excluir rol guardián)
    investigators = [
        c for c in characters
        if str(c.get("role", "")).lower() != "guardian" and "guardi" not in str(c.get("character", "")).lower()
    ]

    # Ordenar por airtime_pct descendente
    sorted_investigators = sorted(
        investigators,
        key=lambda x: float(x.get("airtime_pct") or 0.0),
        reverse=True,
    )

    # Precalcular conteo de turnos por speaker si se proporcionan diálogos
    speaker_turns: dict[str, int] = {}
    if dialogs:
        for d in dialogs:
            spk = d.get("speaker") or ""
            if spk:
                speaker_turns[spk] = speaker_turns.get(spk, 0) + 1

    for c in sorted_investigators:
        c_name = c.get("character") or "Investigador"
        p_name = c.get("player") or "Jugador"
        airtime_pct = float(c.get("airtime_pct") or 0.0)
        speaking_sec = float(c.get("speaking_seconds") or 0.0)
        spk_id = c.get("speaker_id") or ""

        # 1. Cordura perdida
        s_loss = 0
        sanity_incidents = 0
        for se in sanity_events:
            if matches_character(c_name, p_name, se.get("character_name", ""), se.get("player_name", "")):
                s_loss += parse_sanity_loss(se.get("sanity_loss"))
                sanity_incidents += 1

        # 2. Tiradas notables
        crits = 0
        fumbles = 0
        pushed = 0
        for r in critical_rolls:
            if matches_character(c_name, p_name, r.get("character_name", ""), r.get("player_name", "")):
                rtype = normalize_name(r.get("roll_type"))
                outcome = normalize_name(r.get("outcome"))
                if "fumble" in rtype or "pifia" in rtype or "fallo_critico" in rtype:
                    fumbles += 1
                elif "critical" in rtype or "extremo" in rtype or "critico" in rtype or outcome == "critical":
                    crits += 1
                elif "pushed" in rtype or "forzada" in rtype:
                    pushed += 1

        # 3. Pistas encontradas
        clue_count = 0
        for cl in clues:
            if matches_character(c_name, p_name, cl.get("character_name", ""), cl.get("player_name", "")):
                clue_count += 1

        # 4. Combate / Heridas
        combat_count = 0
        for cb in combat_events:
            if matches_character(c_name, p_name, cb.get("character_name", ""), cb.get("player_name", "")):
                combat_count += 1

        # 5. Turnos de diálogo (intervenciones)
        turn_count = 0
        if dialogs:
            if spk_id and spk_id in speaker_turns:
                turn_count = speaker_turns[spk_id]
            else:
                for d in dialogs:
                    if matches_character(c_name, p_name, d.get("character", ""), d.get("player", "")):
                        turn_count += 1

        stats_list.append({
            "character": c_name,
            "player": p_name,
            "speaker_id": spk_id,
            "sanity_loss": s_loss,
            "sanity_incidents": sanity_incidents,
            "critical_successes": crits,
            "fumbles": fumbles,
            "pushed_rolls": pushed,
            "clues_found": clue_count,
            "combat_events": combat_count,
            "turn_count": turn_count,
            "speaking_seconds": speaking_sec,
            "speaking_minutes": round(speaking_sec / 60.0, 1),
            "airtime_pct": round(airtime_pct, 1),
        })

    return stats_list


def build_campaign_investigator_stats(
    session_stats_records: list[list[dict[str, Any]]],
) -> dict[str, Any]:
    """Acumula las estadísticas de investigadores a lo largo de toda la campaña y calcula el medallero.

    Args:
        session_stats_records: Lista de resultados de build_session_investigator_stats para cada sesión.

    Returns:
        dict con 'investigators' (lista agregada ordenada) y 'awards' (medallero honorífico).
    """
    aggregated: dict[str, dict[str, Any]] = {}

    for session_list in session_stats_records:
        for s in session_list:
            c_name = s["character"]
            p_name = s["player"]

            if c_name not in aggregated:
                aggregated[c_name] = {
                    "character": c_name,
                    "player": p_name,
                    "episodes_played": 0,
                    "sanity_loss": 0,
                    "sanity_incidents": 0,
                    "critical_successes": 0,
                    "fumbles": 0,
                    "pushed_rolls": 0,
                    "clues_found": 0,
                    "combat_events": 0,
                    "total_turns": 0,
                    "speaking_seconds": 0.0,
                }

            aggregated[c_name]["episodes_played"] += 1
            aggregated[c_name]["sanity_loss"] += s.get("sanity_loss", 0)
            aggregated[c_name]["sanity_incidents"] += s.get("sanity_incidents", 0)
            aggregated[c_name]["critical_successes"] += s.get("critical_successes", 0)
            aggregated[c_name]["fumbles"] += s.get("fumbles", 0)
            aggregated[c_name]["pushed_rolls"] += s.get("pushed_rolls", 0)
            aggregated[c_name]["clues_found"] += s.get("clues_found", 0)
            aggregated[c_name]["combat_events"] += s.get("combat_events", 0)
            aggregated[c_name]["total_turns"] += s.get("turn_count", 0)
            aggregated[c_name]["speaking_seconds"] += s.get("speaking_seconds", 0.0)

    investigators_list = list(aggregated.values())
    for inv in investigators_list:
        inv["speaking_minutes"] = round(inv["speaking_seconds"] / 60.0, 1)

    # Ordenar por episodios jugados y luego por pistas / cordura
    investigators_list.sort(key=lambda x: (x["episodes_played"], x["sanity_loss"], x["clues_found"]), reverse=True)

    # Cálculo del Medallero de la Aventura
    awards = {}
    if investigators_list:
        # 1. El Más Castigado Mentalmente
        max_san = max(investigators_list, key=lambda x: x["sanity_loss"])
        if max_san["sanity_loss"] > 0:
            awards["most_insane"] = {
                "title": "🧠 El Más Castigado Mentalmente",
                "character": max_san["character"],
                "player": max_san["player"],
                "stat_value": f"-{max_san['sanity_loss']} COR",
                "desc": f"Sufrió la mayor erosión psíquica de la campaña en {max_san['sanity_incidents']} incidentes.",
            }

        # 2. El Sabueso de Arkham (Más pistas)
        max_clues = max(investigators_list, key=lambda x: x["clues_found"])
        if max_clues["clues_found"] > 0:
            awards["best_detective"] = {
                "title": "🔍 El Sabueso de Arkham",
                "character": max_clues["character"],
                "player": max_clues["player"],
                "stat_value": f"{max_clues['clues_found']} pistas",
                "desc": "Líder indiscutible en descubrir indicios, cartas y artefactos clave.",
            }

        # 3. El Rey de las Pifias
        max_fumbles = max(investigators_list, key=lambda x: x["fumbles"])
        if max_fumbles["fumbles"] > 0:
            awards["worst_luck"] = {
                "title": "🎲 El Rey de las Pifias",
                "character": max_fumbles["character"],
                "player": max_fumbles["player"],
                "stat_value": f"{max_fumbles['fumbles']} pifias",
                "desc": "El terror de los dados: las consecuencias más desastrosas en el momento decisivo.",
            }

        # 4. El Favorito del Destino (Críticos)
        max_crits = max(investigators_list, key=lambda x: x["critical_successes"])
        if max_crits["critical_successes"] > 0:
            awards["best_luck"] = {
                "title": "🎯 El Favorito del Destino",
                "character": max_crits["character"],
                "player": max_crits["player"],
                "stat_value": f"{max_crits['critical_successes']} críticos",
                "desc": "Mayor número de éxitos críticos y tiradas milagrosas bajo presión.",
            }

        # 5. El Imán de Balas (Combate)
        max_combat = max(investigators_list, key=lambda x: x["combat_events"])
        if max_combat["combat_events"] > 0:
            awards["iron_body"] = {
                "title": "🩸 El Imán de Balas",
                "character": max_combat["character"],
                "player": max_combat["player"],
                "stat_value": f"{max_combat['combat_events']} refriegas",
                "desc": "El investigador que más plomo, garras y daños físicos absorbió en primera línea.",
            }

        # 6. La Voz Cantante (Airtime)
        max_airtime = max(investigators_list, key=lambda x: x["speaking_seconds"])
        if max_airtime["speaking_seconds"] > 0:
            awards["most_vocal"] = {
                "title": "🗣️ La Voz Cantante",
                "character": max_airtime["character"],
                "player": max_airtime["player"],
                "stat_value": f"{max_airtime['speaking_minutes']} min",
                "desc": "Mayor tiempo de intervención y liderazgo vocal durante las discusiones de mesa.",
            }

    return {
        "investigators": investigators_list,
        "awards": awards,
    }


def render_session_investigator_table(st_module: Any, stats_list: list[dict[str, Any]]) -> None:
    """Renderiza la tabla formateada de estadísticas de personajes para la vista de episodio."""
    st = st_module
    if not stats_list:
        st.info("No hay datos de investigadores disponibles para esta sesión.")
        return

    st.markdown("#### 📋 Balance Empírico de Investigadores (Stats de la Sesión)")
    st.caption("Cifras cuantitativas puras registradas por personaje durante este capítulo:")

    df = pd.DataFrame(stats_list)
    df_display = pd.DataFrame()
    df_display["Personaje"] = df["character"] if "character" in df.columns else ""
    df_display["Jugador"] = df["player"] if "player" in df.columns else ""
    if "sanity_loss" in df.columns:
        df_display["🧠 -SAN"] = df["sanity_loss"].apply(lambda v: f"-{v} pts" if v > 0 else "0")
    else:
        df_display["🧠 -SAN"] = "0"
    df_display["🎯 Críticos"] = df["critical_successes"] if "critical_successes" in df.columns else 0
    df_display["🎲 Pifias"] = df["fumbles"] if "fumbles" in df.columns else 0
    df_display["⚡ Forzadas"] = df["pushed_rolls"] if "pushed_rolls" in df.columns else 0
    df_display["🔍 Pistas"] = df["clues_found"] if "clues_found" in df.columns else 0
    df_display["🩸 Combate"] = df["combat_events"] if "combat_events" in df.columns else 0
    if "airtime_pct" in df.columns:
        df_display["🗣️ Voz %"] = df["airtime_pct"].apply(lambda v: f"{v:.1f}%")
    else:
        df_display["🗣️ Voz %"] = "0.0%"

    st.dataframe(df_display, hide_index=True, width="stretch")


def render_campaign_investigator_scoreboard(
    st_module: Any,
    campaign_stats_dict: dict[str, Any],
    campaign_name: str = "Aventura",
) -> None:
    """Renderiza el Cuadro de Honor y Desgracia completo de la campaña con Medallero y Tabla."""
    st = st_module
    awards = campaign_stats_dict.get("awards", {})
    investigators = campaign_stats_dict.get("investigators", [])

    if not investigators:
        st.info("No hay estadísticas agregadas de investigadores para esta campaña.")
        return

    st.markdown(
        f"""
        <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.08); padding: 12px 16px; border-radius: 8px; margin-bottom: 20px;">
            <b style="color: #64ffda;">🏆 Cuadro de Honor y Desgracia — {campaign_name}</b>
            <p style="color: #94a3b8; margin: 4px 0 0 0; font-size: 0.92rem; line-height: 1.45;">
                Consolidado cuantitativo de todos los personajes a lo largo de la aventura. 
                Los títulos reconocen tanto las proezas de investigación como los mayores infortunios de cordura, dados y heridas.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 1. Medallero de Campaña (Grid de 3 columnas x 2 filas)
    if awards:
        st.subheader("🎖️ Medallero de la Aventura")
        award_keys = ["most_insane", "best_detective", "worst_luck", "best_luck", "iron_body", "most_vocal"]
        cols = st.columns(3)

        for idx, key in enumerate(award_keys):
            if key in awards:
                aw = awards[key]
                col = cols[idx % 3]
                with col:
                    with st.container(border=True):
                        st.markdown(f"<div style='font-size: 1.05rem; font-weight: 600; color: #64ffda;'>{aw['title']}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='font-size: 1.2rem; font-weight: 700; color: #e2e8f0; margin: 4px 0;'>{aw['character']}</div>", unsafe_allow_html=True)
                        st.markdown(f"<span style='color: #94a3b8; font-size: 0.85rem;'>Jugador: <b>{aw['player']}</b></span> • <span style='color: #f59e0b; font-weight: 600;'>{aw['stat_value']}</span>", unsafe_allow_html=True)
                        st.caption(aw["desc"])

        st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)

    # 2. Tabla Consolidada Acumulativa
    st.subheader("📊 Tabla Consolidada de Campaña")
    st.caption("Cifras totales acumuladas por cada investigador durante la aventura (ordenable por cualquier columna):")

    df = pd.DataFrame(investigators)
    df_display = pd.DataFrame()
    df_display["Personaje"] = df["character"]
    df_display["Jugador"] = df["player"]
    df_display["Capítulos"] = df["episodes_played"]
    df_display["🧠 -SAN Total"] = df["sanity_loss"].apply(lambda v: f"-{v} pts" if v > 0 else "0")
    df_display["🎯 Críticos"] = df["critical_successes"]
    df_display["🎲 Pifias"] = df["fumbles"]
    df_display["⚡ Forzadas"] = df["pushed_rolls"]
    df_display["🔍 Pistas"] = df["clues_found"]
    df_display["🩸 Combate"] = df["combat_events"]
    df_display["🗣️ Minutos Habla"] = df["speaking_minutes"]

    st.dataframe(df_display, hide_index=True, width="stretch")
