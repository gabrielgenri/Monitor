# Monitor Crawl & RSS · Provincia de La Rioja, Argentina (v2)

Paquete actualizado con limpieza de procesos huérfanos en `.github/workflows/update-crawl.yml` (`if: always()` + `pkill` + `timeout -k 10`), uso de acciones actualizadas (`actions/checkout@v4` y `actions/setup-python@v5`), catálogo de 53 sitios de La Rioja, extracción multi-formato (`CSV`, `PDF`, `ZIP`, `XLS`, `XLSX`, `DTA`, `DBF`, `SAV`, `TXT`, `JPEG`, `RAR`, `DOCX`, `SHP`, `JSON`, `DOC`, `ODS`, `SHAPE`, `XLSM`), síntesis vinculada por taxonomía y SPA móvil con CRUD de URLs.
