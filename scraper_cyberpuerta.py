#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Scraper Cyberpuerta - Versión para GitHub Actions

- Pegas tus SKUs en un bloque de texto (INPUT_CODES_RAW).
- Usa requests + BeautifulSoup.
- Maneja 429 con reintentos y backoff.
- Intenta detectar:
    * Sin resultados reales
    * Bloqueo / captcha / HTML raro
- Guarda algunos HTML de debug en archivos .html
- Genera:
    * cyberpuerta_datos_paso1.csv / .xlsx
    * cyberpuerta_datos_pasofull.csv / .xlsx
'''

import time
import random
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote_plus
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import pandas as pd

# ================================================================
# 1) AQUÍ PEGAS TUS SKUs (UNO POR LÍNEA)
#    Solo edita este bloque de texto:
# ================================================================

INPUT_CODES_RAW = """

KF556C40BBA-16
KF556C40BBA-32
KF556C40BBAK2-32
"""

def get_input_codes() -> List[str]:
    """
    Convierte el bloque de texto anterior en una lista de SKUs.
    - Ignora líneas vacías.
    - Hace strip() a cada línea.
    """
    codes: List[str] = []
    for line in INPUT_CODES_RAW.splitlines():
        line = line.strip()
        if line:
            codes.append(line)
    return codes


# ================================================================
# 2) SESIÓN HTTP CON RETRY Y HEADERS
# ================================================================

def build_session() -> requests.Session:
    session = requests.Session()

    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # Headers "humanos"
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    })
    return session


def get_with_backoff(
    session: requests.Session,
    url: str,
    max_attempts: int = 4,
    timeout: int = 30
) -> Tuple[Optional[str], Optional[str]]:
    """
    Devuelve (html, error_msg).
    Si no se logra obtener, html = None y error_msg = texto.
    """
    delay = 3.0
    for attempt in range(1, max_attempts + 1):
        try:
            resp = session.get(url, timeout=timeout)
        except Exception as e:
            print(f"⚠️ Error de conexión en intento {attempt} para {url}: {e}")
            if attempt < max_attempts:
                print(f"   Esperando {delay:.1f} s antes de reintentar...")
                time.sleep(delay)
                delay *= 2
                continue
            else:
                return None, f"Error de conexión después de {max_attempts} intentos: {e}"

        if resp.status_code == 200:
            return resp.text, None

        if resp.status_code == 429:
            print(f"⚠️ 429 en intento {attempt} para {url}. Esperando {delay:.1f} s antes de reintentar...")
            if attempt < max_attempts:
                time.sleep(delay)
                delay *= 2
                continue
            else:
                return None, f"Error: 429 Too Many Requests después de {max_attempts} intentos."

        # Otros errores HTTP
        print(f"⚠️ HTTP {resp.status_code} en intento {attempt} para {url}.")
        if attempt < max_attempts:
            print(f"   Esperando {delay:.1f} s antes de reintentar...")
            time.sleep(delay)
            delay *= 2
        else:
            return None, f"Error HTTP {resp.status_code} después de {max_attempts} intentos."

    return None, f"Error desconocido al obtener {url}"


# ================================================================
# 3) PARSE DE LA PÁGINA DE BÚSQUEDA
# ================================================================

DEBUG_HTML_LIMIT = 5  # cuántos HTML "raros" guardar para depurar
debug_html_saved = 0  # contador global


def save_debug_html(prefix: str, code: str, html: str, idx: int) -> None:
    global debug_html_saved
    if debug_html_saved >= DEBUG_HTML_LIMIT:
        return
    safe_code = re.sub(r"[^A-Za-z0-9_-]+", "_", code)[:40]
    fname = f"debug_{prefix}_{idx:03d}_{safe_code}.html"
    try:
        with open(fname, "w", encoding="utf-8") as f:
            f.write(html)
        debug_html_saved += 1
        print(f"📝 HTML de depuración guardado en: {fname}")
    except Exception as e:
        print(f"⚠️ No se pudo guardar HTML de depuración ({fname}): {e}")


def detect_no_results_or_block(html: str) -> str:
    """
    Intenta detectar si la página de búsqueda:
    - No tiene resultados ("no_results")
    - Es un bloqueo / captcha ("blocked")
    - O no se detecta nada especial ("unknown")
    """
    text = BeautifulSoup(html, "lxml").get_text(" ", strip=True).lower()

    # Frases típicas de "no resultados"
    no_results_phrases = [
        "no se encontraron resultados",
        "no se han encontrado resultados",
        "no se encontraron productos",
        "no hay resultados para tu búsqueda",
        "no hay productos que coincidan",
    ]
    for phrase in no_results_phrases:
        if phrase in text:
            return "no_results"

    # Cosas típicas de bloqueo / captcha / cloudflare
    blocked_phrases = [
        "captcha",
        "cloudflare",
        "nuestro sistema ha detectado tráfico inusual",
        "attention required",
        "verificación de seguridad",
    ]
    for phrase in blocked_phrases:
        if phrase in text:
            return "blocked"

    return "unknown"


def parse_search_page_for_product_url(html: str, base_url: str) -> Optional[str]:
    """
    Intenta encontrar el primer URL de producto en la página de búsqueda.
    Devuelve URL absoluto o None.
    """
    soup = BeautifulSoup(html, "lxml")

    # 1) Intentar selectores típicos de cards de producto
    selectors = [
        "div.artBox a",      # layout antiguo
        "div.artbox a",
        "div.productData a",
        "div.product a",
        "div.artTplBox a",
        "a.art-product-link",
        "a.articlePicture",
    ]
    for sel in selectors:
        a = soup.select_one(sel)
        if a and a.get("href"):
            href = a.get("href")
            if not href.startswith("javascript"):
                return urljoin(base_url, href)

    # 2) Fallback: buscar cualquier <a> que apunte a detalles de producto
    candidates = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if any(x in href for x in [
            "/index.php?cl=details",
            "/Computo-", "/C%C3%B3mputo-", "/Memoria-", "/Almacenamiento-",
            "/Memorias-RAM", "/Discos-Duros", "/SSD"
        ]):
            candidates.append(urljoin(base_url, href))

    if candidates:
        return candidates[0]

    return None


# ================================================================
# 4) PARSE DE LA PÁGINA DE PRODUCTO
# ================================================================

def extract_first_money(text: str) -> Optional[Tuple[str, Optional[float]]]:
    """
    Busca el primer patrón tipo $ 1,234.56 en un texto largo.
    Devuelve (texto_precio, precio_float) o (None, None).
    """
    m = re.search(r"\$\s*([0-9][0-9\.\,]*)", text)
    if not m:
        return None, None
    precio_txt = "$ " + m.group(1).strip()

    # Limpiar para convertir a float:
    num = m.group(1)
    num = num.replace(" ", "")
    # Eliminar todo lo que no sea dígito para quedarnos con un número entero
    limpio = re.sub(r"[^\d]", "", num)
    try:
        precio_num = float(limpio)
    except ValueError:
        precio_num = None

    return precio_txt, precio_num


def extract_stock(text: str) -> Tuple[Optional[str], Optional[int]]:
    """
    Intenta encontrar algo como:
    - 'Disponibles: 12 pzas'
    - 'Existencias: 5'
    etc.
    """
    patrones = [
        r"(disponible[s]?:?\s*[0-9]+[^0-9]?)",
        r"(existencias?:?\s*[0-9]+[^0-9]?)",
        r"(stock:?\s*[0-9]+[^0-9]?)",
    ]
    for pat in patrones:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            txt = m.group(1).strip()
            m2 = re.search(r"(\d+)", txt)
            stock_num = int(m2.group(1)) if m2 else None
            return txt, stock_num

    return None, None


def parse_product_page(html: str) -> Tuple[Optional[str], Optional[str], Optional[float], Optional[str], Optional[int]]:
    """
    Devuelve (titulo, precio_txt, precio_num, stock_txt, stock_num)
    """
    soup = BeautifulSoup(html, "lxml")

    # Título
    title_tag = soup.find("h1")
    if title_tag and title_tag.get_text(strip=True):
        titulo = title_tag.get_text(strip=True)
    else:
        if soup.title and soup.title.get_text(strip=True):
            titulo = soup.title.get_text(strip=True)
        else:
            titulo = None

    # Texto completo para buscar precio y stock
    full_text = soup.get_text(" ", strip=True)

    precio_txt, precio_num = extract_first_money(full_text)
    stock_txt, stock_num = extract_stock(full_text)

    return titulo, precio_txt, precio_num, stock_txt, stock_num


# ================================================================
# 5) MAIN
# ================================================================

def main() -> None:
    codes = get_input_codes()
    if not codes:
        print("⚠️ No hay códigos en INPUT_CODES_RAW. Asegúrate de pegar al menos uno.")
        return

    print(f"📥 Usando {len(codes)} códigos para buscar en Cyberpuerta.\n")

    base_search_url = "https://www.cyberpuerta.mx/index.php?cl=search&searchparam="
    base_site_url = "https://www.cyberpuerta.mx/"

    session = build_session()

    rows: List[Dict[str, Any]] = []

    # Encabezado de log
    print("TIMESTAMP\tSKU\tURL_BUSQUEDA\tURL_PRODUCTO\tTITULO\tPRECIO_TEXTO\tPRECIO_NUM\tSTOCK_TEXTO\tSTOCK_NUM\tSTATUS")

    for idx, code in enumerate(codes, start=1):
        code_str = str(code).strip()
        if not code_str:
            continue

        # Espera aleatoria para no parecer bot
        wait_s = random.uniform(30.0, 60.0)
        print(f"\n⏳ Esperando {wait_s:.1f} s antes de buscar código '{code_str}'...")
        time.sleep(wait_s)

        search_url = base_search_url + quote_plus(code_str)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1) BÚSQUEDA
        html_search, err_search = get_with_backoff(session, search_url)

        if html_search is None:
            status = err_search or "Error desconocido en búsqueda"
            print(f"[{idx}/{len(codes)}] {code_str} -> {status}")
            row = {
                "TIMESTAMP": timestamp,
                "SKU": code_str,
                "URL_BUSQUEDA": search_url,
                "URL_PRODUCTO": "",
                "TITULO": "",
                "PRECIO_TEXTO": "",
                "PRECIO_NUM": "",
                "STOCK_TEXTO": "",
                "STOCK_NUM": "",
                "STATUS": status,
            }
            rows.append(row)
            continue

        # Detectar si es no resultados, bloqueo, etc.
        detection = detect_no_results_or_block(html_search)
        product_url: Optional[str] = None

        if detection == "no_results":
            status = "Sin resultados en búsqueda"
            print(f"[{idx}/{len(codes)}] {code_str} -> Sin resultados en búsqueda")
        else:
            # Intentar sacar URL de producto
            product_url = parse_search_page_for_product_url(html_search, base_site_url)
            if product_url:
                status = "OK - Producto encontrado en búsqueda"
                print(f"[{idx}/{len(codes)}] {code_str} -> Producto encontrado: {product_url}")
            else:
                if detection == "blocked":
                    status = "Bloqueado / captcha / anti-bot en búsqueda"
                else:
                    status = "HTML de búsqueda sin patrón de producto (posible layout nuevo o bloqueo)"

                print(f"[{idx}/{len(codes)}] {code_str} -> {status}")
                save_debug_html("search", code_str, html_search, idx)

        # Si no hay URL de producto, guardamos fila sin datos de producto
        if not product_url:
            row = {
                "TIMESTAMP": timestamp,
                "SKU": code_str,
                "URL_BUSQUEDA": search_url,
                "URL_PRODUCTO": "",
                "TITULO": "",
                "PRECIO_TEXTO": "",
                "PRECIO_NUM": "",
                "STOCK_TEXTO": "",
                "STOCK_NUM": "",
                "STATUS": status,
            }
            rows.append(row)
            continue

        # 2) PÁGINA DE PRODUCTO
        html_prod, err_prod = get_with_backoff(session, product_url, max_attempts=3)

        if html_prod is None:
            status_prod = err_prod or "Error desconocido al obtener producto"
            print(f"   ⚠️ Error al obtener producto para {code_str}: {status_prod}")
            row = {
                "TIMESTAMP": timestamp,
                "SKU": code_str,
                "URL_BUSQUEDA": search_url,
                "URL_PRODUCTO": product_url,
                "TITULO": "",
                "PRECIO_TEXTO": "",
                "PRECIO_NUM": "",
                "STOCK_TEXTO": "",
                "STOCK_NUM": "",
                "STATUS": status_prod,
            }
            rows.append(row)
            continue

        titulo, precio_txt, precio_num, stock_txt, stock_num = parse_product_page(html_prod)

        status_final = "OK"
        if not precio_txt:
            status_final = "OK (sin precio detectado)"
        if not titulo:
            status_final = status_final + " / sin título detectado"

        print(f"   ✅ {code_str} -> titulo='{titulo}', precio='{precio_txt}', stock='{stock_txt}'")

        row = {
            "TIMESTAMP": timestamp,
            "SKU": code_str,
            "URL_BUSQUEDA": search_url,
            "URL_PRODUCTO": product_url,
            "TITULO": titulo or "",
            "PRECIO_TEXTO": precio_txt or "",
            "PRECIO_NUM": precio_num if precio_num is not None else "",
            "STOCK_TEXTO": stock_txt or "",
            "STOCK_NUM": stock_num if stock_num is not None else "",
            "STATUS": status_final,
        }
        rows.append(row)

    # ============================================================
    # 6) GUARDAR RESULTADOS (CSV / XLSX)
    # ============================================================
    if not rows:
        print("⚠️ No se generaron filas de resultado.")
        return

    df = pd.DataFrame(rows, columns=[
        "TIMESTAMP", "SKU", "URL_BUSQUEDA", "URL_PRODUCTO",
        "TITULO", "PRECIO_TEXTO", "PRECIO_NUM",
        "STOCK_TEXTO", "STOCK_NUM", "STATUS"
    ])

    # Paso 1 (para compatibilidad con tu workflow)
    csv_paso1 = "cyberpuerta_datos_paso1.csv"
    xlsx_paso1 = "cyberpuerta_datos_paso1.xlsx"

    # Pasofull (mismo contenido, pero nombre que ya usas)
    csv_full = "cyberpuerta_datos_pasofull.csv"
    xlsx_full = "cyberpuerta_datos_pasofull.xlsx"

    df.to_csv(csv_paso1, index=False, encoding="utf-8-sig")
    df.to_csv(csv_full, index=False, encoding="utf-8-sig")

    with pd.ExcelWriter(xlsx_paso1, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="datos", index=False)

    with pd.ExcelWriter(xlsx_full, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="datos", index=False)

    print(f"\n✅ Archivos generados:")
    print(f"   - {csv_paso1}, {xlsx_paso1}")
    print(f"   - {csv_full}, {xlsx_full}")
    print("🎉 Script terminado.")


if __name__ == "__main__":
    main()
