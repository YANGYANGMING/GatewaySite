import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "GatewaySite.settings")
django.setup()
from gateway import models


# gateway_data = {'Enterprise': '中石油aa', 'name': '中石油1号网关', 'network_id': '0.0.1.0', 'gw_status': '1'}
# models.Gateway.objects.all().update(**gateway_data)

# data_obj = models.GWData.objects.values('time_tamp', 'thickness')[:2]
# print(data_obj)
# data_list = []
# for item in data_obj:
#     data_temp = {}
#     data_temp['y'] = item.pop('thickness')
#     data_temp['name'] = item.pop('time_tamp')
#     data_list.append(data_temp)
# print(data_list)
# import json
# def upload(msg_path):
#     with open(msg_path, 'rb') as f:
#         img = f.read()
#     print(img)
#     string = str(img)
#     jsons = json.dumps(string)
#     print(jsons)
#     name = json.loads(jsons)
#     byte = eval(json.loads(jsons))
#     print('name', name)
#     with open('static/location_imgs/2.png', 'wb') as ff:
#         ff.write(byte)
#
# upload('static/location_imgs/1.png')

# print(os.path.exists('static/location_imgs'))
#
# mkdir_lambda = lambda x: os.mkdir(x) if not os.path.exists(x) else True
#
# print(mkdir_lambda('static/location_img1s'))




