# coding=utf-8
from abc import ABCMeta, abstractmethod
import ipaddress
import hashlib
import os
import re
import mailbox
from email.utils import parseaddr
from urllib.parse import urlparse

import constantes 
import utilidades 


#clase  abstracta para sobreescribir los metodos necesarios para buscar las caracteristicas 
class Buscador(metaclass=ABCMeta):
    
    @abstractmethod
    def getBuscadorTitulo(self):
        pass
    
    @abstractmethod
    def getBuscador(self, mensaje):
        pass


FORM_RE = re.compile(r"<\s?\/?\s?form\s?>", re.IGNORECASE)
EMAIL_RE = re.compile(constantes.EMAILREGEX, re.IGNORECASE)
HEX_RE = re.compile(constantes.HEXADECIMALREGEX, re.IGNORECASE)
FLASH_LINK_RE = re.compile(constantes.FLASH_LINKED_CONTENT, re.IGNORECASE)
FLASH_OBJECT_RE = re.compile(constantes.FLASH_OBJECT, re.IGNORECASE)
FORWARDED_RE = re.compile(
    r"(forwarded message|-----\s*original message\s*-----|\bfw:\b|\bfwd:\b)",
    re.IGNORECASE,
)
HOST_WITH_TLD_RE = re.compile(r"^(?:[a-z0-9-]+\.)+[a-z]{2,}$", re.IGNORECASE)
ACTION_WORDS = (
    tuple(constantes.PALABRAS)
    + (
        "verify",
        "verification",
        "confirm",
        "urgent",
        "suspend",
        "security",
        "password",
        "login",
        "update",
        "account",
        "bank",
        "payment",
        "invoice",
    )
)
ACTION_WORD_RES = [re.compile(rf"\b{re.escape(palabra.lower())}\b") for palabra in ACTION_WORDS]
PAYPAL_RE = re.compile(r"\bpaypal\b")
BANK_RE = re.compile(r"\bbank(?:ing)?\b")
ACCOUNT_RE = re.compile(r"\baccount\b")
GMAIL_RE = re.compile(r"\bgmail(?:\.com)?\b")
OUTLOOK_RE = re.compile(r"\boutlook(?:\.com)?\b")
SCRIPT_FALLBACK_RE = re.compile(r"<\s*script\b|javascript\s*:", re.IGNORECASE)

# Umbrales para mantener el dataset binario (0/1) con criterios de riesgo.
URL_COUNT_SUSPICIOUS_MIN = 2
URL_AVG_LEN_SUSPICIOUS_MIN = 23.0
URL_MAX_SUBDOMAINS_SUSPICIOUS_MIN = 2
URL_DIGIT_RATIO_SUSPICIOUS_MIN = 0.03
URL_SUSPICIOUS_CHARS_SUSPICIOUS_MIN = 2
URL_EXTERNAL_RATIO_SUSPICIOUS_MIN = 0.70


def _a_flag(valor):
    return constantes.VERDADERO if valor else constantes.FALSO


def _a_flag_num_ge(valor, umbral):
    try:
        return _a_flag(float(valor) >= float(umbral))
    except (TypeError, ValueError):
        return constantes.FALSO


def _normalizar_valor_binario(valor):
    if isinstance(valor, bool):
        return _a_flag(valor)
    if valor is None:
        return constantes.FALSO
    if isinstance(valor, (int, float)):
        return _a_flag(float(valor) > 0.0)
    texto = str(valor).strip().lower()
    if texto in {"1", "true", "t", "yes", "y", "si"}:
        return constantes.VERDADERO
    if texto in {"0", "false", "f", "no", "n", ""}:
        return constantes.FALSO
    try:
        return _a_flag(float(texto) > 0.0)
    except (TypeError, ValueError):
        return constantes.FALSO


def _get_mensaje_cache(mensaje):
    try:
        cache = mensaje.__dict__.get("_phishing_buscadores_cache")
        if cache is None:
            cache = {}
            mensaje.__dict__["_phishing_buscadores_cache"] = cache
        return cache
    except Exception:
        return {}


def _texto_correo(mensaje):
    cache = _get_mensaje_cache(mensaje)
    texto = cache.get("texto_correo")
    if texto is None:
        texto = utilidades.getDatos(mensaje).lower()
        cache["texto_correo"] = texto
    return texto


def _texto_headers(mensaje):
    cache = _get_mensaje_cache(mensaje)
    headers = cache.get("texto_headers")
    if headers is None:
        partes = []
        for campo in ("From", "Reply-To", "Return-Path", "Sender", "Message-ID", "Received"):
            valor = mensaje.get(campo)
            if valor:
                partes.append(str(valor))
        headers = "\n".join(partes).lower()
        cache["texto_headers"] = headers
    return headers


def _extraer_dominio_email(valor):
    if not valor:
        return None
    _, correo = parseaddr(str(valor))
    if "@" not in correo:
        return None
    dominio = correo.split("@", 1)[1].strip().lower()
    if not dominio:
        return None
    return dominio.lstrip(".")


def _dominio_from(mensaje):
    cache = _get_mensaje_cache(mensaje)
    dominio = cache.get("dominio_from")
    if dominio is None:
        dominio = _extraer_dominio_email(mensaje.get("From"))
        cache["dominio_from"] = dominio or ""
    return dominio or None


def _dominio_reply_to(mensaje):
    cache = _get_mensaje_cache(mensaje)
    dominio = cache.get("dominio_reply_to")
    if dominio is None:
        dominio = _extraer_dominio_email(mensaje.get("Reply-To"))
        cache["dominio_reply_to"] = dominio or ""
    return dominio or None


def _normalizar_host(host):
    if not host:
        return None
    host = str(host).strip().lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return host or None


def _urls_validas(mensaje):
    cache = _get_mensaje_cache(mensaje)
    urls = cache.get("urls_validas")
    if urls is None:
        urls = []
        for url in utilidades.getUrl_Datos(mensaje):
            parsed = urlparse(url)
            if parsed.scheme.lower() not in ("http", "https", "ftp"):
                continue
            host = _normalizar_host(parsed.hostname)
            if not host:
                continue
            urls.append((url, host))
        cache["urls_validas"] = urls
    return urls


def _host_pertenece_a_dominio(host, dominio):
    if not host or not dominio:
        return False
    return host == dominio or host.endswith("." + dominio)


def _ratio_seguro(numerador, denominador):
    if denominador <= 0:
        return 0.0
    return float(numerador) / float(denominador)


def _tiene_contenido(datos):
    return any(str(dato["datos"] or "").strip() for dato in datos)


def _safe_log(*args):
    try:
        print(*args)
    except (OSError, ValueError):
        pass


#se crea clases para cada carasteristicas a buscar

class Dominio(Buscador):
    def getBuscadorTitulo(self):
        return 'Contador De Dominio'
        
    def getBuscador(self, mensaje):
        dominios = set()
        for _, host in _urls_validas(mensaje):
            try:
                ipaddress.ip_address(host)
                continue
            except ValueError:
                pass
            if HOST_WITH_TLD_RE.search(host):
                dominios.add(host)
        return _a_flag(len(dominios) >= 2)

class Link(Buscador):
    def getBuscadorTitulo(self):
        return 'Contador De Link'
    
    def getBuscador(self, mensaje):
        return _a_flag(len(utilidades.getHyperlinks(mensaje)) > 0)

class LinkImage(Buscador):
    def getBuscadorTitulo(self):
        return 'Hiperlink de Imagenes'
    
    def getBuscador(self, mensaje):
        retorno = len(utilidades.getImageLink(mensaje))
        return _a_flag(retorno > 0)
        
class JavaScript(Buscador):
    def getBuscadorTitulo(self):
        return 'Contador De JavaScript'
    
    def getBuscador(self, mensaje):
        if len(utilidades.getJavascript(mensaje)) > 0:
            return constantes.VERDADERO
        correo = _texto_correo(mensaje)
        return _a_flag(SCRIPT_FALLBACK_RE.search(correo) is not None)
        
class EtiquetaFormularioHTML(Buscador):
    def getBuscadorTitulo(self):
        return 'Formulario HTML'

    def getBuscador(self, mensaje):
        correo = _texto_correo(mensaje)
        return _a_flag(FORM_RE.search(correo) is not None)

class ActionWord(Buscador):
    def getBuscadorTitulo(self):
        return 'Llamada de Accion'
    
    def getBuscador(self, mensaje, umbral = 2):
        correo = _texto_correo(mensaje)
        retorno = sum(1 for palabra_re in ACTION_WORD_RES if palabra_re.search(correo))
        try:
            umbral = int(umbral)
        except (TypeError, ValueError):
            umbral = 1
        umbral = max(1, umbral)
        return _a_flag(retorno >= umbral)

class Paypal(Buscador):
    def getBuscadorTitulo(self):
        return 'PAYPAL'
    
    def getBuscador(self, mensaje):
        correo = _texto_correo(mensaje)
        return _a_flag(PAYPAL_RE.search(correo) is not None)

class Bank(Buscador):
    def getBuscadorTitulo(self):
        return 'BANK'
    
    def getBuscador(self, mensaje):
        correo = _texto_correo(mensaje)
        return _a_flag(BANK_RE.search(correo) is not None)

class Account(Buscador):
    def getBuscadorTitulo(self):
        return 'Account'
    
    def getBuscador(self, mensaje):
        correo = _texto_correo(mensaje)
        return _a_flag(ACCOUNT_RE.search(correo) is not None)

class Reenvio(Buscador):
    def getBuscadorTitulo(self):
        return 'Numero de Reenvios'
    
    def getBuscador(self, mensaje):
        correo = _texto_correo(mensaje)
        resultado = FORWARDED_RE.findall(correo)
        return _a_flag(len(resultado) >= 1)

class URL(Buscador):
    def getBuscadorTitulo(self):
        return 'URL en texto'
    
    def getBuscador(self, mensaje):
        return _a_flag(len(utilidades.getUrl_Datos(mensaje)) > 0)


class NumeroURL(Buscador):
    def getBuscadorTitulo(self):
        return "Num URL"

    def getBuscador(self, mensaje):
        return _a_flag_num_ge(len(_urls_validas(mensaje)), URL_COUNT_SUSPICIOUS_MIN)


class PromedioLongitudURL(Buscador):
    def getBuscadorTitulo(self):
        return "Promedio Longitud URL"

    def getBuscador(self, mensaje):
        urls = _urls_validas(mensaje)
        if not urls:
            return constantes.FALSO
        promedio = sum(len(url) for url, _ in urls) / len(urls)
        return _a_flag_num_ge(promedio, URL_AVG_LEN_SUSPICIOUS_MIN)


class MaxSubdominiosURL(Buscador):
    def getBuscadorTitulo(self):
        return "Max Subdominios URL"

    def getBuscador(self, mensaje):
        maximo = 0
        for _, host in _urls_validas(mensaje):
            try:
                ipaddress.ip_address(host)
                continue
            except ValueError:
                pass
            partes = host.split(".")
            subdominios = max(0, len(partes) - 2)
            maximo = max(maximo, subdominios)
        return _a_flag_num_ge(maximo, URL_MAX_SUBDOMAINS_SUSPICIOUS_MIN)


class RatioDigitosURL(Buscador):
    def getBuscadorTitulo(self):
        return "Ratio Digitos URL"

    def getBuscador(self, mensaje):
        urls = _urls_validas(mensaje)
        if not urls:
            return constantes.FALSO
        cadena = "".join(url for url, _ in urls)
        if not cadena:
            return constantes.FALSO
        digitos = sum(1 for c in cadena if c.isdigit())
        ratio = _ratio_seguro(digitos, len(cadena))
        return _a_flag_num_ge(ratio, URL_DIGIT_RATIO_SUSPICIOUS_MIN)


class NumCaracteresSospechososURL(Buscador):
    def getBuscadorTitulo(self):
        return "Num Caracteres Sospechosos URL"

    def getBuscador(self, mensaje):
        urls = _urls_validas(mensaje)
        if not urls:
            return constantes.FALSO
        sospechosos = "@%-_=&?"
        total = sum(sum(1 for c in url if c in sospechosos) for url, _ in urls)
        return _a_flag_num_ge(total, URL_SUSPICIOUS_CHARS_SUSPICIOUS_MIN)


class RatioURLExternas(Buscador):
    def getBuscadorTitulo(self):
        return "Ratio URLs Externas"

    def getBuscador(self, mensaje):
        dominio_from = _dominio_from(mensaje)
        urls = _urls_validas(mensaje)
        if not dominio_from or not urls:
            return constantes.FALSO
        externos = sum(1 for _, host in urls if not _host_pertenece_a_dominio(host, dominio_from))
        ratio = _ratio_seguro(externos, len(urls))
        return _a_flag_num_ge(ratio, URL_EXTERNAL_RATIO_SUSPICIOUS_MIN)


class MismatchReplyToFrom(Buscador):
    def getBuscadorTitulo(self):
        return "Mismatch ReplyTo-From"

    def getBuscador(self, mensaje):
        dominio_from = _dominio_from(mensaje)
        dominio_reply = _dominio_reply_to(mensaje)
        if not dominio_from or not dominio_reply:
            return constantes.FALSO
        return _a_flag(dominio_from != dominio_reply)
        
class Multipart(Buscador):
    def getBuscadorTitulo(self):
        return 'Email Multipart'
    
    def getBuscador(self, mensaje):
        resultado =  utilidades.getMultipart_Email(mensaje)
        return _a_flag(resultado is True)

class IPEnURL(Buscador):
    def getBuscadorTitulo(self):
        return 'IP en URL'
    
    def getBuscador(self, mensaje):
        resultado = len(utilidades.getIPHref(mensaje))
        return _a_flag(resultado > 0)

class ArrobaEnURL(Buscador):
    def getBuscadorTitulo(self):
        return '@ en URL'
    
    def getBuscador(self, mensaje):
        urls = utilidades.getUrl_Datos(mensaje)

        if urls is not None:
            for url in urls:
                email_match = EMAIL_RE.search(url)
                if (url.lower().startswith('mailto:') or (
                    email_match is not None and email_match.group() is not None)):
                    continue
                arroba = url.find("@")
                arrobaHexadecimal = url.find("%40")
                if(arroba != -1 and arrobaHexadecimal != -1):
                    arroba = min(arrobaHexadecimal, arroba)
                else:
                    arroba = max(arroba, arrobaHexadecimal)
                paramindex = url.find('?')
                if paramindex != -1:
                    if (arroba != -1) and (paramindex > arroba):
                        return constantes.VERDADERO
                else:
                    if (arroba != -1):
                        return  constantes.VERDADERO
        return constantes.FALSO
    
class ArchivoAdjunto(Buscador):
    def getBuscadorTitulo(self):
        return 'Archivo Adjunto'
    
    def getBuscador(self, mensaje):
        resultado = utilidades.getContadorArchivoAdjunto(mensaje)
        return _a_flag(resultado > 0)
        
class ContenidoHTML(Buscador):
    def getBuscadorTitulo(self):
        return 'Contenido HTML'
    
    def getBuscador(self, mensaje):
        resultado = utilidades.esHtml(mensaje)
        return _a_flag(resultado)
        
class Gmail(Buscador):
    def getBuscadorTitulo(self):
        return 'Gmail'
    
    def getBuscador(self, mensaje):
        headers = _texto_headers(mensaje)
        return _a_flag(GMAIL_RE.search(headers) is not None)

class Outlook(Buscador):
    def getBuscadorTitulo(self):
        return 'Outlook'
    
    def getBuscador(self, mensaje):
        headers = _texto_headers(mensaje)
        return _a_flag(OUTLOOK_RE.search(headers) is not None)

class Hexadecimal(Buscador):
    def getBuscadorTitulo(self):
        return 'Hexadecimal'
    
    def getBuscador(self, mensaje):
        cadena = _texto_correo(mensaje)
        return _a_flag(HEX_RE.search(cadena) is not None)

class Flash(Buscador):
    
    def getBuscadorTitulo(self):
        return "Flash"
    
    def getBuscador(self,mensaje):
        datos = _texto_correo(mensaje)
        swf = FLASH_LINK_RE.findall(datos)
        flash = FLASH_OBJECT_RE.search(datos)
        return _a_flag((swf is not None and len(swf) > 0) or (flash is not None))


BUSCADORES = (
    EtiquetaFormularioHTML(),
    Dominio(),
    Link(),
    JavaScript(),
    ActionWord(),
    Bank(),
    Account(),
    Reenvio(),
    NumeroURL(),
    PromedioLongitudURL(),
    MaxSubdominiosURL(),
    RatioDigitosURL(),
    NumCaracteresSospechososURL(),
    RatioURLExternas(),
    MismatchReplyToFrom(),
    IPEnURL(),
    Multipart(),
    ArrobaEnURL(),
    ContenidoHTML(),
    Hexadecimal(),
    LinkImage(),
)
BUSCADORES_COMPILED = tuple((buscador.getBuscadorTitulo(), buscador.getBuscador) for buscador in BUSCADORES)

#metodo que permite crear el dataset    
class Pishing:
    def __init__(self,carpeta, archivo_mbox, phishing):
        self.archivo_mbox = archivo_mbox
        self.phishing = phishing
        self.carpeta = carpeta

    def examinar(self):
        ruta_mbox = os.path.abspath(os.path.join(self.carpeta, self.archivo_mbox))
        _safe_log("carpeta :", ruta_mbox)
        mbox = mailbox.mbox(ruta_mbox)

        data = []
        try:
            for mensaje in mbox:
                datos = utilidades.getDatos_Dict(mensaje)
                if not _tiene_contenido(datos):
                    _safe_log("correo vacio")
                    continue

                caracteristicas = {
                    titulo: buscador_fn(mensaje)
                    for titulo, buscador_fn in BUSCADORES_COMPILED
                }
                caracteristicas = {
                    titulo: _normalizar_valor_binario(valor)
                    for titulo, valor in caracteristicas.items()
                }
                try:
                    caracteristicas["MsgHash"] = hashlib.sha1(mensaje.as_bytes()).hexdigest()
                except Exception:
                    caracteristicas["MsgHash"] = ""
                caracteristicas["Phishy"] = self.phishing
                data.append(caracteristicas)
        finally:
            mbox.close()
        return data
