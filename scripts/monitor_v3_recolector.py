#!/usr/bin/env python3
"""
MonitorV3.1 Recolector Híbrido (RSS/Atom + Crawl Web + Imágenes + Adjuntos) - La Rioja, Argentina.
Optimizado para GitHub Actions con Node.js 24 y Python 3.12.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Any
from urllib.parse import urljoin, urlparse

import bs4
import feedparser
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

AR_TZ = timezone(timedelta(hours=-3))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUENTES_PATH = os.path.join(BASE_DIR, "data", "monitor_v3_fuentes.json")
NOTICIAS_PATH = os.path.join(BASE_DIR, "data", "monitor_v3_noticias.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 MonitorV3.1-LaRioja/3.1"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
}

TARGET_EXTENSIONS = {
    "csv", "pdf", "zip", "xls", "xlsx", "dta", "dbf", "sav",
    "txt", "jpeg", "jpg", "rar", "docx", "shp", "json", "doc",
    "ods", "shape", "xlsm"
}

CATEGORY_TAXONOMY_HINTS: dict[str, dict[str, int]] = {
    "Entidades de Gobierno": {
        "Política y Gestión": 2,
        "Normativa y Datos Oficiales": 1,
    },
    "Instituciones Gubernamentales": {
        "Política y Gestión": 1,
        "Normativa y Datos Oficiales": 1,
    },
    "Universidades": {
        "Ciencia, Tecnología y Educación": 2,
    },
    "Centros de Investigación": {
        "Ciencia, Tecnología y Educación": 2,
    },
    "Medios de Comunicación": {
        "Política y Gestión": 1,
    },
}


def now_ar_iso() -> str:
    return datetime.now(AR_TZ).isoformat(timespec="seconds")


def clean_text(text: str, max_len: int | None = None) -> str:
    """Normaliza espacios en blanco preservando la totalidad del contenido textual."""
    cleaned = re.sub(r"\s+", " ", (text or "")).strip()
    return cleaned[:max_len] if max_len else cleaned


def clean_multiline_text(text: str) -> str:
    """Normaliza párrafos sin recortar longitud del cuerpo de la noticia."""
    lines = [re.sub(r"\s+", " ", line).strip() for line in (text or "").splitlines()]
    return "\n\n".join(line for line in lines if line)


def fetch_url(url: str, timeout: int = 14) -> requests.Response | None:
    """Descarga una URL con tolerancia de red y SSL."""
    if not url or not url.startswith(("http://", "https://")):
        return None
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, verify=False)
        resp.raise_for_status()
        return resp
    except Exception:
        return None


def extract_best_image(soup: bs4.BeautifulSoup, base_url: str) -> str:
    """Extrae la imagen principal de la nota (OpenGraph, Twitter Card o <img> relevante)."""
    for prop in ("og:image", "og:image:secure_url"):
        tag = soup.find("meta", property=prop)
        if tag and tag.get("content"):
            return urljoin(base_url, tag["content"].strip())

    for attr_name in ("twitter:image", "twitter:image:src"):
        tag = soup.find("meta", attrs={"name": attr_name})
        if tag and tag.get("content"):
            return urljoin(base_url, tag["content"].strip())

    container = soup.find("article") or soup.find("main") or soup.body or soup
    for img_tag in container.find_all("img"):
        src = (
            img_tag.get("data-src")
            or img_tag.get("data-lazy-src")
            or img_tag.get("src")
            or ""
        ).strip()
        if not src or src.startswith("data:"):
            continue
        low_src = src.lower()
        if any(skip in low_src for skip in ("logo", "icon", "sprite", "avatar", "pixel", "spinner", "emoji")):
            continue
        return urljoin(base_url, src)

    return ""


def extract_rss_entry_image(entry: Any, base_url: str) -> str:
    """Extrae imagen desde media:content, media:thumbnail, enclosures o <img> embebido en el ítem RSS."""
    if entry.get("media_content"):
        for media in entry["media_content"]:
            if media.get("url"):
                return urljoin(base_url, media["url"].strip())
    if entry.get("media_thumbnail"):
        for thumb in entry["media_thumbnail"]:
            if thumb.get("url"):
                return urljoin(base_url, thumb["url"].strip())
    if entry.get("enclosures"):
        for enc in entry["enclosures"]:
            href = enc.get("href") or enc.get("url") or ""
            ftype = (enc.get("type") or "").lower()
            if href and (ftype.startswith("image/") or any(href.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp"))):
                return urljoin(base_url, href.strip())

    raw_html_blocks = [entry.get("summary") or ""]
    for c in entry.get("content") or []:
        raw_html_blocks.append(c.get("value") or "")
    for block in raw_html_blocks:
        if "<img" in block.lower():
            soup = bs4.BeautifulSoup(block, "html.parser")
            img = soup.find("img", src=True)
            if img and img.get("src"):
                return urljoin(base_url, img["src"].strip())
    return ""


def extract_attachments(soup: bs4.BeautifulSoup, base_url: str) -> list[dict[str, str]]:
    """Detecta todos los enlaces a archivos y datasets con extensiones objetivo."""
    found: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for a_tag in soup.find_all("a", href=True):
        full_url = urljoin(base_url, a_tag["href"].strip())
        if full_url in seen_urls:
            continue
        parsed_path = urlparse(full_url).path.lower()
        ext = parsed_path.rsplit(".", 1)[-1] if "." in parsed_path else ""
        if ext in TARGET_EXTENSIONS:
            seen_urls.add(full_url)
            file_name = os.path.basename(urlparse(full_url).path) or f"recurso.{ext}"
            label = clean_text(a_tag.get_text(" ")) or file_name
            found.append({
                "url": full_url,
                "extension": ext.upper(),
                "nombre_archivo": file_name,
                "extracto": label,
            })
    return found


def crawl_article_details(url: str) -> tuple[str, str, str, list[dict[str, str]]]:
    """Recupera copete, cuerpo completo sin restricción de longitud, imagen y adjuntos de una URL."""
    resp = fetch_url(url, timeout=14)
    if not resp:
        return "", "", "", []

    soup = bs4.BeautifulSoup(resp.text, "html.parser")
    image_url = extract_best_image(soup, url)

    meta_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
    copete = clean_text(meta_desc.get("content", "") if meta_desc else "")

    for tag in soup(["script", "style", "noscript", "svg", "footer", "nav", "aside"]):
        tag.decompose()

    container = soup.find("article") or soup.find("main") or soup.body or soup
    paragraphs: list[str] = []
    seen_p: set[str] = set()
    for p in container.find_all(["p", "li"]):
        txt = clean_text(p.get_text(" "))
        if len(txt) >= 30 and txt not in seen_p:
            seen_p.add(txt)
            paragraphs.append(txt)

    body_text = "\n\n".join(paragraphs)
    if not copete and paragraphs:
        copete = paragraphs[0]

    attachments = extract_attachments(soup, url)
    return copete, body_text, image_url, attachments


def classify_text(
    text: str,
    rules: dict[str, list[str]],
    categoria: str = "",
    subtipo: str = "",
    tema_por_defecto: str = "",
) -> tuple[str, list[str]]:
    """Clasifica el contenido ponderando reglas léxicas, categoría y subtipo de fuente sin requerir tema_por_defecto."""
    low = f"{text} {categoria} {subtipo}".lower()
    scores: dict[str, int] = {tax: 0 for tax in rules.keys()}
    matched_tags: list[str] = []

    for tax, keywords in rules.items():
        hits = [kw for kw in keywords if kw.lower() in low]
        scores[tax] = scores.get(tax, 0) + (len(hits) * 3)
        matched_tags.extend(hits)

    for tax_hint, bonus in CATEGORY_TAXONOMY_HINTS.get(categoria, {}).items():
        if tax_hint in scores:
            scores[tax_hint] += bonus

    sub_low = (subtipo or "").lower()
    if any(k in sub_low for k in ("normativa", "estadística", "cartografía", "control", "legislativo")):
        scores["Normativa y Datos Oficiales"] = scores.get("Normativa y Datos Oficiales", 0) + 3
    if any(k in sub_low for k in ("económ", "tributar", "productiv", "energ", "banca", "vitivin")):
        scores["Economía, Finanzas y Producción"] = scores.get("Economía, Finanzas y Producción", 0) + 3
    if any(k in sub_low for k in ("sanitar", "judicial", "seguridad social")):
        scores["Sociedad, Salud y Justicia"] = scores.get("Sociedad, Salud y Justicia", 0) + 3
    if any(k in sub_low for k in ("cultur", "turístic")):
        scores["Cultura y Deportes"] = scores.get("Cultura y Deportes", 0) + 3
    if any(k in sub_low for k in ("científ", "investig", "universidad", "tecnológ", "educativ")):
        scores["Ciencia, Tecnología y Educación"] = scores.get("Ciencia, Tecnología y Educación", 0) + 3

    best_tax = tema_por_defecto.strip() if tema_por_defecto and tema_por_defecto.strip() else "Política y Gestión"
    best_score = -1
    for tax, sc in scores.items():
        if sc > best_score:
            best_score = sc
            best_tax = tax

    extra_candidates = [
        "la rioja", "chilecito", "chepes", "chamical", "aimogasta", "arauco",
        "unlar", "undec", "conicet", "crilar", "boletín oficial", "gestión",
        "salud", "economía", "educación", "cultura", "deportes"
    ]
    for cand in extra_candidates:
        if cand in low and cand not in matched_tags:
            matched_tags.append(cand)

    unique_tags = list(dict.fromkeys(t.lower() for t in matched_tags))[:10]
    return best_tax, unique_tags


def discover_internal_links(soup: bs4.BeautifulSoup, base_url: str, depth: int = 3) -> list[tuple[str, str]]:
    """Descubre enlaces de notas dentro del mismo dominio según la profundidad configurada."""
    domain = urlparse(base_url).netloc
    max_links = max(5, depth * 5)
    discovered: list[tuple[str, str]] = []
    seen: set[str] = set()

    for a_tag in soup.find_all("a", href=True):
        href = urljoin(base_url, a_tag["href"].strip())
        parsed = urlparse(href)
        if parsed.scheme not in ("http", "https") or parsed.netloc != domain:
            continue
        if href.rstrip("/") == base_url.rstrip("/") or href in seen:
            continue
        title_txt = clean_text(a_tag.get_text(" "))
        path_clean = parsed.path.strip("/")
        if len(path_clean) > 10 and len(title_txt) >= 24:
            seen.add(href)
            discovered.append((href, title_txt))
            if len(discovered) >= max_links:
                break
    return discovered


def collect_from_site(site: dict[str, Any], rules: dict[str, list[str]], timestamp: str) -> list[dict[str, Any]]:
    """Recolecta todas las notas disponibles desde RSS/Atom y/o crawl directo del sitio sin truncar cuerpo."""
    items: list[dict[str, Any]] = []
    categoria = site.get("categoria", "Medios de Comunicación")
    subtipo = site.get("subtipo", "")
    default_tax = (site.get("tema_por_defecto") or "").strip()
    crawl_depth = int(site.get("crawl_profundidad") or 3)
    candidates: list[dict[str, str]] = []

    if site.get("usar_rss") and site.get("url_rss"):
        rss_resp = fetch_url(site["url_rss"], timeout=14)
        if rss_resp:
            parsed = feedparser.parse(rss_resp.content)
            for entry in parsed.entries:
                link = (entry.get("link") or site.get("url_web") or "").strip()
                title = clean_text(entry.get("title") or "")
                raw_content = ""
                if entry.get("content"):
                    raw_content = " ".join(c.get("value") or "" for c in entry["content"])
                summary_html = raw_content or (entry.get("summary") or "")
                summary_txt = clean_multiline_text(bs4.BeautifulSoup(summary_html, "html.parser").get_text("\n"))
                img = extract_rss_entry_image(entry, link or site.get("url_web", ""))
                if title and link:
                    candidates.append({
                        "titulo": title,
                        "copete": clean_text(bs4.BeautifulSoup(entry.get("summary") or "", "html.parser").get_text(" ")),
                        "cuerpo": summary_txt,
                        "imagen": img,
                        "enlace": link,
                        "fecha": entry.get("published") or entry.get("updated") or timestamp,
                    })

    if not candidates and site.get("url_web"):
        web_resp = fetch_url(site["url_web"], timeout=14)
        if web_resp:
            soup = bs4.BeautifulSoup(web_resp.text, "html.parser")
            discovered = discover_internal_links(soup, site["url_web"], depth=crawl_depth)
            for href, anchor_title in discovered:
                candidates.append({
                    "titulo": anchor_title,
                    "copete": "",
                    "cuerpo": "",
                    "imagen": "",
                    "enlace": href,
                    "fecha": timestamp,
                })
            if not candidates:
                title_tag = soup.find("title")
                page_title = clean_text(title_tag.get_text(" ") if title_tag else site["nombre"])
                candidates.append({
                    "titulo": page_title or site["nombre"],
                    "copete": "",
                    "cuerpo": "",
                    "imagen": extract_best_image(soup, site["url_web"]),
                    "enlace": site["url_web"],
                    "fecha": timestamp,
                })

    for cand in candidates:
        copete = cand["copete"]
        cuerpo = cand["cuerpo"]
        imagen = cand["imagen"]
        adjuntos: list[dict[str, str]] = []

        if cand["enlace"]:
            crawled_copete, full_body, crawled_img, found_files = crawl_article_details(cand["enlace"])
            if len(full_body) > len(cuerpo):
                cuerpo = full_body
            if not copete and crawled_copete:
                copete = crawled_copete
            if not imagen and crawled_img:
                imagen = crawled_img
            adjuntos = found_files

        if not copete and cuerpo:
            copete = cuerpo.split("\n\n")[0]

        combined_text = f"{cand['titulo']} {copete} {cuerpo}"
        taxonomia, etiquetas = classify_text(
            combined_text,
            rules,
            categoria=categoria,
            subtipo=subtipo,
            tema_por_defecto=default_tax,
        )
        uid = hashlib.sha256(f"{site['id']}|{cand['enlace']}|{cand['titulo']}".encode("utf-8")).hexdigest()[:12]

        items.append({
            "id": f"v3-{uid}",
            "titulo": cand["titulo"],
            "copete": copete,
            "cuerpo": cuerpo or copete or cand["titulo"],
            "imagen": imagen,
            "enlace": cand["enlace"],
            "fuente_id": site["id"],
            "fuente": site["nombre"],
            "categoria": categoria,
            "subtipo": subtipo,
            "localidad": site.get("localidad", "La Rioja Capital"),
            "taxonomia": taxonomia,
            "etiquetas": etiquetas,
            "adjuntos": adjuntos,
            "fecha_publicacion": cand.get("fecha") or timestamp,
            "fecha_recoleccion": timestamp,
        })

    return items


def build_cross_channel_synthesis(notas: list[dict[str, Any]], taxonomies: list[str], timestamp: str) -> list[dict[str, Any]]:
    """Genera síntesis originales cross-canal vinculando fuentes distintas bajo cada taxonomía."""
    syntheses: list[dict[str, Any]] = []
    for idx, tax in enumerate(taxonomies, start=1):
        group = [n for n in notas if n.get("taxonomia") == tax]
        if not group:
            continue
        unique_sources = list(dict.fromkeys(n["fuente"] for n in group))
        top_items = group[:6]
        tags_pool: list[str] = []
        for n in top_items:
            tags_pool.extend(n.get("etiquetas") or [])
        unique_tags = list(dict.fromkeys(tags_pool))[:8]

        bullets = "\n\n".join(
            f"• [{n['fuente']}] {n['titulo']}: {clean_text(n.get('copete') or n.get('cuerpo') or '', 280)}"
            for n in top_items
        )
        fuentes_str = ", ".join(unique_sources[:5])
        cuerpo_original = (
            f"Síntesis automática de MonitorV3.1 para La Rioja en el eje '{tax}', "
            f"integrando registros de {fuentes_str}.\n\n{bullets}"
        )

        syntheses.append({
            "id": f"v3-sintesis-{idx:02d}",
            "taxonomia": tax,
            "fecha_generacion": timestamp,
            "titulo_original": f"Síntesis Cross-Canal · {tax}",
            "copete": f"Vinculación temática de {len(unique_sources)} fuente(s) en La Rioja sobre {tax.lower()}.",
            "cuerpo_original": cuerpo_original,
            "etiquetas_vinculadas": unique_tags,
            "fuentes_cruzadas": [
                {
                    "id_nota": n["id"],
                    "titulo": n["titulo"],
                    "fuente": n["fuente"],
                    "enlace": n["enlace"],
                }
                for n in top_items
            ],
        })
    return syntheses


def main() -> None:
    timestamp = now_ar_iso()
    with open(FUENTES_PATH, "r", encoding="utf-8") as f:
        fuentes_cfg = json.load(f)

    rules: dict[str, list[str]] = fuentes_cfg.get("reglas_clasificacion", {})
    taxonomies: list[str] = fuentes_cfg.get("taxonomias", list(rules.keys()))
    sitios: list[dict[str, Any]] = fuentes_cfg.get("sitios", [])

    previous_notas: list[dict[str, Any]] = []
    if os.path.exists(NOTICIAS_PATH):
        try:
            with open(NOTICIAS_PATH, "r", encoding="utf-8") as f:
                prev_data = json.load(f)
                previous_notas = prev_data.get("notas", [])
        except Exception:
            previous_notas = []

    collected: list[dict[str, Any]] = []
    active_sites = [s for s in sitios if s.get("activo", True)]
    for site in active_sites:
        collected.extend(collect_from_site(site, rules, timestamp))

    merged_by_id: dict[str, dict[str, Any]] = {}
    for item in collected:
        merged_by_id[item["id"]] = item
    for prev in previous_notas:
        if prev.get("id") and prev["id"] not in merged_by_id:
            merged_by_id[prev["id"]] = prev

    final_notas = list(merged_by_id.values())
    contenidos_vinculados = build_cross_channel_synthesis(final_notas, taxonomies, timestamp)

    output = {
        "ultima_actualizacion": timestamp,
        "jurisdiccion": "La Rioja, Argentina",
        "runtime_actions": "Node 24 + Python 3.12",
        "total_sitios_activos": len(active_sites),
        "total_notas": len(final_notas),
        "contenidos_vinculados": contenidos_vinculados,
        "notas": final_notas,
    }

    with open(NOTICIAS_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"MonitorV3.1 completado: {len(final_notas)} notas, {len(contenidos_vinculados)} síntesis.")


if __name__ == "__main__":
    main()
