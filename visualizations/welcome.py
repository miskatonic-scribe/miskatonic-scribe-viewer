#!/usr/bin/env python3
"""Módulo de presentación y bienvenida para La Mazmorra de Pacheco (Spec 22).

Presenta el proyecto Miskatonic Scribe como homenaje analítico y herramienta
de soporte para los creadores y jugadores de La Mazmorra de Pacheco.
"""

from __future__ import annotations

from typing import Any


def render_welcome_banner(st: Any, campaign_title: str | None = None) -> None:
    """Renderiza el panel de bienvenida y contexto en la vista global de campaña."""
    with st.container(border=True):
        st.markdown(
            """
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 6px;">
                <span style="font-size: 1.8rem;">📜</span>
                <div>
                    <h3 style="margin: 0; color: #e6edf3; font-weight: 700; letter-spacing: -0.01em;">
                        Bienvenido a Miskatonic Scribe
                    </h3>
                    <p style="margin: 0; color: #64ffda; font-size: 0.92rem; font-weight: 500;">
                        Un proyecto analítico creado con cariño por un fan de <b>La Mazmorra de Pacheco</b>
                    </p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            Esta herramienta nace con la vocación de devolver a la mesa una pequeña parte de las incontables horas 
            de entretenimiento y grandes historias que nos regaláis en cada campaña. 
            
            A través del análisis automatizado de los **vídeos públicos de vuestro canal de YouTube**, 
            **Miskatonic Scribe** compila una crónica de datos para que el **Guardián** y los **Investigadores** 
            puedan disponer de métricas de mesa útiles para planificar y revivir sus partidas:
            """
        )

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(
                """
                - ⏱️ **Reparto de Foco y Tiempos:** Consulta el tiempo de intervención y habla efectiva de cada investigador para equilibrar el protagonismo narrativo.
                - 📈 **Tensión y Clímax:** Analiza la curva dramática de cada sesión, detectando los picos de suspense y peligro calculados automáticamente.
                """
            )
        with col2:
            st.markdown(
                """
                - 🎲 **Cuadro de Honor y Desgracia:** Registra las pifias y éxitos críticos de la campaña, letalidad en combate y eventos de cordura.
                - 🎭 **Clima de Mesa e Inmersión:** Explora el balance entre los momentos de ficción y los descansos informales de humor que hacen tan única vuestra mesa.
                """
            )
