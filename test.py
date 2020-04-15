import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "GatewaySite.settings")
django.setup()
from gateway import models


# gateway_data = {'Enterprise': '中石油aa', 'name': '中石油1号网关', 'network_id': '0.0.1.0', 'gw_status': '1'}
# models.Gateway.objects.all().update(**gateway_data)

data_obj = models.GWData.objects.values('time_tamp', 'thickness')[:2]
print(data_obj)
data_list = []
for item in data_obj:
    data_temp = {}
    data_temp['y'] = item.pop('thickness')
    data_temp['name'] = item.pop('time_tamp')
    data_list.append(data_temp)
print(data_list)


