# coding=utf-8
import pandas as pd
import csv
from model.resultado import Resultado
from buscadores.pishing import Pishing
from procesamiento.RedNeuronal import RedNeuronal
import os
from flask import Flask, render_template, request
from werkzeug.utils import secure_filename

#vnombres archivos
archivo_mbox = 'phishing.mbox'
archivo_dataset = 'dataset.csv'
archivo_modelo = 'modelo.h5'

#nombres carpetas 
UPLOAD_FOLDER_PHISHING = '../phishing/archivos/entradas/mbox/phishing/'
UPLOAD_FOLDER_NOPHISHING =  '../phishing/archivos/entradas/mbox/nophishing/'
FOLDER_DATASET = '../phishing/archivos/salidas/dataset/'
FOLDER_MODEL = '../phishing/archivos/salidas/modelo/'

class Inicio:
    app = Flask(__name__)

    @app.route('/generacion_dataset', methods=['POST'])
    def  generacion_dataset():
        
        #cargar datos a las carpetas especificas 
        phishing = request.files['pishing']
        nophishing = request.files['nopishing']
        archivo_phishing = secure_filename(phishing.filename)
        archivo_nophishing = secure_filename(nophishing.filename)
        phishing.save(os.path.join(UPLOAD_FOLDER_PHISHING, archivo_phishing))
        nophishing.save(os.path.join(UPLOAD_FOLDER_NOPHISHING, archivo_nophishing))

        #cargo los datos de phishing
        objeto_phishing = Pishing(UPLOAD_FOLDER_PHISHING, phishing.filename,1)
        resultado_phishing = objeto_phishing.examinar()
        #cargo los datos de no phishing
        objeto_nophishing = Pishing(UPLOAD_FOLDER_NOPHISHING, nophishing.filename,0)
        resultado_nophishing = objeto_nophishing.examinar()
        #concateno las listas 
        procesado = resultado_phishing + resultado_nophishing
        df = pd.DataFrame(procesado)
        df.to_csv(FOLDER_DATASET+archivo_dataset, quoting=csv.QUOTE_NONE, index=False)
        print(type(procesado))
        return render_template('dataset.html', resultado = procesado)


    @app.route('/generacion_red_neuronal',methods=['GET'])
    def generacion_red_neuronal():
        red = RedNeuronal(FOLDER_DATASET+archivo_dataset,FOLDER_MODEL+archivo_modelo)
        test_acc, test_loss, prediccion, snn_cm, snn_report, data_accuracy, data_loss = red.procesar()
        objeto = Resultado(test_acc, test_loss, prediccion, snn_cm, snn_report, data_accuracy,data_loss)  
        return render_template('resultado.html', resultado = objeto)

    @app.route('/')
    def carga_datos():
        return render_template('carga.html')

    if __name__ == "__main__":
        app.run(debug=True)