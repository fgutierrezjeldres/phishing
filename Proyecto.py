# coding=utf-8
import pandas as pd
import csv
import logging
import hashlib
from model.resultado import Resultado
from buscadores.pishing import Pishing
import os
from pathlib import Path
from flask import Flask, render_template, request
from werkzeug.utils import secure_filename

#vnombres archivos
archivo_mbox = 'phishing.mbox'
archivo_dataset = 'dataset.csv'
archivo_modelo = 'modelo.h5'

#nombres carpetas (dinamicas, relativas a este archivo)
BASE_DIR = Path(__file__).resolve().parent
DATA_ROOT = Path(os.getenv("PHISHING_DATA_DIR")).expanduser().resolve() if os.getenv("PHISHING_DATA_DIR") else BASE_DIR / "archivos"
UPLOAD_FOLDER_PHISHING = DATA_ROOT / "entradas" / "mbox" / "phishing"
UPLOAD_FOLDER_NOPHISHING = DATA_ROOT / "entradas" / "mbox" / "nophishing"
FOLDER_DATASET = DATA_ROOT / "salidas" / "dataset"
FOLDER_MODEL = DATA_ROOT / "salidas" / "modelo"
LOG_FOLDER = BASE_DIR / "logs"

for carpeta in (UPLOAD_FOLDER_PHISHING, UPLOAD_FOLDER_NOPHISHING, FOLDER_DATASET, FOLDER_MODEL, LOG_FOLDER):
    carpeta.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("phishing_app")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler(LOG_FOLDER / "app.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(file_handler)
    logger.propagate = False


def _render_dataset(df, source_label):
    registros = df.fillna("").to_dict(orient="records")
    feature_keys = [c for c in df.columns if c != "Phishy"]
    return render_template(
        "dataset.html",
        resultado=registros,
        feature_keys=feature_keys,
        source_label=source_label,
    )


def _sha1_file(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _conflict_ratio(df):
    feature_cols = [c for c in df.columns if c not in ["Phishy", "MsgHash"]]
    if not feature_cols or "Phishy" not in df.columns or df.empty:
        return 0.0
    conflicts = df.groupby(feature_cols)["Phishy"].nunique()
    conflicted = conflicts[conflicts > 1]
    if conflicted.empty:
        return 0.0
    keys = conflicted.reset_index()[feature_cols]
    rows_conflicted = df.merge(keys, on=feature_cols, how="inner").shape[0]
    return rows_conflicted / len(df)

class Inicio:
    app = Flask(__name__)

    @app.route('/generacion_dataset', methods=['POST'])
    def  generacion_dataset():
        try:
            #cargar datos a las carpetas especificas
            phishing = request.files['pishing']
            nophishing = request.files['nopishing']
            archivo_phishing = secure_filename(phishing.filename)
            archivo_nophishing = secure_filename(nophishing.filename)
            if not archivo_phishing or not archivo_nophishing:
                raise ValueError("Debe seleccionar ambos archivos .mbox")

            phishing.save(str(UPLOAD_FOLDER_PHISHING / archivo_phishing))
            nophishing.save(str(UPLOAD_FOLDER_NOPHISHING / archivo_nophishing))
            ruta_phishing = UPLOAD_FOLDER_PHISHING / archivo_phishing
            ruta_nophishing = UPLOAD_FOLDER_NOPHISHING / archivo_nophishing

            # Evita entrenar con los mismos datos en ambas clases.
            if _sha1_file(str(ruta_phishing)) == _sha1_file(str(ruta_nophishing)):
                raise ValueError(
                    "Los dos archivos cargados son iguales. "
                    "Debes cargar un mbox phishing y otro no phishing distintos."
                )

            #cargo los datos de phishing
            objeto_phishing = Pishing(str(UPLOAD_FOLDER_PHISHING), archivo_phishing, 1)
            resultado_phishing = objeto_phishing.examinar()
            #cargo los datos de no phishing
            objeto_nophishing = Pishing(str(UPLOAD_FOLDER_NOPHISHING), archivo_nophishing, 0)
            resultado_nophishing = objeto_nophishing.examinar()
            #concateno las listas
            procesado = resultado_phishing + resultado_nophishing
            df = pd.DataFrame(procesado)
            ratio_conflicto = _conflict_ratio(df)
            if ratio_conflicto >= 0.98:
                raise ValueError(
                    "Dataset inconsistente: los features quedan casi identicos entre clases. "
                    "Revisa que no hayas invertido archivos o cargado muestras equivocadas."
                )
            ruta_dataset = FOLDER_DATASET / archivo_dataset
            df.to_csv(str(ruta_dataset), quoting=csv.QUOTE_NONE, index=False)
            logger.info(
                "Dataset generado | filas=%s | phishing=%s | no_phishing=%s | conflicto=%.4f | dataset=%s",
                len(procesado), len(resultado_phishing), len(resultado_nophishing), ratio_conflicto, ruta_dataset
            )
            return _render_dataset(df, "Generado en esta ejecucion")
        except Exception:
            logger.exception("Fallo en generacion_dataset")
            return render_template('carga.html', error_msg="Ocurrio un error al generar el dataset. Revisa logs/app.log"), 500

    @app.route('/ver_dataset', methods=['GET'])
    def ver_dataset():
        try:
            ruta_dataset = FOLDER_DATASET / archivo_dataset
            if not ruta_dataset.exists():
                raise FileNotFoundError("Aun no existe dataset.csv. Genera el dataset primero.")
            df = pd.read_csv(str(ruta_dataset))
            return _render_dataset(df, f"Dataset cargado desde {ruta_dataset.name}")
        except Exception as exc:
            logger.exception("Fallo en ver_dataset")
            return render_template(
                'carga.html',
                error_msg=f"No se pudo mostrar el dataset: {exc}. Revisa logs/app.log",
            ), 500


    @app.route('/generacion_red_neuronal',methods=['GET'])
    def generacion_red_neuronal():
        try:
            from procesamiento.RedNeuronal import RedNeuronal
            red = RedNeuronal(str(FOLDER_DATASET / archivo_dataset), str(FOLDER_MODEL / archivo_modelo))
            (
                test_acc,
                test_loss,
                prediccion,
                snn_cm,
                snn_report,
                snn_report_dict,
                data_accuracy,
                data_loss,
                dataset_stats,
            ) = red.procesar()
            objeto = Resultado(
                test_acc,
                test_loss,
                prediccion,
                snn_cm,
                snn_report,
                snn_report_dict,
                data_accuracy,
                data_loss,
                dataset_stats,
            )
            logger.info("Modelo entrenado | test_acc=%.6f | test_loss=%.6f", test_acc, test_loss)
            return render_template('resultado.html', resultado=objeto)
        except Exception as exc:
            logger.exception("Fallo en generacion_red_neuronal")
            return render_template(
                'carga.html',
                error_msg=f"Ocurrio un error al entrenar la red: {exc}. Revisa logs/app.log",
            ), 500

    @app.route('/')
    def carga_datos():
        return render_template('carga.html', error_msg=None)

    if __name__ == "__main__":
        app.run(debug=True)
