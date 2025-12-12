import os
import re
import time
import random
import sys
import statistics
from datetime import datetime
from urllib.parse import urljoin, quote_plus

import requests
import pandas as pd
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import smtplib
import ssl
from email.message import EmailMessage

# ================= PARÁMETROS (ajústalos si quieres) =================
# Aquí pegas tus SKUs, uno por línea
INPUT_CODES = """

SNV3S/1000G
SA400S37/960G
SDC4/32GB
DTX/64GB
AUSDX128GUICL10A1-RA1
SXS1000/1000G
SA400S37/480G
SDCS3/128GB
HDTB510XK3AA
DTXS/64GB
ASU630SS-480GQ-R
AHD710P-1TU31-CBK
DTX/128GB
SDCS3/256GB
SDCS3/64GB
SEDC600M/7680G
SKC600/512G
SXS1000/2000G
HDTB540XK3CA
ASU630SS-240GQ-R
SXS1000R/2000G
AHD710P-2TU31-CBK
SEDC600M/960G
SNV3S/500G
SDCS2/128GB
SXS1000R/1000G
KF432C16BB/32
AUSDX64GUICL10-RA1
SEDC600M/1920G
SKC600/1024G
DTXM/64GB
HDTB520XK3AA
KF432S20IB/32
SKC600/256G
KC-U2L64-7LB
KF556S40IB-32
SNV3S/2000G
AC008-32G-RWE
SA400S37/240G
KF432C16BB/16
KF552C40BBK2-32
SKC3000S/1024G
AHV620S-1TU31-CBK
SNV3SM3/1T0
AUSDH32GUICL10-RA1
SFYRDK/2000G
KC-U2L64-7LP
SDCZ50-032G-B35
SXS2000/2000G
SEDC600M/3840G
KF432S20IB/16
SEDC600M/480G
SXS2000/4000G
AC906-32G-RWH
SDCG4/256GB
AC008-32G-RKD
SFYR2S/1T0
SNV3S/4000G
DT70/64GB
DTSE9G3/512GB
SKC3000S/512G
100-100000263BOX
AHD710P-4TU31-CBK
PBC20-WH
KF432C16BB1/16
SDCS2/128GBSP
AC008-16G-RKD
SFYR2S/2T0
AC008-16G-RWE
AC906-32G-RWB
SDCG4/512GB
KF432C16BB/8
SDCS3/64GBSP
AC906-32G-RPP
SKC3000D/2048G
KF556S40IBK2-32
KF556S40IBK2-64
SXS2000/1000G
SNV3SM3/2T0
AUSDX512GUI3V30SA2-RA1
AP20000QCD-DGT-CBK
DTX/256GB
100-100000927BOX
AHD710P-5TU31-CBK

AHV620S-2TU31-CBK
AUSDH16GUICL10-RA1
DTMAXA/1TB
KF556S40IB-16
KF432S20IB/8
KVR32S22S8/8
KC-U2G64-5R
KF432S20IBK2/32
KF548S38IB-16
DTXM/256GB
UC310-128G-RBK
100-100000591WOF
KC-S44480-7S
KF556C40BB-32
SDCG4/1TB
AUSDX64GUICL10A1-RA1
AORUS 15 9MF-E2LA583
SDCG4/128GB
AC906-64G-RWB
DTXM/128GB
100-100000926WOF
ASUS ROG STRIX LC III 360 ARGB
AD4S320016G22-SGN
PA328CGV
ASU630SS-1T92Q-R
VG32VQ1B
XG27WCMS
SDSSDE61-2T00-G25
SFYRSK/1000G
TUF-GAMING-1000G
AUV220-32G-RBKBL
SKC600/2048G
AX4U320016G16A-SBKD35G
DTXS/128GB
ASUS PRIME AP-850
SDG4/64GB
PA278CV
XG27AQDMG
ASU650SS-1TT-R
AUSDX256GUICL10A1-RA1
AC906-32G-RBK
DTMAX/1TB
KF552C40BBAK2-32
KF548S38IB-32
HDTCA20XW3AA
ROG-STRIX-1000P-GAMING
HDTX120XSCAA
HDTCA20XK3AA
KF432C16BBK2/64
100-100000457BOX
SNV3SM3/500G
AUV220-32G-RWHGY
AHM800-6TU32G1-CUSBK
AD4S26668G19-SGN
AD4S320032G22-SGN
KF432C16BB1K2/32
AD5S560016G-S
HDWG780XZSTA
HDTCA40XR3CA
SFYR2S/4T0
HDTX140XSCCA
HDTCA20XR3AA
SDCS2/64GBSP
SDSSDE81-2T00-G25
PROART LC 360
AUV250-32G-RBK
SLEG-900-2TCS
KC-U2L64-7LG
AP20000QCD-DGT-CRD
SC740-1000G-CBU
SDR2V6/256GB
ASU800SS-1TT-C
MIC-KF8-00001
AELI-SE880-1TCGY
AD4U320016G22-SGN
KF432C16BBK2/32
SDR2V6/128GB
KF432C16BB12A/16
AD4U266616G19-SGN
SDR2/128GB
KF552C40BB-16
AHD710P-2TU31-CBL
DTKN/128GB
KF432C16BB2A/16
AD4S32008G22-SGN
SDCS3/1TB
KF432C16BB2AK2/32
HDTX140XK3CA
AHV620S-1TU31-CBL
AUSDX256GUI3V30SA2-RA1
KF556C36BBEA-64
SLEG-860-2000GCS
DTKN/64GB
SDSSDE30-2T00-G26
AC008-64G-RWE
SLEG-900-1TCS
ROG ASTRAL RTX5080 16GB
AHD330-2TU31-CBK
KVR32S22D8/16
SDCG4/256GBSP
SKC3000D/4096G
100-1000000253BOX
AC008-64G-RKD
AUV220-64G-RBKBL
AX5U6000C3032G-SLABRBK
KF432C16BB2A/32
SDCS3/512GB
KF556C40BB-16
KF552C40BB-32
SD810-4000G-CBK
KVR32N22S8/16
DTXM/64GB-2P
SDCE/128GB
AGAMMIXS70B-1T-CS
KF548S38IB-8
AHD710P-2TU31-CRD
HDWG51GXZSTA
KF548S38IBK2-32
HDTCA40XW3CA
SDCS2/64GB
HDWG51CXZSTA

""".strip()

# Si quieres URLs directas, las pones aquí
INPUT_URLS = [
    # "https://www.cyberpuerta.mx/index.php?cl=search&searchparam=AUSDH16GUICL10-RA1",
]

BASE_SEARCH = "https://www.cyberpuerta.mx/index.php?cl=search&searchparam="

# --- Control de tiempos (por SKU, como en tu script de Colab) ---
INITIAL_WAIT_RANGE = (50.0, 80.0)
BETWEEN_REQUESTS    = (4.0, 7.0)
MAX_RETRIES         = 7
BACKOFF_BASE        = 4.0
BACKOFF_CAP         = 90.0

ROLLING_WINDOW      = 6
ALPHA_SENSITIVITY   = 1.2

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "Chrome/126.0.0.0 Safari/537.36"
)

# ========= CONFIG GLOBAL DE TIEMPO / LOOPS PARA GITHUB ==============
MAX_TOTAL_HOURS = float(os.environ.get("CYBERPUERTA_MAX_HOURS", "0.07"))
TIME_GUARD_MINUTES = float(os.environ.get("CYBERPUERTA_GUARD_MINUTES", "1"))

# 🔴 AQUÍ ESTABA EL BUG: antes leías CYBERPUERTA_LOOP_INDEX, pero en el YAML mandas LOOP_INDEX
# Soportamos ambos nombres por si acaso.
LOOP_INDEX = int(os.environ.get("LOOP_INDEX", os.environ.get("CYBERPUERTA_LOOP_INDEX", "1")))
if LOOP_INDEX < 1:
    LOOP_INDEX = 1
if LOOP_INDEX > 3:
    LOOP_INDEX = 3

# ================== Sesión HTTP con retries básicos (5xx) ==================
session = requests.Session()
session.headers.update({
    "User-Agent": UA,
    "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.cyberpuerta.mx/",
    "Cache-Control": "no-cache",
})
retry = Retry(
    total=MAX_RETRIES,
    connect=MAX_RETRIES,
    read=MAX_RETRIES,
    backoff_factor=0.5,
    status_forcelist=[500, 502, 503, 504],
    allowed_methods=["GET", "HEAD"],
    raise_on_status=False,
)
session.mount("http://", HTTPAdapter(max_retries=retry))
session.mount("https://", HTTPAdapter(max_retries=retry))


def jitter(a, b):
    return random.uniform(a, b)


def sleep_range(a, b):
    t = jitter(a, b)
    time.sleep(t)
    return t


def to_number(txt):
    if not txt:
        return None
    t = (
        txt.replace("$", "")
          .replace("MXN", "")
          .replace("mxn", "")
          .replace("\xa0", " ")
          .strip()
    )
    t = re.sub(r"[^\d\.,]", "", t).replace(",", "")
    try:
        return float(t)
    except:
        return None


def parse_first_product_url_from_search(html, current_url):
    soup = BeautifulSoup(html, "lxml")
    css_candidates = [
        "h2.productTitle a[href]",
        "a.product__title[href]",
        "a.title[href]",
        'a[href*="cl=details"][href$=".html"]',
        'a[href$=".html"]',
    ]
    for sel in css_candidates:
        a = soup.select_one(sel)
        if a and a.get("href"):
            return urljoin(current_url, a["href"])
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if href.endswith(".html"):
            return urljoin(current_url, href)
    return None


def extract_all_from_product(html):
    soup = BeautifulSoup(html, "lxml")
    title = ""
    h1 = soup.select_one("h1.detailsInfo_right_title") or soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)

    price_text = ""
    meta_price = soup.select_one('meta[itemprop="price"][content]')
    if meta_price:
        price_text = meta_price["content"]
    if not price_text:
        price_span = soup.select_one("#productPrice") or soup.select_one("span.priceText")
        if price_span:
            price_text = price_span.get_text(" ", strip=True)
    if not price_text:
        body_txt = soup.get_text(" ", strip=True)
        m = re.search(r"\$\s*[\d\.,]+", body_txt)
        if m:
            price_text = m.group(0)
    price_num = to_number(price_text)

    stock_text, stock_num = "", None
    s1 = soup.select_one("div.stock span.stockFlag span")
    if s1:
        n = s1.get_text(strip=True)
        if n.isdigit():
            stock_num = int(n)
            stock_text = f"Disponibles: {stock_num} pzas."
    if stock_num is None:
        s2 = soup.select_one("div.stock span.stockFlag")
        if s2:
            txt = s2.get_text(" ", strip=True)
            m = re.search(r"Disponibles?:\s*(\d+)", txt, flags=re.I)
            if m:
                stock_num = int(m.group(1))
                stock_text = f"Disponibles: {stock_num} pzas."
    if stock_num is None:
        body = soup.get_text(" ", strip=True).lower()
        if ("agotado" in body) or ("no disponible" in body):
            stock_num = 0
            stock_text = "Agotado"
        else:
            m = re.search(r"Disponibles?\s*:?\s*(\d+)", body, flags=re.I)
            if m:
                stock_num = int(m.group(1))
                stock_text = f"Disponibles: {stock_num} pzas."

    return title, (price_text or ""), price_num, (stock_text or ""), (stock_num if stock_num is not None else "")


recent_429 = []


def current_429_ratio():
    if not recent_429:
        return 0.0
    return sum(1 for x in recent_429 if x) / len(recent_429)


def planned_initial_wait():
    base = jitter(*INITIAL_WAIT_RANGE)
    ratio = current_429_ratio()
    multiplier = 1.0 + ALPHA_SENSITIVITY * ratio
    planned = base * multiplier
    return planned


def get_with_backoff(url, allow_redirects=True, timeout=30, mark_429_flag=None):
    last_status = None
    for i in range(MAX_RETRIES):
        try:
            r = session.get(url, allow_redirects=allow_redirects, timeout=timeout)
            last_status = r.status_code
            if r.status_code in (200, 404):
                return r
            if r.status_code in (429, 403):
                if mark_429_flag is not None:
                    mark_429_flag[0] = True
                wait = min(BACKOFF_BASE * (2 ** i), BACKOFF_CAP) + jitter(1.0, 4.0)
                print(f"   HTTP {r.status_code} en {url} -> backoff {wait:.1f}s (reintento {i+1}/{MAX_RETRIES})")
                time.sleep(wait)
                continue
            time.sleep(1.5 + i * 0.5)
        except requests.RequestException as e:
            wait = 2.0 + i * 1.25
            print(f"   Error de red en {url}: {e} -> esperando {wait:.1f}s (reintento {i+1}/{MAX_RETRIES})")
            time.sleep(wait)
    return None


COLUMNS = ["TIMESTAMP", "SKU", "URL_BUSQUEDA", "URL_PRODUCTO", "TITULO",
           "PRECIO_TEXTO", "PRECIO_NUM", "STOCK_TEXTO", "STOCK_NUM", "STATUS"]


def row_to_tsv(row: dict) -> str:
    def fmt(x):
        if x is None:
            return ""
        s = str(x)
        return s.replace("\t", " ").replace("\r", " ").replace("\n", " ").strip()
    return "\t".join(fmt(row.get(col, "")) for col in COLUMNS)


def print_header_once():
    print("\t".join(COLUMNS))
    sys.stdout.flush()


# ================= Carga de códigos por LOOP =======================
def load_codes_for_loop(loop_index: int):
    """
    LOOP 1: lee de INPUT_CODES
    LOOP 2: lee de 'cyberpuerta_pending_codes_loop1.txt'
    LOOP 3: lee de 'cyberpuerta_pending_codes_loop2.txt'
    """
    if loop_index == 1:
        codes = [ln.strip() for ln in INPUT_CODES.splitlines() if ln.strip()]
        print(f"📥 Cargando {len(codes)} códigos desde INPUT_CODES embebido (loop 1).")
        return codes

    prev = loop_index - 1
    pending_file = f"cyberpuerta_pending_codes_loop{prev}.txt"
    if os.path.isfile(pending_file):
        with open(pending_file, encoding="utf-8") as f:
            codes = [ln.strip() for ln in f if ln.strip()]
        print(f"📥 Cargando {len(codes)} códigos pendientes desde '{pending_file}' (loop {loop_index}).")
        return codes
    else:
        print(f"ℹ️ No encontré '{pending_file}'. No hay códigos pendientes para loop {loop_index}.")
        return []


def process_code(code):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sku = code
    url_search = BASE_SEARCH + quote_plus(code) + f"&_ts={int(time.time()*1000)}"
    url_prod = ""
    status = "OK"
    title = ""
    p_txt = ""
    p_num = ""
    s_txt = ""
    s_num = ""

    saw_429 = [False]

    initial_wait = planned_initial_wait()
    print(f"   ⏳ Espera inicial antes de buscar '{sku}': {initial_wait:.1f}s (ratio 429 reciente: {current_429_ratio():.2f})")
    time.sleep(initial_wait)

    r = get_with_backoff(url_search, mark_429_flag=saw_429)
    if not r:
        return {
            "TIMESTAMP": ts, "SKU": sku, "URL_BUSQUEDA": url_search, "URL_PRODUCTO": "",
            "TITULO": "", "PRECIO_TEXTO": "", "PRECIO_NUM": "", "STOCK_TEXTO": "",
            "STOCK_NUM": "", "STATUS": "HTTP error búsqueda"
        }
    if r.status_code == 404:
        return {
            "TIMESTAMP": ts, "SKU": sku, "URL_BUSQUEDA": url_search, "URL_PRODUCTO": "",
            "TITULO": "", "PRECIO_TEXTO": "", "PRECIO_NUM": "", "STOCK_TEXTO": "",
            "STOCK_NUM": "", "STATUS": "404 búsqueda"
        }

    _slept = sleep_range(*BETWEEN_REQUESTS)
    first = parse_first_product_url_from_search(r.text, r.url)
    if not first:
        return {
            "TIMESTAMP": ts, "SKU": sku, "URL_BUSQUEDA": url_search, "URL_PRODUCTO": "",
            "TITULO": "", "PRECIO_TEXTO": "", "PRECIO_NUM": "", "STOCK_TEXTO": "",
            "STOCK_NUM": "", "STATUS": "Sin resultados"
        }

    url_prod = first
    r2 = get_with_backoff(url_prod, mark_429_flag=saw_429)
    if not r2 or r2.status_code == 404:
        return {
            "TIMESTAMP": ts, "SKU": sku, "URL_BUSQUEDA": url_search, "URL_PRODUCTO": url_prod,
            "TITULO": "", "PRECIO_TEXTO": "", "PRECIO_NUM": "", "STOCK_TEXTO": "",
            "STOCK_NUM": "", "STATUS": f"HTTP error detalle ({None if not r2 else r2.status_code})"
        }

    title, p_txt, p_num, s_txt, s_num = extract_all_from_product(r2.text)

    recent_429.append(bool(saw_429[0]))
    if len(recent_429) > ROLLING_WINDOW:
        recent_429.pop(0)

    return {
        "TIMESTAMP": ts,
        "SKU": sku,
        "URL_BUSQUEDA": url_search,
        "URL_PRODUCTO": url_prod,
        "TITULO": title,
        "PRECIO_TEXTO": p_txt,
        "PRECIO_NUM": p_num if p_num != "" else "",
        "STOCK_TEXTO": s_txt,
        "STOCK_NUM": s_num if s_num != "" else "",
        "STATUS": status
    }


def process_url(url):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sku = ""
    url_search = url
    url_prod = ""
    status = "OK"
    title = ""
    p_txt = ""
    p_num = ""
    s_txt = ""
    s_num = ""
    saw_429 = [False]

    initial_wait = planned_initial_wait()
    print(f"   ⏳ Espera inicial antes de buscar URL: {initial_wait:.1f}s (ratio 429 reciente: {current_429_ratio():.2f})")
    time.sleep(initial_wait)

    r = get_with_backoff(url_search, mark_429_flag=saw_429)
    if not r:
        return {
            "TIMESTAMP": ts, "SKU": sku, "URL_BUSQUEDA": url_search, "URL_PRODUCTO": "",
            "TITULO": "", "PRECIO_TEXTO": "", "PRECIO_NUM": "", "STOCK_TEXTO": "",
            "STOCK_NUM": "", "STATUS": "HTTP error URL"
        }

    if "searchparam=" in url_search:
        _slept = sleep_range(*BETWEEN_REQUESTS)
        first = parse_first_product_url_from_search(r.text, r.url)
        if first:
            url_prod = first
            r2 = get_with_backoff(url_prod, mark_429_flag=saw_429)
            if r2 and r2.status_code != 404:
                title, p_txt, p_num, s_txt, s_num = extract_all_from_product(r2.text)
            else:
                status = f"HTTP error detalle ({None if not r2 else r2.status_code})"
        else:
            status = "Sin resultados"
    else:
        url_prod = r.url
        title, p_txt, p_num, s_txt, s_num = extract_all_from_product(r.text)

    recent_429.append(bool(saw_429[0]))
    if len(recent_429) > ROLLING_WINDOW:
        recent_429.pop(0)

    return {
        "TIMESTAMP": ts,
        "SKU": sku,
        "URL_BUSQUEDA": url_search,
        "URL_PRODUCTO": url_prod,
        "TITULO": title,
        "PRECIO_TEXTO": p_txt,
        "PRECIO_NUM": p_num if p_num != "" else "",
        "STOCK_TEXTO": s_txt,
        "STOCK_NUM": s_num if s_num != "" else "",
        "STATUS": status
    }


def main(loop_index: int = 1):
    codes = load_codes_for_loop(loop_index)
    urls = [u.strip() for u in INPUT_URLS if u.strip()]
    items = [("code", c) for c in codes] + [("url", u) for u in urls]

    results = []
    total = len(items)
    print(f"👉 LOOP {loop_index} – Procesando {total} ítems…\n")
    print_header_once()

    start_time = time.time()
    limit_seconds = MAX_TOTAL_HOURS * 3600.0 if MAX_TOTAL_HOURS > 0 else None
    guard_seconds = TIME_GUARD_MINUTES * 60.0

    pending_items = []
    stopped_by_time = False

    for i, (kind, payload) in enumerate(items, 1):
        if limit_seconds is not None:
            elapsed = time.time() - start_time
            if elapsed >= max(0.0, limit_seconds - guard_seconds):
                horas_usadas = elapsed / 3600.0
                print(
                    f"⏹️ Se alcanzó el límite de tiempo de {MAX_TOTAL_HOURS:.2f} horas.\n"
                    f"   Se detiene en el ítem {i}/{total}. Lo que falta se guardará como pendientes."
                )
                pending_items = items[i-1:]
                stopped_by_time = True
                break

        try:
            if kind == "code":
                row = process_code(payload)
            else:
                row = process_url(payload)
            results.append(row)

            print(f"[{i}/{total}] {payload} -> {row['STATUS']}")
            print(row_to_tsv(row))
            sys.stdout.flush()

        except Exception as e:
            row = {
                "TIMESTAMP": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "SKU": payload if kind == "code" else "",
                "URL_BUSQUEDA": BASE_SEARCH + quote_plus(payload) if kind == "code" else payload,
                "URL_PRODUCTO": "",
                "TITULO": "", "PRECIO_TEXTO": "", "PRECIO_NUM": "",
                "STOCK_TEXTO": "", "STOCK_NUM": "", "STATUS": f"Error: {e}"
            }
            results.append(row)
            print(f"[{i}/{total}] {payload} -> Error: {e}")
            print(row_to_tsv(row))
            sys.stdout.flush()

    if not stopped_by_time:
        pending_items = []

    pending_codes = [p for (k, p) in pending_items if k == "code"]

    df = pd.DataFrame(results, columns=COLUMNS)
    csv_name = f"cyberpuerta_datos_loop{loop_index}.csv"
    xlsx_name = f"cyberpuerta_datos_loop{loop_index}.xlsx"

    df.to_csv(csv_name, index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(xlsx_name, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Datos")
        ws = writer.sheets["Datos"]
        for col in ["URL_BUSQUEDA", "URL_PRODUCTO"]:
            if col in df.columns:
                c = df.columns.get_loc(col)
                for r, val in enumerate(df[col].fillna(""), start=1):
                    if isinstance(val, str) and val.startswith("http"):
                        ws.write_url(r, c, val, string=val)

    print(f"\n✅ LOOP {loop_index}: '{csv_name}' y '{xlsx_name}' generados.")

    if pending_codes and loop_index < 3:
        pending_file = f"cyberpuerta_pending_codes_loop{loop_index}.txt"
        with open(pending_file, "w", encoding="utf-8") as f:
            for code in pending_codes:
                f.write(code + "\n")
        print(
            f"⚠️ Quedaron {len(pending_codes)} códigos pendientes en el loop {loop_index}.\n"
            f"   Se guardaron en '{pending_file}' para el siguiente loop."
        )
    elif pending_codes and loop_index >= 3:
        pending_file = f"cyberpuerta_pending_codes_loop{loop_index}.txt"
        with open(pending_file, "w", encoding="utf-8") as f:
            for code in pending_codes:
                f.write(code + "\n")
        print(
            f"⚠️ Loop 3 también llegó al límite de tiempo. Se guardaron {len(pending_codes)} pendientes "
            f"en '{pending_file}', pero no habrá un cuarto loop automático."
        )
    else:
        print(f"✅ LOOP {loop_index}: No quedaron códigos pendientes.")

    return df, csv_name, xlsx_name


def enviar_resultados_por_mail(
    sender: str,
    password: str,
    recipient: str,
    archivos_adjuntos=None
):
    if archivos_adjuntos is None:
        archivos_adjuntos = []

    msg = EmailMessage()
    msg["Subject"] = "Resultados scraper Cyberpuerta"
    msg["From"] = sender
    msg["To"] = recipient

    cuerpo = (
        "Hola Abraham,\n\n"
        "Te mando los archivos generados hoy por el scraper de Cyberpuerta.\n\n"
        "Saludos."
    )
    msg.set_content(cuerpo)

    for filename in archivos_adjuntos:
        try:
            with open(filename, "rb") as f:
                data = f.read()
            msg.add_attachment(
                data,
                maintype="application",
                subtype="octet-stream",
                filename=filename,
            )
            print(f"✅ Adjuntado: {filename}")
        except FileNotFoundError:
            print(f"⚠️ No encontré el archivo: {filename}, no se adjunta.")

    context = ssl.create_default_context()
    print("📨 Enviando correo...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(sender, password)
        server.send_message(msg)
    print("✅ Correo enviado correctamente.")


if __name__ == "__main__":
    print(f"🔁 Iniciando scraper – LOOP_INDEX = {LOOP_INDEX}")
    df, csv_name, xlsx_name = main(loop_index=LOOP_INDEX)

    EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
    EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
    EMAIL_TO = os.environ.get("EMAIL_TO")

    if EMAIL_SENDER and EMAIL_PASSWORD and EMAIL_TO:
        enviar_resultados_por_mail(
            sender=EMAIL_SENDER,
            password=EMAIL_PASSWORD,
            recipient=EMAIL_TO,
            archivos_adjuntos=[csv_name, xlsx_name],
        )
    else:
        print("ℹ️ Email no configurado (EMAIL_SENDER / EMAIL_PASSWORD / EMAIL_TO). No se envía correo.")
