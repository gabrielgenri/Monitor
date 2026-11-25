#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MonitorV3.2 - Recolector hibrido RSS/Atom + Crawl HTML sin recorte de contenido."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUENTES_PATH = os.path.join(BASE_DIR, "data", "monitor_v3_fuentes.json")
NOTICIAS_PATH = os.path.join(BASE_DIR, "data", "monitor_v3_noticias.json")

HEADERS = {
    "User-Agent": "MonitorV3.2-LaRioja/3.2 (+https://github.com/) Mozilla/5.0",
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, text/html;q=0.9, */*;q=0.8",
}

DEFAULT_EXTENSIONES = [
    "html", "rss", "xml", "csv", "pdf", "zip", "xls", "xlsx", "dta", "dbf",
    "sav", "txt", "jpeg", "jpg", "rar", "docx", "shp", "json", "doc", "ods",
    "shape", "xlsm",
]

DEFAULT_TAXONOMIAS = [
    "Política y Gestión",
    "Economía, Finanzas y Producción",
    "Ciencia, Tecnología y Educación",
    "Sociedad, Salud y Justicia",
    "Normativa y Datos Oficiales",
    "Cultura y Deportes",
]

DEFAULT_REGLAS = {
    "Política y Gestión": [
        "gobernador", "quintela", "gabinete", "legislatura", "diputados",
        "municipio", "intendente", "gestión", "gobierno", "ministerio",
        "secretaría", "elecciones", "política", "reforma", "constitución",
        "pacto", "federal",
    ],
    "Economía, Finanzas y Producción": [
        "economía", "presupuesto", "impuestos", "rentas", "producción",
        "agro", "olivo", "vid", "vino", "minería", "litio", "parque eólico",
        "energía", "industria", "parque industrial", "comercio", "empleo",
        "salario", "bono", "chachos", "bocade", "banco rioja", "inversión",
        "turismo", "exportación", "pbi",
    ],
    "Ciencia, Tecnología y Educación": [
        "unlar", "utn", "conicet", "crilar", "inta", "inti", "ciencia",
        "tecnología", "investigación", "universidad", "educación", "escuela",
        "docentes", "becas", "innovación", "software", "polo tecnológico",
        "internet", "conectividad", "paper", "tesis",
    ],
    "Sociedad, Salud y Justicia": [
        "salud", "hospital", "vera barros", "madre y el niño", "dengue",
        "vacunación", "justicia", "tribunal", "fiscalía", "juez", "seguridad",
        "policía", "vivienda", "agua", "ipalar", "edelap", "edelar",
        "transporte", "rioja bus", "desarrollo social", "vecinos",
    ],
    "Normativa y Datos Oficiales": [
        "boletín oficial", "ley", "decreto", "resolución", "ordenanza",
        "licitación", "datos abiertos", "estadística", "censo", "indec",
        "digesto", "acordada", "expediente", "pliego", "archivo", "dataset",
        "shapefile", "cartografía", "catastro",
    ],
    "Cultura y Deportes": [
        "cultura", "chaya", "festival", "música", "teatro", "feria del libro",
        "patrimonio", "talampaya", "museo", "artesanía", "deporte", "fútbol",
        "básquet", "riachuelo", "andino", "tesorieri", "amancay", "torneo",
        "superdomo", "autódromo",
    ],
}


def limpiar_texto(raw: str) -> str:
    if not raw:
        return ""
    txt = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", txt).strip()


def limpiar_cuerpo(html_o_texto: str) -> str:
    if not html_o_texto:
        return ""
    soup = BeautifulSoup(html_o_texto, "html.parser")
    for bad in soup(["script", "style", "noscript", "iframe", "nav", "footer", "aside"]):
        bad.decompose()
    parrafos = []
    for p in soup.find_all(["p", "h2", "h3", "li"]):
        t = re.sub(r"\s+", " ", p.get_text(" ", strip=True)).strip()
        if len(t) >= 25:
            parrafos.append(t)
    if parrafos:
        return "\n\n".join(parrafos)
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


def obtener_url(url: str, timeout: int = 12) -> tuple[str, bytes | None]:
    if not url:
        return "", None
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if resp.status_code == 200 and resp.content:
            return resp.url, resp.content
    except Exception:
        pass
    return url, None


def es_imagen_valida(url_img: str) -> bool:
    if not url_img:
        return False
    low = url_img.lower()
    if low.startswith("data:image/svg+xml"):
        return False
    if any(skip in low for skip in ["pixel", "tracker", "1x1", "spacer", "gravatar", "emoji", "sprite"]):
        return False
    return low.startswith("http://") or low.startswith("https://") or low.startswith("data:image/")


def extraer_imagen_item(entry: dict[str, Any], soup_item: BeautifulSoup | None, base_url: str) -> str:
    for attr in ("media_content", "media_thumbnail"):
        items = entry.get(attr) or []
        if isinstance(items, list):
            for m in items:
                u = (m.get("url") or "").strip()
                if es_imagen_valida(u):
                    return urljoin(base_url, u)

    for enc in entry.get("enclosures") or []:
        u = (enc.get("href") or enc.get("url") or "").strip()
        mime = (enc.get("type") or "").lower()
        if ("image" in mime or re.search(r"\.(jpe?g|png|webp|gif)(\?|$)", u.lower())) and es_imagen_valida(u):
            return urljoin(base_url, u)

    for link in entry.get("links") or []:
        if (link.get("type") or "").startswith("image/"):
            u = (link.get("href") or "").strip()
            if es_imagen_valida(u):
                return urljoin(base_url, u)

    if soup_item:
        for meta_name in ["og:image", "twitter:image", "twitter:image:src"]:
            tag = soup_item.find("meta", attrs={"property": meta_name}) or soup_item.find("meta", attrs={"name": meta_name})
            if tag and tag.get("content"):
                u = urljoin(base_url, tag["content"].strip())
                if es_imagen_valida(u):
                    return u

        for img in soup_item.find_all("img"):
            u = (img.get("data-src") or img.get("data-lazy-src") or img.get("src") or "").strip()
            if not u:
                continue
            full_u = urljoin(base_url, u)
            if es_imagen_valida(full_u):
                return full_u

    return ""


def detectar_archivos(urls_candidatas: list[str], extensiones: list[str], base_url: str) -> list[dict[str, str]]:
    exts = {e.lower().lstrip(".") for e in extensiones if e.lower().lstrip(".") not in {"html", "rss", "xml"}}
    encontrados: dict[str, dict[str, str]] = {}
    for u in urls_candidatas:
        if not u:
            continue
        abs_u = urljoin(base_url, u.strip())
        path = urlparse(abs_u).path.lower()
        m = re.search(r"\.([a-z0-9]{2,6})$", path)
        if m:
            ext = m.group(1)
            if ext in exts and abs_u not in encontrados:
                nombre_arch = os.path.basename(urlparse(abs_u).path) or f"archivo.{ext}"
                encontrados[abs_u] = {
                    "nombre": nombre_arch,
                    "extension": ext.upper(),
                    "url": abs_u,
                }
    return list(encontrados.values())


def clasificar_nota(texto_completo: str, sitio: dict[str, Any], reglas: dict[str, list[str]], taxonomias: list[str]) -> tuple[str, list[str]]:
    txt_lower = texto_completo.lower()
    puntajes: Counter[str] = Counter()
    etiquetas: list[str] = []

    for tax in taxonomias:
        kws = reglas.get(tax, [])
        for kw in kws:
            kw_l = kw.lower().strip()
            if not kw_l:
                continue
            if re.search(r"\b" + re.escape(kw_l) + r"\b", txt_lower) or kw_l in txt_lower:
                puntajes[tax] += 1
                etiqueta_fmt = "#" + re.sub(r"[^a-z0-9áéíóúñ]+", "", kw_l)
                if len(etiqueta_fmt) > 1 and etiqueta_fmt not in etiquetas:
                    etiquetas.append(etiqueta_fmt)

    categoria_fuente = (sitio.get("categoria") or "").lower()
    subtipo_fuente = (sitio.get("subtipo") or "").lower()
    if "universidad" in categoria_fuente or "investigación" in categoria_fuente or "ciencia" in subtipo_fuente or "tecnología" in subtipo_fuente:
        puntajes["Ciencia, Tecnología y Educación"] += 1
    elif "estadística" in subtipo_fuente or "boletín" in subtipo_fuente or "geodatos" in subtipo_fuente or "control" in subtipo_fuente:
        puntajes["Normativa y Datos Oficiales"] += 1
    elif "económico" in subtipo_fuente or "hacienda" in subtipo_fuente or "productiva" in subtipo_fuente or "banca" in subtipo_fuente or "energética" in subtipo_fuente:
        puntajes["Economía, Finanzas y Producción"] += 1
    elif "sanitaria" in subtipo_fuente or "judicial" in subtipo_fuente or "seguridad social" in subtipo_fuente:
        puntajes["Sociedad, Salud y Justicia"] += 1
    elif "cultural" in subtipo_fuente or "turística" in subtipo_fuente:
        puntajes["Cultura y Deportes"] += 1
    elif "gobierno" in categoria_fuente:
        puntajes["Política y Gestión"] += 1

    if puntajes:
        mejor_tax = puntajes.most_common(1)[0][0]
    else:
        mejor_tax = taxonomias[0] if taxonomias else "Política y Gestión"

    if not etiquetas:
        etiquetas = ["#larioja", "#" + re.sub(r"[^a-z0-9]+", "", mejor_tax.lower())[:18]]

    return mejor_tax, etiquetas[:8]


def construir_contenidos_vinculados(noticias: list[dict[str, Any]], taxonomias: list[str]) -> list[dict[str, Any]]:
    por_tax: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for n in noticias:
        por_tax[n["taxonomia"]].append(n)

    vinculados: list[dict[str, Any]] = []
    for idx, tax in enumerate(taxonomias, start=1):
        grupo = por_tax.get(tax, [])
        if not grupo:
            continue
        fuentes_unicas = []
        refs = []
        extractos = []
        for item in grupo:
            if item["fuente"] not in fuentes_unicas:
                fuentes_unicas.append(item["fuente"])
            refs.append({
                "id": item["id"],
                "fuente": item["fuente"],
                "titulo": item["titulo"],
                "url": item["url"],
                "fecha": item["fecha"],
            })
            extractos.append(f"[{item['fuente']}] {item['titulo']}: {item['copete']}")

        titulo_orig = f"Síntesis de {tax}: {len(grupo)} registros en {len(fuentes_unicas)} fuentes de La Rioja"
        copete_orig = (
            f"Cruce temático en {tax} consolidando aportes de {', '.join(fuentes_unicas[:5])}"
            f"{' y otras fuentes' if len(fuentes_unicas) > 5 else ''}."
        )
        cuerpo_orig = (
            f"Análisis consolidado de MonitorV3.2 para el eje «{tax}» en la Provincia de La Rioja.\n\n"
            + "\n\n".join(extractos)
        )
        vinculados.append({
            "id": f"vinculo-{idx:02d}",
            "taxonomia": tax,
            "titulo_original": titulo_orig,
            "copete": copete_orig,
            "cuerpo_original": cuerpo_orig,
            "fuentes_vinculadas": fuentes_unicas,
            "notas_referenciadas": refs,
        })
    return vinculados


def recolectar_sitio(sitio: dict[str, Any], reglas: dict[str, list[str]], taxonomias: list[str], extensiones: list[str]) -> list[dict[str, Any]]:
    notas: list[dict[str, Any]] = []
    nombre_sitio = sitio.get("nombre", "Fuente sin nombre")
    url_web = sitio.get("url_web", "")
    url_rss = sitio.get("url_rss", "")
    usar_rss = bool(sitio.get("usar_rss") and url_rss)
    profundidad = int(sitio.get("crawl_profundidad", 2) or 2)
    ahora_iso = datetime.now(timezone.utc).isoformat()

    if usar_rss:
        _, raw_rss = obtener_url(url_rss)
        if raw_rss:
            parsed = feedparser.parse(raw_rss)
            for entry in parsed.entries:
                titulo = limpiar_texto(entry.get("title") or "Sin título")
                enlace = urljoin(url_rss, (entry.get("link") or url_web or "").strip())
                resumen_raw = ""
                if entry.get("content") and isinstance(entry["content"], list):
                    resumen_raw = entry["content"][0].get("value") or ""
                if not resumen_raw:
                    resumen_raw = entry.get("summary") or entry.get("description") or ""

                soup_resumen = BeautifulSoup(resumen_raw, "html.parser") if resumen_raw else None
                copete = limpiar_texto(resumen_raw)
                cuerpo = limpiar_cuerpo(resumen_raw)
                imagen = extraer_imagen_item(entry, soup_resumen, enlace or url_web)

                candidatos_arch = [
                    (l.get("href") or "") for l in (entry.get("links") or [])
                ] + [
                    (e.get("href") or e.get("url") or "") for e in (entry.get("enclosures") or [])
                ]
                if soup_resumen:
                    candidatos_arch.extend([(a.get("href") or "") for a in soup_resumen.find_all("a")])

                if enlace and enlace.startswith("http"):
                    _, raw_nota = obtener_url(enlace, timeout=10)
                    if raw_nota:
                        soup_nota = BeautifulSoup(raw_nota, "html.parser")
                        cuerpo_nota = limpiar_cuerpo(raw_nota)
                        if len(cuerpo_nota) > len(cuerpo):
                            cuerpo = cuerpo_nota
                        if not copete and cuerpo:
                            copete = cuerpo[:280]
                        if not imagen:
                            imagen = extraer_imagen_item({}, soup_nota, enlace)
                        candidatos_arch.extend([(a.get("href") or "") for a in soup_nota.find_all("a")])

                archivos = detectar_archivos(candidatos_arch, extensiones, enlace or url_web)
                tax, etiquetas = clasificar_nota(f"{titulo} {copete} {cuerpo}", sitio, reglas, taxonomias)
                uid = hashlib.sha1(f"{nombre_sitio}|{titulo}|{enlace}".encode("utf-8")).hexdigest()[:12]

                notas.append({
                    "id": f"nota-{uid}",
                    "fuente_id": sitio.get("id", ""),
                    "fuente": nombre_sitio,
                    "categoria": sitio.get("categoria", ""),
                    "subtipo": sitio.get("subtipo", ""),
                    "localidad": sitio.get("localidad", "La Rioja"),
                    "canal": "RSS",
                    "titulo": titulo,
                    "copete": copete or (cuerpo[:240] if cuerpo else titulo),
                    "cuerpo": cuerpo or copete or titulo,
                    "imagen": imagen,
                    "url": enlace or url_web,
                    "fecha": entry.get("published") or entry.get("updated") or ahora_iso,
                    "taxonomia": tax,
                    "etiquetas": etiquetas,
                    "archivos": archivos,
                })

    if not notas and url_web:
        _, raw_web = obtener_url(url_web)
        if raw_web:
            soup_web = BeautifulSoup(raw_web, "html.parser")
            titulo_pag = limpiar_texto(soup_web.title.string if soup_web.title and soup_web.title.string else nombre_sitio)
            cuerpo_pag = limpiar_cuerpo(raw_web)
            imagen_pag = extraer_imagen_item({}, soup_web, url_web)
            enlaces_pag = [(a.get("href") or "") for a in soup_web.find_all("a")]
            archivos_pag = detectar_archivos(enlaces_pag, extensiones, url_web)

            if profundidad >= 2:
                visitados = {url_web}
                for raw_href in enlaces_pag[:25]:
                    abs_h = urljoin(url_web, raw_href.strip())
                    if abs_h in visitados or urlparse(abs_h).netloc != urlparse(url_web).netloc:
                        continue
                    visitados.add(abs_h)
                    _, raw_sub = obtener_url(abs_h, timeout=8)
                    if raw_sub:
                        soup_sub = BeautifulSoup(raw_sub, "html.parser")
                        h1_tag = soup_sub.find(["h1", "h2"])
                        t_sub = limpiar_texto(h1_tag.get_text(" ", strip=True)) if h1_tag else titulo_pag
                        c_sub = limpiar_cuerpo(raw_sub)
                        img_sub = extraer_imagen_item({}, soup_sub, abs_h)
                        arch_sub = detectar_archivos([(a.get("href") or "") for a in soup_sub.find_all("a")], extensiones, abs_h)
                        if len(c_sub) >= 80 or arch_sub:
                            tax_s, etq_s = clasificar_nota(f"{t_sub} {c_sub}", sitio, reglas, taxonomias)
                            uid_s = hashlib.sha1(f"{nombre_sitio}|{t_sub}|{abs_h}".encode("utf-8")).hexdigest()[:12]
                            notas.append({
                                "id": f"nota-{uid_s}",
                                "fuente_id": sitio.get("id", ""),
                                "fuente": nombre_sitio,
                                "categoria": sitio.get("categoria", ""),
                                "subtipo": sitio.get("subtipo", ""),
                                "localidad": sitio.get("localidad", "La Rioja"),
                                "canal": "Crawl HTML",
                                "titulo": t_sub,
                                "copete": c_sub[:260] if c_sub else t_sub,
                                "cuerpo": c_sub or t_sub,
                                "imagen": img_sub or imagen_pag,
                                "url": abs_h,
                                "fecha": ahora_iso,
                                "taxonomia": tax_s,
                                "etiquetas": etq_s,
                                "archivos": arch_sub,
                            })

            if not notas:
                tax_p, etq_p = clasificar_nota(f"{titulo_pag} {cuerpo_pag}", sitio, reglas, taxonomias)
                uid_p = hashlib.sha1(f"{nombre_sitio}|{titulo_pag}|{url_web}".encode("utf-8")).hexdigest()[:12]
                notas.append({
                    "id": f"nota-{uid_p}",
                    "fuente_id": sitio.get("id", ""),
                    "fuente": nombre_sitio,
                    "categoria": sitio.get("categoria", ""),
                    "subtipo": sitio.get("subtipo", ""),
                    "localidad": sitio.get("localidad", "La Rioja"),
                    "canal": "Crawl HTML",
                    "titulo": titulo_pag,
                    "copete": cuerpo_pag[:260] if cuerpo_pag else titulo_pag,
                    "cuerpo": cuerpo_pag or titulo_pag,
                    "imagen": imagen_pag,
                    "url": url_web,
                    "fecha": ahora_iso,
                    "taxonomia": tax_p,
                    "etiquetas": etq_p,
                    "archivos": archivos_pag,
                })

    return notas


def main() -> int:
    t0 = time.time()
    if not os.path.exists(FUENTES_PATH):
        print(f"No se encontro {FUENTES_PATH}", file=sys.stderr)
        return 1

    with open(FUENTES_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    sitios = [s for s in config.get("sitios", []) if s.get("activo", True)]
    reglas = config.get("reglas_clasificacion") or DEFAULT_REGLAS
    taxonomias = config.get("taxonomias") or DEFAULT_TAXONOMIAS
    extensiones = config.get("extensiones_objetivo") or DEFAULT_EXTENSIONES

    todas_notas: list[dict[str, Any]] = []
    for sitio in sitios:
        try:
            items = recolectar_sitio(sitio, reglas, taxonomias, extensiones)
            todas_notas.extend(items)
            print(f"[OK] {sitio.get('nombre')}: {len(items)} notas")
        except Exception as exc:
            print(f"[WARN] {sitio.get('nombre')}: {exc}", file=sys.stderr)

    contenidos_vinculados = construir_contenidos_vinculados(todas_notas, taxonomias)
    salida = {
        "version": "3.2.0-monitor-v3.2-larioja",
        "generado_utc": datetime.now(timezone.utc).isoformat(),
        "jurisdiccion": config.get("jurisdiccion", "Provincia de La Rioja, Argentina"),
        "total_fuentes_activas": len(sitios),
        "total_noticias": len(todas_notas),
        "noticias": todas_notas,
        "contenidos_vinculados": contenidos_vinculados,
    }

    os.makedirs(os.path.dirname(NOTICIAS_PATH), exist_ok=True)
    with open(NOTICIAS_PATH, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)

    print(f"Completado en {time.time() - t0:.2f}s -> {len(todas_notas)} notas y {len(contenidos_vinculados)} vinculos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
