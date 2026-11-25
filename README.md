# MonitorV3.2 · RSS & Crawl La Rioja

Sistema de monitoreo automatizado de medios de comunicación, entidades gubernamentales, universidades y centros de investigación de la **Provincia de La Rioja, Argentina**.

## Estructura del paquete

- `.github/workflows/monitor-v3-larioja.yml`: Automatización en GitHub Actions (Node 24, Python 3.12, 3 ejecuciones diarias a las 08:00, 13:00 y 19:00 ART + disparo manual).
- `data/monitor_v3_fuentes.json`: Catálogo normalizado de 53 fuentes de La Rioja con `tema_por_defecto: ""`, categorías unificadas y 6 taxonomías.
- `data/monitor_v3_noticias.json`: Estructura de salida para notas consolidadas, contenidos vinculados y archivos detectados.
- `scripts/monitor_v3_recolector.py`: Recolector híbrido RSS/Atom + Crawl HTML con normalización de URLs, deduplicación por hash y trazabilidad de estado por fuente.
- `index.html`: SPA responsiva con pestañas unificadas (*Canales RSS y fuentes (CRUD)*), `abrirModalFuente` y `copiarTexto` corregidos.
- `requirements.txt` y `README.md`: Dependencias y guía de despliegue.
