#!/usr/bin/env python3
"""Módulo de pie de página legal, atribución y licencia Creative Commons (Spec 23).

Renderiza el footer legal uniforme en todas las vistas del dashboard y visor.
"""

from __future__ import annotations

from typing import Any


def render_footer(st: Any) -> None:
    """Renderiza el pie de página con avisos legales, atribución y licencia CC BY-NC 4.0."""
    st.markdown("---")
    st.markdown(
        """
        <div style="text-align: center; color: #8b949e; font-size: 0.82rem; line-height: 1.6; margin-top: 10px; margin-bottom: 25px;">
            <p style="margin-bottom: 6px;">
                <b>Miskatonic Scribe</b> • Proyecto analítico independiente desarrollado por fans, gratuito y sin ánimo de lucro.
            </p>
            <p style="margin-bottom: 6px;">
                🎙️ Vídeos, audios y contenido original de las partidas: propiedad de 
                <a href="https://www.youtube.com/@LaMazmorradePacheco" target="_blank" style="color: #64ffda; text-decoration: none; font-weight: 500;">
                    La Mazmorra de Pacheco
                </a>.
                &nbsp;|&nbsp;
                🐙 <i>Call of Cthulhu®</i> es marca registrada de 
                <a href="https://www.chaosium.com/" target="_blank" style="color: #64ffda; text-decoration: none;">
                    Chaosium Inc.
                </a>
            </p>
            <p style="margin-bottom: 0;">
                ⚖️ Métricas, visualizaciones y código protegidos bajo licencia 
                <a href="https://creativecommons.org/licenses/by-nc/4.0/deed.es" target="_blank" style="color: #64ffda; text-decoration: underline; font-weight: 600;">
                    Creative Commons Atribución-NoComercial 4.0 Internacional (CC BY-NC 4.0)
                </a>.
                <br>
                <span style="font-size: 0.76rem; color: #6e7681;">
                    Se permite compartir y adaptar el contenido citando la autoría, prohibiéndose expresamente su comercialización o explotación lucrativa.
                </span>
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
