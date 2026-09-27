# 🐙 Miskatonic Scribe: Visor Analítico de Partidas de Rol

Visor interactivo y tablero de analíticas para partidas de rol de **La Llamada de Cthulhu (7ª Edición)**, basado en la campaña *"La mansión de la locura"*.

Desplegado de forma continua en **Streamlit Community Cloud**.

---

## 📊 Capacidades del Tablero

* **Curva de Tensión Dramática:** Evolución temporal de la tensión psicológica y el clímax narrativo por bloques.
* **Carriles de Habla (Swimlane Timeline):** Gráfico interactivo estilo Gantt con la alternancia de turnos e intervenciones entre Guardián e Investigadores.
* **Reparto y Participación (Airtime):** Ratio de habla Guardián vs. Jugadores y distribución porcentual del tiempo de mesa.
* **Crónica de Cordura y Traumas:** Eventos narrativos de pérdidas de COR, locura temporal, fobias y manías con citas textuales y timestamps.
* **Pistas e Hitos Narrativos:** Registro cronológico de descubrimientos clave y momentos cumbre de la investigación.
* **Drama de Dados:** Conteo de tiradas, pifias, éxitos críticos y saldo letal de la mesa.
* **Índice de Off-Topic:** Estimación del desvío humorístico o metajuego respecto a la atmósfera de horror cósmico.

---

## 🚀 Ejecución Local

Para ejecutar el visor en tu máquina local:

```bash
# 1. Crear y activar entorno virtual
python -m venv .venv
source .venv/bin/activate

# 2. Instalar dependencias mínimas
pip install -r requirements.txt

# 3. Lanzar la aplicación
streamlit run app.py
```

---

## 📜 Créditos y Reconocimientos

* **Mesa de Rol:** Campaña *"La mansión de la locura"* retransmitida y jugada en la comunidad.
* **Motor de Análisis:** Procesado, transcrito y diarizado con la suite de ingeniería de datos e IA de **Miskatonic Scribe**.
