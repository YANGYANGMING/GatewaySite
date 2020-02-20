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
# snr_num = models.Sensor_data.objects.values('sensor_id').all()
# print(snr_num)
# st1 = models.Set_Time.objects.filter(id='4').values('day', 'hour', 'mins').first()
# print('st1:', st1)

# from datetime import datetime
# pre_day = datetime(2015, 12, 7)
# cur_day = datetime(2020, 2, 14)
# print((cur_day - pre_day).days)
# a = [{"周一": 0}, {"周二": 1}, {"周三": 2}, {"周四": 3}, {"周五": 4}, {"周六": 5}, {"周日": 6}]
# for i in a:
#     print(list(i.keys())[0])
#     print(i.values())




