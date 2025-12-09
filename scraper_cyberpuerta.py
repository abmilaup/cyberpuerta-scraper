import re, time, random, sys, statistics
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
import os

# ================= PARÁMETROS (ajústalos si quieres) =================
INPUT_CODES = """

AUSDX128GUICL10A1-RA1
ASU630SS-480GQ-R
AHD710P-1TU31-CBK
AHD710P-2TU31-CBK
AUSDX64GUICL10-RA1
ASU630SS-240GQ-R
AC008-32G-RWE
AHV620S-1TU31-CBK
AUSDH32GUICL10-RA1
AHD710P-4TU31-CBK
AC906-32G-RWH
AC008-32G-RKD
AUSDX512GUI3V30SA2-RA1
PBC20-WH
AC008-16G-RWE
AC008-16G-RKD
AC906-32G-RWB
AHD710P-5TU31-CBK
AC906-32G-RPP
AP20000QCD-DGT-CBK
AUSDH16GUICL10-RA1
AHV620S-2TU31-CBK
 UC310-128G-RBK
AUV250-32G-RBK
AC906-32G-RBK
AC906-64G-RWB
AD4S320016G22-SGN
ASU630SS-1T92Q-R
AUSDX256GUICL10A1-RA1
AUV220-32G-RBKBL
ASU650SS-1TT-R
AUSDX64GUICL10A1-RA1
AD4S320032G22-SGN
AUV220-32G-RWHGY
SLEG-900-2TCS
AHM800-6TU32G1-CUSBK
 SC740-1000G-CBU
AP20000QCD-DGT-CRD
AUV250-64G-RBK
AUV220-64G-RBKBL
AD4S32008G22-SGN
SD810-4000G-CBK
AHD710P-2TU31-CBL
AUV220-32G-RGNPK
AD4U266616G19-SGN
AUSDX256GUI3V30SA2-RA1
AHV620S-1TU31-CBL
AHD330-2TU31-CBK
AC008-64G-RWE
AC008-64G-RKD
AUV210-32G-RGD
AHD710P-2TU31-CRD
AELI-SE880-1TCGY
AD5S560016G-S
APSFG-2T-CSUS
AD4S266616G19-SGN
100-100000591WOF
100-100000263BOX
100-100000927BOX
100-100000457BOX
100-1000000253BOX
XG27WCMS
PA278CV
ASUS ROG STRIX LC III 360 ARGB
PA328CGV
VG32VQ1B
XG27AQDMG
TUF-GAMING-1000G
ASUS PRIME AP-850
MIC-KF8-00001
PROART LC 360
ROG-STRIX-1000P-GAMING
AORUS 15 9MF-E2LA583
G293-Z42-AAP1
SDCZ50-032G-B35
SDSSDE61-2T00-G25M
SDSSDE61-4T00-G25M
SDSSDE81-2T00-G25
SDSSDE61-4T00-G25B
HDTB510XK3AA
HDTB540XK3CA
HDTB520XK3AA
HDTX140XSCCA
HDTX120XSCAA
HDTCA20XW3AA
HDTCA20XK3AA
HDWG780XZSTA
HDTCA40XR3CA
HDTCA20XR3AA
HDTX140XK3CA
HDTCA10XW3AA
HDWG51CXZSTA
HDTCA40XW3CA
HDWG51GXZSTB
HDWG71AXZSTA
HDTX120XK3AA
AGAMMIXS70B-1T-CS
AX4U320016G16A-SBKD35G
AX4U320016G16A-ST50
AX5U6000C3032G-SLABRBK

SNV3S/1000G
SDC4/32GB
SXS1000/1000G
SA400S37/960G
SA400S37/480G
DTX/64GB
SDCS3/128GB
SXS1000/2000G
DTXS/64GB
DTX/128GB
SEDC600M/7680G
SXS1000R/2000G
SDCS3/64GB
SDCS2/128GB
SDCS3/256GB
SXS1000R/1000G
SKC600/512G
DTXM/64GB
SEDC600M/960G
SEDC600M/1920G
SNV3S/2000G
SNV3S/500G
SKC600/1024G
SXS2000/2000G
SA400S37/240G
KC-U2L64-7LB
SKC3000S/1024G
KF432C16BB/16
SEDC600M/480G
KF556S40IB-32
SNV3SM3/1T0
SFYRDK/2000G
SKC3000D/2048G
KF432C16BB/32
SEDC600M/3840G
SDCG4/512GB
DT70/64GB
SNV3S/4000G
SDCG4/256GB
SKC600/256G
SFYR2S/1T0
SXS2000/4000G
KF432S20IB/32
KC-U2L64-7LP
SKC3000S/512G
SDCS3/64GBSP
SDCS2/128GBSP
KF432S20IB/16
KF552C40BBK2-32
KF432C16BB1/16
SFYR2S/2T0
DTX/256GB
KF556S40IBK2-64
KF432C16BB/8
KC-U2G64-5R
SFYR2S/4T0
SNV3SM3/2T0
KF556S40IBK2-32
DTSE9G3/512GB
KVR32S22S8/8
DTXS/128GB
DTXM/128GB
DTMAXA/1TB
KF432S20IBK2/32
KC-S44480-7S
KF548S38IB-16
KF556C40BB-32
KF556S40IB-16
SDCG4/128GB
SKC600/2048G
DTXM/256GB
SFYRSK/1000G
DTMAX/1TB
SXS2000/1000G
KF432C16BBK2/64
SDG4/64GB
SDCG4/1TB
KF548S38IB-32
KF552C40BBAK2-32
SNV3SM3/500G
SDCS2/64GBSP
KC-U2L64-7LG
KF548S38IBK2-32
SDCS2/256GB
SDR2V6/128GB
SDR2V6/256GB
KF432C16BBK2/32
KF552C40BB-16
DTKN/64GB
DTXM/64GB-2P
SDCS3/1TB
KF432C16BB2A/16
KF556C40BBA-32
KF432C16BB1K2/32
SDG4/256GB
SDCG4/256GBSP
KF432C16BB2A/32
KF432S20IBK2/64
KF548S38IB-8
KF432C16BB2AK2/32
SDS3/128GB
KC-U2G64-7GR
DTKN/128GB
SDR2/64GB
KC-U2L128-7LB
KC-U2G64-7GB
SDCS2/64GB
SXS2000/500G
SEDC600ME/960G
SDR2/128GB
SDCE/128GB
SDCG4/128GBSP
SDCS3/512GB
SEDC600ME/3840G
KF560C36BBE2K2-32
KVR32S22D8/16
KF560C36BBE2-16
KVR16LN11/8WP

""".strip()

INPUT_URLS = [
    # Si quieres, puedes poner URLs directas aquí
    # "https://www.cyberpuerta.mx/index.php?cl=search&searchparam=AUSDH16GUICL10-RA1",
]

BASE_SEARCH = "https://www.cyberpuerta.mx/index.php?cl=search&searchparam="

# Detectar si estamos corriendo dentro de GitHub Actions
IS_GITHUB = os.environ.get("GITHUB_ACTIONS") == "true"

if IS_GITHUB:
    # Versión “rápida” para GitHub (≈ 5h30 si antes eran 8h)
    INITIAL_WAIT_RANGE = (34.0, 55.0)   # antes 50–80
    BETWEEN_REQUESTS    = (3.0, 5.0)    # antes 4–7
    MAX_RETRIES         = 7            # mismo número de reintentos
    BACKOFF_BASE        = 3.0          # antes 4
    BACKOFF_CAP         = 62.0         # antes 90
else:
    # Versión original (lenta) para Colab / local
    INITIAL_WAIT_RANGE = (50.0, 80.0)
    BETWEEN_REQUESTS    = (4.0, 7.0)
    MAX_RETRIES         = 7
    BACKOFF_BASE        = 4.0
    BACKOFF_CAP         = 90.0


# Adaptador de espera según “salud” reciente (cuántos 429 hemos visto)
ROLLING_WINDOW      = 6             # últimos N SKUs para medir ratio de 429
ALPHA_SENSITIVITY   = 1.2           # cuánto aumentar/bajar la espera inicial por ratio de 429 (0..1)
#   - Si ratio_429 = 0.0 -> multiplicador ≈ 1.0
#   - Si ratio_429 = 1.0 -> multiplicador ≈ 1.0 + ALPHA_SENSITIVITY

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "Chrome/126.0.0.0 Safari/537.36"
)

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
    return t  # devolvemos lo que realmente durmió para log

def to_number(txt):
    if not txt:
        return None
    t = (
        txt.replace("$","")
          .replace("MXN","")
          .replace("mxn","")
          .replace("\xa0"," ")
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
    # fallback muy genérico
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if href.endswith(".html"):
            return urljoin(current_url, href)
    return None

def extract_all_from_product(html):
    soup = BeautifulSoup(html, "lxml")
    # Título
    title = ""
    h1 = soup.select_one("h1.detailsInfo_right_title") or soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    # Precio
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

    # Stock
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

# ====== Registro de 429 recientes para adaptar la espera inicial ======
recent_429 = []  # lista de bool (True si el SKU tuvo al menos un 429 en su ciclo)

def current_429_ratio():
    if not recent_429:
        return 0.0
    # proporción de SKUs recientes que sufrieron 429
    return sum(1 for x in recent_429 if x) / len(recent_429)

def planned_initial_wait():
    # base aleatoria mínima
    base = jitter(*INITIAL_WAIT_RANGE)  # siempre >= 50s
    ratio = current_429_ratio()         # 0..1
    multiplier = 1.0 + ALPHA_SENSITIVITY * ratio
    planned = base * multiplier
    return planned

def get_with_backoff(url, allow_redirects=True, timeout=30, mark_429_flag=None):
    """
    GET con manejo 429/403:
    - backoff exponencial desde BACKOFF_BASE, con tope BACKOFF_CAP, + jitter.
    - marca en mark_429_flag[0] = True si aparece algún 429.
    """
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

# ================ Helpers de salida en consola (TAB para Excel) ================
COLUMNS = ["TIMESTAMP","SKU","URL_BUSQUEDA","URL_PRODUCTO","TITULO","PRECIO_TEXTO","PRECIO_NUM","STOCK_TEXTO","STOCK_NUM","STATUS"]

def row_to_tsv(row: dict) -> str:
    def fmt(x):
        if x is None:
            return ""
        s = str(x)
        return s.replace("\t"," ").replace("\r"," ").replace("\n"," ").strip()
    return "\t".join(fmt(row.get(col,"")) for col in COLUMNS)

def print_header_once():
    print("\t".join(COLUMNS))
    sys.stdout.flush()

# ========================= Flujo por código / URL =========================
def process_code(code):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sku = code
    url_search = BASE_SEARCH + quote_plus(code) + f"&_ts={int(time.time()*1000)}"
    url_prod = ""
    status = "OK"
    title = ""; p_txt = ""; p_num = ""; s_txt = ""; s_num = ""

    saw_429 = [False]  # se pasa por referencia

    # 1) Espera inicial ADAPTATIVA (nunca < 50s)
    initial_wait = planned_initial_wait()
    print(f"   ⏳ Espera inicial antes de buscar '{sku}': {initial_wait:.1f}s (ratio 429 reciente: {current_429_ratio():.2f})")
    time.sleep(initial_wait)

    # 2) Búsqueda
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
    # 3) Detalle
    r2 = get_with_backoff(url_prod, mark_429_flag=saw_429)
    if not r2 or r2.status_code == 404:
        return {
            "TIMESTAMP": ts, "SKU": sku, "URL_BUSQUEDA": url_search, "URL_PRODUCTO": url_prod,
            "TITULO": "", "PRECIO_TEXTO": "", "PRECIO_NUM": "", "STOCK_TEXTO": "",
            "STOCK_NUM": "", "STATUS": f"HTTP error detalle ({None if not r2 else r2.status_code})"
        }

    title, p_txt, p_num, s_txt, s_num = extract_all_from_product(r2.text)

    # 4) Registrar si hubo 429 en este SKU (para adaptar el próximo)
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
    title = ""; p_txt = ""; p_num = ""; s_txt = ""; s_num = ""
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

# ======================= Envío de correo ============================
def enviar_resultados_por_mail(
    sender: str,
    password: str,
    recipient: str,
    archivos_adjuntos=None
):
    """
    Envía un correo con los archivos adjuntos generados por el scraper.
    recipient puede ser un string con varios correos separados por comas.
    """
    if archivos_adjuntos is None:
        archivos_adjuntos = []

    # 1) Crear mensaje
    msg = EmailMessage()
    msg["Subject"] = "Resultados scraper Cyberpuerta"
    msg["From"] = sender
    msg["To"] = recipient  # puede ser "a@b.com, c@d.com"

    cuerpo = (
        "Hola Abraham,\n\n"
        "Te mando los archivos generados hoy por el scraper de Cyberpuerta.\n\n"
        "Saludos."
    )
    msg.set_content(cuerpo)

    # 2) Adjuntar archivos
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

    # 3) Enviar usando Gmail (SMTP_SSL, puerto 465)
    context = ssl.create_default_context()
    print("📨 Enviando correo...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(sender, password)
        server.send_message(msg)
    print("✅ Correo enviado correctamente.")

# =============================== Main ===============================
def main():
    codes = [ln.strip() for ln in INPUT_CODES.splitlines() if ln.strip()]
    urls  = [u.strip() for u in INPUT_URLS if u.strip()]
    items = [("code", c) for c in codes] + [("url", u) for u in urls]

    results = []
    total = len(items)
    print(f"Procesando {total} ítems…\n")
    print("\t".join(COLUMNS))
    sys.stdout.flush()

    for i, (kind, payload) in enumerate(items, 1):
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

    # Exporta CSV/XLSX
    df = pd.DataFrame(results, columns=COLUMNS)
    df.to_csv("cyberpuerta_datos.csv", index=False, encoding="utf-8-sig")

    with pd.ExcelWriter("cyberpuerta_datos.xlsx", engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Datos")
        ws = writer.sheets["Datos"]
        for col in ["URL_BUSQUEDA", "URL_PRODUCTO"]:
            if col in df.columns:
                c = df.columns.get_loc(col)
                for r, val in enumerate(df[col].fillna(""), start=1):
                    if isinstance(val, str) and val.startswith("http"):
                        ws.write_url(r, c, val, string=val)

    print("\n✅ Listo: 'cyberpuerta_datos.csv' y 'cyberpuerta_datos.xlsx' generados.")
    return df

# ========================== Punto de entrada ========================
if __name__ == "__main__":
    # 1) Ejecutar scraper
    df = main()

    # 2) Leer credenciales y destinatarios de variables de entorno
    sender = os.environ.get("EMAIL_SENDER")
    password = os.environ.get("EMAIL_PASSWORD")
    recipient = os.environ.get("EMAIL_TO")  # puede contener varios correos separados por comas

    if sender and password and recipient:
        enviar_resultados_por_mail(
            sender=sender,
            password=password,
            recipient=recipient,
            archivos_adjuntos=["cyberpuerta_datos.csv", "cyberpuerta_datos.xlsx"],
        )
    else:
        print("⚠️ No se configuraron variables de entorno de correo. No se envía email.")
