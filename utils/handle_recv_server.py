import threading, time, json, re
from GatewaySite.settings import headers_dict
from gateway.views import views
from gateway import models
from utils import handle_func


handle_func = handle_func.Handle_func()


def handle_recv_server(topic, payload):
    print('---------------------------------')
    # print(topic)
    # print(payload)
    header = payload['header']   # get_data_manually    update_sensor
    def abc():
        if header == headers_dict['heart_ping']:    # 心跳
            handle_func.heart_ping(topic, payload)

        elif header == headers_dict['get_data_manually']:  # 手动获取
            handle_func.get_data_manually(topic, payload)

        elif header == headers_dict['update_sensor']:      # 更新传感器
            handle_func.update_sensor(topic, payload)

        elif header == headers_dict['add_sensor']:         # 添加传感器
            handle_func.add_sensor(topic, payload)

        elif header == headers_dict['remove_sensor']:      # 删除传感器
            handle_func.remove_sensor(topic, payload)

        elif header == headers_dict['resume_sensor']:      # 恢复传感器
            print('恢复传感器')
            handle_func.resume_sensor(topic, payload)

        elif header == headers_dict['pause_sensor']:       # 禁止传感器
            print('禁止传感器')
            handle_func.pause_sensor(topic, payload)

        elif header == headers_dict['update_gateway']:       # 更新网关
            print('更新网关')
            handle_func.update_gateway(topic, payload)

    if payload['id'] == 'server':  # 开线程防止IO阻塞
        single_threading = threading.Thread(target=abc)
        single_threading.start()




