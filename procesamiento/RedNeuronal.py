import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow import keras
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler

RANDOM_STATE = 42
TEST_SIZE = 0.20
CALIBRATION_SIZE = 0.20
THRESHOLD_CANDIDATES = tuple(float(v) for v in np.arange(0.30, 0.61, 0.02))
CLASS_WEIGHT_BOOST_CANDIDATES = (1.10, 1.30, 1.50, 1.70)
TARGET_MAX_FPR = 0.12
MAX_EPOCHS = 70
BATCH_SIZE = 64


class RedNeuronal:
    def __init__(self, archivo_dataset, archivo_modelo):
        self.archivo_dataset = archivo_dataset
        self.archivo_modelo = archivo_modelo
        self.dataset_diagnostic = None

    def _add_warning(self, texto):
        if not texto:
            return
        if self.dataset_diagnostic:
            self.dataset_diagnostic += "\n" + texto
        else:
            self.dataset_diagnostic = texto

    def _build_model(self, input_dim):
        model = keras.models.Sequential(
            [
                keras.layers.Input(shape=(input_dim,)),
                keras.layers.Dense(64, activation="relu"),
                keras.layers.Dropout(0.25),
                keras.layers.Dense(32, activation="relu"),
                keras.layers.Dropout(0.20),
                keras.layers.Dense(1, activation="sigmoid"),
            ]
        )

        optimizer = keras.optimizers.Adam(learning_rate=0.001)
        model.compile(
            optimizer=optimizer,
            loss="binary_crossentropy",
            metrics=[
                keras.metrics.BinaryAccuracy(name="accuracy"),
                keras.metrics.Precision(name="precision"),
                keras.metrics.Recall(name="recall"),
                keras.metrics.AUC(name="auc"),
            ],
        )
        return model

    def _callbacks(self):
        return [
            keras.callbacks.EarlyStopping(
                monitor="val_auc",
                mode="max",
                patience=7,
                restore_best_weights=True,
            ),
            keras.callbacks.ReduceLROnPlateau(
                monitor="val_loss",
                mode="min",
                factor=0.5,
                patience=3,
                min_lr=1e-5,
            ),
        ]

    def _class_weight(self, y_train, boost):
        counts = np.bincount(y_train, minlength=2).astype(np.float32)
        total = float(counts.sum())
        pesos = {}
        for clase, conteo in enumerate(counts):
            if conteo <= 0:
                continue
            pesos[clase] = total / (2.0 * float(conteo))
        if 1 in pesos:
            pesos[1] *= float(boost)
        return pesos

    def _metricas_umbral(self, y_true, prob, threshold):
        pred = (prob >= threshold).astype(int)
        cm = confusion_matrix(y_true, pred, labels=[0, 1])
        tn, fp, fn, tp = cm.ravel()

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        fpr = fp / (fp + tn) if (fp + tn) else 0.0
        specificity = tn / (tn + fp) if (tn + fp) else 0.0
        balanced = (recall + specificity) / 2.0

        return {
            "threshold": float(threshold),
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "fpr": float(fpr),
            "balanced_acc": float(balanced),
        }

    def _seleccionar_threshold(self, y_true, prob):
        candidatos = [self._metricas_umbral(y_true, prob, t) for t in THRESHOLD_CANDIDATES]

        def _score(m):
            penalidad_fpr = max(0.0, m["fpr"] - TARGET_MAX_FPR)
            return (
                (0.65 * m["recall"])
                + (0.25 * m["f1"])
                + (0.10 * m["precision"])
                - (1.20 * penalidad_fpr)
            )

        candidatos.sort(
            key=lambda m: (
                m["fpr"] <= TARGET_MAX_FPR,
                _score(m),
                m["recall"],
                -m["fpr"],
            ),
            reverse=True,
        )
        mejor = candidatos[0]
        return mejor["threshold"], mejor

    def _split_train_test(self, X, y, groups=None):
        if groups is None:
            return train_test_split(
                X,
                y,
                train_size=1.0 - TEST_SIZE,
                test_size=TEST_SIZE,
                random_state=RANDOM_STATE,
                stratify=y,
            )

        df_groups = pd.DataFrame({"group": groups, "y": y})
        resumen = df_groups.groupby("group")["y"].mean()
        group_ids = resumen.index.to_numpy()
        group_labels = (resumen.values >= 0.5).astype(int)

        # Si no hay suficiente variabilidad a nivel de grupos, fallback a split estratificado normal.
        if len(group_ids) < 20 or len(np.unique(group_labels)) < 2:
            self._add_warning("No fue posible usar split por MsgHash; se aplico split estratificado comun.")
            return train_test_split(
                X,
                y,
                train_size=1.0 - TEST_SIZE,
                test_size=TEST_SIZE,
                random_state=RANDOM_STATE,
                stratify=y,
            )

        g_train, g_test = train_test_split(
            group_ids,
            train_size=1.0 - TEST_SIZE,
            test_size=TEST_SIZE,
            random_state=RANDOM_STATE,
            stratify=group_labels,
        )
        train_mask = np.isin(groups, g_train)
        test_mask = np.isin(groups, g_test)

        # Guardas de robustez.
        if train_mask.sum() == 0 or test_mask.sum() == 0:
            self._add_warning("Split por MsgHash invalido; se aplico split estratificado comun.")
            return train_test_split(
                X,
                y,
                train_size=1.0 - TEST_SIZE,
                test_size=TEST_SIZE,
                random_state=RANDOM_STATE,
                stratify=y,
            )

        X_train, X_test = X[train_mask], X[test_mask]
        y_train, y_test = y[train_mask], y[test_mask]

        if len(np.unique(y_train)) < 2 or len(np.unique(y_test)) < 2:
            self._add_warning("Split por MsgHash produjo clase unica en un fold; se aplico split estratificado comun.")
            return train_test_split(
                X,
                y,
                train_size=1.0 - TEST_SIZE,
                test_size=TEST_SIZE,
                random_state=RANDOM_STATE,
                stratify=y,
            )

        return X_train, X_test, y_train, y_test

    def _preparar_dataset(self, datos):
        if "Phishy" not in datos.columns:
            raise ValueError("El dataset no contiene la columna obligatoria 'Phishy'.")

        datos = datos.copy()
        meta_cols = []
        groups = None

        if "MsgHash" in datos.columns:
            datos["MsgHash"] = datos["MsgHash"].fillna("").astype(str)
            antes = len(datos)
            datos = datos.drop_duplicates(subset=["MsgHash", "Phishy"]).reset_index(drop=True)
            removidas = antes - len(datos)
            if removidas > 0:
                self._add_warning(f"Se eliminaron {removidas} filas duplicadas por MsgHash+Phishy.")
            groups = datos["MsgHash"].to_numpy()
            meta_cols.append("MsgHash")

        feature_cols = [col for col in datos.columns if col not in {"Phishy", *meta_cols}]
        if not feature_cols:
            raise ValueError("El dataset no contiene columnas de caracteristicas.")

        datos[feature_cols] = datos[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
        datos["Phishy"] = pd.to_numeric(datos["Phishy"], errors="coerce")

        if datos["Phishy"].isna().any():
            raise ValueError("La columna 'Phishy' contiene valores no numericos.")

        datos["Phishy"] = datos["Phishy"].astype(int)
        etiquetas = set(datos["Phishy"].unique().tolist())
        if not etiquetas.issubset({0, 1}):
            raise ValueError("La columna 'Phishy' solo puede contener 0 o 1.")

        # Diagnostico de superposicion de clases para exactamente los mismos features.
        conflictos = datos.groupby(feature_cols)["Phishy"].nunique()
        vectores_conflictivos = conflictos[conflictos > 1]
        if not vectores_conflictivos.empty:
            conflict_keys = vectores_conflictivos.reset_index()[feature_cols]
            filas_conflictivas = datos.merge(conflict_keys, on=feature_cols, how="inner").shape[0]
            ratio = filas_conflictivas / len(datos)
            if ratio >= 0.98:
                raise ValueError(
                    "Dataset inconsistente: demasiadas filas tienen exactamente los mismos "
                    "features con etiquetas opuestas. Regenera el dataset con muestras "
                    "mejor separadas o revisa los mbox cargados."
                )
            if ratio >= 0.30:
                self._add_warning(
                    "Advertencia de datos: hay alta superposicion entre clases "
                    f"({ratio:.1%} de filas con features conflictivos)."
                )

        return datos, feature_cols, groups

    def _seleccionar_boost_y_threshold(self, X_train, y_train, input_dim):
        X_fit, X_cal, y_fit, y_cal = train_test_split(
            X_train,
            y_train,
            train_size=1.0 - CALIBRATION_SIZE,
            test_size=CALIBRATION_SIZE,
            random_state=RANDOM_STATE,
            stratify=y_train,
        )

        mejor = None
        for boost in CLASS_WEIGHT_BOOST_CANDIDATES:
            model = self._build_model(input_dim)
            class_weight = self._class_weight(y_fit, boost)
            history = model.fit(
                X_fit,
                y_fit,
                epochs=MAX_EPOCHS,
                batch_size=BATCH_SIZE,
                validation_split=0.2,
                callbacks=self._callbacks(),
                class_weight=class_weight,
                verbose=0,
            )

            prob_cal = model.predict(X_cal, verbose=0).reshape(-1)
            threshold, metricas = self._seleccionar_threshold(y_cal, prob_cal)
            score = (0.65 * metricas["recall"]) + (0.25 * metricas["f1"]) + (0.10 * metricas["precision"])

            if mejor is None or score > mejor["score"]:
                mejor = {
                    "boost": float(boost),
                    "threshold": float(threshold),
                    "score": float(score),
                    "metricas_cal": metricas,
                    "class_weight": class_weight,
                    "model": model,
                    "history_df": pd.DataFrame(history.history),
                }

        return mejor

    def procesar(self):
        self.dataset_diagnostic = None

        datos = pd.read_csv(self.archivo_dataset, sep=",")
        datos, feature_cols, groups = self._preparar_dataset(datos)

        X = datos[feature_cols].astype(np.float32).values
        y = datos["Phishy"].astype(np.int32).values

        scaler = MinMaxScaler()
        X = scaler.fit_transform(X)

        X_train, X_test, y_train, y_test = self._split_train_test(X, y, groups)

        input_dim = X_train.shape[1]
        tf.keras.utils.set_random_seed(RANDOM_STATE)

        # Calibramos boost y threshold sobre subset interno de entrenamiento.
        mejor_config = self._seleccionar_boost_y_threshold(X_train, y_train, input_dim)
        boost_final = mejor_config["boost"]
        threshold_final = mejor_config["threshold"]
        class_weight_final = mejor_config["class_weight"]
        model = mejor_config["model"]
        df = mejor_config["history_df"]
        data_accuracy = df[["accuracy"]]
        data_loss = df[["loss"]]

        evaluacion = model.evaluate(X_test, y_test, verbose=0, return_dict=True)
        test_loss = float(evaluacion.get("loss", 0.0))

        prob_phishing = model.predict(X_test, verbose=0).reshape(-1)
        snn_predicted = (prob_phishing >= threshold_final).astype(int)
        prediccion = np.column_stack([1.0 - prob_phishing, prob_phishing])
        test_acc = float((snn_predicted == y_test).mean())

        snn_cm = confusion_matrix(y_test, snn_predicted, labels=[0, 1])
        snn_report = classification_report(y_test, snn_predicted, zero_division=0)
        snn_report_dict = classification_report(
            y_test,
            snn_predicted,
            output_dict=True,
            zero_division=0,
        )

        snn_report_dict["config"] = {
            "threshold": float(threshold_final),
            "class_weight": class_weight_final,
            "class_weight_boost": float(boost_final),
            "target_max_fpr": float(TARGET_MAX_FPR),
            "threshold_candidates": [float(x) for x in THRESHOLD_CANDIDATES],
            "boost_candidates": [float(x) for x in CLASS_WEIGHT_BOOST_CANDIDATES],
            "calibration_metrics": mejor_config["metricas_cal"],
        }

        if self.dataset_diagnostic:
            snn_report = self.dataset_diagnostic + "\n\n" + snn_report
            snn_report_dict["warning"] = self.dataset_diagnostic

        snn_report = (
            f"Threshold phishing={threshold_final:.2f} | "
            f"class_weight={class_weight_final} | "
            f"boost={boost_final:.2f} | target_max_fpr={TARGET_MAX_FPR:.2f}\n\n"
            + snn_report
        )

        model.save(self.archivo_modelo, include_optimizer=False)

        return (
            test_acc,
            test_loss,
            prediccion.tolist(),
            snn_cm.tolist(),
            snn_report,
            snn_report_dict,
            data_accuracy.values.tolist(),
            data_loss.values.tolist(),
        )
