MonitorV3.1 · La Rioja, Argentina (Node 24 + SPA RSS)

Versión MonitorV3.1 optimizada para GitHub Actions con Node.js 24 (FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"), programación 3 veces al día (0 11,16,22 * * * UTC -> 08:00, 13:00 y 19:00 ART), limpieza de procesos huérfanos (if: always()), catálogo completo de 53 fuentes de La Rioja sin tema_por_defecto preasignado, clasificación semántica por reglas y categoría, extracción completa de cuerpo e imagen por nota, síntesis cross-canal y SPA minimalista móvil.

Estructura de carpetas para GitHub

.github/workflows/monitor-v3-larioja.yml

data/monitor_v3_fuentes.json

data/monitor_v3_noticias.json

scripts/monitor_v3_recolector.py

index.html

requirements.txt

README.md
