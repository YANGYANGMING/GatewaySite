import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "GatewaySite.settings")
django.setup()
from gateway import models

# obj = models.GWData.objects.values('alias__alias').filter(sensor_id='10010001201908230002')[0]['alias__alias']
# print(obj)
# models.GWData.objects.create(com_version='com_version', sensor_id='10010001201908200001', time_tamp='time_tamp', temperature=23,
#                             gain=60, battery=50, data_len=2048, thickness=10, data="122132", alias=obj
#                              )
# print(models.GWData.objects.values('alias__alias').first())
snr_num = models.Sensor_data.objects.values('sensor_id').all()
print(snr_num)

