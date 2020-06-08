from gateway import models
from gateway.views import views
from GatewaySite.settings import headers_dict
from utils import handle_func


class OperateSensor(object):

    def __init__(self):
        pass

    def update_sensor(self, receive_data, response):
        """
        更新传感器
        :param receive_data:
        :param response:
        :return:
        """
        sensor_id = receive_data.pop('sensor_id')  # 删掉sensor_id以免被修改
        alias = receive_data['alias']
        alias_list = list(models.Sensor_data.objects.filter(delete_status=0).values('alias', 'sensor_id'))
        for item in alias_list:
            if alias == item['alias'] and sensor_id != item['sensor_id']:
                response['msg'] = '此传感器名称已被使用'
                return response

        # 更新sensor数据
        models.Sensor_data.objects.filter(sensor_id=sensor_id).update(**receive_data)
        response['status'] = True
        response['msg'] = '更新任务成功'
        # 更新成功，同时同步数据库和调度器
        views.auto_Timing_time(network_id=receive_data['network_id'])

        return response

    def add_sensor(self, receive_data, sensor_id, response):
        """
        增加传感器，先判断此传感器是否是软删除的传感器，如果是，则执行对应的更新任务，否则执行添加任务
        :param receive_data:
        :param sensor_id:
        :param response:
        :return:
        """
        network_id = receive_data['network_id']
        alias = receive_data['alias']
        # 判断network_id是否符合此网关格式
        gw_network_id = models.Gateway.objects.values('network_id').first()['network_id']
        if gw_network_id.rsplit('.', 1)[0] != network_id.rsplit('.', 1)[0]:
            response['msg'] = '网络号格式不正确，网络号应该是【%s.x】' % gw_network_id.rsplit('.', 1)[0]
            return response
        # 判断此传感器是否是软删除的传感器
        is_soft_delete = handle_func.check_soft_delete(network_id)
        if is_soft_delete:  # 是软删除的sensor
            print('是软删除......')
            # 添加sensor数据
            receive_data['delete_status'] = 0
            models.Sensor_data.objects.filter(network_id=network_id).update(**receive_data)
            response['status'] = True
            response['msg'] = '添加任务成功'
            # 添加成功，同时同步数据库和调度器
            views.auto_Timing_time()
        else:
            network_id_list = []
            sensor_id_list = []
            alias_list = []
            network_ids = list(models.Sensor_data.objects.filter(delete_status=0).values('network_id', 'sensor_id', 'alias'))
            for item in network_ids:
                network_id_list.append(item['network_id'])
                sensor_id_list.append(item['sensor_id'])
                alias_list.append(item['alias'])
            if sensor_id == "":
                response['msg'] = '传感器ID不能为空！'
            elif network_id == "":
                response['msg'] = '网络号不能为空！'
            elif network_id in network_id_list or sensor_id in sensor_id_list:
                response['msg'] = '已有此传感器，请检查此传感器ID和传感器网络号'
            elif alias in alias_list:
                response['msg'] = '此传感器名称已被使用'

            # 添加sensor数据
            print(receive_data)
            # 添加成功，同时同步数据库和调度器
            # 把'1.1.1.4'转化成16进制0x01010104
            hex_network_id = handle_func.str_hex_dec(network_id)
            command = "set 74 " + sensor_id + " " + str(int(hex_network_id, 16))
            print('command', command)
            add_sensor_response = views.gw0.serCtrl.getSerialresp(command)
            print('add_sensor_response', add_sensor_response.strip('\n'))
            # add_sensor_response = 'ok'
            if add_sensor_response.strip('\n') == 'ok':
                models.Sensor_data.objects.create(**receive_data)
                response['status'] = True
                response['msg'] = '添加任务成功'
            views.auto_Timing_time()

        return response

    def remove_sensor(self, sensor_id, response):
        """
        根据对应的sensor_id删除传感器
        :param sensor_id:
        :param response:
        :return:
        """
        command = "set 74 " + sensor_id + " 0"
        print('command', command)
        print("response['receive_data']['forcedelete']", response['receive_data']['forcedelete'])
        if response['receive_data']['forcedelete']:
            models.Sensor_data.objects.filter(sensor_id=sensor_id).delete()
        else:
            models.Sensor_data.objects.filter(sensor_id=sensor_id).update(delete_status=1)  # 数据库软删除
        response['status'] = True
        response['msg'] = '删除任务成功'
        # 删除成功，同时同步数据库和调度器
        views.auto_Timing_time()

        return response


class OperateGateway(object):

    def __init__(self):
        pass

    def update_gateway(self, gateway_data):
        models.Gateway.objects.all().update(**gateway_data)
        topic = gateway_data['network_id']
        header = headers_dict['update_gateway']
        result = {'status': True, 'msg': '更新网关成功', 'gateway_data': gateway_data}
        handle_func.send_gwdata_to_server(views.client, topic, result, header)
        return result

    def add_gateway(self, gateway_data):
        models.Gateway.objects.create(**gateway_data)
        topic = gateway_data['network_id']
        header = headers_dict['add_gateway']
        result = {'status': True, 'msg': '添加网关成功', 'gateway_data': gateway_data}
        handle_func.send_gwdata_to_server(views.client, topic, result, header)
        return result

