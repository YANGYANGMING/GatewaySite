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
        receive_data.pop('sensor_id')  # 删掉sensor_id以免被修改
        network_id = receive_data['network_id']
        # 判断填写的network_id是否合法
        gwntid = models.Gateway.objects.values('network_id')[0]['network_id']
        if network_id.rsplit('.', 1)[0] + '.0' != gwntid:
            response['msg'] = '传感器网络号有误，需填写%s.x格式' % network_id.rsplit('.', 1)[0]

        alias = receive_data['alias']
        alias_list = list(models.Sensor_data.objects.filter(delete_status=0).values('alias', 'network_id'))
        for item in alias_list:
            if alias == item['alias'] and network_id != item['network_id']:
                response['msg'] = '此传感器名称已被使用'
                return response

        # 更新sensor数据
        models.Sensor_data.objects.filter(network_id=network_id).update(**receive_data)
        response['status'] = True
        response['msg'] = '更新传感器成功'
        # 更新成功，同时同步数据库和调度器
        views.auto_Timing_time(network_id=network_id)

        return response

    def add_sensor(self, receive_data, sensor_id, response):
        """
        增加传感器，先判断此传感器是否是软删除的传感器，如果是，则执行对应的更新传感器，否则执行添加传感器
        :param receive_data:
        :param sensor_id:
        :param response:
        :return:
        """
        network_id = receive_data['network_id']
        alias = receive_data['alias']
        # 判断填写的network_id是否合法
        gwntid = models.Gateway.objects.values('network_id')[0]['network_id']
        if network_id.rsplit('.', 1)[0] + '.0' != gwntid:
            response['msg'] = '传感器网络号有误，需填写%s.x格式' % network_id.rsplit('.', 1)[0]
            return response

        # 判断此传感器是否是软删除的传感器
        is_soft_delete = handle_func.check_soft_delete(network_id)
        if is_soft_delete:  # 是软删除的sensor
            print('是软删除......')
            # 添加sensor数据
            receive_data['delete_status'] = 0
            models.Sensor_data.objects.filter(network_id=network_id).update(**receive_data)
            response['status'] = True
            response['msg'] = '添加传感器成功'
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
            else:
                # 添加sensor数据
                print(receive_data)
                # 添加成功，同时同步数据库和调度器
                # 把'0.0.1.3'转化成'259'
                hex_network_id = handle_func.str_hex_dec(network_id)
                command = "set 74 " + sensor_id + " " + hex_network_id
                print('command', command)
                # add_sensor_response = views.gw0.serCtrl.getSerialData(command, timeout=6)
                # print('add_sensor_response', add_sensor_response.strip('\n'))
                add_sensor_response = 'ok'
                if add_sensor_response.strip('\n') == 'ok':
                    models.Sensor_data.objects.create(**receive_data)
                    response['status'] = True
                    response['msg'] = '添加传感器成功'
                    # 添加成功，同时同步数据库和调度器
                    views.auto_Timing_time()
                else:
                    response['msg'] = '添加传感器失败，传感器未响应'

        return response

    def remove_sensor(self, sensor_id, response):
        """
        根据对应的sensor_id删除传感器
        :param sensor_id:
        :param response:
        :return:
        """
        response['msg'] = '删除传感器失败'
        print("response['receive_data']['forcedelete']", response['receive_data']['forcedelete'])
        if response['receive_data']['forcedelete']:
            models.Sensor_data.objects.filter(sensor_id=sensor_id).delete()
        else:
            models.Sensor_data.objects.filter(sensor_id=sensor_id).update(delete_status=1)  # 数据库软删除
        response['status'] = True
        response['msg'] = '删除传感器成功'
        # 删除成功，同时同步数据库和调度器
        views.auto_Timing_time()

        return response


class OperateGateway(object):

    def __init__(self):
        pass

    def update_gateway(self, gateway_data, user):
        result = {'status': False, 'msg': '更新网关失败'}
        try:
            models.Gateway.objects.all().update(**gateway_data)
            header = headers_dict['update_gateway']
            result = {'status': True, 'msg': '更新网关成功', 'gateway_data': gateway_data, 'user': user}
            handle_func.send_gwdata_to_server(views.client, 'pub', result, header)
        except Exception as e:
            print(e)
        return result

    def add_gateway(self, gateway_data, user):
        result = {'status': False, 'msg': '更新网关失败'}
        try:
            models.Gateway.objects.create(**gateway_data)
            header = 'add_gateway'
            result = {'status': True, 'msg': '添加网关成功', 'gateway_data': gateway_data, 'user': user}
            handle_func.send_gwdata_to_server(views.client, 'pub', result, header)
        except Exception as e:
            print(e)
        return result

