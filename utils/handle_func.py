import threading, time, json, re, os
from functools import reduce
from GatewaySite.settings import headers_dict, heart_timeout
from gateway.views import views
from gateway import models
from PIL import Image


class Handle_func(object):

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
        # 接收到心跳后赋值：gw_status=1
        models.Gateway.objects.update(gw_status=1)

        gwntid = models.Gateway.objects.values('network_id')[0]['network_id']
        result = {'gwntid': gwntid}
        send_gwdata_to_server(views.client, topic, result, headers_dict['heart_ping'])

    def get_data(self, topic, payload):
        """
        接收服务器的获取数据指令，并执行
        :param topic:
        :param payload:
        :return:
        """
        print('取数.......')
        result = views.server_get_data(payload.get('data'))
        views.log.log(result['status'], result['msg'], result.get('network_id'))
        send_gwdata_to_server(views.client, topic, result, headers_dict['gwdata'])

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
        send_gwdata_to_server(views.client, topic, response, headers_dict['update_sensor'])

    def add_sensor(self, topic, payload):
        """
        接收服务器的增加传感器指令，并执行
        :param topic:
        :param payload:
        :return:
        """
        print('添加........')
        response = views.receive_server_data(payload.get('data'))
        views.log.log(response['status'], response['msg'], payload.get('data').get('network_id'), payload.get('user'))
        send_gwdata_to_server(views.client, topic, response, headers_dict['add_sensor'])

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
        send_gwdata_to_server(views.client, topic, response, headers_dict['remove_sensor'])

    def resume_sensor(self, topic, payload):
        """
        接收服务器的恢复传感器指令，并执行
        :param topic:
        :param payload:
        :return:
        """
        ret = {'status': False, 'msg': '开通失败'}
        try:
            jobs_id = 'cron_time ' + payload["network_id"]
            views.scheduler.resume_job(jobs_id)
            views.scheduler.print_jobs()
            models.Sensor_data.objects.filter(network_id=payload["network_id"]).update(sensor_run_status=1)
            ret = {'status': True, 'msg': '开通成功', 'network_id': payload["network_id"]}
            send_gwdata_to_server(views.client, topic, ret, headers_dict['resume_sensor'])
        except Exception as e:
            send_gwdata_to_server(views.client, topic, ret, headers_dict['resume_sensor'])
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
            jobs_id = 'cron_time ' + payload["network_id"]
            views.scheduler.pause_job(jobs_id)
            views.scheduler.print_jobs()
            models.Sensor_data.objects.filter(network_id=payload["network_id"]).update(sensor_run_status=0)
            ret = {'status': True, 'msg': '禁止成功', 'network_id': payload["network_id"]}
            send_gwdata_to_server(views.client, topic, ret, headers_dict['pause_sensor'])
        except Exception as e:
            send_gwdata_to_server(views.client, topic, ret, headers_dict['pause_sensor'])
            print(e)
        views.log.log(ret['status'], ret['msg'], payload.get('network_id'), payload.get('user'))

    def update_gateway(self, topic, payload):
        """
        接收服务器的更新网关指令，并执行
        :param topic:
        :param payload:
        :return:
        """
        ret = views.operate_gateway.update_gateway(payload['gateway_data'])
        views.log.log(ret['status'], ret['msg'], topic, payload.get('user'))


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
        if exist_img_path:
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
    sensor_obj_list = models.Sensor_data.objects.filter(delete_status=0)
    # 准备发送的命令字符串  command = "get 65 1"
    for sensor_obj in sensor_obj_list.values('network_id', 'id'):
        resend_num = 1
        try:
            network_id = sensor_obj['network_id']
            command = "get 65 " + network_id.rsplit('.', 1)[1]
            print('command', command)
            while resend_num < 3:  # 未收到数据后重发
                online_of_sensor_status_response = views.gw0.serCtrl.getSerialresp(command)
                print('online_of_sensor_status_response', online_of_sensor_status_response.strip('\n'))
                if online_of_sensor_status_response.strip('\n') == 'ok':
                    models.Sensor_data.objects.filter(network_id=network_id).update(sensor_online_status=1)
                    break
                else:
                    models.Sensor_data.objects.filter(network_id=network_id).update(sensor_online_status=0)
                    resend_num += 1

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
    topic = models.Gateway.objects.values('network_id')[0]['network_id']  # gwntid
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
    print('time_data', time_data)
    for k, v in time_data.items():
        if not v:
            time_data[k] = '*'
        else:
            v_temp = ''
            for i in v:
                v_temp += i + ','
                time_data[k] = v_temp[: -1]
    return time_data


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
    sche_job_time_list = []
    for job_obj in views.scheduler.get_jobs():
        sche_job_id_list.append(job_obj.id.split(' ')[1])
        sche_job_time_list.append(
            {'month': str(job_obj.trigger.fields[1]), 'day': str(job_obj.trigger.fields[2]),
             'hour': str(job_obj.trigger.fields[5]), 'mins': str(job_obj.trigger.fields[6])})

    return sche_job_id_list, sche_job_time_list


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
    selected_user_permissions_list = list_dict_duplicate_removal(selected_user_permissions_list)
    return cur_user_all_permissions_list, selected_user_permissions_list


def list_dict_duplicate_removal(distinct_list):
    """
    给列表中的字典去重
    :param distinct_list:
    :return:
    """
    run_function = lambda x, y: x if y in x else x + [y]
    return reduce(run_function, [[], ] + distinct_list)


##########################################################
handle_func = Handle_func()


def handle_recv_server(topic, payload):

    def handle_recv_threading():
        # 反射
        header = payload['header']  # get_data    update_sensor
        getattr(handle_func, header)(topic, payload)

    if payload['id'] == 'server':  # 开线程防止IO阻塞
        single_threading = threading.Thread(target=handle_recv_threading)
        single_threading.start()

##########################################################












