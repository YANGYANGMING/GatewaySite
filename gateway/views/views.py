from django.shortcuts import render, HttpResponse, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from gateway import permissions
from GatewaySite import settings
from socket import *
import time, threading, re

import apscheduler.job
from apscheduler.schedulers.background import BackgroundScheduler

import datetime
import serial

from gateway.eelib.eelib.gateway import *
from gateway.eelib.eelib.sensor import SerialCtrl
from gateway.eelib.eelib.message import *
from GatewaySite.settings import headers_dict
from utils.mqtt_client import MQTT_Client
from utils import handle_recv_server
from utils import handle_func
from utils.operate_sensor import OperateSensor, OperateGateway

msg_file = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/message.txt'
msg_printer = MessagePrinter(msg_file)

gwCtrl = GatewayCtrl()

gser = serial.Serial("/dev/ttyS9", 115200, timeout=1)
# gser = serial.Serial("/dev/ttyAMA0", 115200, timeout=1)
gw0 = Gateway(gser)

mqtt_client = MQTT_Client()
client = mqtt_client.client
operate_sensor = OperateSensor()
operate_gateway = OperateGateway()


num = 0
tstp_start = 1559354400  # 2019年6月1日10时0分0秒
tstp_step = 24 * 60 * 60

latest_job_id = '0000'
latest_job1_id = '0000'

# Operation flag bit
# When acquiring data manually, only one sensor can work in the same time
btn_sample = False
# Get data automatically
auto_operation = False
# Polling for data
btn_polling = False
# Running status of task id = 0000
operation_status = None

# Timing task start flag bit
CycleStatus = False
TimingStatus = False

tcp_client_status = False

# Instantiate timer task
scheduler = BackgroundScheduler()
sche = BackgroundScheduler()
sche_sync_sensors = BackgroundScheduler()
heart_timeout_sche = BackgroundScheduler()

st = models.Set_Time.objects.filter(id=1).values('year', 'month', 'day', 'hour', 'mins')[0]
# Initialize timing data after program restart
models.Set_Time.objects.filter(id=2).update(month='', day='', hour='', mins='')
# Initialize original status infomation
models.TimeStatus.objects.filter(id=1).update(timing_status='false', cycle_status='false', text_status='已暂停',
                                              button_status='暂停')

# def auto_Timing_time():
#     """
#     Regular check ---- update/add
#     :return:
#     """
#     try:
#         scheduler.print_jobs()
#         # if not manual sample or polling sample, check for updates
#         if not btn_sample and not btn_polling:
#             db_job_id_list = []
#             # All task time and sensor_id in the database
#             db_job_list = list(models.Sensor_data.objects.filter(delete_status=0).values('network_id', 'received_time_data'))
#             # The list of sensor_id and sensor_time for scheduled tasks that already exist in the scheduler
#             sche_job_id_list, sche_job_time_list = job_id_list()
#             # Compare: when adding or updating tasks in the database, add or update schedluer tasks
#             for db_job in db_job_list:
#                 received_time_data_dict = eval(db_job['received_time_data'])
#                 jobs_id = 'cron_time ' + db_job['network_id']
#                 print(jobs_id)
#                 db_job_id_list.append(db_job['network_id'])
#                 if db_job['network_id'] in sche_job_id_list:
#                     st_temp = {'year': '*', 'month': received_time_data_dict['month'],
#                                'day': received_time_data_dict['day'], 'hour': received_time_data_dict['hour'],
#                                'minute': received_time_data_dict['mins']}
#                     temp_trigger = scheduler._create_trigger(trigger='cron', trigger_args=st_temp)
#                     scheduler.modify_job(jobs_id, trigger=temp_trigger)
#                     # After updating the data, you need to resume_job()
#                     scheduler.resume_job(jobs_id)
#                     # print('update task')
#                 else:
#                     # update task
#                     scheduler.add_job(time_job, 'cron', year='*', month=received_time_data_dict['month'],
#                                       day=received_time_data_dict['day'], hour=received_time_data_dict['hour'],
#                                       minute=received_time_data_dict['mins'], second='00', id=jobs_id)
#                     # print('add task')
#
#             # Compare: when a task is deleted in the database, the scheduler task is also deleted
#             for sche_job_id in sche_job_id_list:
#                 if sche_job_id != '0000':
#                     if sche_job_id not in db_job_id_list:
#                         temp_sche_job_id = 'cron_time ' + sche_job_id
#                         scheduler.remove_job(temp_sche_job_id)
#                         print('remove %s seccess' % sche_job_id)
#             global latest_job_id  # 0000
#             latest_job_id = scheduler.get_jobs()[0].id.split(' ')[1]
#             # print('latest_job_id=======================================================================', latest_job_id)
#             # print(latest_job_id)
#             # print(scheduler.get_jobs())
#             # print(dir(scheduler.get_jobs()[0]))
#             # print(dir(scheduler.get_jobs()[0].trigger))
#             # print(scheduler.get_jobs()[0].trigger.fields)
#             # print(scheduler.get_jobs()[0].trigger.fields[5])
#             # print(scheduler.get_jobs())
#             # print(scheduler.get_jobs()[0].next_run_time)
#             # print(scheduler.get_jobs()[0].id.split('')[1])
#             # print(scheduler.get_jobs()[0].trigger)
#             # print(scheduler.get_jobs())
#
#             # print(datetime.datetime.now())
#     except Exception as e:
#         print('auto_Timing_time:', e)

def cal_heart_timeout():
    """
    心跳超时改变状态
    :return:
    """
    print('timeout......')
    models.Gateway.objects.update(gw_status=0)


def auto_Timing_time(network_id=None):
    """
    Regular check ---- update/add
    :return:
    """
    try:
        # if not manual sample or polling sample, check for updates
        if not btn_sample and not btn_polling:

            if network_id:
                # update sensor
                received_time_data = eval(models.Sensor_data.objects.filter(network_id=network_id).values('received_time_data')[0]['received_time_data'])
                st_temp = {'year': '*', 'month': received_time_data['month'],
                           'day': received_time_data['day'], 'hour': received_time_data['hour'],
                           'minute': received_time_data['mins']}
                temp_trigger = scheduler._create_trigger(trigger='cron', trigger_args=st_temp)
                scheduler.modify_job('cron_time ' + network_id, trigger=temp_trigger)
                # After updating the data, you need to resume_job()
                scheduler.resume_job('cron_time ' + network_id)
                print('update task' + network_id)

            db_job_id_list = []
            # All task time and sensor_id in the database
            db_job_list = list(models.Sensor_data.objects.filter(delete_status=0).values('network_id', 'received_time_data'))
            print(db_job_list)
            # The list of sensor_id and sensor_time for scheduled tasks that already exist in the scheduler
            sche_job_id_list, sche_job_time_list = handle_func.job_id_list()
            # Compare: when adding or updating tasks in the database, add or update schedluer tasks

            for db_job in db_job_list:
                received_time_data_dict = eval(db_job['received_time_data'])
                jobs_id = 'cron_time ' + db_job['network_id']
                print(jobs_id)
                db_job_id_list.append(db_job['network_id'])
                # add sensor
                if db_job['network_id'] not in sche_job_id_list:
                    scheduler.add_job(time_job, 'cron', year='*', month=received_time_data_dict['month'],
                                      day=received_time_data_dict['day'], hour=received_time_data_dict['hour'],
                                      minute=received_time_data_dict['mins'], second='00', id=jobs_id)
                    print('add task')

            # Compare: when a task is deleted in the database, the scheduler task is also deleted
            for sche_job_id in sche_job_id_list:
                if sche_job_id != '0000':
                    if sche_job_id not in db_job_id_list:
                        temp_sche_job_id = 'cron_time ' + sche_job_id
                        scheduler.remove_job(temp_sche_job_id)
                        print('remove %s seccess' % sche_job_id)
            global latest_job_id  # 0000
            latest_job_id = scheduler.get_jobs()[0].id.split(' ')[1]
            # print('latest_job_id=======================================================================', latest_job_id)
            # print(latest_job_id)
            # print(scheduler.get_jobs())
            # print(dir(scheduler.get_jobs()[0]))
            # print(dir(scheduler.get_jobs()[0].trigger))
            # print(scheduler.get_jobs()[0].trigger.fields)
            # print(scheduler.get_jobs()[0].trigger.fields[5])
            # print(scheduler.get_jobs())
            # print(scheduler.get_jobs()[0].next_run_time)
            # print(scheduler.get_jobs()[0].id.split('')[1])
            # print(scheduler.get_jobs()[0].trigger)
            # print(scheduler.get_jobs())
            scheduler.print_jobs()
            # print(datetime.datetime.now())
    except Exception as e:
        print('auto_Timing_time:', e)


def time_job():
    """
    Timed mode task: cron
    :return:
    """
    global num
    global btn_polling
    global auto_operation
    gwData = {}
    if latest_job_id == '0000':
        # Polling sensor
        snr_num = models.Sensor_data.objects.values('network_id').all()
        print('snr_num', snr_num)
        snr_num_list = [item['network_id'] for item in snr_num]
        btn_polling = True  # Polling collection flag bit
        pause_all_sensor()
    else:
        # 单一传感器，手动采集数据/自动采集数据
        snr_num_list = [latest_job_id]
        if btn_sample:  # 如果是手动采样
            pause_all_sensor()
        else:
            auto_operation = True  # 自动采集标志位
    # print('btn_polling', btn_polling)
    # print('auto_operation', auto_operation)
    # print('btn_sample', btn_sample)
    # print('snr_num_list', snr_num_list)
    for network_id in snr_num_list:
        resend_num = 1
        while resend_num < 3:  # 未采集到数据时,重发一次
            time_now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
            msg_printer.print2File("\r\ntime task: " + str(time_now) + "\r\n")
            print("num=" + str(num) + ",  " + str(time_now) + ', ' + network_id)
            tstp_test = tstp_start + num * tstp_step
            num = num + 1
            r, gwData = gw0.sendData2Server(network_id, tstp_test)
            topic = models.Gateway.objects.values('network_id')[0]['network_id']
            print(r.message)
            if r.status:
                if auto_operation or btn_polling:  # 如果是自动采集或者轮询，则发送网关数据到服务器
                    header = 'gwdata'
                    result = {'status': True, 'message': '获取成功', 'gwData': gwData}
                    handle_func.send_gwdata_to_server(client, topic, result, header)
                break
            else:
                resend_num += 1

    btn_polling = False
    auto_operation = False
    resume_all_sensor()
    # print('btn_polling2', btn_polling)
    # print('auto_operation2', auto_operation)
    # print('btn_sample2', btn_sample)

    return gwData


try:
    """定时初始化"""
    scheduler.add_job(time_job, 'cron', year=st['year'], month=st['month'], day=st['day'],
                            hour=st['hour'], minute=st['mins'], second='00', id='cron_time 0000')
    scheduler.start()
    # 加载程序时暂停定时器
    scheduler.pause_job('cron_time 0000')
    print(scheduler.get_job('cron_time 0000'))
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


# 每分钟执行一次更新/添加
# try:
#     sche.add_job(auto_Timing_time, 'interval', minutes=0, seconds=10, id='auto_Timing_time')
#     sche.start()
# except Exception as e:
#     print(e)
#     sche.shutdown()


def pause_all_sensor():
    """轮询or手动触发开始，暂停所有传感器"""
    for job_obj in scheduler.get_jobs():
        if job_obj.id[-4:] == "0000":
            global operation_status     # 暂停之前先获取任务id=0000的运行状态
            operation_status = job_obj.next_run_time
            # print('operation_status', operation_status)

        job_obj.pause()
        # print('job_obj_pause', job_obj)


def resume_all_sensor():
    """轮询or手动触发结束，恢复所有传感器"""
    for job_obj in scheduler.get_jobs():
        # print('operation_status', operation_status)
        if job_obj.id[-4:] == "0000" and not operation_status:
            # print('job_obj_resume0000', job_obj)
            pass
        else:
            job_obj.resume()
            # print('job_obj_resume', job_obj)


@login_required
def index(request):
    """
    首页
    :param request:
    :return:
    """
    global tcp_client_status
    tcp_status = {'tcp_client_status': tcp_client_status}
    latest_data = models.GWData.objects.values('id', 'network_id', 'network_id__alias', 'battery', 'temperature', 'thickness').order_by('-id')[:5]
    sensor_nums = models.Sensor_data.objects.all().count()

    return render(request, 'index.html', locals())


@permissions.check_permission
@login_required
def config_time(request):
    """
    设置时间
    :param request:
    :return:
    """
    time_now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
    # form = DataForm()
    # 最新的X条数据
    latest_data = models.GWData.objects.values('id', 'network_id', 'time_tamp', 'battery', 'temperature', 'thickness', 'network_id__alias').order_by('-id')[:5]
    # 服务器返回的最新的数据
    latest_post_return = models.Post_Return.objects.last()
    # 最新的定时时间/循环时间/时间状态/手动设置id/设置参数，用于刷新页面时保留输入信息
    latest_Timing_time = models.Set_Time.objects.filter(id=2).values('month', 'day', 'hour', 'mins').first()
    for k, v in latest_Timing_time.items():
        if v == "*":
            latest_Timing_time[k] = ''
    latest_Cycle_time = models.Set_Time.objects.filter(id=4).values('day', 'hour', 'mins').first()
    latest_time_status = models.TimeStatus.objects.filter(id=1).values('timing_status', 'cycle_status', 'text_status',
                                                                       'button_status').first()

    latest_set_id = models.Set_param.objects.filter(id=1).values('menu_get_id').first()

    all_sensor_list = models.Sensor_data.objects.filter(delete_status=0).values('network_id', 'alias')

    context = {
        "time": time_now,

        "month_cron": [i for i in range(1, 13)],
        "Day_cron": [i for i in range(1, 29)],
        "Hour_cron": [i for i in range(0, 24)],
        "Minute_cron": [i for i in range(0, 60)],

        "cHz": [cHz for cHz in range(1, 4)],
        "gain": [gain for gain in range(60, 101)],
        "avg_time": [avg_time for avg_time in range(0, 11)],
        "Hz": [Hz for Hz in range(2, 5)],
        "Sample_depth": [Sample_depth for Sample_depth in range(2, 7, 2)],
        "Sample_Hz": [200, 5000],

    }

    test = {'status': 'true'}

    ret = {'status': False, 'message': '提交失败'}
    if request.method == "GET":
        # form = DataForm()
        return render(request, 'gateway/config_time.html', locals())


@permissions.check_permission
@login_required
def all_data_report(request):
    """
    全部数据
    :param request:
    :return:
    """
    data_obj = models.GWData.objects.values('id', 'network_id__alias', 'network_id', 'battery', 'temperature',
                                            'thickness', 'time_tamp').order_by('-id')

    return render(request, 'gateway/all_data_report.html', locals())


@permissions.check_permission
@login_required
def thickness_report(request):
    """
    单个传感器厚度曲线
    :param request:
    :return:
    """
    # db中存在的数据
    data_obj = models.GWData.objects.filter().values('network_id', 'network_id__alias').distinct()
    print(data_obj)
    return render(request, 'gateway/thickness_report.html', locals())


@permissions.check_permission
@login_required
def all_sensor_data(request):
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
        "Sample_depth": [Sample_depth for Sample_depth in range(2, 7, 2)],
        "Sample_Hz": [200, 5000],
    }
    sensor_obj = models.Sensor_data.objects.filter(delete_status=0).order_by('-id')
    # 添加下次运行时间
    # sche_obj = scheduler.get_jobs()
    # for i in sensor_obj:
    #     for ii in sche_obj:
    #         if i.sensor_id == ii.id.split(' ')[1]:
    #             i.next_run_time = str(ii.next_run_time).split('+')[0]

    return render(request, "gateway/all_sensor_data.html", locals())


@permissions.check_permission
@login_required
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
        # 把next_run_time放进每个传感器对象中
        for ii in sche_obj:
            if sensor_item.network_id == ii.id.split(' ')[1]:
                sensor_item.next_run_time = str(ii.next_run_time).split('+')[0]
                print(sche_obj)
                print(sensor_item.next_run_time)
        received_time_data = models.Sensor_data.objects.filter(sensor_id=sensor_item.sensor_id).values('sensor_id', 'received_time_data')
        # 把年月日分别放进每个传感器对象中
        for ii in received_time_data:
            if sensor_item.sensor_id == ii['sensor_id']:
                sensor_item.month = eval(ii['received_time_data'])['month']
                sensor_item.day = eval(ii['received_time_data'])['day']
                sensor_item.hour = eval(ii['received_time_data'])['hour']
                sensor_item.mins = eval(ii['received_time_data'])['mins']

    return render(request, "gateway/sensor-manage.html", locals())


@login_required
@csrf_exempt
def set_Timing_time(request):
    """
    设置轮询定时时间
    :param request:
    :return:
    """
    ret = {'status': False, 'message': '定时时间设置失败'}
    try:
        if request.method == 'POST' and not btn_sample and not auto_operation:
            arr = request.POST.getlist('TimingDateList')
            time_list = handle_func.handle_data(arr)  # 处理数据
            print('time_list', time_list)
            if time_list != []:
                received_time_data_dict = {}
                for ii in time_list:
                    received_time_data_dict.update(ii)
                conform = handle_func.judge_time(received_time_data_dict, '0000')
                if conform:
                    for item in time_list:
                        models.Set_Time.objects.filter(id=2).update(**item)
                    start_Timing_time(2)
                    auto_Timing_time()
                    ret = {'status': True, 'message': '定时时间设置成功'}
                    global TimingStatus
                    TimingStatus = True
                else:
                    ret['message'] = '设置时间冲突,请选择其他时间'
        else:
            ret['message'] = '其他节点正在采集数据，请稍等...'
    except Exception as e:
        print('set_Timing_time', e)
        return HttpResponse(json.dumps(ret))

    return HttpResponse(json.dumps(ret))


@login_required
@csrf_exempt
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


def start_Timing_time(nid, reset=False):
    """
    设置/更新定时时间
    :param nid: 设定时间的id
    :param reset: 重置按钮标志位，如果为true，把定时模式暂停
    :return:
    """
    global st
    st = models.Set_Time.objects.filter(id=nid).values('year', 'month', 'day', 'hour', 'mins').first()
    print('st:', st)
    st_temp = {'year': st['year'], 'month': st['month'], 'day': st['day'], 'hour': st['hour'],
               'minute': st['mins']}
    try:
        temp_trigger = scheduler._create_trigger(trigger='cron', trigger_args=st_temp)
        scheduler.modify_job('cron_time 0000', trigger=temp_trigger)
        if reset:
            scheduler.pause_job('cron_time 0000')
        else:
            scheduler.resume_job('cron_time 0000')

        scheduler.get_job('cron_time 0000')
    except Exception as e:
        print('start_Timing_time:', e)
        scheduler.shutdown()


@login_required
def pause_Timing_time(request):
    """
    暂停定时时间
    :param request:
    :return:
    """
    ret = {'status': False, 'message': None}
    try:
        if TimingStatus:
            scheduler.pause_job('cron_time 0000')
            scheduler.get_job('cron_time 0000')
            ret = {'status': True, 'message': 'success'}
        print(TimingStatus)
    except Exception as e:
        print(e)
    return HttpResponse(json.dumps(ret))


@login_required
def resume_Timing_time(request):
    """
    恢复定时时间
    :param request:
    :return:
    """
    ret = {'status': False, 'message': None}
    try:
        if TimingStatus:
            scheduler.resume_job('cron_time 0000')
            scheduler.pause_job('cron_time 0000')
            scheduler.get_job('cron_time 0000')
            ret = {'status': True, 'message': 'success'}
        print(TimingStatus)
    except Exception as e:
        print(e)
    return HttpResponse(json.dumps(ret))


@login_required
def resume_cycle_time(request):
    """
    恢复循环时间
    :param request:
    :return:
    """
    ret = {'status': False, 'message': None}
    try:
        if CycleStatus:
            scheduler.pause_job('cron_time 0000')
            scheduler.get_job('cron_time 0000')
            ret = {'status': True, 'message': 'success'}
    except Exception as e:
        print(e)
    return HttpResponse(json.dumps(ret))


@login_required
@csrf_exempt
def reset_Timing_time(request):
    """
    重置定时时间
    :param request:
    :return:
    """
    ret = {'status': False, 'message': None}
    try:
        models.Set_Time.objects.filter(id=2).update(year='*', month='1', day='1', hour='0', mins='0')
        start_Timing_time(2, reset=True)
        scheduler.pause_job('cron_time 0000')
        ret['status'] = True
        ret['message'] = 'success'
        global TimingStatus
        TimingStatus = False
    except Exception as e:
        print(e)
    return HttpResponse(json.dumps(ret))


# @login_required
@csrf_exempt
def manual_get(request, network_id):
    """
    网关手动触发任务
    :param request:
    :return:
    """
    result = {'status': False, 'message': "获取失败", 'gwData': {}}
    global btn_sample
    try:
        if not btn_sample and not btn_polling and not auto_operation:
            btn_sample = True  # 手动采集标志位
            global latest_job_id
            latest_job_id = network_id
            if models.Set_param.objects.count() == 0:
                models.Set_param.objects.create(menu_get_id=latest_job_id, param="")
            else:
                models.Set_param.objects.filter(id=1).update(menu_get_id=latest_job_id)
            if latest_job_id == '':
                result['message'] = "没有选择传感器"
            else:
                gwData = time_job()
                if gwData:
                    result = {'status': True, 'message': "获取成功", 'gwData': gwData}
                topic = models.Gateway.objects.values('network_id')[0]['network_id']
                handle_func.send_gwdata_to_server(client, topic, result, headers_dict['gwdata'])
            btn_sample = False
            # print('btn_sample2', btn_sample)
        else:
            if btn_polling:
                result['message'] = "请稍等，定时轮询模式正在采集数据..."
            elif auto_operation or btn_sample:
                result['message'] = "请稍等，已有传感器正在采集数据..."
    except Exception as e:
        print(e)
        btn_sample = False
    if request.method == 'POST':
        return HttpResponse(json.dumps(result))


@login_required
@csrf_exempt
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
        print(response)
    except Exception as e:
        print(e)

    return HttpResponse(json.dumps(response))


@login_required
def edit_sensor_time(request, sensor_id):
    """
    编辑传感器时间
    :param request:
    :return:
    """
    received_time_data = eval(models.Sensor_data.objects.filter(sensor_id=sensor_id).values('received_time_data')[0]['received_time_data'])
    sensor_obj = models.Sensor_data.objects.get(sensor_id=sensor_id)
    date_of_installation = str(sensor_obj.date_of_installation)
    # sensor_type = sensor_obj._meta.get_field('sensor_type')
    # Importance = sensor_obj._meta.get_field('Importance')·
    sensor_type = {'ETM-100': 0}
    Importance = {'重要': 1, '一般': 0}
    material = {'未定义': 0, '碳钢': 1, '不锈钢': 2}
    context = {
        "month_cron": [i for i in range(1, 13)],
        "day_cron": [i for i in range(1, 29)],
        "hour_cron": [i for i in range(0, 24)],
        "minute_cron": [i for i in range(0, 60)],
    }

    return render(request, "gateway/edit_sensor_time.html", locals())\


@login_required
def edit_sensor_alarm_msg(request, sensor_id):
    """
    编辑传感器报警信息
    :param request:
    :return:
    """
    sensor_obj = models.Sensor_data.objects.get(sensor_id=sensor_id)

    return render(request, "gateway/edit_sensor_alarm_msg.html", locals())


@login_required
def add_sensor_page(request, network_id):
    """
    增加传感器
    :param request:
    :param network_id: 如果network_id=='new',说明是新增传感器,否则是恢复被软删除的network_id的传感器
    :return:
    """
    gateway_obj = models.Gateway.objects.first()
    if gateway_obj:
        sensor_type = {'ETM-100': 0}
        Importance = {'一般': 0, '重要': 1}
        material = {'未定义': 0, '碳钢': 1, '不锈钢': 2}
        context = {
            "month_cron": [i for i in range(1, 13)],
            "day_cron": [i for i in range(1, 29)],
            "hour_cron": [i for i in range(0, 24)],
            "minute_cron": [i for i in range(0, 60)],
        }
        return render(request, 'gateway/add_sensor_time.html', locals())
    else:
        # 添加网关
        gw_status = {'在线': 1, '离线': 0}

        return render(request, 'gateway/set_gateway.html', locals())


@permissions.check_permission
@login_required
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
        result = operate_gateway.update_gateway(gateway_data)
    else:
        # add_gateway
        result = operate_gateway.add_gateway(gateway_data)

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
        gw_status = {'message': ''}
    if gw_status:
        result = {'message': '<a href="#"><i style="font-size: larger" class="fa fa-circle text-green"></i>&nbsp;&nbsp;已连接服务器</a>'}
    else:
        result = {'message': '<a href="#"><i style="font-size: larger" class="fa fa-circle text-red"></i>&nbsp;&nbsp;未连接服务器</a>'}

    return HttpResponse(json.dumps(result))


@csrf_exempt
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

        topic = models.Gateway.objects.values('network_id')[0]['network_id']

        sensor_id = receive_data['sensor_id']
        choice = receive_data.pop('choice')
        received_time_data = receive_data.get('received_time_data')
        if received_time_data:
            received_time_data = handle_func.handle_receive_data(received_time_data)
            # 验证时间
            conform = handle_func.judge_time(received_time_data, receive_data['network_id'])
        else:  # 只更新报警信息参数
            conform = True

        # 更新
        if choice == 'update':
            location_img_json = receive_data.pop('location_img_json')
            response = operate_sensor.update_sensor(receive_data, conform, response)
            if response['status']:
                receive_data['location_img_json'] = location_img_json
                data = {'id': 'client', 'header': 'update_sensor', 'status': True, 'times': time.time(), 'receive_data': receive_data}
                client.publish(topic, json.dumps(data))  # 把网关更新的sensor数据发送给server

        # 添加
        elif choice == 'add':
            location_img_json = receive_data.pop('location_img_json')
            response = operate_sensor.add_sensor(receive_data, sensor_id, conform, response)
            if response['status']:
                receive_data['location_img_json'] = location_img_json
                data = {'id': 'client', 'header': 'add_sensor', 'status': True, 'receive_data': receive_data}
                client.publish(topic, json.dumps(data))  # 把网关增加的sensor数据发送给server

        # 删除
        elif choice == 'remove':
            location_img_json = receive_data.pop('location_img_json')
            response = operate_sensor.remove_sensor(sensor_id, response)
            if response['status']:
                receive_data['location_img_json'] = location_img_json
                data = {'id': 'client', 'header': 'remove_sensor', 'status': True, 'receive_data': receive_data}
                client.publish(topic, json.dumps(data))  # 把网关增加的sensor数据发送给server

        return HttpResponse(json.dumps(response))


def receive_server_data(receive_data):
    """
    接收服务器的数据，用于在服务器页面操作传感器的增删改操作
    :param receive_data:
    :return:
    """
    response = {'status': False, 'msg': '操作失败', 'times': time.time(), 'receive_data': receive_data}
    print('receive_data', receive_data)  # {"received_time_data":{"month":[],"day":[],"hour":["1"],"mins":["1"]},"sensor_id":"536876188","alias":"1号传感器","network_id":"0.0.0.1","choice":"update"}

    sensor_id = receive_data['sensor_id']
    choice = receive_data.pop('choice')
    received_time_data = receive_data.get('received_time_data')
    if received_time_data:
        received_time_data = handle_func.handle_receive_data(received_time_data)
        # 验证时间
        conform = handle_func.judge_time(received_time_data, receive_data['network_id'])
    else:  # 只更新报警信息参数
        conform = True

    # 更新
    if choice == 'update':
        location_img_json = receive_data.pop('location_img_json')
        if location_img_json:
            location_img_path_and_name = receive_data['location_img_path']
            location_img_path = location_img_path_and_name.rsplit('/', 1)[0] + '/'
            # 判断是是否存在路径
            handle_func.mkdir_path(path=location_img_path)
            location_img_bytes = eval(json.loads(location_img_json.strip('\r\n')))
            with open(location_img_path_and_name, 'wb') as f:
                f.write(location_img_bytes)

        response = operate_sensor.update_sensor(receive_data, conform, response)
        # 先pop掉location_img_json,把receive_data更新给网关后,需要再给receive_data添上location_img_json,以便返回给server进行存储
        response['receive_data']['location_img_json'] = location_img_json

    # 添加
    elif choice == 'add':
        location_img_json = receive_data.pop('location_img_json')
        if location_img_json:
            location_img_path_and_name = receive_data['location_img_path']
            location_img_path = location_img_path_and_name.rsplit('/', 1)[0] + '/'
            # 判断是是否存在路径
            handle_func.mkdir_path(path=location_img_path)
            location_img_bytes = eval(json.loads(location_img_json.strip('\r\n')))
            with open(location_img_path_and_name, 'wb') as f:
                f.write(location_img_bytes)

        response = operate_sensor.add_sensor(receive_data, sensor_id, conform, response)
        # 先pop掉location_img_json,把receive_data添加给网关后,需要再给receive_data添上location_img_json,以便返回给server进行存储
        response['receive_data']['location_img_json'] = location_img_json

    # 删除
    elif choice == 'remove':
        response = operate_sensor.remove_sensor(sensor_id, response)

    return response


@login_required
@csrf_exempt
def sensor_data_val_set(request):
    """
    设置模态框中的传感器参数
    :param request:
    :return:
    """
    result = {'status': False, 'message': '设置失败'}
    try:
        new_val_dict = {}
        val_dict = json.loads(request.POST.get('val_dict'))
        print('val_dict', val_dict)
        #用于赋值
        latest_set_val = models.Sensor_data.objects.filter(sensor_id=val_dict['sensor_id']).values('cHz', 'gain', 'avg_time', 'Hz', 'Sample_depth', 'Sample_Hz')[0]
        print(latest_set_val)
        network_id = models.Sensor_data.objects.filter(sensor_id=val_dict['sensor_id']).values('network_id')[0]['network_id']
        #判断Sample_Hz参数是否合法
        if int(val_dict['Sample_Hz']) < 200 or int(val_dict['Sample_Hz']) > 5000:
            result = {'status': False, 'message': '采样频率参数范围：200-5000'}
            return HttpResponse(json.dumps(result))

        #筛选出修改的数据new_val_dict
        for k, v in val_dict.items():
            if k == 'sensor_id' or v == '':
                pass
            else:
                new_val_dict[k] = v
        print('new_val_dict', new_val_dict)

        # 准备发送的命令字符串  cmd_str = "set 0001 2 60 4 2 2 500"
        cmd_str = str(" " + val_dict['cHz'] + " " + val_dict['gain'] + " " + val_dict[
            'avg_time'] + " " + val_dict['Hz'] + " " + val_dict['Sample_depth'] + " " + val_dict['Sample_Hz'])
        command = "set 71 " + network_id.rsplit('.', 1)[1] + cmd_str
        print('command', command)
        set_val_response = gw0.serCtrl.getSerialresp(command)
        print('set_val_response', set_val_response.strip('\n'))
        if set_val_response.strip('\n') == 'ok':
            handle_func.update_sensor_data(val_dict)
            models.Sensor_data.objects.filter(sensor_id=val_dict['sensor_id']).update(**new_val_dict)

            result = {'status': True, 'message': '设置成功'}
    except Exception as e:
        print(e, '设置参数失败')

    return HttpResponse(json.dumps(result))


def server_manual_get(network_id):
    """
    服务器手动触发任务
    :param request:
    :return:
    """
    result = {'status': False, 'msg': '获取失败', 'gwData':{}}
    global btn_sample
    try:
        if not btn_sample and not btn_polling and not auto_operation:
            btn_sample = True  # 手动采集标志位
            global latest_job_id
            latest_job_id = network_id
            print(latest_job_id)
            if models.Set_param.objects.count() == 0:
                models.Set_param.objects.create(menu_get_id=latest_job_id, param="")
            else:
                models.Set_param.objects.filter(id=1).update(menu_get_id=latest_job_id)
            if latest_job_id == '':
                result['msg'] = "没有选择传感器"
            else:
                # 需要返回网关数据
                gwData = time_job()
                if gwData == {}:
                    result['msg'] = "未获取到数据"
                else:
                    result = {'status': True, 'msg': "获取成功", 'gwData': gwData}
            btn_sample = False
        else:
            if btn_polling:
                result['msg'] = "请稍等，定时轮询模式正在采集数据..."
            elif auto_operation or btn_sample:
                result['msg'] = "请稍等，已有传感器正在采集数据..."
    except Exception as e:
        print(e)
        btn_sample = False
    return result


# def init_gwntid():
#     """
#     首先检查是否已经自动配置了gwntid，一般没有gwntid表示网关是初次上电
#     :return:
#     """
#     gw_network_id = models.GW_network_id.objects.all()
#     if not gw_network_id:
#         command = "get gwntid"
#         print('command', command)
#         # gwntid = gw0.serCtrl.getSerialresp(command)
#         gwntid = '0.0.1.0'
#         print('gwntid_response', gwntid.strip('\n'))
#         if handle_func.check_gwntid(gwntid):
#             models.GW_network_id.objects.create(network_id=gwntid)
#     else:
#         gwntid = gw_network_id.values('network_id')[0]['network_id']
#
#     return gwntid


# 每次加载程序或者刷新页面的时候马上更新数据库和调度器中的任务一次
auto_Timing_time()
# handle_func.check_online_of_sensor_status()


def test(request):

    return render(request, 'test.html', locals())

@ csrf_exempt
def test_json(request):
    if request.method == 'POST':
        user = json.loads(request.POST.get('user'))
        aaa = json.loads(request.POST.get('aaa'))
        print(user)
        print(aaa)
    return HttpResponse(json.dumps('...'))


