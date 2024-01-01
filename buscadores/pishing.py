# coding=utf-8
from abc import ABCMeta, abstractmethod

#from numpy import append,
import constantes 
import utilidades 
import pandas as pd
import re

import mailbox


#clase  abstracta para sobreescribir los metodos necesarios para buscar las caracteristicas 
class Buscador:
    __metaclass__ = ABCMeta
    
    @abstractmethod
    def getBuscadorTitulo(self):
        pass
    
    @abstractmethod
    def getBuscador(self, mensaje):
        pass
#se crea clases para cada carasteristicas a buscar

class Dominio(Buscador):
    def getBuscadorTitulo(self):
        titulo = 'Contador De Dominio'
        return titulo
        
    def getBuscador(self, mensaje):
        super(Dominio, self).getBuscador(mensaje)
        correo = utilidades.getDatos(mensaje).lower()
        retorno = re.compile(constantes.URLREGEX, re.IGNORECASE).search(correo) != None
        if retorno == constantes.VERDADERO:
            return constantes.VERDADERO
        else:
            return constantes.FALSO

class Link(Buscador):
    def getBuscadorTitulo(self):
        titulo = 'Contador De Link'
        return titulo
    
    def getBuscador(self, mensaje):
        super(Link, self).getBuscador(mensaje)
        correo = utilidades.getDatos(mensaje).lower()
        retorno = re.compile(r'<a[^>]+href=\'(.*?)\'[^>]*>(.*)?</a>', re.IGNORECASE).search(correo) != None
        if retorno == constantes.VERDADERO:
            return constantes.VERDADERO
        else:
            return constantes.FALSO

class LinkImage(Buscador):
    def getBuscadorTitulo(self):
        titulo = 'Hiperlink de Imagenes'
        return titulo
    
    def getBuscador(self, mensaje):
        retorno = len(utilidades.getImageLink(mensaje))
        if retorno > 0:
            return constantes.VERDADERO
        else:
            return constantes.FALSO
        
class JavaScript(Buscador):
    def getBuscadorTitulo(self):
        titulo = 'Contador De JavaScript'
        return titulo
    
    def getBuscador(self, mensaje):
        retorno = len(utilidades.getJavascript(mensaje))
        if retorno > 0:
            return constantes.VERDADERO
        else:
            return constantes.FALSO
        
class EtiquetaFormularioHTML(Buscador):
    def getBuscadorTitulo(self):
        titulo = 'Formulario HTML'
        return titulo

    def getBuscador(self, mensaje):
        super(EtiquetaFormularioHTML, self).getBuscador(mensaje)
        correo = utilidades.getDatos(mensaje).lower()
        retorno = re.compile(r'<\s?\/?\s?form\s?>', re.IGNORECASE).search(correo) != None
        if retorno == constantes.VERDADERO:
            return constantes.VERDADERO
        else:
            return constantes.FALSO

class ActionWord(Buscador):
    def getBuscadorTitulo(self):
        titulo = 'Llamada de Accion'
        return titulo
    
    def getBuscador(self, mensaje, umbral = 3):
        super(ActionWord, self).getBuscador(mensaje)
        correo =  utilidades.getDatos(mensaje).lower()
        retorno = 0
        palabras_encontradas = []
        for palabra in constantes.PALABRAS:
            if re.search(palabra, correo):
                retorno += 1
                palabras_encontradas.append(palabra)
                
        #return retorno       
        if retorno >= umbral:
            return constantes.VERDADERO
        else:
            return constantes.FALSO  

class Paypal(Buscador):
    def getBuscadorTitulo(self):
        titulo = 'PAYPAL'
        return titulo
    
    def getBuscador(self, mensaje):
        super(Paypal, self).getBuscador(mensaje)
        correo =  utilidades.getDatos(mensaje).lower()
        if re.search("paypal", correo):
            return constantes.VERDADERO
        else:
            return constantes.FALSO 

class Bank(Buscador):
    def getBuscadorTitulo(self):
        titulo = 'BANK'
        return titulo
    
    def getBuscador(self, mensaje):
        super(Bank, self).getBuscador(mensaje)
        correo =  utilidades.getDatos(mensaje).lower()
        if re.search("bank", correo):
            return constantes.VERDADERO
        else:
            return constantes.FALSO 

class Account(Buscador):
    def getBuscadorTitulo(self):
        titulo = 'Account'
        return titulo
    
    def getBuscador(self, mensaje):
        super(Account, self).getBuscador(mensaje)
        correo =  utilidades.getDatos(mensaje).lower()
        if re.search("account", correo):
            return constantes.VERDADERO
        else:
            return constantes.FALSO 

class Reenvio(Buscador):
    def getBuscadorTitulo(self):
        titulo = 'Numero de Reenvios'
        return titulo
    
    def getBuscador(self, mensaje):
        super(Reenvio, self).getBuscador(mensaje)
        correo =  utilidades.getDatos(mensaje).lower()
        resultado = re.findall("forwarded message", correo)
        if len(resultado) >= 2:
            return constantes.VERDADERO
        else:
            return constantes.FALSO 

class URL(Buscador):
    def getBuscadorTitulo(self):
        titulo = 'Contador De Link'
        return titulo
    
    def getBuscador(self, mensaje):
        super(URL, self).getBuscador(mensaje)
        correo = utilidades.getDatos(mensaje).lower()
        retorno = re.compile(constantes.URLREGEX_NOT_ALONE, re.IGNORECASE).search(correo) != None
        if retorno == constantes.VERDADERO:
            return constantes.VERDADERO
        else:
            return constantes.FALSO
        
class Multipart(Buscador):
    def getBuscadorTitulo(self):
        titulo = 'Email Multipart'
        return titulo
    
    def getBuscador(self, mensaje):
        resultado =  utilidades.getMultipart_Email(mensaje)
        if resultado == True:
            return constantes.VERDADERO
        else:
            return constantes.FALSO

class IPEnURL(Buscador):
    def getBuscadorTitulo(self):
        titulo = 'IP en URL'
        return titulo
    
    def getBuscador(self, mensaje):
        resultado = len(utilidades.getIPHref(mensaje))
        if resultado > 0:
            return constantes.VERDADERO
        else:
            return constantes.FALSO

class ArrobaEnURL(Buscador):
    def getBuscadorTitulo(self):
        titulo = '@ en URL'
        return titulo
    
    def getBuscador(self, mensaje):
        email = re.compile(constantes.EMAILREGEX, re.IGNORECASE)
        urls = utilidades.getUrl_Datos(mensaje)

        if urls is not None:
            for url in urls:
                if (url.lower().startswith('mailto:') or (
                    email.search(url) != None and email.search(url).group() != None)):
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
        titulo = 'Archivo Adjunto'
        return titulo
    
    def getBuscador(self, mensaje):
        resultado = utilidades.getContadorArchivoAdjunto(mensaje)
        if resultado > 0:
            return constantes.VERDADERO
        else:
            return constantes.FALSO
        
class ContenidoHTML(Buscador):
    def getBuscadorTitulo(self):
        titulo = 'Contenido HTML'
        return titulo
    
    def getBuscador(self, mensaje):
        resultado = utilidades.esHtml(mensaje)
        if resultado:
            return constantes.VERDADERO
        else:
            return constantes.FALSO
        
class Gmail(Buscador):
    def getBuscadorTitulo(self):
        titulo = 'Gmail'
        return titulo
    
    def getBuscador(self, mensaje):
        super(Gmail, self).getBuscador(mensaje)
        correo =  utilidades.getDatos(mensaje).lower()
        if re.search("gmail", correo):
            return constantes.VERDADERO
        else:
            return constantes.FALSO 

class Outlook(Buscador):
    def getBuscadorTitulo(self):
        titulo = 'Outlook'
        return titulo
    
    def getBuscador(self, mensaje):
        super(Outlook, self).getBuscador(mensaje)
        correo =  utilidades.getDatos(mensaje).lower()
        if re.search("outlook", correo):
            return constantes.VERDADERO
        else:
            return constantes.FALSO

class Hexadecimal(Buscador):
    def getBuscadorTitulo(self):
        titulo = 'Hexadecimal'
        return titulo
    
    def getBuscador(self, mensaje):
        super(Hexadecimal, self).getBuscador(mensaje)
        cadena = utilidades.getDatos(mensaje).lower()
        retorno = re.compile(constantes.HEXADECIMALREGEX, re.IGNORECASE).search(cadena) != None
        if retorno == constantes.VERDADERO:
            return constantes.VERDADERO
        else:
            return constantes.FALSO

class Flash(Buscador):
    
    def getBuscadorTitulo(self):
        titulo = "Flash"
        return titulo
    
    def getBuscador(self,mensaje):
        super(Flash,self).getBuscador(mensaje)
        datos = utilidades.getDatos(mensaje).lower()
        swf = re.compile(constantes.FLASH_LINKED_CONTENT, re.IGNORECASE).findall(datos)
        flash = re.compile(constantes.FLASH_OBJECT, re.IGNORECASE).search(datos)
        if (swf != None and len(swf) >0) or \
        (flash != None):
            return constantes.VERDADERO
        else:
            return constantes.FALSO

#metodo que permite crear el dataset    
class Pishing:
    def __init__(self,carpeta, archivo_mbox, phishing):
        self.archivo_mbox = archivo_mbox
        self.phishing = phishing
        self.carpeta = carpeta

    def examinar(self):
        
        print("carpeta : ", self.carpeta + self.archivo_mbox)
        mbox = mailbox.mbox(self.carpeta + self.archivo_mbox)
        
        i = 1
        data = []
        buscadores = [EtiquetaFormularioHTML(),Dominio(),Link(),JavaScript(),ActionWord(), Paypal(), Bank(),Account(),
                      Reenvio(), URL(),IPEnURL(),Multipart(), ArrobaEnURL(), ArchivoAdjunto(), ContenidoHTML(),
                       Gmail(), Outlook(),Flash(),Hexadecimal(),LinkImage()]
        for mensaje in mbox:
            caracteristicas = {}
            total = 0
            datos =  utilidades.getDatos_Dict(mensaje)
            for dato in datos:
                    total +=len(re.sub(r'\s+','',dato["datos"]))
            if total < 1:
                print("correo vacio: " + utilidades.getDatos(mensaje))
                continue
            for buscador in buscadores:
                caracteristicas[buscador.getBuscadorTitulo()] = buscador.getBuscador(mensaje)

            caracteristicas["Phishy"] = self.phishing
            data.append(caracteristicas)
        return data