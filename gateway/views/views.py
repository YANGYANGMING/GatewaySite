from django.shortcuts import render, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from gateway import permissions
from GatewaySite import settings
from lib.log import Logger
from apscheduler.schedulers.background import BackgroundScheduler
from gateway.eelib.eelib.gateway import *
from gateway.eelib.eelib.message import *
from utils.mqtt_client import MQTT_Client
from utils import handle_func
from utils.operate_sensor import OperateSensor, OperateGateway
from queue import PriorityQueue
import serial
import threading


msg_file = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/message.txt'
msg_printer = MessagePrinter(msg_file)

gser = serial.Serial("/dev/ttyS3", 115200, timeout=1)
# gser = serial.Serial("/dev/ttyAMA0", 115200, timeout=1)

gw0 = Gateway(gser)
gwCtrl = GatewayCtrl()
operate_sensor = OperateSensor()
operate_gateway = OperateGateway()
log = Logger()

try:
    mqtt_client = MQTT_Client()
    client = mqtt_client.client
except Exception as e:
    print(e)

num = 0

gw_queue = PriorityQueue()

# Timing task start flag bit
TimingStatus = False

# Instantiate timer task
scheduler = BackgroundScheduler()
# sche_sync_sensors = BackgroundScheduler()
heart_timeout_sche = BackgroundScheduler()

# Gateway power on status is 0
if models.Gateway.objects.first():
    models.Gateway.objects.update(gw_status=0)

# Initialize original status infomation
if models.TimeStatus.objects.filter(id=1).exists():
    models.TimeStatus.objects.filter(id=1).update(timing_status='false', text_status='已暂停', button_status='暂停')
else:
    models.TimeStatus.objects.create(timing_status='false', text_status='已暂停', button_status='暂停')

# Initialize timing data after program restart
if models.Set_Time.objects.filter(id=1).exists():
    models.Set_Time.objects.filter(id=1).update(days=1, hours=0, minutes=0)
else:
    models.Set_Time.objects.create(days=1, hours=0, minutes=0)


def send_network_id_to_server_queue(network_id, true_header, val_dict=None, receive_data=None, level=10):
    """
    发送network到服务端队列，等待采样
    :param network_id:
    :param level:
    :return:
    """
    if network_id == '0.0.0.0':
        # Polling sensor
        snr_num = models.Sensor_data.objects.values('network_id').all()
        network_id_list = [item['network_id'] for item in snr_num]
        level = 8
    else:
        # Single sensor, manual data collection / automatic data collection
        network_id_list = [network_id]
    print('network_id_list', network_id_list)

    gateway_obj = models.Gateway.objects.values('Enterprise', 'gw_status').first()
    gw_status = gateway_obj['gw_status']
    enterprise = gateway_obj['Enterprise']
    print('gateway_obj', gateway_obj)
    header = 'send_network_id_to_queue'
    result = {'status': True, 'network_id_list': network_id_list, 'Enterprise': enterprise, 'level': level,
              'true_header': true_header, 'val_dict': val_dict, 'receive_data': receive_data}
    print('send_network_id_to_server_queue_result', result)
    if gw_status:  # 如果连接服务器成功，把network_id_list发送到服务器队列
        print("把network_id_list发送到服务器队列")
        handle_func.send_gwdata_to_server(client, 'pub', result, header)
    else:  # 如果连接服务器失败，把network_id_list发送到网关队列
        print("把network_id_list发送到网关队列")
        for network_id_item in network_id_list:
            gw_queue.put((level, json.dumps({'network_id': network_id_item,
                                             'true_header': true_header,
                                             'val_dict': val_dict,
                                             'receive_data': receive_data,
                                             })))


def auto_Timing_time(network_id=None):
    """
    Regular check ---- update/add
    Timed mode task: interval
    :return:
    """
    try:
        if network_id:
            # update sensor
            received_time_data = eval(models.Sensor_data.objects.filter(network_id=network_id).
                                      values('received_time_data')[0]['received_time_data'])
            st_temp = {'days': int(received_time_data['days']), 'hours': int(received_time_data['hours']),
                       'minutes': int(received_time_data['minutes'])}
            temp_trigger = scheduler._create_trigger(trigger='interval', trigger_args=st_temp)
            scheduler.modify_job('interval_time ' + network_id, trigger=temp_trigger)
            # After updating the data, you need to resume_job()
            jobs_status = models.Sensor_data.objects.filter(network_id=network_id).values('sensor_run_status')[0]['sensor_run_status']
            if jobs_status:  # if it is online status
                scheduler.resume_job('interval_time ' + network_id)
            print('update task' + network_id)

        db_job_id_list = []
        # All task time and sensor_id in the database
        db_job_list = list(models.Sensor_data.objects.filter(delete_status=0).values('network_id', 'received_time_data'))
        # The list of sensor_id and sensor_time for scheduled tasks that already exist in the scheduler
        sche_job_id_list = handle_func.job_id_list()

        # Compare: when adding or updating tasks in the database, add or update schedluer tasks
        for db_job in db_job_list:
            received_time_data_dict = eval(db_job['received_time_data'])
            jobs_id = 'interval_time ' + db_job['network_id']
            print(jobs_id)
            db_job_id_list.append(db_job['network_id'])
            # add sensor
            if db_job['network_id'] not in sche_job_id_list:
                scheduler.add_job(send_network_id_to_server_queue, 'interval', days=int(received_time_data_dict['days']),
                                  hours=int(received_time_data_dict['hours']), minutes=int(received_time_data_dict['minutes']),
                                  id=jobs_id, args=[db_job['network_id'], 'gwdata'])
                cur_sensor_run_status = models.Sensor_data.objects.filter(network_id=db_job['network_id']).values('sensor_run_status')[0]['sensor_run_status']
                # Pause the corresponding sensor when starting or restarting
                if not cur_sensor_run_status:
                    scheduler.pause_job(jobs_id)
                print('add task')

        # Remove/Compare: when a task is deleted in the database, the scheduler task is also deleted
        for sche_job_id in sche_job_id_list:
            if sche_job_id != '0.0.0.0':
                if sche_job_id not in db_job_id_list:
                    temp_sche_job_id = 'interval_time ' + sche_job_id
                    scheduler.remove_job(temp_sche_job_id)
                    print('remove %s seccess' % sche_job_id)
        scheduler.print_jobs()
    except Exception as e:
        print('auto_Timing_time:', e)


def time_job(network_id):
    """
    Perform sampling tasks
    :return:
    """
    global num
    gwData = {}
    print('network_id', network_id)
    try:
        # for network_id in snr_num_list:
        resend_num = 1
        while resend_num < 3:
            time_now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
            msg_printer.print2File("\r\ntime task: " + str(time_now) + "\r\n")
            print("num=" + str(num) + ",  " + str(time_now) + ', ' + network_id)
            num = num + 1
            r, gwData = gw0.sendData2Server(network_id)
            print(r.message)
            if not r.status:
                resend_num += 1
                if resend_num == 3:
                    models.Sensor_data.objects.filter(network_id=network_id).update(sensor_online_status=0)
                    break
            else:
                break
    except Exception as e:
        print('取数出错！', e)

    return gwData


def cal_heart_timeout():
    """
    心跳超时改变状态
    :return:
    """
    print('timeout......')
    models.Gateway.objects.update(gw_status=0)


try:
    """定时初始化"""
    scheduler.add_job(send_network_id_to_server_queue, 'interval', days=settings.initial_time['days'],
                      hours=settings.initial_time['hours'], minutes=settings.initial_time['minutes'],
                      id='interval_time 0.0.0.0', args=["0.0.0.0", "gwdata"])
    scheduler.start()
    # 加载程序时暂停定时器
    scheduler.pause_job('interval_time 0.0.0.0')
    print(scheduler.get_job('interval_time 0.0.0.0'))
except Exception as e:
    print('err:', e)
    scheduler.shutdown()


try:
    heart_timeout_sche.add_job(cal_heart_timeout, 'interval', minutes=settings.heart_timeout['minutes'],
                               seconds=settings.heart_timeout['seconds'], id='cal_heart_timeout')
    heart_timeout_sche.start()
except Exception as e:
    print(e)
    heart_timeout_sche.shutdown()


@login_required
def index(request):
    """
    首页
    :param request:
    :return:
    """

    latest_data = models.GWData.objects.values('id', 'network_id', 'network_id__alias', 'battery', 'temperature', 'thickness').order_by('-id')[:10]
    sensor_nums = models.Sensor_data.objects.all().count()
    all_sensor_list = models.Sensor_data.objects.values('network_id', 'alias', 'sensor_run_status', 'sensor_online_status').filter(delete_status=0)
    print('all_sensor_list', all_sensor_list)

    return render(request, 'index.html', locals())


@login_required
@permissions.check_permission
def config_time(request):
    """
    设置时间
    :param request:
    :return:
    """
    # 最新的X条数据
    latest_data = models.GWData.objects.values('id', 'network_id', 'time_tamp', 'battery', 'temperature', 'thickness', 'network_id__alias').order_by('-id')[:5]
    # 最新的定时时间/时间状态/手动设置id，用于刷新页面时保留输入信息
    latest_Timing_time = models.Set_Time.objects.filter(id=1).values('days', 'hours', 'minutes').first()
    latest_time_status = models.TimeStatus.objects.filter(id=1).values('timing_status', 'text_status', 'button_status').first()
    latest_set_id = request.session.get('latest_set_id', '')
    all_sensor_list = models.Sensor_data.objects.filter(delete_status=0).values('network_id', 'alias')

    context = {
        "Day_interval": [i for i in range(0, 32)],
        "Hour_interval": [i for i in range(0, 24)],
        "Minute_interval": [i for i in range(0, 60)],
    }

    ret = {'status': False, 'message': '提交失败'}
    if request.method == "GET":
        return render(request, 'gateway/config_time.html', locals())


@login_required
# @permissions.check_permission
def all_data_report(request):
    """
    全部数据
    :param request:
    :return:
    """
    data_obj = models.GWData.objects.values('id', 'network_id__alias', 'network_id', 'battery', 'temperature',
                                            'thickness', 'time_tamp').order_by('-id')

    return render(request, 'gateway/all_data_report.html', locals())


@login_required
# @permissions.check_permission
def thickness_report(request):
    """
    单个传感器厚度曲线
    :param request:
    :return:
    """
    # db中存在的数据
    # data_obj = models.GWData.objects.filter().values('network_id', 'network_id__alias').distinct()
    data_obj = models.Sensor_data.objects.filter(delete_status=0).values('network_id', 'alias').distinct()
    print(data_obj)
    return render(request, 'gateway/thickness_report.html', locals())


@login_required
@permissions.check_permission
def edit_sensor_params(request):
    """
    传感器参数详情
    :param request:
    :return:
    """
    context = {
        "cHz": [cHz for cHz in range(1, 4)],
        "gain": [gain for gain in range(60, 101)],
        "avg_time": [avg_time for avg_time in range(0, 11)],
        "Hz": [Hz for Hz in range(2, 5)],
        "Sample_depth": [Sample_depth for Sample_depth in range(0, 3)],
        "Sample_Hz": [200, 5000],
    }
    sensor_obj = models.Sensor_data.objects.filter(delete_status=0).order_by('-id')

    return render(request, "gateway/edit_sensor_params.html", locals())


@login_required
@permissions.check_permission
def sensor_manage(request):
    """
    传感器管理
    :param request:
    :return:
    """
    sensor_obj = models.Sensor_data.objects.all().order_by('-id')
    sensor_online_status = {'离线': 0, '在线': 1}
    sensor_run_status = {'开通': 1, '禁止': 0}
    sche_obj = scheduler.get_jobs()
    for sensor_item in sensor_obj:
        # 把start_date放进每个传感器对象中
        for ii in sche_obj:
            if sensor_item.network_id == ii.id.split(' ')[1]:
                sensor_item.start_date = str(ii.next_run_time).split('.')[0]
        received_time_data = models.Sensor_data.objects.filter(sensor_id=sensor_item.sensor_id).\
            values('sensor_id', 'received_time_data')

    return render(request, "gateway/sensor-manage.html", locals())


@csrf_exempt
@login_required
def set_timing_time(request):
    """
    设置轮询定时时间
    :param request:
    :return:
    """
    ret = {'status': False, 'message': '定时时间设置失败'}
    try:
        # if request.method == 'POST' and not btn_sample and not auto_operation:
        arr = request.POST.getlist('TimingDateList')
        if any(list(map(int, arr))):
            time_dict = handle_func.handle_data(arr)  # 处理数据
            print('time_dict', time_dict)
            models.Set_Time.objects.filter(id=1).update(**time_dict)
            start_Timing_time(request)
            auto_Timing_time()
            ret = {'status': True, 'message': '定时时间设置成功'}
            global TimingStatus
            TimingStatus = True
        else:
            ret['message'] = '时间不合法！'
    except Exception as e:
        print('set_Timing_time', e)
        return HttpResponse(json.dumps(ret))

    return HttpResponse(json.dumps(ret))


@csrf_exempt
@login_required
def save_status(request):
    """
    保存之前的状态
    :param request:
    :return:
    """
    ret = {'status': False, 'message': None}
    try:
        data_list = request.POST.get('data')
        data_list = json.loads(data_list)
        print('data_list', data_list)
        models.TimeStatus.objects.filter(id=1).update(**data_list)
        ret = {'status': True, 'message': 'success'}
    except Exception as e:
        print(e)
    return HttpResponse(json.dumps(ret))


@login_required
def start_Timing_time(request, reset=False):
    """
    设置/更新定时时间
    :param reset: 重置按钮标志位，如果为true，把定时模式暂停
    :return:
    """
    print('aaaaaaaa')
    st_temp = models.Set_Time.objects.filter(id=1).values('days', 'hours', 'minutes')[0]
    for k, v in st_temp.items():
        st_temp[k] = int(v)
    print('st_temp', st_temp)
    try:
        temp_trigger = scheduler._create_trigger(trigger='interval', trigger_args=st_temp)
        scheduler.modify_job('interval_time 0.0.0.0', trigger=temp_trigger)
        if reset:
            scheduler.pause_job('interval_time 0.0.0.0')
        else:
            scheduler.resume_job('interval_time 0.0.0.0')
            print('resume_job........')

        scheduler.get_job('interval_time 0.0.0.0')
    except Exception as e:
        print('start_Timing_time:', e)
        scheduler.shutdown()


@login_required
def pause_Timing_time(request):
    """
    暂停轮询定时时间
    :param request:
    :return:
    """
    ret = {'status': False, 'message': None}
    try:
        if TimingStatus:
            scheduler.pause_job('interval_time 0.0.0.0')
            scheduler.get_job('interval_time 0.0.0.0')
            ret = {'status': True, 'message': 'success'}
        print(TimingStatus)
    except Exception as e:
        print(e)
    return HttpResponse(json.dumps(ret))


@login_required
def resume_Timing_time(request):
    """
    恢复轮询定时时间
    :param request:
    :return:
    """
    ret = {'status': False, 'message': None}
    try:
        if TimingStatus:
            scheduler.resume_job('interval_time 0.0.0.0')
            # scheduler.pause_job('interval_time 0.0.0.0')
            scheduler.get_job('interval_time 0.0.0.0')
            ret = {'status': True, 'message': 'success'}
        print(TimingStatus)
    except Exception as e:
        print(e)
    return HttpResponse(json.dumps(ret))


@csrf_exempt
@login_required
def reset_Timing_time(request):
    """
    重置定时时间
    :param request:
    :return:
    """
    ret = {'status': False, 'message': None}
    try:
        models.Set_Time.objects.filter(id=1).update(days='1', hours='0', minutes='0')
        start_Timing_time(request, reset=True)
        scheduler.pause_job('interval_time 0.0.0.0')
        ret['status'] = True
        ret['message'] = 'success'
        global TimingStatus
        TimingStatus = False
    except Exception as e:
        print(e)
    return HttpResponse(json.dumps(ret))


@csrf_exempt
@login_required
def data_json_report(request, nid):
    """
    从数据库中获取数据进行绘图
    :param request:
    :param nid: 网关数据id
    :return:
    """
    response = []
    try:
        data_dict = models.GWData.objects.filter(id=nid).values('id', 'network_id', 'network_id__alias', 'data', 'thickness').first()
        data_list = list(enumerate(eval(data_dict['data'])))
        temp = {
            'name': "--名称：" + data_dict['network_id__alias'] + ' --厚度：' + data_dict['thickness'],
            'data': data_list
        }
        response.append(temp)
    except Exception as e:
        print(e)

    return HttpResponse(json.dumps(response))


@login_required
def thickness_json_report(request):
    """
    从数据库中获取厚度值进行绘图
    :param request:
    :return:
    """
    network_id = request.GET.get('network_id')
    alias = models.Sensor_data.objects.filter(network_id=network_id).values('alias')[0]['alias']
    response = {}
    try:
        data_obj = list(models.GWData.objects.filter(network_id=network_id).values('time_tamp', 'thickness'))
        thickness_avg = handle_func.cal_thickness_avg(data_obj)
        data_list = []
        for item in data_obj:
            data_temp = {}
            data_temp['y'] = float(item.pop('thickness'))
            data_temp['name'] = item.pop('time_tamp')
            data_list.append(data_temp)
        response['datas'] = [{'name': '厚度值', 'data': data_list}]
        response['alias'] = alias
        response['yAxis_max_limit'] = thickness_avg * 2
        response['thickness_avg'] = thickness_avg
    except Exception as e:
        print(e)

    return HttpResponse(json.dumps(response))


@login_required
@permissions.check_permission
def edit_sensor(request, sensor_id):
    """
    编辑传感器
    :param request:
    :return:
    """
    received_time_data = eval(models.Sensor_data.objects.filter(sensor_id=sensor_id).values('received_time_data')[0]['received_time_data'])
    sensor_obj = models.Sensor_data.objects.get(sensor_id=sensor_id)
    date_of_installation = str(sensor_obj.date_of_installation)
    sensor_type = {'ETM-100': 0}
    Importance = {'重要': 1, '一般': 0}
    material = models.Material.objects.values('id', 'name').all().order_by('id')
    context = {
        "day_interval": [i for i in range(0, 32)],
        "hour_interval": [i for i in range(0, 24)],
        "minute_interval": [i for i in range(0, 60)],
    }

    return render(request, "gateway/edit_sensor_time.html", locals())


@login_required
@permissions.check_permission
def edit_sensor_alarm_msg(request, sensor_id):
    """
    编辑传感器报警信息
    :param request:
    :return:
    """
    sensor_obj = models.Sensor_data.objects.get(sensor_id=sensor_id)

    return render(request, "gateway/edit_sensor_alarm_msg.html", locals())


@login_required
@permissions.check_permission
def add_sensor_page(request, network_id):
    """
    增加传感器
    :param request:
    :param network_id: 如果network_id=='new',说明是新增传感器,否则是恢复被软删除的network_id的传感器
    :return:
    """
    gateway_obj = models.Gateway.objects.exists()
    if gateway_obj:
        gwntid = models.Gateway.objects.values('network_id')[0]['network_id']
        gwntid_prefix = gwntid.rsplit('.', 1)[0]
        sensor_type = {'ETM-100': 0}
        Importance = {'一般': 0, '重要': 1}
        material = models.Material.objects.values('id', 'name').all().order_by('id')
        longitude = 0.0
        latitude = 0.0
        context = {
            "day_interval": [i for i in range(0, 32)],
            "hour_interval": [i for i in range(0, 24)],
            "minute_interval": [i for i in range(0, 60)],
        }
        return render(request, 'gateway/add_sensor.html', locals())
    else:
        # 添加网关
        gw_status = {'在线': 1, '离线': 0}

        return render(request, 'gateway/set_gateway.html', locals())


@login_required
@permissions.check_permission
def set_gateway_page(request):
    """
    设置网关页面
    :param request:
    :return:
    """
    gateway_obj = models.Gateway.objects.first()
    gw_status = {'在线': 1, '离线': 0}
    return render(request, 'gateway/set_gateway.html', locals())


@csrf_exempt
@permissions.check_permission
def set_gateway_json(request):
    """
    设置网关
    :param request:
    :return:
    """
    gateway_data = json.loads(request.POST.get('gateway_data'))
    gateway_obj = models.Gateway.objects.first()
    print(gateway_data)  # {'Enterprise': '中石油', 'name': '中石油1号网关', 'network_id': '0.0.1.0', 'gw_status': '1'}
    if gateway_obj:
        # update gateway
        result = operate_gateway.update_gateway(gateway_data, user=str(request.user))
    else:
        # add_gateway
        result = operate_gateway.add_gateway(gateway_data, user=str(request.user))
    log.log(result['status'], result['msg'], gateway_data['network_id'], str(request.user))

    return HttpResponse(json.dumps(result))


@csrf_exempt
@login_required
def get_gateway_networkid(request):
    """
    发送命令获取网关网络号
    :param request:
    :return:
    """
    result = {'status': False, 'gw_ntid': '未获取到网关网络号'}
    command = "get 78 "
    get_gwntid_response = gw0.serCtrl.getSerialData(command, timeout=5)
    print('get_gwntid_response', get_gwntid_response.strip('\n'))
    if get_gwntid_response:
        get_gwntid_response = handle_func.str_dec_hex(get_gwntid_response)
        print('get_gwntid_response', get_gwntid_response.strip('\n'))
        result = {'status': True, 'gw_ntid': get_gwntid_response}

    return HttpResponse(json.dumps(result))


@login_required
def test_signal_strength(request, network_id):
    """
    测试信号强度
    :param request:
    :param network_id:
    :return:
    """
    send_network_id_to_server_queue(network_id, "test_signal_strength", level=1)

    test_signal_strength_result = {'status': False, 'msg': ''}
    start_time = time.time()
    while (time.time() - start_time) < 70:  # 防止此时正在取数，设70秒最大值
        time.sleep(0.5)
        if handle_func.test_signal_strength_result:
            test_signal_strength_result = handle_func.test_signal_strength_result
            break

    handle_func.test_signal_strength_result = {}

    # resend_num = 0
    # command = "get 65 " + network_id.rsplit('.', 1)[1]
    # while resend_num < 2:  # 未收到数据后重发
    #     online_of_sensor_signal_strength_response = gw0.serCtrl.getSerialData(command, timeout=6)
    #     response_msg = online_of_sensor_signal_strength_response.strip('\n').split(',')[0]
    #     if response_msg == 'ok':
    #         models.Sensor_data.objects.filter(network_id=network_id).update(sensor_online_status=1)
    #         response_strength = online_of_sensor_signal_strength_response.strip('\n').split(',')[1]
    #         print('test_signal_strength_response_strength', response_strength)
    #         msg_of_signal_strength = handle_func.judgment_level_of_test_signal_strength(response_strength)
    #         result = {'status': True, 'msg': msg_of_signal_strength}
    #         break
    #     else:
    #         models.Sensor_data.objects.filter(network_id=network_id).update(sensor_online_status=0)
    #         resend_num += 1
    #         msg_of_signal_strength = handle_func.judgment_level_of_test_signal_strength(-1)
    #         result = {'status': False, 'msg': msg_of_signal_strength}

    return HttpResponse(json.dumps(test_signal_strength_result))


@login_required
@csrf_exempt
def judge_username_exist_json(request):
    """
    判断是否存在用户名
    :param request:
    :return:
    """
    response = {'status': False, 'msg': ''}
    name = request.POST.get('name')
    previous_name = request.POST.get('previouse_name')
    if name == previous_name:
        user_is_exist = None
    else:
        user_is_exist = models.UserProfile.objects.filter(name=name).exists()

    if user_is_exist:
        response = {'status': True, 'msg': '此用户已存在！'}

    return HttpResponse(json.dumps(response))


@csrf_exempt
def show_soundV_json(request):
    """
    查找显示声速
    :param request:
    :return:
    """
    if request.method == 'POST':
        selected_material_id = json.loads(request.POST.get('selected_material_id'))
        soundV = models.Material.objects.values('sound_V').get(id=selected_material_id)['sound_V']
        result = {'soundV': soundV}

        return HttpResponse(json.dumps(result))


def refresh_gw_status(request):
    """
    定时刷新网关与服务器连接状态
    :param request:
    :return:
    """
    try:
        gw_status = models.Gateway.objects.values('gw_status').first()['gw_status']
    except Exception as e:
        print(e)
        gw_status = False
    if gw_status:
        result = {'message': '<a href="#"><i style="font-size: larger" class="fa fa-circle text-green"></i>&nbsp;&nbsp;已连接服务器</a>'}
    else:
        result = {'message': '<a href="#"><i style="font-size: larger" class="fa fa-circle text-red"></i>&nbsp;&nbsp;未连接服务器</a>'}

    return HttpResponse(json.dumps(result))


@csrf_exempt
@login_required
@permissions.check_permission
def receive_gw_data(request):
    """
    接收网关的数据，用于在网关页面操作传感器的增删改操作
    :param request:
    :return:
    """
    if request.method == 'POST':

        receive_data = handle_func.handle_img_and_data(request)

        response = {'status': False, 'msg': '操作失败', 'receive_data': receive_data}
        print('receive_data', receive_data)  # {"received_time_data":{"month":[],"day":[],"hour":["1"],"mins":["1"]},"sensor_id":"536876188","alias":"1号传感器","network_id":"0.0.0.1","choice":"update"}

        sensor_id = receive_data['sensor_id']
        network_id = receive_data.get('network_id')
        choice = receive_data.pop('choice')
        location_img_json = receive_data.pop('location_img_json')

        # 更新
        if choice == 'update':
            response = operate_sensor.update_sensor(receive_data, response)
            log.log(response['status'], response['msg'], network_id, request.user)
            print('response', response)
            if response['status']:
                receive_data['location_img_json'] = location_img_json
                data = {'id': 'client', 'header': 'update_sensor', 'status': response['status'], 'msg': response['msg'],
                        'user': str(request.user), 'receive_data': receive_data}
                try:
                    client.publish('pub', json.dumps(data))  # 把网关更新的sensor数据发送给server
                except Exception as e:
                    print(e)

        # 添加
        elif choice == 'add':
            receive_data["choice"] = "add"
            receive_data["location_img_json"] = location_img_json
            send_network_id_to_server_queue(network_id, 'add_sensor', receive_data=receive_data, level=2)

        # 删除
        elif choice == 'remove':
            response = operate_sensor.remove_sensor(sensor_id, response)
            log.log(response['status'], response['msg'], network_id, request.user)
            if response['status']:
                receive_data['location_img_json'] = location_img_json
                data = {'id': 'client', 'header': 'remove_sensor', 'status': response['status'], 'msg': response['msg'],
                        'user': str(request.user), 'receive_data': receive_data}
                try:
                    client.publish('pub', json.dumps(data))  # 把网关删除的sensor数据发送给server
                except Exception as e:
                    print(e)

        return HttpResponse(json.dumps(response))


def receive_server_data(receive_data):
    """
    接收服务器的数据，用于在服务器页面操作传感器的增删改操作
    :param receive_data: 收到服务器的时间是已经在服务器端验证通过的时间，可以直接使用
    :return:
    """
    response = {'status': False, 'msg': '操作失败', 'receive_data': receive_data}
    print('receive_data=------------', receive_data)  # {"received_time_data":{"month":[],"day":[],"hour":["1"],"mins":["1"]},"sensor_id":"536876188","alias":"1号传感器","network_id":"0.0.0.1","choice":"update"}

    sensor_id = receive_data['sensor_id']
    choice = receive_data.pop('choice')
    location_img_json = receive_data.pop('location_img_json')

    received_time_data = receive_data.get('received_time_data')
    if received_time_data:  # 如果是更新报警信息
        if received_time_data['days'] == received_time_data['hours'] == received_time_data['minutes'] == '0':
            response['msg'] = '时间不合法！'
            return HttpResponse(json.dumps(response))

    # 更新
    if choice == 'update':
        if location_img_json:
            location_img_path_and_name = receive_data['location_img_path']
            location_img_path = location_img_path_and_name.rsplit('/', 1)[0] + '/'
            # 判断是是否存在路径
            handle_func.mkdir_path(path=location_img_path)
            location_img_bytes = eval(json.loads(location_img_json.strip('\r\n')))
            with open(location_img_path_and_name, 'wb') as f:
                f.write(location_img_bytes)

        response = operate_sensor.update_sensor(receive_data, response)
        # 先pop掉location_img_json,把receive_data更新给网关后,需要再给receive_data添上location_img_json,以便返回给server进行存储
        response['receive_data']['location_img_json'] = location_img_json

    # 添加
    elif choice == 'add':
        if location_img_json:
            location_img_path_and_name = receive_data['location_img_path']
            location_img_path = location_img_path_and_name.rsplit('/', 1)[0] + '/'
            # 判断是是否存在路径
            handle_func.mkdir_path(path=location_img_path)
            location_img_bytes = eval(json.loads(location_img_json.strip('\r\n')))
            with open(location_img_path_and_name, 'wb') as f:
                f.write(location_img_bytes)

        response = operate_sensor.add_sensor(receive_data, sensor_id, response)
        # 先pop掉location_img_json,把receive_data添加给网关后,需要再给receive_data添上location_img_json,以便返回给server进行存储
        response['receive_data']['location_img_json'] = location_img_json

    # 删除
    elif choice == 'remove':
        response = operate_sensor.remove_sensor(sensor_id, response)

    return response


@csrf_exempt
@login_required
@permissions.check_permission
def set_sensor_params(request):
    """
    设置模态框中的传感器参数
    :param request:
    :return:
    """
    result = {'status': False, 'msg': '设置参数中...'}
    val_dict = json.loads(request.POST.get('val_dict'))
    network_id = val_dict.pop('network_id')
    print('val_dict', val_dict)
    try:
        # 判断Sample_Hz参数是否合法
        if int(val_dict['Sample_Hz']) < 200 or int(val_dict['Sample_Hz']) > 5000:
            result = {'status': False, 'msg': '采样频率参数范围：200-5000'}
            return HttpResponse(json.dumps(result))

        send_network_id_to_server_queue(network_id, 'set_sensor_params', val_dict=val_dict, level=4)

    except Exception as e:
        print(e, '设置参数失败')

    # log.log(result['status'], result['msg'], network_id, str(request.user))

    return HttpResponse(json.dumps(result))


@csrf_exempt
@login_required
@permissions.check_permission
def manual_get(request, network_id):
    """
    网关手动触发任务
    :param request:
    :return:
    """
    result = {'status': False, 'message': "成功加入采样队列，请等待...", 'gwData': {}, 'network_id': network_id}
    request.session['latest_set_id'] = network_id
    if network_id == '':
        result['message'] = "没有选择传感器"
    else:
        send_network_id_to_server_queue(network_id, 'gwdata', level=6)

    return HttpResponse(json.dumps(result))


@csrf_exempt
def check_alias_to_update_sensor(request):
    """
    检查服务器中是否存在alias，为update sensor准备
    :param request:
    :return:
    """
    ret = {'check_alias_payload': '', 'msg': ''}
    gw_status = models.Gateway.objects.values('Enterprise', 'gw_status').first()['gw_status']
    if request.method == 'POST' and gw_status:
        alias = request.POST.get('alias')
        network_id = request.POST.get('network_id')
        result = {'alias': alias, 'network_id': network_id}
        header = 'check_alias'
        handle_func.send_gwdata_to_server(client, 'pub', result, header)
        start_time = time.time()
        ret = {'check_alias_payload': '', 'msg': ''}
        while (time.time() - start_time) < 2:
            if handle_func.check_alias_payload:
                check_alias_payload = handle_func.check_alias_payload['alias_is_exist']
                ret = {'check_alias_payload': check_alias_payload}
                if ret['check_alias_payload']:
                    ret['msg'] = '已存在此名称！'
                else:
                    ret['msg'] = ''
                break
        handle_func.check_alias_payload = {}

    return HttpResponse(json.dumps(ret))


def server_get_data(network_id):
    """
    服务器队列中的触发任务命令
    :param network_id:
    :return:
    """
    result = {'status': False, 'msg': '[%s]获取失败，传感器未响应' % network_id, 'gwData': {}, 'network_id': network_id}

    try:
        if network_id == '':
            result['msg'] = "没有选择传感器"
        else:
            # 需要返回网关数据
            gwData = time_job(network_id)
            if gwData != {}:
                result = {'status': True, 'msg': "[%s]获取成功" % network_id, 'gwData': gwData, 'network_id': network_id}
    except Exception as e:
        print(e)

    return result


def gw_get_data_func():
    """
    网关未连接服务器时，从网关自己队列中获取network_id进行取数
    :return:
    """
    while True:
        get_queue_data = gw_queue.get()
        print('get_queue_data', get_queue_data)
        gw_queue_1 = json.loads(get_queue_data[1])
        true_header = gw_queue_1.get('true_header')
        network_id = gw_queue_1.get('network_id')
        if true_header == "gwdata":
            time_job(network_id)
        elif true_header == "add_sensor":
            receive_server_data(gw_queue_1.get('receive_data'))
        elif true_header == "set_sensor_params":
            val_dict = gw_queue_1.get('val_dict')
            handle_func.set_sensor_params_func(network_id, val_dict)
        elif true_header == "test_signal_strength":
            network_id = gw_queue_1.get('network_id')
            handle_func.handle_test_signal_strength(network_id)
            print("test_signal_strength.......................................", network_id)


# 网关取数队列线程
threading.Thread(target=gw_get_data_func).start()


auto_Timing_time()
# handle_func.check_online_of_sensor_status()



