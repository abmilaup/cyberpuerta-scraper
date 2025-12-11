import os
import re
import sys
import time
import random
from datetime import datetime
from urllib.parse import urljoin, quote_plus

import requests
import pandas as pd
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import smtplib
from email.message import EmailMessage

# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

BASE_URL = "https://www.cyberpuerta.mx/"
BASE_SEARCH = BASE_URL + "index.php?cl=search&searchparam="

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
}

# ¿Estamos corriendo dentro de GitHub Actions?
IS_GITHUB = os.environ.get("GITHUB_ACTIONS") == "true"

# Límite de tiempo TOTAL del script (sólo se usa en GitHub si está definido)
GLOBAL_MAX_RUNTIME_SECONDS = None
if IS_GITHUB:
    GLOBAL_MAX_RUNTIME_SECONDS = float(
        os.environ.get("CYBERPUERTA_MAX_RUNTIME", "21000")
    )

# Número máximo de pasadas (loops) sobre códigos pendientes
MAX_PASSES = int(os.environ.get("CYBERPUERTA_MAX_PASSES", "3"))

# Colchón en segundos antes del límite de tiempo para cortar cada pasada
PASS_GUARD_SECONDS = float(os.environ.get("CYBERPUERTA_PASS_GUARD", "600"))

# Parámetros de espera y backoff (ajustados para GitHub / local)
if IS_GITHUB:
    # Versión optimizada para GitHub (prudente pero más rápida)
    INITIAL_WAIT_RANGE = (30.0, 45.0)  # espera inicial antes de cada SKU
    BETWEEN_REQUESTS = (2.0, 4.0)      # espera entre requests
    MAX_RETRIES = 4
    BACKOFF_BASE = 3.0
    BACKOFF_CAP = 45.0
    ALPHA_SENSITIVITY = 0.5           # sensibilidad al ratio de 429
    ROLLING_WINDOW = 10               # cuántos últimos status mirar
else:
    # Versión algo más tranquila para local/colab
    INITIAL_WAIT_RANGE = (40.0, 70.0)
    BETWEEN_REQUESTS = (3.0, 6.0)
    MAX_RETRIES = 6
    BACKOFF_BASE = 3.0
    BACKOFF_CAP = 60.0
    ALPHA_SENSITIVITY = 0.8
    ROLLING_WINDOW = 8


# ============================================================
# ENTRADAS (CÓDIGOS / URLS)
# ============================================================

# Aquí pegas tus SKUs de Cyberpuerta / partes, uno por línea:
INPUT_CODES = """
KF560C36BBE2-16
"""

# Si además quieres pasar URLs directas de producto:
INPUT_URLS = [
    # "https://www.cyberpuerta.mx/Algo/Producto.html",
]


def load_codes():
    """
    Devuelve la lista de códigos a procesar.

    - Por defecto usa INPUT_CODES embebido.
    - Si existe la env CYBERPUERTA_CODES_FILE y el archivo existe,
      lee los códigos (uno por línea) desde ese archivo.
    """
    codes_literal = [ln.strip() for ln in INPUT_CODES.splitlines() if ln.strip()]
    codes_file = os.environ.get("CYBERPUERTA_CODES_FILE")

    if codes_file and os.path.isfile(codes_file):
        try:
            with open(codes_file, encoding="utf-8") as f:
                file_codes = [ln.strip() for ln in f if ln.strip()]
            if file_codes:
                print(f"📥 Leyendo {len(file_codes)} códigos desde archivo '{codes_file}'.")
                return file_codes
            else:
                print(f"⚠️ El archivo '{codes_file}' está vacío; uso INPUT_CODES embebido.")
        except Exception as e:
            print(f"⚠️ No se pudo leer '{codes_file}': {e}. Uso INPUT_CODES embebido.")

    print(f"📥 Usando {len(codes_literal)} códigos embebidos en INPUT_CODES.")
    return codes_literal


# ============================================================
# COLUMNAS DE SALIDA
# ============================================================

COLUMNS = [
    "TIMESTAMP",
    "SKU",
    "URL_BUSQUEDA",
    "URL_PRODUCTO",
    "TITULO",
    "PRECIO_TEXTO",
    "PRECIO_NUM",
    "STOCK_TEXTO",
    "STOCK_NUM",
    "STATUS",
]


def row_to_tsv(row: dict) -> str:
    """Convierte un dict row a una línea TSV para imprimir en consola."""
    return "\t".join(str(row.get(col, "") or "") for col in COLUMNS)


# ============================================================
# SESIÓN HTTP + ESPERAS ADAPTATIVAS
# ============================================================

def build_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=MAX_RETRIES,
        backoff_factor=0.0,  # el backoff lo manejamos nosotros
        status_forcelist=[429, 403, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


session = build_session()
recent_status_codes = []  # para calcular ratio de 429


def compute_adaptive_initial_wait() -> float:
    """Calcula una espera inicial adaptativa según el ratio reciente de 429."""
    base = random.uniform(*INITIAL_WAIT_RANGE)
    if not recent_status_codes:
        return base

    last = recent_status_codes[-ROLLING_WINDOW:]
    ratio_429 = 0.0
    if last:
        ratio_429 = sum(1 for c in last if c == 429) / len(last)

    factor = 1.0 + ALPHA_SENSITIVITY * ratio_429
    wait = base * factor
    return wait


def fetch_url(url: str) -> str:
    """
    Hace GET a una URL con reintentos y backoff manual para 429/403/errores.
    Devuelve el texto HTML.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(url, headers=HEADERS, timeout=30)
            status = resp.status_code

            # Guardar status en lista para ratio de 429
            recent_status_codes.append(status)
            if len(recent_status_codes) > ROLLING_WINDOW:
                del recent_status_codes[0]

            if status in (429, 403):
                wait = min(BACKOFF_BASE * (2 ** (attempt - 1)), BACKOFF_CAP)
                print(
                    f"⚠️ {status} en intento {attempt} para {url}. "
                    f"Esperando {wait:.1f} s antes de reintentar..."
                )
                time.sleep(wait)
                continue

            resp.raise_for_status()
            # Pausa pequeña entre requests para no pegar demasiado rápido
            time.sleep(random.uniform(*BETWEEN_REQUESTS))
            return resp.text

        except requests.RequestException as e:
            if attempt == MAX_RETRIES:
                print(f"❌ Error definitivo al pedir {url}: {e}")
                raise
            wait = min(BACKOFF_BASE * (2 ** (attempt - 1)), BACKOFF_CAP)
            print(
                f"⚠️ Error {e} en intento {attempt} para {url}. "
                f"Esperando {wait:.1f} s antes de reintentar..."
            )
            time.sleep(wait)

    raise RuntimeError(f"No se pudo obtener {url} después de {MAX_RETRIES} intentos.")


# ============================================================
# PARSEO HTML: PRECIO / STOCK / PRODUCTOS
# ============================================================

def parse_price(text: str):
    """
    Convierte un texto tipo '$ 1,234.56' o '1.234,56' a float.
    Devuelve None si no se puede.
    """
    if not text:
        return None

    cleaned = re.sub(r"[^\d,\.]", "", text)

    if "," in cleaned and "." in cleaned:
        # Heurística: si la coma está al final, es decimal estilo '1.234,56'
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    else:
        cleaned = cleaned.replace(",", "")

    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_stock(text: str):
    """
    Extrae un número aproximado de stock a partir de un texto.
    - Si contiene 'agotado' o 'no disponible' => 0
    - Si contiene un número => ese número
    - Si no, devuelve None
    """
    if not text:
        return None

    lower = text.lower()
    if "agotado" in lower or "no disponible" in lower:
        return 0

    m = re.search(r"(\d+)", text)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass

    return None


def scrape_product_page(url: str, sku: str = "") -> dict:
    """
    Parsea la página de producto de Cyberpuerta para extraer:
    - título
    - precio
    - stock (aproximado)
    """
    html = fetch_url(url)
    soup = BeautifulSoup(html, "lxml")

    # Título
    title_el = soup.find("h1")
    title = title_el.get_text(strip=True) if title_el else ""

    # Precio (intentamos varios selectores típicos)
    price_el = (
        soup.select_one('[itemprop="price"]')
        or soup.select_one(".price")
        or soup.select_one(".offer-price")
    )
    price_text = price_el.get_text(" ", strip=True) if price_el else ""
    price_num = parse_price(price_text) if price_text else None

    # Stock (texto donde aparezca 'disponible' o 'agotado')
    stock_text = ""
    stock_num = None

    stock_candidates = soup.find_all(
        string=re.compile(r"(disponible|agotado|no disponible)", re.I)
    )
    if stock_candidates:
        # Tomamos el primero razonable
        st = stock_candidates[0]
        if hasattr(st, "parent"):
            stock_text = st.parent.get_text(" ", strip=True)
        else:
            stock_text = str(st)
        stock_num = parse_stock(stock_text)

    status = "OK"
    if not price_num and not price_text:
        status = "Sin precio detectable"
    if not title:
        status = "OK (sin título)" if status == "OK" else status + " + sin título"

    return {
        "TITULO": title,
        "PRECIO_TEXTO": price_text,
        "PRECIO_NUM": price_num,
        "STOCK_TEXTO": stock_text,
        "STOCK_NUM": stock_num,
        "STATUS": status,
    }


def search_code_in_cyberpuerta(code: str):
    """
    Busca el código en Cyberpuerta y devuelve:
    (url_busqueda, url_producto, status_text)
    """
    search_url = BASE_SEARCH + quote_plus(code)
    html = fetch_url(search_url)
    soup = BeautifulSoup(html, "lxml")

    # Intentamos agarrar el primer enlace de producto razonable
    link = (
        soup.select_one("a.product-link")
        or soup.select_one("a[href*='/articulo/']")
        or soup.select_one("a[href*='Producto']")
    )

    if not link:
        return search_url, "", "Sin resultados en búsqueda"

    href = link.get("href", "")
    product_url = urljoin(BASE_URL, href)

    return search_url, product_url, "Encontrado en búsqueda"


# ============================================================
# PROCESAMIENTO DE CÓDIGOS / URLS
# ============================================================

def process_code(code: str) -> dict:
    """
    Procesa un código (SKU): hace espera inicial, lo busca y luego scrapea.
    """
    wait_s = compute_adaptive_initial_wait()
    print(f"⏳ Esperando {wait_s:.1f} s antes de buscar código '{code}'...")
    time.sleep(wait_s)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        search_url, product_url, status = search_code_in_cyberpuerta(code)
        if not product_url:
            # No hay producto, devolvemos fila básica
            return {
                "TIMESTAMP": ts,
                "SKU": code,
                "URL_BUSQUEDA": search_url,
                "URL_PRODUCTO": "",
                "TITULO": "",
                "PRECIO_TEXTO": "",
                "PRECIO_NUM": None,
                "STOCK_TEXTO": "",
                "STOCK_NUM": None,
                "STATUS": status,
            }

        data = scrape_product_page(product_url, sku=code)
        row = {
            "TIMESTAMP": ts,
            "SKU": code,
            "URL_BUSQUEDA": search_url,
            "URL_PRODUCTO": product_url,
        }
        row.update(data)
        return row

    except Exception as e:
        return {
            "TIMESTAMP": ts,
            "SKU": code,
            "URL_BUSQUEDA": BASE_SEARCH + quote_plus(code),
            "URL_PRODUCTO": "",
            "TITULO": "",
            "PRECIO_TEXTO": "",
            "PRECIO_NUM": None,
            "STOCK_TEXTO": "",
            "STOCK_NUM": None,
            "STATUS": f"Error: {e}",
        }


def process_url(url: str) -> dict:
    """
    Procesa una URL directa de producto.
    """
    wait_s = compute_adaptive_initial_wait()
    print(f"⏳ Esperando {wait_s:.1f} s antes de pedir URL directa '{url}'...")
    time.sleep(wait_s)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        data = scrape_product_page(url, sku="")
        row = {
            "TIMESTAMP": ts,
            "SKU": "",
            "URL_BUSQUEDA": "",
            "URL_PRODUCTO": url,
        }
        row.update(data)
        return row

    except Exception as e:
        return {
            "TIMESTAMP": ts,
            "SKU": "",
            "URL_BUSQUEDA": "",
            "URL_PRODUCTO": url,
            "TITULO": "",
            "PRECIO_TEXTO": "",
            "PRECIO_NUM": None,
            "STOCK_TEXTO": "",
            "STOCK_NUM": None,
            "STATUS": f"Error: {e}",
        }


# ============================================================
# EXPORTAR EXCEL/CSV
# ============================================================

def write_outputs(rows, label):
    """
    Escribe CSV y XLSX con el sufijo 'label'.
    Devuelve lista con los nombres de archivo generados (o [] si no hay filas).
    """
    if not rows:
        print(f"ℹ️ No hay filas para escribir en paso '{label}'.")
        return []

    df = pd.DataFrame(rows, columns=COLUMNS)

    csv_name = f"cyberpuerta_datos_paso{label}.csv"
    xlsx_name = f"cyberpuerta_datos_paso{label}.xlsx"

    df.to_csv(csv_name, index=False, encoding="utf-8-sig")

    with pd.ExcelWriter(xlsx_name, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Datos")
        ws = writer.sheets["Datos"]
        # Hacer que las URLs sean clicables
        for col in ["URL_BUSQUEDA", "URL_PRODUCTO"]:
            if col in df.columns:
                c = df.columns.get_loc(col)
                for r, val in enumerate(df[col].fillna(""), start=1):
                    if isinstance(val, str) and val.startswith("http"):
                        ws.write_url(r, c, val, string=val)

    print(f"✅ Archivos generados para paso '{label}': {csv_name}, {xlsx_name}")
    return [csv_name, xlsx_name]


# ============================================================
# EMAIL (OPCIONAL)
# ============================================================

def send_email_if_configured(attachments):
    """
    Envía un email con los archivos adjuntos si están configuradas
    EMAIL_SENDER, EMAIL_PASSWORD y EMAIL_TO en variables de entorno.
    """
    sender = os.environ.get("EMAIL_SENDER")
    password = os.environ.get("EMAIL_PASSWORD")
    to_addr = os.environ.get("EMAIL_TO")

    if not (sender and password and to_addr):
        print("ℹ️ Email no configurado (EMAIL_SENDER / EMAIL_PASSWORD / EMAIL_TO). No envío correo.")
        return

    # Filtrar sólo archivos que realmente existan
    attachments = [a for a in attachments if os.path.isfile(a)]
    if not attachments:
        print("ℹ️ No hay archivos existentes para adjuntar. No envío correo.")
        return

    msg = EmailMessage()
    msg["Subject"] = "Resultados scraper Cyberpuerta"
    msg["From"] = sender
    msg["To"] = to_addr
    msg.set_content(
        "Te envío los archivos generados por el scraper de Cyberpuerta.\n\n"
        "Archivos adjuntos:\n" + "\n".join(attachments)
    )

    for fname in attachments:
        try:
            with open(fname, "rb") as f:
                data = f.read()
            msg.add_attachment(
                data,
                maintype="application",
                subtype="octet-stream",
                filename=os.path.basename(fname),
            )
        except Exception as e:
            print(f"⚠️ No se pudo adjuntar {fname}: {e}")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)
        print("📧 Email enviado con éxito.")
    except Exception as e:
        print(f"⚠️ Error al enviar email: {e}")


# ============================================================
# MAIN CON LOOP DE HASTA 3 PASADAS
# ============================================================

def main():
    global_start = time.time()

    codes_initial = load_codes()
    urls_initial = [u.strip() for u in INPUT_URLS if u.strip()]

    pending_codes = codes_initial[:]  # copia
    urls = urls_initial

    all_results = []          # todas las filas de todas las pasadas
    all_files_for_email = []  # todos los archivos generados

    for pass_idx in range(1, MAX_PASSES + 1):
        if not pending_codes and (pass_idx == 1 or not urls):
            print("✅ No hay códigos pendientes y no hay URLs que procesar. Termino.")
            break

        print("\n" + "=" * 60)
        print(f"🌀 INICIANDO PASO {pass_idx} (de máximo {MAX_PASSES})")
        print("=" * 60 + "\n")

        items = [("code", c) for c in pending_codes]
        # Sólo en la primera pasada procesamos también URLs directas
        if pass_idx == 1 and urls:
            items += [("url", u) for u in urls]

        results_pass = []
        total = len(items)
        print(f"Procesando {total} ítems en el paso {pass_idx}...\n")
        print("\t".join(COLUMNS))
        sys.stdout.flush()

        stopped_by_time = False
        stop_index = total  # índice donde se detiene (1-based)

        for i, (kind, payload) in enumerate(items, 1):
            # --------- Checar límite de tiempo global (si aplica) ----------
            if GLOBAL_MAX_RUNTIME_SECONDS is not None:
                elapsed = time.time() - global_start
                remaining = GLOBAL_MAX_RUNTIME_SECONDS - elapsed
                if remaining <= PASS_GUARD_SECONDS:
                    print(
                        f"⏹️ Paso {pass_idx}: cerca del límite de tiempo global "
                        f"({elapsed/3600:.2f} h usadas, {remaining/60:.1f} min libres). "
                        f"Deteniendo en ítem {i}/{total}."
                    )
                    stopped_by_time = True
                    stop_index = i
                    break
            # --------------------------------------------------------------

            if kind == "code":
                row = process_code(payload)
            else:
                row = process_url(payload)

            results_pass.append(row)
            all_results.append(row)

            print(f"[{i}/{total}] {payload} -> {row['STATUS']}")
            print(row_to_tsv(row))
            sys.stdout.flush()

        # --------- Determinar códigos pendientes tras este paso ----------
        if stopped_by_time:
            # Los ítems desde stop_index en adelante no fueron procesados
            remaining_items = items[stop_index - 1:]
            pending_codes = [
                p for (k, p) in remaining_items if k == "code"
            ]
        else:
            pending_codes = []

        # --------- Guardar resultados de este paso ----------
        files_pass = write_outputs(results_pass, label=pass_idx)
        all_files_for_email.extend(files_pass)

        # --------- Guardar pendientes de este paso (si hay) ----------
        if pending_codes:
            pending_file = f"cyberpuerta_pending_codes_paso{pass_idx}.txt"
            with open(pending_file, "w", encoding="utf-8") as f:
                for code in pending_codes:
                    f.write(code + "\n")
            print(
                f"⚠️ Quedaron {len(pending_codes)} códigos pendientes en el paso {pass_idx}, "
                f"guardados en '{pending_file}'."
            )
            all_files_for_email.append(pending_file)
        else:
            print(f"✅ En el paso {pass_idx} no quedaron códigos pendientes.")

        # Si no se detuvo por tiempo, ya terminamos todo lo que había que hacer
        if not stopped_by_time:
            print("✅ No se detuvo por tiempo; no es necesario otro paso.")
            break

    # =====================================================
    # Archivo FULL con todo lo que se alcanzó a procesar
    # =====================================================
    full_files = write_outputs(all_results, label="full")
    all_files_for_email.extend(full_files)

    # Quitar duplicados en la lista de archivos
    all_files_for_email = list(dict.fromkeys(all_files_for_email))

    # Enviar email si está configurado
    send_email_if_configured(all_files_for_email)

    print("\n🎉 Script terminado.")


if __name__ == "__main__":
    main()
