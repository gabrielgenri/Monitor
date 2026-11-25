# MonitorV3.1 · RSS & Crawl La Rioja (Node 24 + GitHub Actions)

Paquete listo para repositorio en GitHub con ejecución programada 3 veces al día (`0 11,16,22 * * *` UTC -> `08:00`, `13:00` y `19:00` hora de La Rioja, Argentina), optimizado con `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"` y limpieza de procesos huérfanos.

## Estructura del paquete

```text
monitor-v3.1-larioja.zip
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

## Características principales

* **53 fuentes de La Rioja, Argentina:** 20 medios de comunicación, 20 entidades e instituciones gubernamentales, 6 universidades y 7 centros de investigación, todas con `tema_por_defecto` en blanco (`""`) para clasificación dinámica.
* **Extracción sin recorte e imágenes:** Obtiene título, copete, cuerpo completo sin límite artificial de caracteres, imagen (`media:content`, `media:thumbnail`, `enclosures`, `og:image` o `<img>`) y archivos en múltiples extensiones (`CSV`, `PDF`, `ZIP`, `XLS`, `XLSX`, `DTA`, `DBF`, `SAV`, `TXT`, `JPEG`, `JPG`, `RAR`, `DOCX`, `SHP`, `JSON`, `DOC`, `ODS`, `SHAPE`, `XLSM`).
* **Modal por canal RSS/fuente:** Al hacer clic sobre el nombre de la fuente o canal se abre una ventana modal con las notas recolectadas, imagen, copete, cuerpo, enlace y botón de copia.
* **Contenidos vinculados por taxonomía:** Agrupa aportes bajo las 6 taxonomías temáticas en `contenidos_vinculados` con copia rápida.
* **SPA minimalista y CRUD:** Interfaz adaptable a móviles con segmentación por categorías, taxonomías, etiquetas y gestión CRUD de fuentes.
