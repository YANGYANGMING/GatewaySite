import threading, time, json, re
from GatewaySite.settings import headers_dict
from gateway.views import views
from gateway import models

class Handle_func(object):
    def __init__(self):
        pass

    def heart_ping(self, topic, payload):
        """

        :param topic:
        :param payload:
        :return:
        """
        print('心跳.......')
        gwntid = models.Gateway.objects.values('network_id')[0]['network_id']
        result = {'gwntid': gwntid}
        send_gwdata_to_server(views.client, topic, result, headers_dict['heart_ping'])

    def get_data_manually(self, topic, payload):
        """
        手动获取数据
        :param topic:
        :param payload:
        :return:
        """
        print('取数.......')
        result = views.server_manual_get(payload.get('data'))
        send_gwdata_to_server(views.client, topic, result, headers_dict['gwdata'])

    def update_sensor(self, topic, payload):
        """
        更新传感器
        :param topic:
        :param payload:
        :return:
        """
        print('更新.......')
        response = views.receive_server_data(data=payload.get('data'))
        send_gwdata_to_server(views.client, topic, response, headers_dict['update_sensor'])

    def add_sensor(self, topic, payload):
        """
        增加传感器
        :param topic:
        :param payload:
        :return:
        """
        print('添加........')
        response = views.receive_server_data(data=payload.get('data'))
        send_gwdata_to_server(views.client, topic, response, headers_dict['add_sensor'])

    def remove_sensor(self, topic, payload):
        """
        删除传感器
        :param topic:
        :param payload:
        :return:
        """
        print('删除........')
        response = views.receive_server_data(data=payload.get('data'))
        send_gwdata_to_server(views.client, topic, response, headers_dict['remove_sensor'])

    def resume_sensor(self, topic, payload):
        """
        恢复传感器
        :param topic:
        :param payload:
        :return:
        """
        ret = {'status': False, 'message': '开通失败'}
        try:
            jobs_id = 'cron_time ' + payload["network_id"]
            views.scheduler.resume_job(jobs_id)
            models.Sensor_data.objects.filter(network_id=payload["network_id"]).update(sensor_run_status=1)
            ret = {'status': True, 'message': '开通成功', 'network_id': payload["network_id"]}
            send_gwdata_to_server(views.client, topic, ret, headers_dict['resume_sensor'])
        except Exception as e:
            send_gwdata_to_server(views.client, topic, ret, headers_dict['resume_sensor'])
            print(e)

    def pause_sensor(self, topic, payload):
        """
        禁止传感器
        :param topic:
        :param payload:
        :return:
        """
        ret = {'status': False, 'message': '禁止失败'}
        try:
            jobs_id = 'cron_time ' + payload["network_id"]
            views.scheduler.pause_job(jobs_id)
            models.Sensor_data.objects.filter(network_id=payload["network_id"]).update(sensor_run_status=0)
            ret = {'status': True, 'message': '禁止成功', 'network_id': payload["network_id"]}
            send_gwdata_to_server(views.client, topic, ret, headers_dict['pause_sensor'])
        except Exception as e:
            send_gwdata_to_server(views.client, topic, ret, headers_dict['pause_sensor'])
            print(e)

    def update_gateway(self, topic, payload):
        """
        更新网关
        :param topic:
        :param payload:
        :return:
        """
        views.operate_gateway.update_gateway(payload['gateway_data'])


def send_gwdata_to_server(client, topic, result, header):
    """
    网关给服务器返回数据
    :param client:
    :param topic: 主题（gwntid）
    :param result: 返回结果
    :param header: 到服务端匹配的头信息
    :return:
    """
    result['header'] = header
    result['id'] = 'client'
    client.publish(topic, json.dumps(result))  # 网关给服务器返回数据



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
                models.Sensor_data.objects.filter(network_id=network_id).update(sensor_online_status=1)
            else:
                models.Sensor_data.objects.filter(network_id=network_id).update(sensor_online_status=0)

        except Exception as e:
            print(e, '检查节点失败')
    # 上电检查完所有节点后，发送sensor数据给server
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
    result = {'sync_sensors': sync_sensors}
    send_gwdata_to_server(views.client, topic, result, headers_dict['sync_sensors'])


def str_hex_dec(network_id):
    """
    16进制字符串ip转换成十进制   eg: '0.0.1.3' >> '259'
    :param network_id:
    :return:
    """
    hex_network_id = '0x'
    for network_item in network_id.split('.'):
        if len(hex(int(network_item)).split('0x')[1]) == 1:
            hex_network_id += '0' + hex(int(network_item)).split('0x')[1]
        else:
            hex_network_id += hex(int(network_item)).split('0x')[1]
    return hex_network_id


def str_dec_hex(network_id):
    """
    十进制转16进制字符ip   eg: '259' >> '0.0.1.3'
    :param network_id:
    :return:
    """
    network_id_hex = str(hex(int(network_id))).split('x')[1]  # 103
    network_id_str = (8 - len(network_id_hex)) * '0' + network_id_hex
    pattern = re.compile('.{2}')
    network_id_str_list = pattern.findall(network_id_str)
    network_id_list = [str(int(item)) for item in network_id_str_list]
    network_id = '.'.join(network_id_list)

    return network_id


def update_sensor_data(all_vals):
    """
    参数设置成功后，更新传感器信息列表
    :param all_vals: 设置的传感器参数
    :return:
    """
    try:
        models.Sensor_data.objects.filter(sensor_id=all_vals['sensor_id']).update(
            cHz=all_vals['cHz'],
            gain=all_vals['gain'],
            avg_time=all_vals['avg_time'],
            Hz=all_vals['Hz'],
            Sample_depth=all_vals['Sample_depth'],
            Sample_Hz=all_vals['Sample_Hz'],
        )
    except Exception as e:
        print(e)


def handle_data(arr):
    """
    处理定时模式发过来的数据
    :param arr: [{'month': temp_list[0]}, {'day': temp_list[1]}, {'hour': temp_list[2]}, {'mins': temp_list[3]}]
    :return:
    """
    # ['', '', '', '1,4,8']
    temp_list = []
    if len(arr) == 4:
        if arr[0] == arr[1] == arr[2] == arr[3] == '':
            return temp_list
        else:
            for item in arr:
                if item:
                    temp_list.append(item)
                else:
                    temp_list.append('*')
            time_list = [{'month': temp_list[0]}, {'day': temp_list[1]}, {'hour': temp_list[2]},
                         {'mins': temp_list[3]}]
        return time_list
    if len(arr) == 3:
        if arr[0] == arr[1] == arr[2] == '' or arr[0] == arr[1] == arr[2] == 0:
            return temp_list
        else:
            for item in arr:
                if item:
                    temp_list.append(item)
                else:
                    temp_list.append('0')
            time_list = [{'day': temp_list[0]}, {'hour': temp_list[1]},
                         {'mins': temp_list[2]}]

        return time_list


def handle_receive_data(time_data):
    """
    处理接收的用于增加/修改的时间
    :param time_data:
    :return:
    """
    for k, v in time_data.items():
        if v == []:
            time_data[k] = '*'
        else:
            v_temp = ''
            for i in v:
                v_temp += i + ','
                time_data[k] = v_temp[: -1]
    return time_data


def judge_time(received_time_data_dict, network_id):
    """
    判断时间是否冲突，判断方法：先对比mins，如果mins有重复时间或者有'*'，以对比mins的方法对比hour的值，
    如果hour有重复时间，对比month和day，一旦发现有重复时间，conform = False，并且跳出循环
    :param received_time_data_dict: 接收到的时间字典：{'month': '2', 'day': '*', 'hour': '6', 'mins': '0,30'}
    :param sche_job_time_list: 任务调度器中的任务时间：
                        [{'year': '*', 'month': '2,5', 'day': '*', 'mins': '0', 'hour': '6'},
                        {'year': '*', 'month': '1,5', 'day': '*', 'mins': '29', 'hour': '18'},
                        {'year': '*', 'month': '1', 'day': '*', 'mins': '29', 'hour': '18'},
                        {'year': '*', 'month': '*', 'day': '*', 'mins': '*', 'hour': '*'}]
    :return:
    """
    sche_job_time_list = []
    # 不验证正在修改的传感器的时间
    for job_obj in views.scheduler.get_jobs():
        if job_obj.id.split(' ')[1] != network_id:
            sche_job_time_list.append({'year': str(job_obj.trigger.fields[0]),
                                       'month': str(job_obj.trigger.fields[1]),
                                       'day': str(job_obj.trigger.fields[2]),
                                       'hour': str(job_obj.trigger.fields[5]),
                                       'mins': str(job_obj.trigger.fields[6])})
    conform = True
    print('sche_job_time_list', sche_job_time_list)
    for sche_item in sche_job_time_list:
        # check mins
        if [ii for ii in received_time_data_dict['mins'].split(',') if ii in sche_item['mins'].split(',')] != [] \
                or sche_item['mins'] == '*' or received_time_data_dict['mins'] == '*':
            # check hour
            if [ii for ii in received_time_data_dict['hour'].split(',') if ii in sche_item['hour'].split(',')] != [] \
                    or sche_item['hour'] == '*' or received_time_data_dict['hour'] == '*':
                # check day
                if [ii for ii in received_time_data_dict['day'].split(',') if
                    ii in sche_item['day'].split(',')] != [] \
                        or sche_item['day'] == '*' or received_time_data_dict['day'] == '*':
                    # check month
                    if [ii for ii in received_time_data_dict['month'].split(',') if
                        ii in sche_item['month'].split(',')] != [] \
                            or sche_item['month'] == '*' or received_time_data_dict['month'] == '*':
                        # check year
                        if [ii for ii in ['*'] if ii in sche_item['year'].split(',')] != [] or sche_item[
                            'year'] == '*':
                            conform = False
                            break
    print('conform', conform)
    return conform


def check_gwntid(ntid_response):
    """
    检查gwntid合法性
    :param ntid_response:
    :return:
    """
    success = True

    return success


def check_soft_delete(receive_data, network_id):
    """
    添加传感器是验证此传感器是否已软删除
    :param receive_data:
    :return:
    """
    all_network_id_list = models.Sensor_data.objects.filter(delete_status=1).values('network_id')
    for sensor_item in all_network_id_list:
        if network_id == sensor_item['network_id']:
            return True
    return False












