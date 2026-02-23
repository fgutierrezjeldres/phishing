class Resultado:
    def __init__(
        self,
        test_acc,
        test_loss,
        prediccion,
        snn_cm,
        snn_report,
        snn_report_dict,
        data_accuracy,
        data_loss,
        dataset_stats=None,
    ):
        self.test_acc = test_acc
        self.test_loss = test_loss
        self.prediccion = prediccion
        self.snn_cm = snn_cm
        self.snn_report = snn_report
        self.snn_report_dict = snn_report_dict
        self.data_accuracy = data_accuracy
        self.data_loss = data_loss
        self.dataset_stats = dataset_stats or {}


 
