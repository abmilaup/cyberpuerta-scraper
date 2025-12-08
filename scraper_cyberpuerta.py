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
KF560C36BBE2-16

""".strip()

INPUT_URLS = [
    # Si quieres, puedes poner URLs directas aquí
    # "https://www.cyberpuerta.mx/index.php?cl=search&searchparam=AUSDH16GUICL10-RA1",
]

BASE_SEARCH = "https://www.cyberpuerta.mx/index.php?cl=search&searchparam="

# --- Control de tiempos ---
INITIAL_WAIT_RANGE = (50.0, 80.0)   # espera mínima obligatoria ANTES de la búsqueda (primer intento) por SKU
BETWEEN_REQUESTS    = (4.0, 7.0)    # espera entre búsqueda y detalle
MAX_RETRIES         = 7             # reintentos por petición (para 429/403/5xx)
BACKOFF_BASE        = 4.0           # base para backoff exponencial en 429/403
BACKOFF_CAP         = 90.0          # tope de cada backoff

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
