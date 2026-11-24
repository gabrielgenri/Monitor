#!/usr/bin/env python3
"""
MonitorV2 Recolector y Crawler Integral - Provincia de La Rioja, Argentina
- Lee data/monitor_v2_fuentes.json
- Escribe data/monitor_v2_noticias.json
- Soporta RSS/Atom, crawl HTML y archivos CSV, PDF, ZIP, XLS, XLSX, DTA, DBF, SAV, TXT, JPEG, RAR, DOCX, SHP, JSON, DOC, ODS, SHAPE, XLSM
"""

import os
import re
import io
import json
import hashlib
import zipfile
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin, urlparse

import requests
import urllib3
import feedparser
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import pandas as pd
except Exception:
    pd = None

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

try:
    import docx
except Exception:
    docx = None

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
SITIOS_PATH = os.path.join(DATA_DIR, "monitor_v2_fuentes.json")
CONSOLIDADAS_PATH = os.path.join(DATA_DIR, "monitor_v2_noticias.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MonitorV2LaRiojaBot/2.0; +https://github.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
}

TARGET_EXTS = {
    ".csv", ".pdf", ".zip", ".xls", ".xlsx", ".dta", ".dbf", ".sav",
    ".txt", ".jpeg", ".jpg", ".rar", ".docx", ".shp", ".json", ".doc",
    ".ods", ".shape", ".xlsm"
}

STOPWORDS_ES = {
    "para", "como", "pero", "sobre", "entre", "desde", "hasta", "donde",
    "cuando", "quien", "cual", "este", "esta", "estos", "estas", "ese",
    "esa", "esos", "esas", "aquel", "aquella", "con", "sin", "por", "los",
    "las", "del", "una", "uno", "unos", "unas", "que", "más", "sus", "han",
    "fue", "ser", "son", "tiene", "tienen", "rioja", "provincia", "argentina"
}


def now_ar_iso():
    tz_ar = timezone(timedelta(hours=-3))
    return datetime.now(tz_ar).isoformat(timespec="seconds")


def clean_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def make_id(url, title=""):
    raw = (url or "") + "|" + (title or "")
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()[:16]


def get_extension(url):
    path = urlparse(url).path.lower()
    for ext in TARGET_EXTS:
        if path.endswith(ext):
            return ext.lstrip(".")
    return "html"


def extract_tags(title, copete, cuerpo, max_tags=6):
    combined = f"{title} {copete} {cuerpo[:500]}".lower()
    words = re.findall(r"[a-záéíóúñü]{4,}", combined)
    freq = {}
    for w in words:
        if w in STOPWORDS_ES:
            continue
        freq[w] = freq.get(w, 0) + 1
    ordered = sorted(freq.items(), key=lambda x: (-x[1], x[0]))
    return [w for w, _ in ordered[:max_tags]]


def classify_taxonomy(title, copete, cuerpo, reglas, default_tax):
    text = f"{title} {copete} {cuerpo[:1200]}".lower()
    best_tax = default_tax
    best_score = 0
    for tax, keywords in reglas.items():
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score > best_score:
            best_score = score
            best_tax = tax
    return best_tax


def inspect_binary_attachment(url, ext):
    info = {
        "url": url,
        "extension": ext.upper(),
        "nombre_archivo": os.path.basename(urlparse(url).path) or f"archivo.{ext}",
        "extracto": ""
    }
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12, verify=False, stream=True)
        if resp.status_code != 200:
            return info
        content = resp.content[:2_500_000]
        if ext == "pdf" and PdfReader is not None:
            reader = PdfReader(io.BytesIO(content))
            pages_txt = [(p.extract_text() or "") for p in reader.pages[:2]]
            info["extracto"] = clean_text(" ".join(pages_txt))[:450]
        elif ext in {"csv", "txt", "json"}:
            info["extracto"] = clean_text(content.decode("utf-8", errors="ignore"))[:450]
        elif ext in {"xlsx", "xls", "xlsm", "ods"} and pd is not None:
            df = pd.read_excel(io.BytesIO(content), nrows=5)
            cols = ", ".join([str(c) for c in df.columns[:8]])
            info["extracto"] = f"Planilla ({len(df.columns)} cols): {cols}"
        elif ext == "docx" and docx is not None:
            doc = docx.Document(io.BytesIO(content))
            info["extracto"] = clean_text(" ".join(p.text for p in doc.paragraphs[:8]))[:450]
        elif ext == "zip":
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                info["extracto"] = "Contenido ZIP: " + ", ".join(zf.namelist()[:10])
        elif ext in {"dta", "dbf", "sav", "shp", "shape", "doc", "rar", "jpeg", "jpg"}:
            info["extracto"] = f"Recurso binario {ext.upper()} indexado ({round(len(content)/1024, 1)} KB)"
    except Exception as e:
        info["extracto"] = f"Enlace {ext.upper()} detectado ({str(e)[:60]})"
    return info


def crawl_article_page(url):
    result = {"titulo": "", "copete": "", "cuerpo": "", "imagen": "", "adjuntos": []}
    try:
        resp = requests.get(url, headers=HEADERS, timeout=14, verify=False)
        if resp.status_code != 200:
            return result
        ctype = resp.headers.get("Content-Type", "").lower()
        if "text/html" not in ctype and "application/xhtml" not in ctype:
            ext = get_extension(url)
            if ext != "html":
                att = inspect_binary_attachment(url, ext)
                result["titulo"] = att["nombre_archivo"]
                result["copete"] = f"Documento oficial / dataset en formato {ext.upper()}"
                result["cuerpo"] = att["extracto"] or f"Archivo descargable en {url}"
                result["adjuntos"].append(att)
            return result

        soup = BeautifulSoup(resp.text, "html.parser")
        og_title = soup.find("meta", property="og:title")
        h1 = soup.find("h1")
        if og_title and og_title.get("content"):
            result["titulo"] = clean_text(og_title["content"])
        elif h1:
            result["titulo"] = clean_text(h1.get_text())
        elif soup.title:
            result["titulo"] = clean_text(soup.title.get_text())

        og_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
        if og_desc and og_desc.get("content"):
            result["copete"] = clean_text(og_desc["content"])

        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            result["imagen"] = urljoin(url, og_img["content"].strip())
        else:
            for img in soup.find_all("img", src=True):
                src = img["src"].strip()
                if any(k in src.lower() for k in ["logo", "icon", "sprite", "avatar", "pixel"]):
                    continue
                result["imagen"] = urljoin(url, src)
                break

        container = soup.find("article") or soup.find("main") or soup.body
        paragraphs = []
        if container:
            for p in container.find_all("p"):
                txt = clean_text(p.get_text())
                if len(txt) >= 45:
                    paragraphs.append(txt)
        result["cuerpo"] = "\n\n".join(paragraphs[:18])
        if not result["copete"] and paragraphs:
            result["copete"] = paragraphs[0][:260]

        seen_att = set()
        for a in soup.find_all("a", href=True):
            full_href = urljoin(url, a["href"].strip())
            ext = get_extension(full_href)
            if ext != "html" and full_href not in seen_att:
                seen_att.add(full_href)
                result["adjuntos"].append(inspect_binary_attachment(full_href, ext))
                if len(result["adjuntos"]) >= 5:
                    break
    except Exception:
        pass
    return result


def discover_links_from_homepage(url_web, limit=6):
    links = []
    seen = set()
    domain = urlparse(url_web).netloc
    try:
        resp = requests.get(url_web, headers=HEADERS, timeout=14, verify=False)
        if resp.status_code != 200:
            return links
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = urljoin(url_web, a["href"].strip())
            parsed = urlparse(href)
            if parsed.scheme not in {"http", "https"}:
                continue
            ext = get_extension(href)
            text = clean_text(a.get_text())
            is_doc = ext != "html"
            is_article = parsed.netloc == domain and len(parsed.path.strip("/")) > 12 and (len(text) >= 22 or is_doc)
            if (is_doc or is_article) and href not in seen and href.rstrip("/") != url_web.rstrip("/"):
                seen.add(href)
                links.append((href, text, ext))
                if len(links) >= limit:
                    break
    except Exception:
        pass
    return links


def build_linked_contents(notas, taxonomias, timestamp_iso):
    vinculados = []
    for tax in taxonomias:
        grupo = [n for n in notas if n.get("taxonomia") == tax]
        if not grupo:
            continue
        fuentes_unicas = []
        for n in grupo:
            if n["fuente"] not in fuentes_unicas:
                fuentes_unicas.append(n["fuente"])
        tag_counts = {}
        for n in grupo:
            for t in n.get("etiquetas", []):
                tag_counts[t] = tag_counts.get(t, 0) + 1
        top_tags = [t for t, _ in sorted(tag_counts.items(), key=lambda x: -x[1])[:5]]
        copete_orig = f"Síntesis multi-fuente en {tax}: {len(grupo)} registros relevados en {len(fuentes_unicas)} canales de La Rioja."
        bloques = [f"Panorama consolidado de la jurisdicción La Rioja en '{tax}', integrando {', '.join(fuentes_unicas[:5])}."]
        for idx, n in enumerate(grupo[:5], 1):
            resumen_n = n.get("copete") or (n.get("cuerpo") or "")[:200]
            bloques.append(f"{idx}. [{n['fuente']}] {n['titulo']}: {resumen_n}")
        if top_tags:
            bloques.append("Etiquetas vinculadas: " + ", ".join(f"#{t}" for t in top_tags) + ".")
        vinculados.append({
            "id": make_id(tax, timestamp_iso[:13]),
            "taxonomia": tax,
            "fecha_generacion": timestamp_iso,
            "titulo_original": f"Informe Vinculado · {tax} ({len(grupo)} notas cruzadas)",
            "copete": copete_orig,
            "cuerpo_original": "\n\n".join(bloques),
            "etiquetas_vinculadas": top_tags,
            "fuentes_cruzadas": [
                {
                    "id_nota": n["id"],
                    "titulo": n["titulo"],
                    "fuente": n["fuente"],
                    "categoria": n["categoria"],
                    "enlace": n["enlace"],
                    "tipo_recurso": n.get("tipo_recurso", "HTML")
                }
                for n in grupo[:8]
            ]
        })
    return vinculados


def main():
    with open(SITIOS_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    existing = {"notas": [], "contenidos_vinculados": [], "historial_corridas": []}
    if os.path.exists(CONSOLIDADAS_PATH):
        try:
            with open(CONSOLIDADAS_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            pass

    reglas = config.get("reglas_clasificacion", {})
    taxonomias = config.get("taxonomias", [])
    sitios_activos = [s for s in config.get("sitios", []) if s.get("activo", True)]
    notas_by_id = {n["id"]: n for n in existing.get("notas", [])}
    nuevas_count = 0
    adjuntos_count = 0
    ts = now_ar_iso()

    for sitio in sitios_activos:
        candidatos = []
        if sitio.get("usar_rss") and sitio.get("url_rss", "").strip():
            try:
                resp = requests.get(sitio["url_rss"].strip(), headers=HEADERS, timeout=14, verify=False)
                if resp.status_code == 200:
                    parsed_feed = feedparser.parse(resp.content)
                    for entry in parsed_feed.entries[:5]:
                        link = entry.get("link", "").strip()
                        if not link:
                            continue
                        img_rss = ""
                        if "media_content" in entry and entry.media_content:
                            img_rss = entry.media_content[0].get("url", "")
                        elif "media_thumbnail" in entry and entry.media_thumbnail:
                            img_rss = entry.media_thumbnail[0].get("url", "")
                        candidatos.append({
                            "enlace": link,
                            "titulo_feed": clean_text(entry.get("title", "")),
                            "copete_feed": clean_text(BeautifulSoup(entry.get("summary", ""), "html.parser").get_text()),
                            "fecha": entry.get("published", ts),
                            "imagen_feed": img_rss,
                            "origen": "RSS+Crawl"
                        })
            except Exception:
                pass

        if len(candidatos) < 2:
            for href, anchor_txt, ext in discover_links_from_homepage(sitio["url_web"], limit=4):
                if any(c["enlace"] == href for c in candidatos):
                    continue
                candidatos.append({
                    "enlace": href,
                    "titulo_feed": anchor_txt,
                    "copete_feed": "",
                    "fecha": ts,
                    "imagen_feed": "",
                    "origen": "Crawl Web"
                })

        for cand in candidatos:
            link = cand["enlace"]
            ext = get_extension(link)
            crawled = crawl_article_page(link)
            titulo = crawled["titulo"] or cand["titulo_feed"] or link
            copete = crawled["copete"] or cand["copete_feed"] or f"Registro relevado desde {sitio['nombre']}."
            cuerpo = crawled["cuerpo"] or copete
            imagen = crawled["imagen"] or cand["imagen_feed"]
            adjuntos = crawled["adjuntos"]
            adjuntos_count += len(adjuntos)
            nid = make_id(link, titulo)
            tax = classify_taxonomy(titulo, copete, cuerpo, reglas, sitio.get("tema_por_defecto", "Política y Gestión"))
            tags = extract_tags(titulo, copete, cuerpo)
            if nid not in notas_by_id:
                nuevas_count += 1
            notas_by_id[nid] = {
                "id": nid,
                "titulo": titulo,
                "copete": copete[:400],
                "cuerpo": cuerpo[:4500],
                "imagen": imagen,
                "enlace": link,
                "fuente_id": sitio["id"],
                "fuente": sitio["nombre"],
                "categoria": sitio.get("categoria", "Medios de Comunicación"),
                "subtipo": sitio.get("subtipo", ""),
                "localidad": sitio.get("localidad", "La Rioja"),
                "origen_extraccion": cand["origen"],
                "tipo_recurso": ext.upper(),
                "taxonomia": tax,
                "etiquetas": tags,
                "adjuntos": adjuntos,
                "fecha_publicacion": cand["fecha"],
                "fecha_recoleccion": ts
            }

    todas_notas = sorted(notas_by_id.values(), key=lambda x: x.get("fecha_recoleccion", ""), reverse=True)[:350]
    vinculados = build_linked_contents(todas_notas, taxonomias, ts)
    historial = existing.get("historial_corridas", [])
    historial.insert(0, {
        "fecha": ts,
        "sitios_procesados": len(sitios_activos),
        "notas_totales": len(todas_notas),
        "notas_nuevas": nuevas_count,
        "adjuntos_detectados": adjuntos_count
    })
    output = {
        "ultima_actualizacion": ts,
        "jurisdiccion": "La Rioja, Argentina",
        "total_sitios_activos": len(sitios_activos),
        "total_notas": len(todas_notas),
        "historial_corridas": historial[:30],
        "contenidos_vinculados": vinculados,
        "notas": todas_notas
    }
    with open(CONSOLIDADAS_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"[{ts}] MonitorV2 finalizado: {len(todas_notas)} notas ({nuevas_count} nuevas), {len(vinculados)} síntesis vinculadas.")


if __name__ == "__main__":
    main()
