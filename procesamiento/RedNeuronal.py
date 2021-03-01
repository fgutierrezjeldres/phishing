
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import tensorflow  as tf 
from tensorflow  import keras
from sklearn.metrics import classification_report,confusion_matrix
from sklearn.model_selection import train_test_split
from tabulate import tabulate



class RedNeuronal:
    def __init__(self, archivo_dataset, archivo_modelo, ):
        self.archivo_dataset = archivo_dataset
        self.archivo_modelo = archivo_modelo

    def procesar(self):
        datos = pd.read_csv(self.archivo_dataset, sep=",")
        X = datos.drop(["Phishy"], axis=1).values #variables de todas las caracteristicas menos la ultima 
        Y = datos["Phishy"].values #variable que tiene el resultado
  
        
        #separamos datos de prueba con datos (20% de datos de prueba)
        X_train, X_test, Y_train, Y_test = train_test_split(X, Y, train_size=0.8,test_size=0.2, random_state=0)#generador de numero aleatoreo dejarlo en 0)
        
        #categorizamos los resultados de y_train y de y_test (dejar los resultados en 0 y 1 )
        y = keras.utils.to_categorical(Y_train) #0 o 1 
        y_test = keras.utils.to_categorical(Y_test) #0 o 1 
        
        #validamos los   campos X_train e y  
        assert X_train.shape[0] == y.shape[0]

        #definimos el imput y el output
        input_dim = X_train.shape[1]
        outuput_dim = y.shape[1]

        #preparamos el ambiente de la red neuronal 
        model = keras.models.Sequential([
            keras.layers.Dense(80, activation=tf.nn.relu, input_shape=(input_dim,)),# activador relu
            keras.layers.Dense(80, activation=tf.nn.relu),#cada capa es de 80 neuronas
            keras.layers.Dense(80, activation=tf.nn.relu),
            keras.layers.Dense(outuput_dim, activation=tf.nn.sigmoid) #entrega los resultados clasificacion binaria se usa en sigmoid
        ])
        model.compile(optimizer = 'adam', loss = 'binary_crossentropy', metrics = ['accuracy'])
        model.summary()
        
        #entrenamos los resultados
        history = model.fit(X_train, y, workers=4, epochs=1000, verbose=2)
        df = pd.DataFrame(history.history)
        data_accuracy = df[["accuracy"]] 
        data_loss = df[["loss"]]

        #si queremos graficar 
        #f = plt.figure(figsize=(16, 5))
        #rows = 1
        #cols = 2
        #f.add_subplot(rows, cols, 1)
        #sns.lineplot(data=df[["accuracy"]])
        #f.add_subplot(rows, cols, 2)
        #sns.lineplot(data=df[["loss"]])
        #plt.show()
        #evaluamos la precision del modelo 
        test_loss, test_acc = model.evaluate(X_test, y_test)

        #generamos la prediccion
        prediccion = model.predict(X_test)
        snn_predicted = np.argmax(prediccion, axis=1)

        #Creamos la matriz de confusión
        snn_cm = confusion_matrix(np.argmax(y_test, axis=1), snn_predicted)
        # generamos el reporte de clasificacion 
        #El puntaje f1 le brinda la media armónica de precisión y recuperación. 
        # Los puntajes correspondientes a cada clase le indicarán la precisión del clasificador al clasificar los puntos de datos en esa clase en particular en comparación con todas las demás clases.
        #El soporte es el número de muestras de la respuesta verdadera que se encuentran en esa clase.
        snn_report = classification_report(np.argmax(y_test, axis=1), snn_predicted)
        model.save(self.archivo_modelo, include_optimizer=False)
        print('snn_report', snn_report)
        return test_acc, test_loss, prediccion.tolist(), snn_cm.tolist(), snn_report, data_accuracy.values.tolist(),data_loss.values.tolist()
        



      