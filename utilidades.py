from bs4 import BeautifulSoup
import html
import ipaddress
import re
from urllib.parse import urlparse
from constantes import *

_URL_RE = re.compile(URLREGEX, re.IGNORECASE)
_HREF_RE = re.compile(HREFREGEX, re.IGNORECASE)
_IP_RE = re.compile(IPREGEX, re.IGNORECASE)
_URL_TEXT_RE = re.compile(URLREGEX_NOT_ALONE, re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s")
_URL_TRAILING_RE = re.compile(r"[)\].,;:'\"<>]+$")
_SCRIPT_SCHEME_RE = re.compile(r"^\s*javascript:", re.IGNORECASE)
_HTML_HINT_RE = re.compile(
    r"<\s*(html|body|a|form|script|img|iframe|table|div|span|input|button)\b",
    re.IGNORECASE,
)

_FALLBACK_CACHE = {}
_TEXT_MIME_PREFIXES = ("text/",)
_TEXT_MIME_TYPES = {"application/xhtml+xml", "application/xml", "message/rfc822"}


def _get_cache(mensaje):
    try:
        cache = mensaje.__dict__.get("_phishing_cache")
        if cache is None:
            cache = {}
            mensaje.__dict__["_phishing_cache"] = cache
        return cache
    except Exception:
        key = id(mensaje)
        cache = _FALLBACK_CACHE.get(key)
        if cache is None:
            cache = {}
            _FALLBACK_CACHE[key] = cache
        return cache


def _to_text(datos):
    if isinstance(datos, bytes):
        return datos.decode("utf-8", errors="ignore")
    return str(datos)


def _append_unique(resultado, vistos, valor):
    if valor and valor not in vistos:
        vistos.add(valor)
        resultado.append(valor)


def _normalizar_url(url):
    if url is None:
        return None
    limpia = html.unescape(str(url)).strip()
    if not limpia:
        return None
    if limpia.startswith("//"):
        return "http:" + limpia
    return _URL_TRAILING_RE.sub("", limpia)


def _es_mime_texto(mime_type):
    mime = str(mime_type or "").lower()
    return mime.startswith(_TEXT_MIME_PREFIXES) or mime in _TEXT_MIME_TYPES


#traer el contenido del correo
def getDatos(mensaje):
    cache = _get_cache(mensaje)
    resultado = cache.get("datos_texto")
    if resultado is None:
        partes = []
        for dato in getDatos_Dict(mensaje):
            partes.append(dato["mimeType"] + "\t" + str(dato["datos"]) + "\n")
        resultado = "".join(partes)
        cache["datos_texto"] = resultado
    return resultado


def __getDatos_Resultado__(mensaje, retorno):
    # Conserva compatibilidad con el nombre anterior.
    return getDatos(mensaje)


def _collect_datos_dict(mensaje, retorno):
    if mensaje.is_multipart():
        for subMensaje in (mensaje.get_payload() or []):
            _collect_datos_dict(subMensaje, retorno)
        return retorno

    datos = mensaje.get_payload()
    if str(mensaje.get("Content-Transfer-Encoding")).lower() == "base64":
        datos = mensaje.get_payload(decode=True)

    retorno.append({"mimeType": mensaje.get_content_type(), "datos": datos})
    return retorno


def getDatos_Dict(mensaje):
    cache = _get_cache(mensaje)
    resultado = cache.get("datos_dict")
    if resultado is None:
        resultado = _collect_datos_dict(mensaje, [])
        cache["datos_dict"] = resultado
    return resultado


def __getDatos_Dict_Rec__(mensaje, retorno):
    # Conserva compatibilidad con el nombre anterior.
    retorno.extend(getDatos_Dict(mensaje))
    return retorno


def _get_soups(mensaje, solo_html=True):
    cache = _get_cache(mensaje)
    cache_key = "html_soups" if solo_html else "all_soups"
    soups = cache.get(cache_key)
    if soups is None:
        soups = []
        for dato in getDatos_Dict(mensaje):
            mime_type = str(dato["mimeType"]).lower()
            if solo_html and mime_type != "text/html":
                continue
            if not solo_html and not _es_mime_texto(mime_type):
                continue
            soups.append(BeautifulSoup(_to_text(dato["datos"]), "lxml"))
        cache[cache_key] = soups
    return soups

def getJavascript(mensaje):
    cache = _get_cache(mensaje)
    resultado = cache.get("javascript_tags")
    if resultado is not None:
        return resultado

    resultado = []
    for soup in _get_soups(mensaje, solo_html=True):
        resultado.extend(soup.find_all("script"))

        for tag in soup.find_all(True):
            attrs = tag.attrs or {}

            tiene_evento = any(str(attr).lower().startswith("on") for attr in attrs.keys())
            if tiene_evento:
                resultado.append(tag)
                continue

            tiene_js_scheme = False
            for attr in ("href", "src", "action", "formaction"):
                valor = attrs.get(attr)
                if valor is None:
                    continue
                valores = valor if isinstance(valor, list) else [valor]
                if any(
                    _SCRIPT_SCHEME_RE.search(str(item) or "")
                    for item in valores
                    if item is not None
                ):
                    tiene_js_scheme = True
                    break
            if tiene_js_scheme:
                resultado.append(tag)
    cache["javascript_tags"] = resultado
    return resultado


def getHyperlinks(mensaje):
    cache = _get_cache(mensaje)
    resultado = cache.get("hyperlinks")
    if resultado is None:
        resultado = []
        vistos = set()
        for soup in _get_soups(mensaje, solo_html=True):
            for link in soup.find_all("a", href=True):
                href = _normalizar_url(link.get("href"))
                if href:
                    _append_unique(resultado, vistos, href)
        cache["hyperlinks"] = resultado
    return resultado

def  getIPHref(mensaje):
    cache = _get_cache(mensaje)
    resultado = cache.get("ip_href")
    if resultado is not None:
        return resultado

    urls = getUrl_Datos(mensaje)
    resultado = []
    vistos = set()
    if urls is not None:
        for url in urls:
            host = urlparse(url).hostname
            if host:
                try:
                    ip_obj = ipaddress.ip_address(host)
                    _append_unique(resultado, vistos, str(ip_obj))
                    continue
                except ValueError:
                    pass
            encontrado = _IP_RE.search(url)
            if encontrado and encontrado.group(1) is not None:
                _append_unique(resultado, vistos, encontrado.group(1))
    cache["ip_href"] = resultado
    return resultado

def getUrl_Datos(mensaje):
    cache = _get_cache(mensaje)
    urls = cache.get("urls")
    if urls is None:
        urls = []
        vistos = set()

        for href in getHyperlinks(mensaje):
            parsed = urlparse(href)
            if parsed.scheme.lower() in ("http", "https", "ftp", "mailto"):
                _append_unique(urls, vistos, href)

        for dato in getDatos_Dict(mensaje):
            if not _es_mime_texto(dato.get("mimeType")):
                continue
            texto = _to_text(dato["datos"])
            for match in _URL_TEXT_RE.finditer(texto):
                url = _normalizar_url(match.group(0))
                _append_unique(urls, vistos, url)

        cache["urls"] = urls
    return urls

def getString_Url(string):
    resultado = []
    vistos = set()
    datosLimpios = _WHITESPACE_RE.sub(" ", string or "")

    for match in _URL_TEXT_RE.finditer(datosLimpios):
        url = _normalizar_url(match.group(0))
        _append_unique(resultado, vistos, url)

    links = _HREF_RE.findall(datosLimpios)
    for link in links:
        href = link[0] if isinstance(link, tuple) else link
        href = _normalizar_url(href)
        if href and esUrl(href):
            _append_unique(resultado, vistos, href)
    return resultado

def esUrl(link):
    return _URL_RE.search(link) is not None

def getMultipart_Email(mensaje): 
    return mensaje.is_multipart()

def getContadorArchivoAdjunto(mensaje):
    return __getContadorArchivoAdjunto__(mensaje, contador=0)

def __getContadorArchivoAdjunto__(mensaje, contador):
    pendientes = [mensaje]
    total = contador
    while pendientes:
        actual = pendientes.pop()
        if actual.is_multipart():
            pendientes.extend(actual.get_payload() or [])
            continue
        if __archivoAdjunto__(actual):
            total += 1
    return total


def __archivoAdjunto__(mensaje):
    contenido = mensaje.get("Content-Disposition", failobj=None) 
    return contenido is not None and contenido.lower().find("attachment") != -1

def esHtml(mensaje):
    if "text/html" in getTipo(mensaje):
        return True
    for dato in getDatos_Dict(mensaje):
        if not _es_mime_texto(dato.get("mimeType")):
            continue
        texto = _to_text(dato.get("datos", ""))
        if _HTML_HINT_RE.search(texto):
            return True
    return False

def getTipo(mensaje):
    cache = _get_cache(mensaje)
    tipos = cache.get("tipos_mime")
    if tipos is None:
        tipos = [dato["mimeType"] for dato in getDatos_Dict(mensaje)]
        cache["tipos_mime"] = tipos
    return tipos

def __getContenidoTipo__(mensaje, tipo):
    # Conserva compatibilidad con el nombre anterior.
    tipo.extend(getTipo(mensaje))
    return tipo
    
def getImageLink(mensaje):
    cache = _get_cache(mensaje)
    resultado = cache.get("image_links")
    if resultado is not None:
        return resultado

    resultado = []
    for soup in _get_soups(mensaje, solo_html=True):
        links = soup.find_all("a")
        for link in links:
            if link.find("img") is not None:
                resultado.append(link)
    cache["image_links"] = resultado
    return resultado
