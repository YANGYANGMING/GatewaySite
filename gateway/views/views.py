from django.shortcuts import render, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from gateway import permissions
from GatewaySite import settings
from lib.log import Logger
from apscheduler.schedulers.background import BackgroundScheduler
from gateway.eelib.eelib.gateway import *
from gateway.eelib.eelib.message import *
from utils.mqtt_client import MQTT_Client
from utils import handle_func
from utils.operate_sensor import OperateSensor, OperateGateway
from utils.socket_client import sign_and_communicate_with_server
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
    log.log(False, e)

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
        log.log(False, 'auto_Timing_time出错！%s' % e, network_id)


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
        log.log(False, '取数出错！%s' % e, network_id)
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
@csrf_exempt
def all_data_report(request):
    """
    全部数据
    :param request:
    :return:
    """
    if request.method == "GET":
        return render(request, 'gateway/all_data_report.html')
    elif request.method == 'POST':
        draw = int(request.POST.get('draw'))  # 记录操作次数
        start = int(request.POST.get('start'))  # 起始位置
        length = int(request.POST.get('length'))  # 每页显示数据量
        search_key = request.POST.get('search[value]')  # 搜索关键字
        order_column_id = request.POST.get('order[0][column]')  # 排序字段索引
        order_column_rule = request.POST.get('order[0][dir]')  # 排序规则：ase/desc

        querysets = models.GWData.objects.values('id', 'network_id', 'network_id__alias', 'battery',
                                                    'time_tamp', 'thickness', 'temperature').all()

        order_column_dict = {'0': 'id', '1': 'network_id__alias', '2': 'network_id', '3': 'time_tamp',
                             '4': 'battery', '5': 'temperature', '6': 'thickness'}
        all_count = querysets.count()

        if search_key:
            querysets = query_filter(search_key, querysets)
        if order_column_rule == 'desc':
            querysets = querysets.order_by('-%s' % order_column_dict[order_column_id])
        if order_column_rule == 'asc':
            querysets = querysets.order_by(order_column_dict[order_column_id])

        filter_count = querysets.count()
        querysets = querysets[start: start + length]

        for oper_item in querysets:
            oper_item['operation'] = '<a href="javascript:;" style="cursor: pointer;" onclick="GetData(this);">' \
                                     '<i class="fa fa-pencil"></i> 数据详情</a>'

        dic = {
            'draw': draw,
            'recordsTotal': all_count,
            'recordsFiltered': filter_count,
            'data': list(querysets),
        }

        return HttpResponse(json.dumps(dic))


# 搜索
def query_filter(search_key, querysets):
    q = Q()
    q.connector = "OR"
    filter_field = ['network_id__network_id', 'network_id__alias', 'time_tamp', 'temperature', 'battery',
                    'thickness']
    for filter_item in filter_field:
        q.children.append(("%s__contains" % filter_item, search_key))
    result = querysets.filter(q)

    return result


@login_required
def thickness_report(request):
    """
    单个传感器厚度曲线
    :param request:
    :return:
    """
    # db中存在的数据
    # data_obj = models.GWData.objects.filter().values('network_id', 'network_id__alias').distinct()
    data_obj = models.Sensor_data.objects.filter(delete_status=0).values('network_id', 'alias').distinct()
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
            models.Set_Time.objects.filter(id=1).update(**time_dict)
            start_Timing_time(request)
            auto_Timing_time()
            ret = {'status': True, 'message': '定时时间设置成功'}
            global TimingStatus
            TimingStatus = True
        else:
            ret['message'] = '时间不合法！'
    except Exception as e:
        print('设置轮询定时时间', e)
        log.log(False, '设置轮询定时时间失败！%s' % e)
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
        models.TimeStatus.objects.filter(id=1).update(**data_list)
        ret = {'status': True, 'message': 'success'}
    except Exception as e:
        print(e)
        log.log(False, "save_status: %s" % e)
    return HttpResponse(json.dumps(ret))


@login_required
def start_Timing_time(request, reset=False):
    """
    设置/更新定时时间
    :param reset: 重置按钮标志位，如果为true，把定时模式暂停
    :return:
    """
    st_temp = models.Set_Time.objects.filter(id=1).values('days', 'hours', 'minutes')[0]
    for k, v in st_temp.items():
        st_temp[k] = int(v)
    try:
        temp_trigger = scheduler._create_trigger(trigger='interval', trigger_args=st_temp)
        scheduler.modify_job('interval_time 0.0.0.0', trigger=temp_trigger)
        if reset:
            scheduler.pause_job('interval_time 0.0.0.0')
        else:
            scheduler.resume_job('interval_time 0.0.0.0')

        scheduler.get_job('interval_time 0.0.0.0')
    except Exception as e:
        print('start_Timing_time:', e)
        log.log(False, "start_Timing_time: %s" % e)
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
    except Exception as e:
        print(e)
        log.log(False, "pause_Timing_time: %s" % e)
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
    except Exception as e:
        print(e)
        log.log(False, "resume_Timing_time: %s" % e)
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
        log.log(False, "reset_Timing_time: %s" % e)
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
        thick_mm, Sound_T, PeakIndex1, PeakIndex2 = calThickness(data=eval(data_dict['data']), gain_db=60, nSize=len(eval(data_dict['data'])))
        response.append([temp])
        response.append(PeakIndex1)
        response.append(PeakIndex2)
    except Exception as e:
        print(e)
        log.log(False, "data_json_report: %s" % e)

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
        log.log(False, "thickness_json_report: %s" % e)

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
    if not gateway_obj:  # 数据库没有网关记录，则查看设置网关的配置文件是否有已经设置的网关网络号
        with open('set_gwntid', 'r') as f:
            gwntid = f.read().strip('\n')
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
    # print(gateway_data)  # {'Enterprise': '中石油', 'name': '中石油1号网关', 'network_id': '0.0.1.0', 'gw_status': '1'}
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
def set_gateway_networkid(request):
    """
    发送命令设置网关网络号
    :param request:
    :return:
    """
    result = {'status': False, 'msg': '设置网络号失败'}
    try:
        gw_ntid = request.POST.get('s_gwntid')
        check_network_id = handle_func.check_network_id(gw_ntid)
        if check_network_id:
            network_id = handle_func.str_hex_dec(gw_ntid)
            command = "set 78 " + network_id
            set_gwntid_response = gw0.serCtrl.getSerialData(command, timeout=7)
            print('command', command)
            print('set_gwntid_response', set_gwntid_response.strip('\n'))
            if set_gwntid_response == 'ok':
                with open('set_gwntid', 'w') as f:
                    f.write(gw_ntid)
                result = {'status': True, 'msg': '设置网络号成功'}
        else:
            result = {'status': False, 'msg': '网络号有误'}
    except Exception as e:
        print(e)
        log.log(False, "set_gateway_networkid: %s" % e)
        result = {'status': False, 'msg': '网络号有误'}

    return HttpResponse(json.dumps(result))


@csrf_exempt
@login_required
def get_gateway_networkid(request):
    """
    发送命令获取网关网络号
    :param request:
    :return:
    """
    result = {'status': False, 'gw_ntid': '未获取到网络号'}
    try:
        command = "get 78 "
        get_gwntid_response = gw0.serCtrl.getSerialData(command, timeout=7)
        print('get_gwntid_response', get_gwntid_response.strip('\n'))
        if get_gwntid_response:
            get_gwntid_response = handle_func.str_dec_hex(get_gwntid_response)
            result = {'status': True, 'gw_ntid': get_gwntid_response}
    except Exception as e:
        print(e)
        log.log(False, "get_gateway_networkid: %s" % e)

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


@csrf_exempt
def CAL_Sound_T_json(request):
    """
    计算声时
    :param request:
    :return:
    """
    if request.method == 'POST':
        result = {'material_name': '', 'Sound_T': 0, 'CAL_msg': ''}
        selected_material_id = request.POST.get('selected_material_id')
        network_id = request.POST.get('network_id')
        material_name = models.Material.objects.values('name').get(id=selected_material_id)['name']
        result['material_name'] = material_name
        gwdata_obj = models.GWData.objects.filter(network_id=network_id)
        if gwdata_obj:
            gwdata = eval(gwdata_obj.values('data').first()['data'])
        else:
            gwdata = []
            result['CAL_msg'] = '计算声时失败，此传感器未采集任何数据，请先采集一次数据后，再点击校准'

        thick_mm, Sound_T, PeakIndex1, PeakIndex2 = calThickness(data=gwdata, gain_db=60, nSize=len(gwdata))

        result['Sound_T'] = Sound_T

        return HttpResponse(json.dumps(result))


@csrf_exempt
def CAL_Sound_V_json(request):
    """
    校准声速
    :param request:
    :return:
    """
    if request.method == 'POST':
        try:
            thickness = float(request.POST.get('thickness'))
            Sound_T = float(request.POST.get('Sound_T'))
            material_id = request.POST.get('material_id')
            Sound_V = int(thickness * 40e6 * 2 / Sound_T / 1000)
            models.Material.objects.filter(id=material_id).update(sound_V=Sound_V)
            result = {'status': True, 'Sound_V': Sound_V}
        except:
            result = {'status': False, 'Sound_V': 0}

        return HttpResponse(json.dumps(result))


def refresh_gw_status(request):
    """
    定时刷新网关与服务器连接状态
    :param request:
    :return:
    """
    try:
        if models.Gateway.objects.exists():
            gw_status = models.Gateway.objects.values('gw_status').first()['gw_status']
        else:
            gw_status = False
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

        response = {'status': False, 'msg': '', 'receive_data': receive_data}
        # print('receive_data', receive_data)  # {"received_time_data":{"month":[],"day":[],"hour":["1"],"mins":["1"]},"sensor_id":"536876188","alias":"1号传感器","network_id":"0.0.0.1","choice":"update"}

        sensor_id = receive_data['sensor_id']
        network_id = receive_data.get('network_id')
        choice = receive_data.pop('choice')
        location_img_json = receive_data.pop('location_img_json')

        # 更新
        if choice == 'update':
            response = operate_sensor.update_sensor(receive_data, response)
            log.log(response['status'], response['msg'], network_id, request.user)
            if response['status']:
                receive_data['location_img_json'] = location_img_json
                data = {'id': 'client', 'header': 'update_sensor', 'status': response['status'], 'msg': response['msg'],
                        'user': str(request.user), 'receive_data': receive_data}
                try:
                    client.publish('pub', json.dumps(data))  # 把网关更新的sensor数据发送给server
                except Exception as e:
                    print(e)
                    log.log(False, "receive_gw_data  update sensor: %s" % e)

        # 添加
        elif choice == 'add':
            gateway_status = models.Gateway.objects.values('gw_status').first()['gw_status']
            receive_data["choice"] = "add"
            receive_data["location_img_json"] = location_img_json
            if gateway_status:
                send_network_id_to_server_queue(network_id, 'add_sensor', receive_data=receive_data, level=2)
                response = {'status': True, 'msg': '正在添加中...', 'receive_data': receive_data}
            else:
                response = receive_server_data(receive_data)
                log.log(response['status'], response['msg'], receive_data['network_id'])

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
                    log.log(False, "receive_gw_data  remove sensor: %s" % e)

        return HttpResponse(json.dumps(response))


def receive_server_data(receive_data):
    """
    接收服务器的数据，用于在服务器页面操作传感器的增删改操作
    :param receive_data: 收到服务器的时间是已经在服务器端验证通过的时间，可以直接使用
    :return:
    """
    response = {'status': False, 'msg': '操作失败', 'receive_data': receive_data}
    # print('receive_data=------------', receive_data)  # {"received_time_data":{"month":[],"day":[],"hour":["1"],"mins":["1"]},"sensor_id":"536876188","alias":"1号传感器","network_id":"0.0.0.1","choice":"update"}

    sensor_id = receive_data['sensor_id']
    choice = receive_data.pop('choice')
    location_img_json = receive_data.pop('location_img_json')

    received_time_data = receive_data.get('received_time_data')
    if received_time_data:  # 如果是更新信息
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
    # print('val_dict', val_dict)
    try:
        # 判断Sample_Hz参数是否合法
        if int(val_dict['Sample_Hz']) < 200 or int(val_dict['Sample_Hz']) > 5000:
            result = {'status': False, 'msg': '采样频率参数范围：200-5000'}
            return HttpResponse(json.dumps(result))

        send_network_id_to_server_queue(network_id, 'set_sensor_params', val_dict=val_dict, level=4)

    except Exception as e:
        print(e, '设置参数失败')
        log.log(False, "set_sensor_params: %s" % e)

    # log.log(result['status'], result['msg'], network_id, str(request.user))

    return HttpResponse(json.dumps(result))


@login_required
@permissions.check_permission
def system_settings(request):
    """
    系统设置
    :param request:
    :return:
    """
    upload_obj = models.UploadData.objects.values('upload_data_to_administration_server', 'upload_data_to_local_server').first()
    upload_to_administration_status = upload_obj['upload_data_to_administration_server']
    upload_to_local_server_status = upload_obj['upload_data_to_local_server']
    gateway_obj = models.Gateway.objects.exists()
    if gateway_obj:
        gateway_name = models.Gateway.objects.values('name').first()['name']

    return render(request, 'gateway/system_settings.html', locals())


@csrf_exempt
@login_required
@permissions.check_permission
def delete_gateway(request, gateway_name):
    """
    删除网关
    :param request:
    :param gateway_name:
    :return:
    """
    all_sensor_obj = models.Sensor_data.objects.values('alias').all()
    all_gwdata_obj = models.GWData.objects.values('time_tamp', 'network_id__alias').all()[:10]
    sensor_count = models.Sensor_data.objects.count()
    gwdata_count = models.GWData.objects.count()

    if request.method == 'POST':
        import copy
        gateway_obj = models.Gateway.objects.values('name', 'network_id').first()
        gateway_name = gateway_obj['name']
        network_id = copy.deepcopy(gateway_obj['network_id'])
        input_gateway_name = request.POST.get('gateway_name')
        if gateway_name == input_gateway_name:
            gateway_data = {'network_id': network_id}
            result = operate_gateway.delete_gateway(gateway_data, user=str(request.user))
            log.log(result['status'], result['msg'], network_id, str(request.user))
            return render(request, "index.html")
        else:
            delete_gateway_msg = '网关删除失败，网关名称输入有误！'

    return render(request, "gateway/delete_gateway.html", locals())


@login_required
def control_upload_data_to_administration(request):
    """
    设置 上传数据到特检局 的开关
    :param request:
    :return:
    """
    upload_to_administration_status = json.loads(request.GET.get('upload_to_administration_status'))
    models.UploadData.objects.update(upload_data_to_administration_server=upload_to_administration_status)
    result = {'upload_to_administration_status': upload_to_administration_status}

    return HttpResponse(json.dumps(result))


@login_required
def control_upload_data_to_local_server(request):
    """
    设置 上传数据到本地服务器 的开关
    :param request:
    :return:
    """
    upload_data_to_local_server = json.loads(request.GET.get('upload_data_to_local_server'))
    models.UploadData.objects.update(upload_data_to_local_server=upload_data_to_local_server)
    result = {'upload_data_to_local_server': upload_data_to_local_server}

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
def check_sensor_params_is_exists(request):
    """
    检查服务器中是否已存在sensor: alias, sensor_id, network_id
    :param request:
    :return:
    """
    ret = {'alias_payload': '', 'network_id_payload': '', 'sensor_id_payload': '', 'alias_msg': '', 'network_id_msg': '', 'sensor_id_msg': ''}
    gw_status = models.Gateway.objects.values('Enterprise', 'gw_status').first()['gw_status']
    if request.method == 'POST':
        alias = request.POST.get('alias')
        network_id = request.POST.get('network_id')
        sensor_id = request.POST.get('sensor_id')
        choice = request.POST.get('choice')
        gwntid = models.Gateway.objects.values('network_id').first()['network_id']
        if network_id.rsplit('.', 1)[0] + '.0' == gwntid:
            start_time = time.time()
            if gw_status:  # 如果链接服务器成功，则发送到服务器端验证
                is_soft_delete = handle_func.check_soft_delete(network_id)
                if is_soft_delete:  # 是软删除的sensor
                    check_alias_payload = False
                    network_id_payload = False
                    sensor_id_payload = False
                    ret = {'alias_payload': check_alias_payload, 'network_id_payload': network_id_payload, 'sensor_id_payload': sensor_id_payload}
                else:
                    result = {'alias': alias, 'network_id': network_id, 'sensor_id': sensor_id, 'choice': choice}
                    header = 'check_sensor_params_is_exists'
                    handle_func.send_gwdata_to_server(client, 'pub', result, header)
                    ret = {'alias_payload': '', 'network_id_payload': '', 'sensor_id_payload': '', 'alias_msg': '', 'network_id_msg': '', 'sensor_id_msg': ''}
                    while (time.time() - start_time) < 2:
                        if handle_func.check_sensor_params_payload:
                            check_alias_payload = handle_func.check_sensor_params_payload['alias_is_exist']
                            network_id_payload = handle_func.check_sensor_params_payload['network_id_is_exist']
                            sensor_id_payload = handle_func.check_sensor_params_payload['sensor_id_is_exist']
                            ret = {'alias_payload': check_alias_payload, 'network_id_payload': network_id_payload, 'sensor_id_payload': sensor_id_payload}
                            break
                    if ret['alias_payload']:
                        ret['alias_msg'] = '已存在此名称！'
                    else:
                        ret['alias_msg'] = ''
                    if ret['network_id_payload']:
                        ret['network_id_msg'] = '已存在此网络号！'
                    else:
                        ret['network_id_msg'] = ''
                    if ret['sensor_id_payload']:
                        ret['sensor_id_msg'] = '已存在此ID！'
                    else:
                        ret['sensor_id_msg'] = ''
                    handle_func.check_sensor_params_payload = {}

            else:  # 如果链接服务器失败，则发到网关端验证
                if choice == 'update':
                    check_alias_payload = models.Sensor_data.objects.filter(alias=alias).exclude(network_id=network_id).exists()
                    network_id_payload = False
                    sensor_id_payload = False
                    ret = {'alias_payload': check_alias_payload, 'network_id_payload': network_id_payload, 'sensor_id_payload': sensor_id_payload}
                elif choice == 'add':
                    is_soft_delete = handle_func.check_soft_delete(network_id)
                    if is_soft_delete:  # 是软删除的sensor
                        check_alias_payload = False
                        network_id_payload = False
                        sensor_id_payload = False
                    else:
                        check_alias_payload = models.Sensor_data.objects.filter(alias=alias).exists()
                        network_id_payload = models.Sensor_data.objects.filter(network_id=network_id).exists()
                        sensor_id_payload = models.Sensor_data.objects.filter(sensor_id=sensor_id).exists()
                    ret = {'alias_payload': check_alias_payload, 'network_id_payload': network_id_payload, 'sensor_id_payload': sensor_id_payload}
                if ret['alias_payload']:
                    ret['alias_msg'] = '已存在此名称！'
                else:
                    ret['alias_msg'] = ''
                if ret['network_id_payload']:
                    ret['network_id_msg'] = '已存在此网络号！'
                else:
                    ret['network_id_msg'] = ''
                if ret['sensor_id_payload']:
                    ret['sensor_id_msg'] = '已存在此ID！'
                else:
                    ret['sensor_id_msg'] = ''

        else:
            ret['network_id_payload'] = 1
            ret['network_id_msg'] = '网络号错误！'

    return HttpResponse(json.dumps(ret))


@csrf_exempt
def check_GW_alias(request):
    """
    检查服务器中是否存在网关alias，为update/add gateway准备
    :param request:
    :return:
    """
    ret = {'check_GW_alias_payload': '', 'msg': ''}
    if request.method == 'POST':
        name = request.POST.get('name')
        network_id = request.POST.get('network_id')
        old_gateway_name = request.POST.get('old_gateway_name')
        result = {'name': name, 'network_id': network_id}
        gateway_exist = models.Gateway.objects.exists()
        result['gateway_exist'] = gateway_exist
        result['old_gateway_name'] = old_gateway_name
        header = 'check_GW_alias'
        handle_func.send_gwdata_to_server(client, 'pub', result, header)
        start_time = time.time()
        ret = {'check_GW_alias_payload': '', 'msg': ''}
        while (time.time() - start_time) < 2:
            if handle_func.check_GW_alias_payload:
                check_GW_alias_payload = handle_func.check_GW_alias_payload['GW_alias_is_exist']
                ret = {'check_GW_alias_payload': check_GW_alias_payload}
                if ret['check_GW_alias_payload']:
                    ret['msg'] = '已存在此网关名称！'
                else:
                    ret['msg'] = ''
                break
        handle_func.check_GW_alias_payload = {}

    return HttpResponse(json.dumps(ret))


def server_get_data(network_id):
    """
    服务器队列中的触发任务命令
    :param network_id:
    :return:
    """
    result = {'status': False, 'msg': '', 'gwData': {}, 'network_id': network_id}

    try:
        if network_id == '':
            result['msg'] = "没有选择传感器"
        else:
            # 需要返回网关数据
            gwData = time_job(network_id)
            alias = models.Sensor_data.objects.values('alias').get(network_id=network_id)['alias']
            if gwData != {}:
                result = {'status': True, 'msg': "[%s]获取成功" % alias, 'gwData': gwData, 'network_id': network_id}
                # 判断是否把数据发送给特检局
                upload_data_to_administration_server_status = models.UploadData.objects.values('upload_data_to_administration_server').first()['upload_data_to_administration_server']
                print('判断是否把数据发送给特检局', upload_data_to_administration_server_status)
                if upload_data_to_administration_server_status:
                    gwData['network_id'] = network_id
                    send_data = handle_func.handle_data_to_send_administration(data=gwData)
                    threading.Thread(target=sign_and_communicate_with_server, args=(send_data,)).start()
            else:
                result['msg'] = '[%s]获取失败，传感器未响应' % alias

    except Exception as e:
        print(e)
        log.log(False, "server_get_data: %s" % e)

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
            gwData = time_job(network_id)
            if gwData != {}:
                pass
                # 判断是否把数据发送给特检局
                upload_data_to_administration_server_status = models.UploadData.objects.values('upload_data_to_administration_server').first()['upload_data_to_administration_server']
                print('判断是否把数据发送给特检局', upload_data_to_administration_server_status)
                if upload_data_to_administration_server_status:
                    gwData['network_id'] = network_id
                    send_data = handle_func.handle_data_to_send_administration(data=gwData)
                    print('send_data', send_data)
                    threading.Thread(target=sign_and_communicate_with_server, args=(send_data,)).start()
        elif true_header == "add_sensor":
            receive_server_data(gw_queue_1.get('receive_data'))
        elif true_header == "set_sensor_params":
            val_dict = gw_queue_1.get('val_dict')
            handle_func.set_sensor_params_func(network_id, val_dict)
        elif true_header == "test_signal_strength":
            network_id = gw_queue_1.get('network_id')
            handle_func.handle_test_signal_strength(network_id)


# 网关取数队列线程
threading.Thread(target=gw_get_data_func).start()


auto_Timing_time()
# handle_func.check_online_of_sensor_status()



