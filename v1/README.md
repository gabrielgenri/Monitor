# Monitor Crawl & RSS · Provincia de La Rioja, Argentina

Sistema integral de rastreo web (`crawl`), consumo de canales RSS/Atom, indexación de documentos oficiales y datasets (`CSV`, `PDF`, `ZIP`, `XLS`, `XLSX`, `DTA`, `DBF`, `SAV`, `TXT`, `JPEG`, `RAR`, `DOCX`, `SHP`, `JSON`, `DOC`, `ODS`, `SHAPE`, `XLSM`), vinculación temática automática y aplicación web SPA móvil desplegada con **GitHub Pages + GitHub Actions**.

## Estructura del Repositorio

```text
.
├── .github/
│   └── workflows/
│       └── update-crawl.yml        # Ejecución programada 3 veces al día + disparo manual
├── data/
│   ├── sitios_larioja.json         # Catálogo exhaustivo de medios, gobierno, universidades y centros CyT de La Rioja
│   └── noticias_consolidadas.json  # Notas extraídas (título, copete, cuerpo, imagen, adjuntos) + contenidos vinculados
├── scripts/
│   └── fetch_and_classify.py       # Crawler + lector RSS + parser de archivos + generador de síntesis vinculadas
├── index.html                      # SPA minimalista móvil con CRUD de URLs y exportación JSON
└── requirements.txt                # Dependencias Python
```

## Despliegue en GitHub

1. Sube todos los archivos a un repositorio en GitHub en la rama `main`.
2. Ve a **Settings → Actions → General → Workflow permissions** y activa **Read and write permissions**.
3. Ve a **Settings → Pages**, selecciona **Deploy from a branch** (`main` / `/ (root)`) y guarda.
4. En **Actions → Crawl y RSS La Rioja (3x al dia)** pulsa **Run workflow** para ejecutar el primer rastreo en vivo. El cron correrá automáticamente a las **08:00, 13:00 y 19:00 (hora Argentina UTC-3)**.
5. Usa la pestaña **Sitios y CRUD URLs** en la app web para agregar, editar, pausar o eliminar URLs y descarga `sitios_larioja.json` para actualizar `data/sitios_larioja.json` en tu repositorio.
