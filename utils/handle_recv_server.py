import threading, time, json, re
from GatewaySite.settings import headers_dict
from utils import handle_func


handle_func = handle_func.Handle_func()


def handle_recv_server(topic, payload):
    # print(topic)
    # print(payload)
    header = payload['header']   # get_data_manually    update_sensor

    def handle_recv_threading():
        # 反射
        getattr(handle_func, header)(topic, payload)

        # if header == headers_dict['heart_ping']:    # 心跳
        #     handle_func.heart_ping(topic, payload)
        #
        # elif header == headers_dict['get_data_manually']:  # server端手动获取
        #     handle_func.get_data_manually(topic, payload)
        #
        # elif header == headers_dict['update_sensor']:      # 更新传感器
        #     handle_func.update_sensor(topic, payload)
        #
        # elif header == headers_dict['add_sensor']:         # 添加传感器
        #     handle_func.add_sensor(topic, payload)
        #
        # elif header == headers_dict['remove_sensor']:      # 删除传感器
        #     handle_func.remove_sensor(topic, payload)
        #
        # elif header == headers_dict['check_time_between_gws']:      # 接收判断时间冲突结果
        #     handle_func.check_time_between_gws(topic, payload)
        #
        # elif header == headers_dict['resume_sensor']:      # 恢复传感器
        #     print('恢复传感器')
        #     handle_func.resume_sensor(topic, payload)
        #
        # elif header == headers_dict['pause_sensor']:       # 禁止传感器
        #     print('禁止传感器')
        #     handle_func.pause_sensor(topic, payload)
        #
        # elif header == headers_dict['update_gateway']:       # 更新网关
        #     print('更新网关')
        #     handle_func.update_gateway(topic, payload)

    if payload['id'] == 'server':  # 开线程防止IO阻塞
        single_threading = threading.Thread(target=handle_recv_threading)
        single_threading.start()




