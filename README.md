# MonitorV3.2 · RSS & Crawl La Rioja (Node 24 + GitHub Actions)

Paquete completo de **MonitorV3.2** para la Provincia de La Rioja, Argentina, con ejecución programada 3 veces al día (`0 11,16,22 * * *` UTC -> `08:00`, `13:00` y `19:00` hora local), optimizado con `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"`, control de concurrencia y limpieza de procesos huérfanos.

## Estructura del paquete

```text
monitor-v3.2-larioja.zip
├── .github/
│   └── workflows/
│       └── monitor-v3-larioja.yml
├── data/
│   ├── monitor_v3_fuentes.json
│   └── monitor_v3_noticias.json
├── scripts/
│   └── monitor_v3_recolector.py
├── index.html
├── requirements.txt
└── README.md
```
