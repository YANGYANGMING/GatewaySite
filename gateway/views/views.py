from django.shortcuts import render, HttpResponse, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from gateway import permissions
from socket import *
import time, threading, re

import apscheduler.job
from apscheduler.schedulers.background import BackgroundScheduler

import datetime
import serial

from gateway.eelib.eelib.gateway import *
from gateway.eelib.eelib.sensor import SerialCtrl
from gateway.eelib.eelib.message import *
from GatewaySite.settings import headers_dict, ip_port
from utils.mqtt_client import MQTT_Client
from utils import handle_func

msg_file = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/message.txt'
msg_printer = MessagePrinter(msg_file)

gwCtrl = GatewayCtrl()

gser = serial.Serial("/dev/ttyS3", 115200, timeout=1)
# gser = serial.Serial("/dev/ttyAMA0", 115200, timeout=1)
gw0 = Gateway(gser)

mqtt_client = MQTT_Client()
client = mqtt_client.client


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
scheduler1 = BackgroundScheduler()
sche = BackgroundScheduler()
sche_sync_sensors = BackgroundScheduler()
clear_sche = BackgroundScheduler()

st = models.Set_Time.objects.filter(id=1).values('year', 'month', 'day', 'hour', 'mins')[0]
st1 = models.Set_Time.objects.filter(id=3).values('day', 'hour', 'mins')[0]
# Initialize timing data after program restart
models.Set_Time.objects.filter(id=2).update(month='', day='', hour='', mins='')
models.Set_Time.objects.filter(id=4).update(day='0', hour='0', mins='0')
# Initialize original status infomation
models.TimeStatus.objects.filter(id=1).update(timing_status='false', cycle_status='false', text_status='已暂停',
                                              button_status='暂停')


# try:
#     global tcp_client
#     tcp_client = socket(AF_INET, SOCK_STREAM)
#     tcp_client.connect(ip_port)
#
# except Exception as e:
#     print('连接', e)


def auto_Timing_time():
    """
    Regular check ---- update/add
    :return:
    """
    try:
        # if not manual sample or polling sample, check for updates
        if not btn_sample and not btn_polling:
            db_job_id_list = []
            # All task time and sensor_id in the database
            db_job_list = list(models.Sensor_data.objects.values('network_id', 'received_time_data'))
            # The list of sensor_id and sensor_time for scheduled tasks that already exist in the scheduler
            sche_job_id_list, sche_job_time_list = job_id_list()
            # Compare: when adding or updating tasks in the database, add or update schedluer tasks
            for db_job in db_job_list:
                received_time_data_dict = eval(db_job['received_time_data'])
                jobs_id = 'cron_time ' + db_job['network_id']
                db_job_id_list.append(db_job['network_id'])
                if db_job['network_id'] in sche_job_id_list:
                    st_temp = {'year': '*', 'month': received_time_data_dict['month'],
                               'day': received_time_data_dict['day'], 'hour': received_time_data_dict['hour'],
                               'minute': received_time_data_dict['mins']}
                    temp_trigger = scheduler._create_trigger(trigger='cron', trigger_args=st_temp)
                    scheduler.modify_job(jobs_id, trigger=temp_trigger)
                    # After updating the data, you need to resume_job()
                    scheduler.resume_job(jobs_id)
                    # print('update task')
                else:
                    # update task
                    scheduler.add_job(time_job, 'cron', year='*', month=received_time_data_dict['month'],
                                      day=received_time_data_dict['day'], hour=received_time_data_dict['hour'],
                                      minute=received_time_data_dict['mins'], second='00', id=jobs_id)
                    # print('add task')

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
            # scheduler.print_jobs()
            # print(datetime.datetime.now())
    except Exception as e:
        print('auto_Timing_time:', e)


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
        for job_obj in scheduler.get_jobs():
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
            if [ii for ii in received_time_data_dict['mins'].split(',') if ii in sche_item['mins'].split(',')] != []\
                    or sche_item['mins'] == '*' or received_time_data_dict['mins'] == '*':
                # check hour
                if [ii for ii in received_time_data_dict['hour'].split(',') if ii in sche_item['hour'].split(',')] != []\
                        or sche_item['hour'] == '*' or received_time_data_dict['hour'] == '*':
                    # check day
                    if [ii for ii in received_time_data_dict['day'].split(',') if ii in sche_item['day'].split(',')] != [] \
                            or sche_item['day'] == '*' or received_time_data_dict['day'] == '*':
                        # check month
                        if [ii for ii in received_time_data_dict['month'].split(',') if ii in sche_item['month'].split(',')] != [] \
                                or sche_item['month'] == '*' or received_time_data_dict['month'] == '*':
                            # check year
                            if [ii for ii in ['*'] if ii in sche_item['year'].split(',')] != [] or sche_item['year'] == '*':
                                conform = False
                                break
        print('conform', conform)
        return conform


def job_id_list():
    """
    A list of the sensor_id of a scheduled task that already exists in the scheduler
    :return:
    """
    sche_job_id_list = []
    sche_job_time_list = []
    for job_obj in scheduler.get_jobs():
        sche_job_id_list.append(job_obj.id.split(' ')[1])
        sche_job_time_list.append(
            {'month': str(job_obj.trigger.fields[1]), 'day': str(job_obj.trigger.fields[2]),
             'hour': str(job_obj.trigger.fields[5]), 'mins': str(job_obj.trigger.fields[6])})
    return sche_job_id_list, sche_job_time_list


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
        time_now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
        msg_printer.print2File("\r\ntime task: " + str(time_now) + "\r\n")
        print("num=" + str(num) + ",  " + str(time_now) + ', ' + network_id)
        tstp_test = tstp_start + num * tstp_step
        num = num + 1
        r, gwData = gw0.sendData2Server(network_id, tstp_test)
        topic = latest_job_id.rsplit('.', 1)[0] + '.0'
        if (r.status == True):
            msg_printer.print2File("post,return:\r\n" + str(r.result))
            dic = r.result
            models.Post_Return.objects.create(result_all_data=dic)
            # 检查数据库是否超限
            delete_data = Delete_data()
            delete_data.count_postdata()
            print("post,return:\r\n" + str(r.result))
            if auto_operation:  # 如果是自动采集，则发送网关数据到服务器
                header = 'gwdata'
                result = {'status': True, 'message': '获取成功', 'gwData':gwData}
                handle_func.send_gwdata_to_server(client, topic, result, header)
        else:
            msg_printer.print2File(r.message)
            print(r.message)
            if auto_operation:  # 如果是自动采集，则发送网关数据到服务器
                header = 'gwdata'
                result = {'status': False, 'message': '获取失败', 'gwData': {}}
                handle_func.send_gwdata_to_server(client, topic, result, header)

    btn_polling = False
    auto_operation = False
    resume_all_sensor()
    # print('btn_polling2', btn_polling)
    # print('auto_operation2', auto_operation)
    # print('btn_sample2', btn_sample)

    return gwData


def time_job1():
    """
    循环模式任务: interval
    :return:
    """
    global num
    global latest_job1_id
    if latest_job1_id == '0000':
        #轮询传感器
        snr_num = models.Sensor_data.objects.values('network_id').all()
        snr_num_list = [item['sensor_id'] for item in snr_num]
    else:
        #单一传感器
        snr_num_list = [latest_job_id]
    for snr_item in snr_num_list:
        time_now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
        msg_printer.print2File("\r\ntime task: " + str(time_now) + "\r\n")
        print("num=" + str(num) + ",  " + str(time_now) + ', ' + snr_item)
        tstp_test = tstp_start + num * tstp_step
        num = num + 1
        r = gw0.sendData2Server(snr_item, tstp_test)
        if (r.status == True):
            msg_printer.print2File("post,return:\r\n" + str(r.result))
            dic = r.result
            models.Post_Return.objects.create(result_all_data=dic)
            # 检查数据库是否超限
            delete_data = Delete_data()
            delete_data.count_postdata()
            print("post,return:\r\n" + str(r.result))
        else:
            msg_printer.print2File(r.message)
            print(r.message)


try:
    """定时初始化"""
    job = scheduler.add_job(time_job, 'cron', year=st['year'], month=st['month'], day=st['day'],
                            hour=st['hour'], minute=st['mins'], second='00', id='cron_time 0000')
    scheduler.start()

    job1 = scheduler1.add_job(time_job1, 'interval', days=int(st1['day']), hours=int(st1['hour']),
                              minutes=int(st1['mins']),
                              seconds=0, id='interval_time 0000')
    scheduler1.start()

    # 加载程序时暂停定时器
    apscheduler.job.Job.pause(job)
    apscheduler.job.Job.pause(job1)
    # scheduler1.pause_job(job_id='interval_time 0000')
    print(job)
    print(job1)
except Exception as e:
    print('err:', e)
    scheduler.shutdown()
    scheduler1.shutdown()


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


# 每分钟执行一次更新/添加
try:
    sche.add_job(auto_Timing_time, 'interval', minutes=0, seconds=10, id='interval_time')
    sche.start()
except Exception as e:
    print(e)
    sche.shutdown()


@login_required
def index(request):
    """
    首页
    :param request:
    :return:
    """
    global tcp_client_status
    tcp_status = {'tcp_client_status': tcp_client_status}
    latest_data = models.GWData.objects.values('id', 'sensor_id', 'battery', 'temperature', 'thickness', 'alias').order_by('-id')[:5]
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
    latest_data = models.GWData.objects.values('id', 'sensor_id', 'time_tamp', 'battery', 'temperature', 'thickness', 'alias').order_by('-id')[:5]
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
    # latest_set_param = eval(models.Set_param.objects.filter(id=1).values('param').first()['param'])
    # scheduler调度器中已经存在的定时任务的sensor_id列表
    sche_job_id_list, sche_job_time_list = job_id_list()
    sche_job_id_dict = {}
    print('sche_job_id_list', sche_job_id_list)
    for item in sche_job_id_list:
        if item != "0000":
            sche_job_id_dict[item] = models.Sensor_data.objects.values('alias').get(network_id=item)['alias']
            # sche_job_id_dict['0.0.0.1'] = models.Sensor_data.objects.values('alias').get(network_id=item)['alias']
    print('sche_job_id_dict', sche_job_id_dict)

    context = {
        "time": time_now,
        # "form": form,
        "Day_interval": [i for i in range(0, 32)],
        "Hour_interval": [i for i in range(0, 24)],
        "Minute_interval": [i for i in range(0, 60)],

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

    # elif request.method == "POST":
    #     form = DataForm(request.POST)
    #     # print(form)
    #     if form.is_valid():
    #         mainURL = form.cleaned_data.get("url")
    #         if mainURL:
    #             cunt = models.URL.objects.filter(id=2).count()
    #             if cunt:
    #                 models.URL.objects.filter(id=2).update(mainURL=mainURL)
    #                 gwCtrl.get_url()
    #             else:
    #                 models.URL.objects.create(mainURL=mainURL)
    #                 gwCtrl.get_url()
    #             ret = {'status': True, 'message': '提交成功'}

        # return HttpResponse(json.dumps(ret))


@permissions.check_permission
@login_required
def all_data_report(request):
    """
    全部数据
    :param request:
    :return:
    """
    data_obj = models.GWData.objects.values().order_by('-id')

    return render(request, 'gateway/all_data_report.html', locals())


@permissions.check_permission
@login_required
def thickness_report(request):
    """
    单个传感器厚度曲线
    :param request:
    :return:
    """
    # scheduler调度器中已经存在的定时任务的sensor_id列表
    # sche_job_id_list, sche_job_time_list = job_id_list()
    # sche_job_id_dict = {}
    # for item in sche_job_id_list:
    #     if item != "0000":
    #         sche_job_id_dict[item] = models.Sensor_data.objects.values('alias').get(network_id=item)['alias']

    # db中存在的数据
    data_obj = models.GWData.objects.all().values('sensor_id', 'alias').distinct()
    print(data_obj)
    return render(request, 'gateway/thickness_report.html', locals())


@permissions.check_permission
@login_required
def all_sensor_data(request):
    """
    传感器详情
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
    sensor_obj = models.Sensor_data.objects.all().order_by('-id')
    # 添加下次运行时间
    # sche_obj = scheduler.get_jobs()
    # for i in sensor_obj:
    #     for ii in sche_obj:
    #         if i.sensor_id == ii.id.split(' ')[1]:
    #             i.next_run_time = str(ii.next_run_time).split('+')[0]

    return render(request, "gateway/all_sensor_data.html", locals())


@permissions.check_permission
@login_required
def set_sensor_time(request):
    """
    给传感器设置时间
    :param request:
    :return:
    """
    sensor_obj = models.Sensor_data.objects.all().order_by('-id')
    sche_obj = scheduler.get_jobs()
    for i in sensor_obj:
        # 把next_run_time放进每个传感器对象中
        for ii in sche_obj:
            if i.network_id == ii.id.split(' ')[1]:
                i.next_run_time = str(ii.next_run_time).split('+')[0]
                print(sche_obj)
                print(i.next_run_time)
        received_time_data = models.Sensor_data.objects.filter(sensor_id=i.sensor_id).values('sensor_id', 'received_time_data')
        # 把年月日分别放进每个传感器对象中
        for ii in received_time_data:
            if i.sensor_id == ii['sensor_id']:
                i.month = eval(ii['received_time_data'])['month']
                i.day = eval(ii['received_time_data'])['day']
                i.hour = eval(ii['received_time_data'])['hour']
                i.mins = eval(ii['received_time_data'])['mins']

    return render(request, "gateway/set_sensor_time.html", locals())


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
            time_list = handle_data(arr)  # 处理数据
            print('time_list', time_list)
            if time_list != []:
                received_time_data_dict = {}
                for ii in time_list:
                    received_time_data_dict.update(ii)
                conform = judge_time(received_time_data_dict, '0000')
                if conform:
                    for item in time_list:
                        print('item', item)
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
def set_cycle_time(request):
    """
    设置循环时间
    :param request:
    :return:
    """
    ret = {'status': False, 'message': '循环时间设置失败'}
    try:
        if request.method == 'POST':
            arr = request.POST.getlist('CycleDateList')
            time_list = handle_data(arr)  # 处理数据
            for item in time_list:
                if list(item.values())[0] == '':
                    key = list(item.keys())[0]
                    item[key] = '0'
            print(time_list)
            if time_list[0]['day'] == time_list[1]['hour'] == time_list[2]['mins'] == '0':
                pass
            else:
                for item in time_list:
                    models.Set_Time.objects.filter(id=4).update(**item)
                start_cycle_time(4)
                ret = {'status': True, 'message': '循环时间设置成功'}
                global CycleStatus
                CycleStatus = True
    except Exception as e:
        print(e)

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
            apscheduler.job.Job.pause(job)
        else:
            apscheduler.job.Job.resume(job)
        apscheduler.job.Job.pause(job1)
        print(job)
        print(job1)
    except Exception as e:
        print('start_Timing_time:', e)
        scheduler.shutdown()


def start_cycle_time(nid, reset=False):
    """
    循环时间
    :param nid: 设定时间的id
    :param reset: 重置按钮标志位，如果为true，把循环模式暂停
    :return:
    """
    global st1
    try:
        st1 = models.Set_Time.objects.filter(id=nid).values('day', 'hour', 'mins').first()
        print('st1:', st1)
        st1_temp = {'days': int(st1['day']), 'hours': int(st1['hour']), 'minutes': int(st1['mins'])}
        temp_trigger = scheduler1._create_trigger(trigger='interval', trigger_args=st1_temp)
        scheduler1.modify_job('interval_time 0000', trigger=temp_trigger, next_run_time=datetime.datetime.now()
                                                                                        + datetime.timedelta(
            days=int(st1['day']), hours=int(st1['hour']), minutes=int(st1['mins'])))
        if reset:
            apscheduler.job.Job.pause(job1)
        else:
            apscheduler.job.Job.resume(job1)
        apscheduler.job.Job.pause(job)
        print(job)
        print(job1)
    except Exception as e:
        print(e)
        scheduler1.shutdown()


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
            apscheduler.job.Job.pause(job)
            print(job)
            print(job1)
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
            apscheduler.job.Job.resume(job)
            apscheduler.job.Job.pause(job1)
            print(job)
            print(job.next_run_time)
            print(job1)
            ret = {'status': True, 'message': 'success'}
        print(TimingStatus)
    except Exception as e:
        print(e)
    return HttpResponse(json.dumps(ret))


@login_required
def pause_cycle_time(request):
    """
    暂停循环时间
    :param request:
    :return:
    """
    ret = {'status': False, 'message': None}
    try:
        if CycleStatus:
            apscheduler.job.Job.pause(job1)
            print(job)
            print(job1)
            ret = {'status': True, 'message': 'success'}
            print(CycleStatus)
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
            apscheduler.job.Job.resume(job1)
            apscheduler.job.Job.pause(job)
            print(job)
            print(job1)
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
        apscheduler.job.Job.pause(job)
        ret['status'] = True
        ret['message'] = 'success'
        global TimingStatus
        TimingStatus = False
    except Exception as e:
        print(e)
    return HttpResponse(json.dumps(ret))


@login_required
@csrf_exempt
def reset_Cycle_time(request):
    """
    重置循环时间
    :param request:
    :return:
    """
    ret = {'status': False, 'message': None}
    try:
        models.Set_Time.objects.filter(id=4).update(day='0', hour='0', mins='0')
        start_cycle_time(4, reset=True)
        ret['status'] = True
        ret['message'] = 'success'
        global CycleStatus
        CycleStatus = False
    except Exception as e:
        print(e)
    return HttpResponse(json.dumps(ret))


# @login_required
@csrf_exempt
def manual_get(request, network_id):
    """
    手动触发任务
    :param request:
    :return:
    """
    result = {'status': False, 'message': "获取失败"}
    global btn_sample
    try:
        if not btn_sample and not btn_polling and not auto_operation:
            btn_sample = True  # 手动采集标志位
            global latest_job_id
            latest_job_id = network_id.replace('A', '.')
            print(latest_job_id)
            if models.Set_param.objects.count() == 0:
                models.Set_param.objects.create(menu_get_id=latest_job_id, param="")
            else:
                models.Set_param.objects.filter(id=1).update(menu_get_id=latest_job_id)
            if latest_job_id == '':
                result['message'] = "没有选择传感器"
            else:
                gwData = time_job()
                result = {'status': True, 'message': "获取成功", 'gwData': gwData}
                topic = latest_job_id.rsplit('.', 1)[0] + '.0'
                result['header'] = headers_dict['gwdata']
                result['id'] = 'client'
                client.publish(topic, json.dumps(result))  # 网关手动取数后给服务器返回数据
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
        data_dict = models.GWData.objects.filter(id=nid).values('sensor_id', 'alias', 'data', 'thickness').first()
        data_list = list(enumerate(eval(data_dict['data'])))
        temp = {
            'name': "--名称：" + data_dict['alias'] + ' --厚度：' + data_dict['thickness'],
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
    sensor_id = request.GET.get('sensor_id')
    response = []
    thickness_temp = []
    id = []
    try:
        data_list = list(models.GWData.objects.filter(sensor_id=sensor_id).values('id', 'alias', 'time_tamp', 'thickness'))
        alias = data_list[0]['alias']
        for thick in data_list:
            thickness_temp.append(float(thick['thickness']))
            id.append(thick['id'])


        data_list = list(zip(id, thickness_temp))
        temp = {
            'name': "--名称：" + alias,
            'data': data_list
        }
        print(temp)
        response.append(temp)
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
    sensor_type = sensor_obj._meta.get_field('sensor_type')
    Importance = sensor_obj._meta.get_field('Importance')
    context = {
        "month_cron": [i for i in range(1, 13)],
        "day_cron": [i for i in range(1, 29)],
        "hour_cron": [i for i in range(0, 24)],
        "minute_cron": [i for i in range(0, 60)],
    }

    return render(request, "gateway/edit_sensor_time.html", locals())


@login_required
def add_sensor_page(request):
    """
    增加传感器
    :param request:
    :return:
    """
    sensor_obj = models.Sensor_data.objects.first()
    sensor_type = sensor_obj._meta.get_field('sensor_type')
    Importance = sensor_obj._meta.get_field('Importance')
    context = {
        "month_cron": [i for i in range(1, 13)],
        "day_cron": [i for i in range(1, 29)],
        "hour_cron": [i for i in range(0, 24)],
        "minute_cron": [i for i in range(0, 60)],
    }
    return render(request, 'gateway/add_sensor_time.html', locals())


@csrf_exempt
def receive_gw_data(request):
    """
    接收网关的数据，用于在网关页面操作传感器的增删改操作
    :param request:
    :return:
    """
    if request.method == 'POST':
        # receive_data是接收网关自己的数据
        receive_data = json.loads(request.POST.get('data'))
        response = {'status': False, 'msg': '操作失败', 'receive_data': receive_data}
        print('receive_data', receive_data)  # {"received_time_data":{"month":[],"day":[],"hour":["1"],"mins":["1"]},"sensor_id":"536876188","alias":"1号传感器","network_id":"0.0.0.1","choice":"update"}

        topic = receive_data['network_id'].rsplit('.', 1)[0] + '.0'

        if receive_data['sensor_type'] == '':
            receive_data['sensor_type'] = '0'
        if receive_data['Importance'] == '':
            receive_data['Importance'] = '0'

        sensor_id = receive_data['sensor_id']
        received_time_data = receive_data['received_time_data']
        choice = receive_data.pop('choice')

        received_time_data = handle_receive_data(received_time_data)

        # 验证时间
        conform = judge_time(received_time_data, receive_data['network_id'])

        # 更新
        if choice == 'update':
            response = update_sensor(receive_data, conform, response)
            if response['status']:
                data = {'id': 'client', 'header': 'update_sensor', 'status': True, 'receive_data': receive_data}
                client.publish(topic, json.dumps(data))  # 把网关更新的sensor数据发送给server

        # 添加
        elif choice == 'add':
            response = add_sensor(receive_data, sensor_id, conform, response)
            if response['status']:
                data = {'id': 'client', 'header': 'add_sensor', 'status': True, 'receive_data': receive_data}
                client.publish(topic, json.dumps(data))  # 把网关增加的sensor数据发送给server

        # 删除
        elif choice == 'remove':
            response = remove_sensor(sensor_id, response)
            if response['status']:
                data = {'id': 'client', 'header': 'remove_sensor', 'status': True, 'receive_data': receive_data}
                client.publish(topic, json.dumps(data))  # 把网关增加的sensor数据发送给server

        return HttpResponse(json.dumps(response))


def receive_server_data(data):
    """
    接收服务器的数据，用于在服务器页面操作传感器的增删改操作
    :param data:
    :return:
    """
    receive_data = data
    response = {'status': False, 'msg': '操作失败', 'receive_data': receive_data}
    # print('receive_data', receive_data)  # {"received_time_data":{"month":[],"day":[],"hour":["1"],"mins":["1"]},"sensor_id":"536876188","alias":"1号传感器","network_id":"0.0.0.1","choice":"update"}

    if receive_data['sensor_type'] == '':
        receive_data['sensor_type'] = '0'
    if receive_data['Importance'] == '':
        receive_data['Importance'] = '0'

    sensor_id = receive_data['sensor_id']
    received_time_data = receive_data['received_time_data']
    choice = receive_data.pop('choice')

    received_time_data = handle_receive_data(received_time_data)

    # 验证时间
    conform = judge_time(received_time_data, receive_data['network_id'])

    # 更新
    if choice == 'update':
        response = update_sensor(receive_data, conform, response)

    # 添加
    elif choice == 'add':
        response = add_sensor(receive_data, sensor_id, conform, response)

    # 删除
    elif choice == 'remove':
        response = remove_sensor(sensor_id, response)

    return response




def update_sensor(receive_data, conform, response):
    sensor_id = receive_data.pop('sensor_id')
    if conform:
        # 更新sensor数据
        models.Sensor_data.objects.filter(sensor_id=sensor_id).update(**receive_data)
        response['status'] = True
        response['msg'] = '更新任务成功'
        # 更新成功，同时同步数据库和调度器
        auto_Timing_time()
    else:
        response['msg'] = '输入时间和现有传感器时间冲突，请输入其他时间'

    return response


def add_sensor(receive_data, sensor_id, conform, response):
    network_id = receive_data['network_id']
    sensor_id_list = []
    sensor_ids = list(models.Sensor_data.objects.values('sensor_id'))
    for item in sensor_ids:
        sensor_id_list.append(item['sensor_id'])
    if sensor_id == "":
        response['msg'] = '传感器ID不能为空！'
    elif sensor_id in sensor_id_list:
        response['msg'] = '已有此传感器，请返回编辑此传感器'
    elif conform:
        # 添加sensor数据
        print(receive_data)
        # 添加成功，同时同步数据库和调度器
        # 把'1.1.1.4'转化成16进制0x01010104
        hex_network_id = str_hex_dec(network_id)
        command = "set 74 " + sensor_id + " " + str(int(hex_network_id, 16))
        print('command', command)
        # add_sensor_response = gw0.serCtrl.getSerialresp(command)
        # print('add_sensor_response', add_sensor_response.strip('\n'))
        add_sensor_response = 'ok'
        if add_sensor_response.strip('\n') == 'ok':
            models.Sensor_data.objects.create(**receive_data)
            response['status'] = True
            response['msg'] = '添加任务成功'
        auto_Timing_time()
    else:
        response['msg'] = '输入时间和现有传感器时间冲突，请输入其他时间'

    return response

def remove_sensor(sensor_id, response):
    command = "set 74 " + sensor_id + " 0"
    print('command', command)
    # remove_sensor_response = gw0.serCtrl.getSerialresp(command)
    # print('remove_sensor_response', remove_sensor_response.strip('\n'))
    remove_sensor_response = 'ok'
    if remove_sensor_response.strip('\n') == 'ok':
        models.Sensor_data.objects.filter(sensor_id=sensor_id).delete()
        response['status'] = True
        response['msg'] = '删除任务成功'
        # 删除成功，同时同步数据库和调度器
    auto_Timing_time()

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
        latest_set_val = models.Sensor_data.objects.filter(sensor_id__endswith=val_dict['sensor_id']).values('cHz', 'gain', 'avg_time', 'Hz', 'Sample_depth', 'Sample_Hz')[0]
        print(latest_set_val)
        network_id = models.Sensor_data.objects.filter(sensor_id__endswith=val_dict['sensor_id']).values('network_id')[0]['network_id']
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
            update_sensor_data(val_dict)
            models.Sensor_data.objects.filter(sensor_id=val_dict['sensor_id']).update(**new_val_dict)

            result = {'status': True, 'message': '设置成功'}
    except Exception as e:
        print(e, '设置参数失败')

    return HttpResponse(json.dumps(result))


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


def server_manual_get(network_id):
    """
    服务器手动触发任务
    :param request:
    :return:
    """
    result = {'status': False, 'message': '获取失败', 'gwData':{}}
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
                result['message'] = "没有选择传感器"
            else:
                # 需要返回网关数据
                gwData = time_job()
                if gwData == {}:
                    result['message'] = "未获取到数据"
                else:
                    result = {'status': True, 'message': "获取成功", 'gwData': gwData}
            btn_sample = False
        else:
            if btn_polling:
                result['message'] = "请稍等，定时轮询模式正在采集数据..."
            elif auto_operation or btn_sample:
                result['message'] = "请稍等，已有传感器正在采集数据..."
    except Exception as e:
        print(e)
        btn_sample = False
    return result


def check_gwntid(ntid_response):
    """
    检查gwntid合法性
    :param ntid_response:
    :return:
    """
    success = True

    return success


def init_gwntid():
    """
    首先检查是否已经自动配置了gwntid，一般没有gwntid表示网关是初次上电
    :return:
    """
    gw_network_id = models.GW_network_id.objects.all()
    if not gw_network_id:
        command = "get gwntid"
        print('command', command)
        # gwntid = gw0.serCtrl.getSerialresp(command)
        gwntid = '0.0.1.0'
        print('gwntid_response', gwntid.strip('\n'))
        if check_gwntid(gwntid):
            models.GW_network_id.objects.create(network_id=gwntid)
    else:
        gwntid = gw_network_id.values('network_id')[0]['network_id']

    return gwntid


def str_hex_dec(network_id):
    hex_network_id = '0x'
    for network_item in network_id.split('.'):
        if len(hex(int(network_item)).split('0x')[1]) == 1:
            hex_network_id += '0' + hex(int(network_item)).split('0x')[1]
        else:
            hex_network_id += hex(int(network_item)).split('0x')[1]
    return hex_network_id


# 每次加载程序或者刷新页面的时候马上更新数据库和调度器中的任务一次
auto_Timing_time()
# check_online_of_sensor_status()



