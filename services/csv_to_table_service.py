from django.db.models import Q
import os,csv
from django.apps import apps

class CsvToTableService():

    def __init__(self,csv_file= None):
        self.csv_file          = csv_file


    def model_finder(self,model_name):
        model = None
        for app_config in apps.get_app_configs():
            try:
                model = apps.get_model(app_label=app_config.label, model_name=model_name)
                break
            except LookupError:
                continue
        return model


    def csv_file_reader(self):

        file_name   = self.csv_file.name
        model_name  = file_name.split('.')[0].split('/')[-1]
        model       = self.model_finder(model_name)
        csv_data    = csv.DictReader(self.csv_file.read().decode('utf-8').splitlines())

        if model is not None:
          for row in csv_data:
            data = {}
            for key,value in row.items():
                key= key.lower().rstrip('').lstrip('').replace(' ','')
                data = {key:value}
            model.objects.create(**data)

        return


