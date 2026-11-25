# MonitorV3.2 · RSS & Crawl La Rioja

Sistema de monitoreo automatizado de medios de comunicación, organismos gubernamentales, universidades y centros de investigación de la **Provincia de La Rioja, Argentina**.

## Estructura del proyecto

- `.github/workflows/monitor-v3-larioja.yml`: Automatización en GitHub Actions (Node 24, Python 3.12, 3 ejecuciones diarias a las 08:00, 13:00 y 19:00 ART + ejecución manual).
- `data/monitor_v3_fuentes.json`: Catálogo unificado de 53 fuentes de La Rioja con `tema_por_defecto: ""`, categorías normalizadas, 6 taxonomías y reglas de clasificación.
- `data/monitor_v3_noticias.json`: Salida consolidada de notas, imágenes, síntesis cruzadas (`contenidos_vinculados`) y archivos detectados.
- `scripts/monitor_v3_recolector.py`: Recolector híbrido RSS/Atom + Crawl HTML con normalización de URLs, deduplicación por hash, limpieza de ruido HTML y trazabilidad de estado HTTP por fuente.
- `index.html`: SPA móvil con filtros por taxonomía, modal por fuente/canal, vista de archivos detectados y CRUD local con exportación de JSON.
- `requirements.txt`: Dependencias de Python.

## Despliegue en GitHub

1. Sube todos los archivos a la rama `main` respetando las carpetas `.github/workflows/`, `data/` y `scripts/`.
2. En **Settings → Actions → General → Workflow permissions**, habilita **Read and write permissions**.
3. En **Settings → Pages**, selecciona **Deploy from a branch** (`main` / `/ (root)`).
4. Ve a **Actions → MonitorV3.2 Crawl y RSS La Rioja (Node 24 / 3x al dia)** y pulsa **Run workflow** para poblar `data/monitor_v3_noticias.json`.
