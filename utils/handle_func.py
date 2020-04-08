import threading, time, json
from GatewaySite.settings import headers_dict
from gateway.views import views
from gateway import models


def handle_recv_server_cmd(topic, payload):
    print('---------------------------------')
    print('payload', payload)
    header = payload['header']   # get_data_manually    update_sensor
    value = payload.get('data')
    def abc():
        if header == headers_dict['get_data_manually']:  # 手动获取
            print('取数.......')
            result = views.server_manual_get(value)
            send_gwdata_to_server(views.client, topic, result, headers_dict['gwdata'])
        elif header == headers_dict['update_sensor']:  # 更新传感器
            print('更新.......')
            response = views.receive_server_data(data=value)
            send_gwdata_to_server(views.client, topic, response, headers_dict['update_sensor'])
        elif header == headers_dict['add_sensor']:  # 添加传感器
            print('添加........')
            response = views.receive_server_data(data=value)
            send_gwdata_to_server(views.client, topic, response, headers_dict['add_sensor'])
        elif header == headers_dict['remove_sensor']:  # 删除传感器
            print('删除........')
            response = views.receive_server_data(data=value)
            send_gwdata_to_server(views.client, topic, response, headers_dict['remove_sensor'])
    if payload['id'] == 'server':
        single_threading = threading.Thread(target=abc)
        single_threading.start()


def check_online_of_sensor_status():
    """
    上电检查节点在线状态
    :param request:
    :return:
    """
    sensor_obj_list = models.Sensor_data.objects.all()
    # 准备发送的命令字符串  command = "get 65 1"
    for sensor_obj in sensor_obj_list.values('network_id', 'id'):
        try:
            network_id = sensor_obj['network_id']
            command = "get 65 " + network_id.rsplit('.', 1)[1]
            print('command', command)
            online_of_sensor_status_response = views.gw0.serCtrl.getSerialresp(command)
            print('online_of_sensor_status_response', online_of_sensor_status_response.strip('\n'))
            if online_of_sensor_status_response.strip('\n') == 'ok':
                models.Sensor_data.objects.filter(network_id=network_id).update(sensor_status=1)
            else:
                models.Sensor_data.objects.filter(network_id=network_id).update(sensor_status=0)

        except Exception as e:
            print(e, '检查节点失败')
    # 上电检查完所有节点后，发送sensor数据给server
    # if tcp_client_status:
    send_all_sensor(headers_dict)


def send_all_sensor(headers_dict):
    """
    发送所有传感器数据到server
    :param headers_dict:
    :return:
    """
    topic = models.GW_network_id.objects.values('network_id')[0]['network_id']  # gwntid
    sync_sensors = list(models.Sensor_data.objects.all().values())
    for item in sync_sensors:
        item['date_of_installation'] = str(item['date_of_installation'])
        item['gateway'] = topic
        item.pop('id')
    sync_sensors_dict = {'header': headers_dict['sync_sensors'], 'sync_sensors': sync_sensors}
    views.client.publish(topic, json.dumps(sync_sensors_dict))


def send_gwdata_to_server(client, topic, result, header):
    """
    网关取数后返回给服务器
    :param client:
    :param topic: 主题（gwntid）
    :param result: 返回结果
    :param header: 到服务端匹配的头信息
    :return:
    """
    result['header'] = header
    result['id'] = 'client'
    client.publish(topic, json.dumps(result))  # 网关取数后给服务器返回数据

