from gateway import models
from gateway.views import views
from utils import handle_func


class OperateSensor(object):

    def __init__(self):
        pass

    def update_sensor(self, receive_data, conform, response):
        """
        更新传感器
        :param receive_data:
        :param conform:
        :param response:
        :return:
        """
        sensor_id = receive_data.pop('sensor_id')  # 删掉sensor_id以免被修改
        if conform:
            # 更新sensor数据
            models.Sensor_data.objects.filter(sensor_id=sensor_id).update(**receive_data)
            response['status'] = True
            response['msg'] = '更新任务成功'
            # 更新成功，同时同步数据库和调度器
            views.auto_Timing_time(network_id=receive_data['network_id'])
        else:
            response['msg'] = '输入时间和现有传感器时间冲突，请输入其他时间'

        return response

    def add_sensor(self, receive_data, sensor_id, conform, response):
        """
        增加传感器，先判断此传感器是否是软删除的传感器，如果是，则执行对应的更新任务，否则执行添加任务
        :param receive_data:
        :param sensor_id:
        :param conform:
        :param response:
        :return:
        """
        network_id = receive_data['network_id']
        is_soft_delete = handle_func.check_soft_delete(receive_data, network_id)
        if is_soft_delete:  # 是软删除的sensor
            print('是软删除......')
            if conform:
                # 添加sensor数据
                receive_data['delete_status'] = 0
                models.Sensor_data.objects.filter(network_id=network_id).update(**receive_data)
                response['status'] = True
                response['msg'] = '添加任务成功'
                # 添加成功，同时同步数据库和调度器
                views.auto_Timing_time()
            else:
                response['msg'] = '输入时间和现有传感器时间冲突，请输入其他时间'
        else:
            network_id_list = []
            network_ids = list(models.Sensor_data.objects.filter(delete_status=0).values('network_id'))
            for item in network_ids:
                network_id_list.append(item['network_id'])
            if sensor_id == "":
                response['msg'] = '传感器ID不能为空！'
            elif network_id == "":
                response['msg'] = '网络号不能为空！'
            elif network_id in network_id_list:
                response['msg'] = '已有此传感器，请检查此传感器ID和传感器网络号'
            elif conform:
                # 添加sensor数据
                print(receive_data)
                # 添加成功，同时同步数据库和调度器
                # 把'1.1.1.4'转化成16进制0x01010104
                hex_network_id = handle_func.str_hex_dec(network_id)
                command = "set 74 " + sensor_id + " " + str(int(hex_network_id, 16))
                print('command', command)
                # add_sensor_response = gw0.serCtrl.getSerialresp(command)
                # print('add_sensor_response', add_sensor_response.strip('\n'))
                add_sensor_response = 'ok'
                if add_sensor_response.strip('\n') == 'ok':
                    models.Sensor_data.objects.create(**receive_data)
                    response['status'] = True
                    response['msg'] = '添加任务成功'
                views.auto_Timing_time()
            else:
                response['msg'] = '输入时间和现有传感器时间冲突，请输入其他时间'

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
        # remove_sensor_response = gw0.serCtrl.getSerialresp(command)
        # print('remove_sensor_response', remove_sensor_response.strip('\n'))
        remove_sensor_response = 'ok'
        if remove_sensor_response.strip('\n') == 'ok':
            # models.Sensor_data.objects.filter(sensor_id=sensor_id).delete()
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
        header = 'update_gateway'
        result = {'status': True, 'message': '更新网关成功', 'gateway_data': gateway_data}
        handle_func.send_gwdata_to_server(views.client, topic, result, header)
        return result

    def add_gateway(self, gateway_data):
        models.Gateway.objects.create(**gateway_data)
        topic = gateway_data['network_id']
        header = 'add_gateway'
        result = {'status': True, 'message': '添加网关成功', 'gateway_data': gateway_data}
        handle_func.send_gwdata_to_server(views.client, topic, result, header)
        return result

