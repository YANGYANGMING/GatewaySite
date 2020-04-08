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


# receive_data = """['{"time_data":{"month":[],"day":[],"hour":["9"],"mins":["50","51"]}}', '{"sensor_id":"10010001201908230004"}', '{"alias":"4号传感器"}', '{"remove":"false"}']"""
# # time_data = eval(receive_data[0])['time_data']  # {'month': [], 'day': [], 'hour': ['9'], 'mins': ['50', '51']}
# # print(time_data)
# receive_data = eval(receive_data)
# print(type(receive_data))
# for sensor_obj in models.Sensor_data.objects.all().values('network_id', 'id'):
#     network_id = sensor_obj['network_id']
#     is_exist = models.Sensor_online_status.objects.filter(sensor__network_id=network_id).exists()
#     print(is_exist)
#     models.Sensor_online_status.objects.filter(sensor_id=sensor_obj['id']).update(sensor_status=1)

# a = '0.0.1.2'
# b = hex_network_id = '0x' + ''.join(a.split('.'))
# print(str(int(hex_network_id, 16)))
# hex_network_id = '0x'
# for network_item in '0.0.1.4'.split('.'):
#     if len(hex(int(network_item)).split('0x')[1]) == 1:
#         hex_network_id += '0' + hex(int(network_item)).split('0x')[1]
#     else:
#         hex_network_id += hex(int(network_item)).split('0x')[1]
# print(hex_network_id)
# print(str(int(hex_network_id, 16)))
d = {'status': True, 'msg': '更新任务成功', 'receive_data': {'received_time_data': {'month': '*', 'day': '*', 'hour': '2', 'mins': '2'}, 'alias': '1号传感器', 'network_id': '0.0.1.1', 'sensor_type': '0', 'Importance': '0', 'date_of_installation': '2020-03-24', 'initial_thickness': '10.0', 'alarm_thickness': '8.0', 'alarm_battery': '50', 'area': '一区', 'location': '1号出料管道处', 'assembly_crewman': 'yyy', 'location_img_path': '', 'description': '1号出料管道腐蚀测量'}, 'header': 'update_sensor'}
key = list(d.keys())[0]
value = d.get(key)
print(value)
