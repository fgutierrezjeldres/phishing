# coding=utf-8
from abc import ABCMeta, abstractmethod
import ipaddress
import os
import re
import mailbox
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
FORWARDED_RE = re.compile("forwarded message")
HOST_WITH_TLD_RE = re.compile(r"^(?:[a-z0-9-]+\.)+[a-z]{2,}$", re.IGNORECASE)
ACTION_WORD_RES = [re.compile(rf"\b{re.escape(palabra.lower())}\b") for palabra in constantes.PALABRAS]
PAYPAL_RE = re.compile(r"\bpaypal\b")
BANK_RE = re.compile(r"\bbank(?:ing)?\b")
ACCOUNT_RE = re.compile(r"\baccount\b")
GMAIL_RE = re.compile(r"\bgmail(?:\.com)?\b")
OUTLOOK_RE = re.compile(r"\boutlook(?:\.com)?\b")
SCRIPT_FALLBACK_RE = re.compile(r"<\s*script\b|javascript\s*:", re.IGNORECASE)


def _a_flag(valor):
    return constantes.VERDADERO if valor else constantes.FALSO


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
        for url in utilidades.getUrl_Datos(mensaje):
            parsed = urlparse(url)
            host = parsed.hostname
            if not host:
                continue
            try:
                ipaddress.ip_address(host)
                continue
            except ValueError:
                pass
            if HOST_WITH_TLD_RE.search(host):
                return constantes.VERDADERO
        return constantes.FALSO

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
            umbral = 2
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
        return _a_flag(len(resultado) >= 2)

class URL(Buscador):
    def getBuscadorTitulo(self):
        return 'Contador De Link'
    
    def getBuscador(self, mensaje):
        return _a_flag(len(utilidades.getUrl_Datos(mensaje)) > 0)
        
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
        correo = _texto_correo(mensaje)
        return _a_flag(GMAIL_RE.search(correo) is not None)

class Outlook(Buscador):
    def getBuscadorTitulo(self):
        return 'Outlook'
    
    def getBuscador(self, mensaje):
        correo = _texto_correo(mensaje)
        return _a_flag(OUTLOOK_RE.search(correo) is not None)

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
    Paypal(),
    Bank(),
    Account(),
    Reenvio(),
    URL(),
    IPEnURL(),
    Multipart(),
    ArrobaEnURL(),
    ArchivoAdjunto(),
    ContenidoHTML(),
    Gmail(),
    Outlook(),
    Flash(),
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
                caracteristicas["Phishy"] = self.phishing
                data.append(caracteristicas)
        finally:
            mbox.close()
        return data
