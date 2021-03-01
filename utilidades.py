from bs4 import BeautifulSoup
import re
from constantes import *


#traer el contenido del correo
def getDatos(mensaje):
    return __getDatos_Resultado__(mensaje, retorno="")

def __getDatos_Resultado__(mensaje, retorno):
    datos = mensaje.get_payload()
    if str(mensaje.get('Content-Transfer-Encoding')).lower() == "base64":
        datos = mensaje.get_payload(decode=True)

    if datos and mensaje.is_multipart():
        for subMensaje in datos:
            retorno += __getDatos_Resultado__(subMensaje, retorno)
    else:
        return mensaje.get_content_type() + "\t" + str(datos) + "\n"
    return retorno

def getDatos_Dict(mensaje):
    return __getDatos_Dict_Rec__(mensaje, [])


def __getDatos_Dict_Rec__(mensaje, retorno):
    datos = mensaje.get_payload()
    if mensaje.is_multipart():
        for subMensaje in datos:
            __getDatos_Dict_Rec__(subMensaje, retorno)
    else:
        retorno.append({"mimeType": mensaje.get_content_type(), "datos": datos})
    return retorno

def getJavascript(mensaje):
    resultado = []
    datos = getDatos_Dict(mensaje)
    for dato in datos:
        if dato["mimeType"].lower() == "text/html":
            contenidohtml = dato["datos"]
            soup = BeautifulSoup(contenidohtml,  'lxml')
            scripts = soup.findAll("script")
            for script in scripts:
                resultado.append(script)
    return resultado

def  getIPHref(mensaje):
    urls = getUrl_Datos(mensaje)
    ipHref = re.compile(IPREGEX, re.IGNORECASE)
    resultado = []
    if urls is not None:
        for url in urls:
            if ipHref.search(url) and ipHref.search(url).group(1) is not None:
                resultado.append(ipHref.search(url).group(1))
    return resultado

def getUrl_Datos(mensaje):
    return getString_Url(getDatos(mensaje))

def getString_Url(string):
    resultado = []
    datosLimpios = re.sub(r'\s', ' ', string)
    constante = re.compile(HREFREGEX, re.IGNORECASE)
    links = constante.findall(datosLimpios)
    for link in links:
        if esUrl(link):
            resultado.append(link)
    return resultado

def esUrl(link):
    return re.compile(URLREGEX, re.IGNORECASE).search(link) is not None

def getMultipart_Email(mensaje): 
    resultado =  mensaje.is_multipart()
    return resultado

def getContadorArchivoAdjunto(mensaje):
    return __getContadorArchivoAdjunto__(mensaje, contador = 0)

def __getContadorArchivoAdjunto__(mensaje, contador):
    datos = mensaje.get_payload()
    if mensaje.is_multipart():
        for subDatos in datos:
            contador +=__getContadorArchivoAdjunto__(subDatos, contador)
    else:
        if __archivoAdjunto__(mensaje):
            return 1
    return contador
def __archivoAdjunto__(mensaje):
    contenido = mensaje.get("Content-Disposition", failobj=None) 
    return contenido is not None and contenido.lower().find("attachment") != -1

def esHtml(mensaje):
    resultado = ("text/html" in getTipo(mensaje))
    datos = getDatos_Dict(mensaje)
    for dato in datos:
        if resultado or BeautifulSoup(dato["datos"], 'lxml').find():
            return True
    return resultado

def getTipo(mensaje):
    return __getContenidoTipo__(mensaje, [])

def __getContenidoTipo__(mensaje, tipo):
    datos = mensaje.get_payload()
    if mensaje.is_multipart():
        for subMensaje in datos:
            __getContenidoTipo__(subMensaje, tipo)
    else:
        tipo.append(mensaje.get_content_type())
    return tipo
    
def getImageLink(mensaje):
    resultado = []
    datos = getDatos_Dict(mensaje)
    for dato in datos:
        if dato["mimeType"].lower() == "text/html":
            contenidohtml = dato["datos"]
            soup = BeautifulSoup(contenidohtml,  'lxml')
            links = soup.findAll('a')
            for link in links:
                if link.find('img')!=None:
                    resultado.append(link)          
    return resultado