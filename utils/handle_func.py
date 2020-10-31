import threading, time, json, re, os
from functools import reduce
from GatewaySite.settings import headers_dict, heart_timeout
from gateway.views import views
from gateway import models
from PIL import Image


check_sensor_params_payload = {}
check_GW_alias_payload = {}
test_signal_strength_result = {}


class HandleFunc(object):

    def __init__(self):
        pass

    def heart_ping(self, topic, payload):
        """
        接收心跳
        :param topic:
        :param payload:
        :return:
        """
        temp_trigger = views.heart_timeout_sche._create_trigger(trigger='interval', trigger_args=heart_timeout)
        views.heart_timeout_sche.modify_job('cal_heart_timeout', trigger=temp_trigger)
        # After updating the data, you need to resume_job()
        views.heart_timeout_sche.resume_job('cal_heart_timeout')
        if models.Gateway.objects.exists():
            # 接收到心跳后赋值：gw_status=1
            models.Gateway.objects.update(gw_status=1)
            gwntid = models.Gateway.objects.values('network_id')[0]['network_id']
            result = {'gwntid': gwntid}
            send_gwdata_to_server(views.client, 'pub', result, headers_dict['heart_ping'])

    def get_data(self, topic, payload):
        """
        接收服务器的获取数据指令，并执行
        :param topic:
        :param payload:
        :return:
        """
        print('取数.......')
        result = views.server_get_data(payload.get('data'))
        # 检查是否允许发送采集到的数据给本地服务器
        if models.UploadData.objects.values('upload_data_to_local_server').first()['upload_data_to_local_server']:
            views.log.log(result['status'], result['msg'], result.get('network_id'))
            send_gwdata_to_server(views.client, 'pub', result, headers_dict['gwdata'])
            # MQTT websocket传输通道未加密，删除获取的数据信息gwData，只返回提示信息
            del result['gwData']
            send_gwdata_to_server(views.client, topic, result, headers_dict['gwdata'])  # 发送给MQTT websocket，用于显示给指定订阅用户界面

    def update_sensor(self, topic, payload):
        """
        接收服务器的更新传感器指令，并执行
        :param topic:
        :param payload:
        :return:
        """
        print('更新.......')
        response = views.receive_server_data(payload.get('data'))
        views.log.log(response['status'], response['msg'], payload.get('data').get('network_id'), payload.get('user'))
        print('response....', response)
        response['user'] = payload.get('user')
        send_gwdata_to_server(views.client, 'pub', response, headers_dict['update_sensor'])  # 发送给MQTT后端服务器，用于处理数据
        # # MQTT websocket传输通道未加密，删除获取的数据信息receive_data，只返回提示信息
        response['network_id'] = response['receive_data']['network_id']
        del response['receive_data']
        send_gwdata_to_server(views.client, topic, response, headers_dict['update_sensor'])  # 发送给MQTT websocket，用于显示给指定订阅用户界面

    def add_sensor(self, topic, payload):
        """
        接收服务器的增加传感器指令，并执行
        :param topic:
        :param payload:
        :return:
        """
        print('添加........')
        print('payload', payload)
        print('topic', topic)
        response = views.receive_server_data(payload.get('data'))
        views.log.log(response['status'], response['msg'], payload.get('data').get('network_id'))
        response['user'] = payload.get('user')
        send_gwdata_to_server(views.client, 'pub', response, headers_dict['add_sensor'])
        # # MQTT websocket传输通道未加密，删除获取的数据信息receive_data，只返回提示信息
        response['network_id'] = response['receive_data']['network_id']
        del response['receive_data']
        send_gwdata_to_server(views.client, topic, response, headers_dict['add_sensor'])  # 发送给MQTT websocket，用于显示给指定订阅用户界面

    def remove_sensor(self, topic, payload):
        """
        接收服务器的删除传感器指令，并执行
        :param topic:
        :param payload:
        :return:
        """
        print('删除........')
        response = views.receive_server_data(payload.get('data'))
        views.log.log(response['status'], response['msg'], payload.get('data').get('network_id'), payload.get('user'))
        response['user'] = payload.get('user')
        send_gwdata_to_server(views.client, 'pub', response, headers_dict['remove_sensor'])
        # # MQTT websocket传输通道未加密，删除获取的数据信息receive_data，只返回提示信息
        response['network_id'] = response['receive_data']['network_id']
        del response['receive_data']
        send_gwdata_to_server(views.client, topic, response, headers_dict['remove_sensor'])  # 发送给MQTT websocket，用于显示给指定订阅用户界面

    def resume_sensor(self, topic, payload):
        """
        接收服务器的恢复传感器指令，并执行
        :param topic:
        :param payload:
        :return:
        """
        ret = {'status': False, 'msg': '开通失败'}
        try:
            jobs_id = 'interval_time ' + payload["network_id"]
            views.scheduler.resume_job(jobs_id)
            views.scheduler.print_jobs()
            models.Sensor_data.objects.filter(network_id=payload["network_id"]).update(sensor_run_status=1)
            ret = {'status': True, 'msg': '开通成功', 'network_id': payload["network_id"]}
            ret['user'] = payload.get('user')
            send_gwdata_to_server(views.client, 'pub', ret, headers_dict['resume_sensor'])
        except Exception as e:
            ret['user'] = payload.get('user')
            send_gwdata_to_server(views.client, 'pub', ret, headers_dict['resume_sensor'])
            print(e)
        views.log.log(ret['status'], ret['msg'], payload.get('network_id'), payload.get('user'))

    def pause_sensor(self, topic, payload):
        """
        接收服务器的禁止传感器指令，并执行
        :param topic:
        :param payload:
        :return:
        """
        ret = {'status': False, 'msg': '禁止失败'}
        try:
            jobs_id = 'interval_time ' + payload["network_id"]
            views.scheduler.pause_job(jobs_id)
            views.scheduler.print_jobs()
            models.Sensor_data.objects.filter(network_id=payload["network_id"]).update(sensor_run_status=0)
            ret = {'status': True, 'msg': '禁止成功', 'network_id': payload["network_id"]}
            ret['user'] = payload.get('user')
            send_gwdata_to_server(views.client, 'pub', ret, headers_dict['pause_sensor'])
        except Exception as e:
            ret['user'] = payload.get('user')
            send_gwdata_to_server(views.client, 'pub', ret, headers_dict['pause_sensor'])
            print(e)
        views.log.log(ret['status'], ret['msg'], payload.get('network_id'), payload.get('user'))

    def set_sensor_params(self, topic, payload):
        """
        接收服务器的设置传感器参数（增益）指令，并执行
        :param topic:
        :param payload:
        :return:
        """
        try:
            val_dict = payload['val_dict']
            network_id = payload['network_id']
            result = set_sensor_params_func(network_id, val_dict)

            send_gwdata_to_server(views.client, 'pub', result, "set_sensor_params")
            # # MQTT websocket传输通道未加密，删除获取的数据信息params_dict，只返回提示信息
            del result['params_dict']
            send_gwdata_to_server(views.client, topic, result, "set_sensor_params")  # 发送给MQTT websocket，用于显示给指定订阅用户界面
        except Exception as e:
            print(e, '设置参数失败')

    def update_gateway(self, topic, payload):
        """
        接收服务器的更新网关指令，并执行
        :param topic:
        :param payload:
        :return:
        """
        ret = views.operate_gateway.update_gateway(payload['gateway_data'], payload.get('user'))
        views.log.log(ret['status'], ret['msg'], topic, payload.get('user'))

    def check_sensor_params_is_exists(self, topic, payload):
        """
        接收服务器检查的alias是否存在的结果
        :param topic:
        :param payload:
        :return:
        """
        global check_sensor_params_payload
        check_sensor_params_payload = payload

    def check_GW_alias(self, topic, payload):
        """
        接收服务器检查的alias是否存在的结果
        :param topic:
        :param payload:
        :return:
        """
        global check_GW_alias_payload
        check_GW_alias_payload = payload

    def test_signal_strength(self, topic, payload):
        """
        接收服务器的测试信号强度的命令
        :param topic:
        :param payload:
        :return:
        """
        network_id = payload['network_id']
        handle_test_signal_strength(network_id)


class HandleImgs(object):
    """处理图片"""

    def __init__(self):
        pass

    def get_size(self, file):
        """获取文件大小：KB"""
        size = os.path.getsize(file)
        return size / 1024

    def get_outfile(self, infile, outfile):
        """拼接输出文件地址"""
        if outfile:
            return outfile
        dir, suffix = os.path.splitext(infile)
        outfile = '{}-out{}'.format(dir, suffix)
        return outfile

    def compress_image(self, infile, outfile='', mb=100, step=10, quality=80):
        """不改变图片尺寸压缩到指定大小
        :param infile: 压缩源文件
        :param outfile: 压缩文件保存地址
        :param mb: 压缩目标，KB
        :param step: 每次调整的压缩比率
        :param quality: 初始压缩比率
        :return: 压缩文件地址，压缩文件大小
        """
        o_size = self.get_size(infile)
        if o_size <= mb:
            return infile
        outfile = self.get_outfile(infile, outfile)
        while o_size > mb:
            im = Image.open(infile)
            im.save(outfile, quality=quality)
            if quality - step < 0:
                break
            quality -= step
            o_size = self.get_size(outfile)
        # 删除原文件，修改新文件名称
        old_file_name = infile
        os.remove(infile)
        os.rename(outfile, old_file_name)

    def resize_image(self, infile, outfile='', x_s=400):
        """修改图片尺寸
        :param infile: 图片源文件
        :param outfile: 重设尺寸文件保存地址
        :param x_s: 设置的宽度
        :return:
        """
        im = Image.open(infile)
        x, y = im.size
        y_s = int(y * x_s / x)
        out = im.resize((x_s, y_s), Image.ANTIALIAS)
        outfile = self.get_outfile(infile, outfile)
        out.save(outfile)
        # 删除原文件，修改新文件名称
        old_file_name = infile
        os.remove(infile)
        os.rename(outfile, old_file_name)


def handle_img_and_data(request):
    """
    压缩剪裁图片，合并数据格式
    :param request:
    :return:
    """
    handleimgs = HandleImgs()
    data = json.loads(request.POST.get('data'))
    exist_img_path = data.pop('exist_img_path')
    location_img_obj = request.FILES.get('location_img_obj')
    # 判断是否有路径，没有就创建
    gw_network_id = models.Gateway.objects.values('network_id')[0]['network_id']
    Base_img_path = mkdir_path(gw_network_id=gw_network_id)
    if location_img_obj:
        img_name = location_img_obj.name
        # 写图片
        with open(Base_img_path + location_img_obj.name, 'wb') as f:
            f.write(location_img_obj.read())
        # 压缩图片
        handleimgs.compress_image(Base_img_path + location_img_obj.name)
        # 裁剪图片
        handleimgs.resize_image(Base_img_path + location_img_obj.name)
        # 处理数据格式
        with open(Base_img_path + location_img_obj.name, 'rb') as ff:
            img_bytes = ff.read()
        img_json = json.dumps(str(img_bytes))
        data['location_img_json'] = img_json
        data['location_img_path'] = Base_img_path + img_name
    else:
        data['location_img_json'] = ''
        if exist_img_path and exist_img_path != 'None':
            data['location_img_path'] = Base_img_path + exist_img_path.rsplit('/', 1)[1]
    return data


def mkdir_path(path=None, gw_network_id=None):
    """
    判断是否有路径，没有就创建
    :return:
    """
    if path:  # server发送过来的path
        if not os.path.exists(path):
            os.mkdir(path)
    elif gw_network_id:  # gw前端传过来的gw_network_id
        path = 'static/location_imgs_%s/' % gw_network_id
        if not os.path.exists(path):
            os.mkdir(path)
    return path


def set_sensor_params_func(network_id, val_dict):
    """
    设置参数功能函数
    :return:
    """
    alias = models.Sensor_data.objects.values('alias').get(network_id=network_id)['alias']
    # 准备发送的命令字符串  cmd_str = "set 0001 2 60 4 2 2 500"
    cmd_str = str(" " + val_dict['cHz'] + " " + val_dict['gain'] + " " + val_dict[
        'avg_time'] + " " + val_dict['Hz'] + " " + val_dict['Sample_depth'] + " " + val_dict['Sample_Hz'])
    command = "set 71 " + network_id.rsplit('.', 1)[1] + cmd_str
    print('command', command)
    set_val_response = views.gw0.serCtrl.getSerialData(command, timeout=7)
    print('set_val_response', set_val_response.strip('\n'))
    # set_val_response = 'ok'
    if set_val_response.strip('\n') == 'ok':
        update_sensor_data(val_dict)
        models.Sensor_data.objects.filter(network_id=network_id).update(**val_dict)
        result = {'status': True, 'network_id': network_id, 'msg': '[%s]设置参数成功' % alias, 'params_dict': val_dict}
    else:
        result = {'status': False, 'network_id': network_id, 'msg': '[%s]设置参数失败' % alias, 'params_dict': val_dict}

    views.log.log(result['status'], result['msg'], network_id)

    return result


def handle_test_signal_strength(network_id):
    """
    测试信号强度
    :param network_id:
    :return:
    """
    command = "get 65 " + network_id.rsplit('.', 1)[1]
    online_of_sensor_signal_strength_response = views.gw0.serCtrl.getSerialData(command, timeout=7)
    # online_of_sensor_signal_strength_response = 'ok, 40'
    response_msg = online_of_sensor_signal_strength_response.strip('\n').split(',')[0]
    if response_msg == 'ok':
        models.Sensor_data.objects.filter(network_id=network_id).update(sensor_online_status=1)
        response_strength = online_of_sensor_signal_strength_response.strip('\n').split(',')[1]
        print('test_signal_strength_response_strength', response_strength)
        msg_of_signal_strength = judgment_level_of_test_signal_strength(response_strength)
        result = {'status': True, 'msg': msg_of_signal_strength}
    else:
        models.Sensor_data.objects.filter(network_id=network_id).update(sensor_online_status=0)
        msg_of_signal_strength = judgment_level_of_test_signal_strength(-1)
        result = {'status': False, 'msg': msg_of_signal_strength}

    global test_signal_strength_result
    test_signal_strength_result = result


def send_gwdata_to_server(client, topic, result, header):
    """
    网关给服务器返回数据
    :param client:
    :param topic: 主题（'pub'）
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
    sensor_obj_list = models.Sensor_data.objects.filter(delete_status=0)
    # 准备发送的命令字符串  command = "get 65 1"
    for sensor_obj in sensor_obj_list.values('network_id', 'id'):
        try:
            network_id = sensor_obj['network_id']
            command = "get 65 " + network_id.rsplit('.', 1)[1]
            print('command', command)
            online_of_sensor_status_response = views.gw0.serCtrl.getSerialData(command, timeout=7)
            response_msg = online_of_sensor_status_response.strip('\n').split(',')[0]
            print('online_of_sensor_status_response_msg', response_msg)
            if response_msg == 'ok':
                models.Sensor_data.objects.filter(network_id=network_id).update(sensor_online_status=1)
                response_strength = online_of_sensor_status_response.strip('\n').split(',')[1]
                print('online_of_sensor_status_response_strength', response_strength)
            else:
                models.Sensor_data.objects.filter(network_id=network_id).update(sensor_online_status=0)

        except Exception as e:
            print(e, '检查节点失败')
    # 上电检查完所有节点后，发送sensor数据给server
    send_all_sensor()


def send_all_sensor():
    """
    发送所有传感器数据到server
    :param headers_dict:
    :return:
    """
    try:
        topic = models.Gateway.objects.values('network_id')[0]['network_id']  # gwntid
        sync_sensors = list(models.Sensor_data.objects.all().values())
        for item in sync_sensors:
            item['date_of_installation'] = str(item['date_of_installation'])
            item['gateway'] = topic
            item.pop('id')
        result = {'status': True, 'sync_sensors': sync_sensors, 'msg': "同步传感器数据成功"}
        send_gwdata_to_server(views.client, 'pub', result, headers_dict['sync_sensors'])
    except Exception as e:
        print(e)


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
    hex_network_id = str(int(hex_network_id, 16))

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
    network_id_list = [str(int(item, 16)) for item in network_id_str_list]
    network_id = '.'.join(network_id_list)

    return network_id


def check_network_id(network_id):
    """
    检查network_id合法性
    :param network_id:
    :return:
    """
    try:
        ntid_split_list = network_id.split('.')
        a = ntid_split_list[0]
        b = ntid_split_list[1]
        c = ntid_split_list[2]
        d = ntid_split_list[3]
        if 0 <= int(a) < 255 and 0 <= int(b) < 255 and 0 <= int(c) < 255 and 0 <= int(d) < 255 and len(ntid_split_list) == 4:
            return True
        else:
            return False

    except Exception as e:
        print('network_id不合法', e)
        return False


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
    :param arr: [{'days': temp_list[1]}, {'hours': temp_list[2]}, {'minutes': temp_list[3]}]
    :return:
    """
    # ['', '', '1,4,8']
    temp_list = []
    for item in arr:
        if item:
            temp_list.append(item)
        else:
            temp_list.append('0')
    time_dict = {'days': temp_list[0], 'hours': temp_list[1], 'minutes': temp_list[2]}

    return time_dict


def check_soft_delete(network_id):
    """
    添加传感器时验证此传感器是否已软删除
    :param network_id:
    :return:
    """
    all_network_id_list = models.Sensor_data.objects.filter(delete_status=1).values('network_id')
    for sensor_item in all_network_id_list:
        if network_id == sensor_item['network_id']:
            return True
    return False


def job_id_list():
    """
    A list of the sensor_id of a scheduled task that already exists in the scheduler
    :return:
    """
    sche_job_id_list = []
    for job_obj in views.scheduler.get_jobs():
        sche_job_id_list.append(job_obj.id.split(' ')[1])

    return sche_job_id_list


def cal_thickness_avg(data_list):
    """
    计算厚度值平均值
    :param data_list:
    :return:
    """
    thickness_total = 0
    thickness_num = len(data_list)
    for item in data_list:
        thickness_total += float(item['thickness'])
    thickness_avg = thickness_total / thickness_num

    return thickness_avg


def show_selected_permissions(request, Group, nid):
    """
    在编辑用户页面显示选中的用户权限
    :return:
    """
    # 当前登录用户所拥有的角色权限和被手动分配的权限
    cur_user_role_permissions_list = list(
        Group.objects.values('permissions__id', 'permissions__name').filter(user=request.user.id))
    cur_user_manual_assign_permissions_list = models.UserProfile.objects.get(
        id=request.user.id).user_permissions.values('id', 'name').all()
    # 当前被选中要修改的用户所拥有的角色权限和被手动分配的权限
    selected_user_role_permissions_list = list(Group.objects.values('permissions__id').filter(user=nid))
    selected_user_manual_assign_permissions_list = models.UserProfile.objects.get(id=nid).user_permissions.values(
        'id').all()
    # 变换key保持一致
    cur_user_all_permissions_list = []
    for item in cur_user_manual_assign_permissions_list:
        item_temp = {}
        item_temp['permissions__id'] = item['id']
        item_temp['permissions__name'] = item['name']
        cur_user_all_permissions_list.append(item_temp)
    # 当前登录用户所拥有的角色权限和被手动分配的权限的总和
    cur_user_all_permissions_list += cur_user_role_permissions_list
    cur_user_all_permissions_list = list_dict_duplicate_removal(cur_user_all_permissions_list)
    # 当前被选中要修改的用户所拥有的角色权限和被手动分配的权限的总和
    selected_user_permissions_list = [item['permissions__id'] for item in selected_user_role_permissions_list] + \
                                     [item['id'] for item in selected_user_manual_assign_permissions_list]
    if not selected_user_permissions_list[0]:  # 如果没有设置权限，默认为-1，防止前端console显示出错
        selected_user_permissions_list[0] = -1
    selected_user_permissions_list = list_dict_duplicate_removal(selected_user_permissions_list)
    return cur_user_all_permissions_list, selected_user_permissions_list


def judgment_level_of_test_signal_strength(response_strength):
    """
    判断信号强度等级
    :return:
    """
    try:
        response_strength = int(response_strength)
    except Exception as e:
        response_strength = -1
        print("-1====", e)
    if 0 < response_strength < 20:
        msg_of_signal_strength = '测试信号强度 <b style="color: red">弱</b>'
    elif 20 <= response_strength < 50:
        msg_of_signal_strength = '测试信号强度 <b style="color: orange">中</b>'
    elif response_strength >= 50:
        msg_of_signal_strength = '测试信号强度 <b style="color: green">强</b>'
    else:
        msg_of_signal_strength = '测试信号强度 <b style="color: red">失联</b>'

    return msg_of_signal_strength


def list_dict_duplicate_removal(distinct_list):
    """
    给列表中的字典去重
    :param distinct_list:
    :return:
    """
    run_function = lambda x, y: x if y in x else x + [y]
    return reduce(run_function, [[], ] + distinct_list)


def handle_data_to_send_administration(data):
    """
    处理发送给特检局的数据
    :param data:
    :return:
    """
    network_id = data['network_id']
    Sensor_obj = models.Sensor_data.objects.values('sensor_id', 'material', 'sensor_run_status', 'received_time_data',
                                              'Hz', 'alarm_battery', 'battery').get(network_id=network_id)
    material_id = Sensor_obj['material']
    sensor_id = Sensor_obj['sensor_id']
    Sensor_Mac = sensor_id[-10:]
    material_obj = models.Material.objects.values('name', 'sound_V', 'temperature_co').get(id=material_id)
    material_name = material_obj['name']
    temperature = round(float(data['temperature']), 2)
    thickness = round(float(data['thickness']), 2)
    # 计算true_sound_V
    sound_V = material_obj['sound_V']
    temperature_co = material_obj['temperature_co']
    true_sound_V = float(sound_V - ((temperature - 25) * temperature_co))
    # 设备开闭状态
    sensor_status = True if Sensor_obj['sensor_run_status'] else False
    # 计算当前时间
    Current_T = data['time_tamp']
    # 超声频率
    Ultrasonic_Freq = float(Sensor_obj['Hz']) * 1000
    # 转定时时间格式
    received_time_data = eval(Sensor_obj['received_time_data'])
    Gauge_Cycle = str(int(received_time_data['days']) * 24 + int(received_time_data['hours'])) + ":00:00"
    # 电量 --> 电压
    battery = 5.0 + round(float(Sensor_obj['battery']) / 100, 1)
    alarm_battery = 5.0 + round(float(Sensor_obj['alarm_battery']) / 100, 1)
    DATA = {
        "Current_T": Current_T,
        "Sensor_Mac": Sensor_Mac,
        "Gauge_Cycle": Gauge_Cycle,
        "Material_Type": "45",
        "Material_Temp": temperature,
        "Environmental_Temp": 30.00,
        "Sound_Velocity": true_sound_V,
        "Voltage": battery,
        "LIM_Voltage": alarm_battery,
        "Ultrasonic_Freq": Ultrasonic_Freq,
        "Time_Cycle": "72:00:00",
        "Status": sensor_status,
        "Thickness": [
            {"Sensor_NO": sensor_id, "Thickness": thickness},
        ]
    }
    return DATA


##########################################################
handle_func = HandleFunc()


def handle_recv_server(topic, payload):

    def handle_recv_threading():
        # 反射
        header = payload['header']  # get_data    update_sensor
        getattr(handle_func, header)(topic, payload)

    if payload['id'] == 'server':  # 开线程防止IO阻塞
        single_threading = threading.Thread(target=handle_recv_threading)
        single_threading.start()

##########################################################












