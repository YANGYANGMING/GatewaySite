from django.shortcuts import render, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from gateway.origin_base import Origin
from utils.FormClass import DataForm

import apscheduler.job
from apscheduler.schedulers.background import BackgroundScheduler

import datetime
import serial

from gateway.eelib.eelib.gateway import *
from gateway.eelib.eelib.sensor import SerialCtrl
from gateway.eelib.eelib.message import *

msg_file = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/message.txt'
msg_printer = MessagePrinter(msg_file)

gwCtrl = GatewayCtrl()

gser = serial.Serial("/dev/ttyS3", 115200, timeout=1)
# gser = serial.Serial("/dev/ttyAMA0", 115200, timeout=1)
gw0 = Gateway(gser)
serCtrl = SerialCtrl(gser)

i = 0
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


add_sensor = 0
del_sensor = 0

# Timing task start flag bit
CycleStatus = False
TimingStatus = False

# Instantiate timer task
scheduler = BackgroundScheduler()
scheduler1 = BackgroundScheduler()
sche = BackgroundScheduler()
clear_sche = BackgroundScheduler()

st = models.Set_Time.objects.filter(id=1).values('year', 'month', 'day', 'hour', 'mins')[0]
st1 = models.Set_Time.objects.filter(id=3).values('day', 'hour', 'mins')[0]
# Initialize timing data after program restart
models.Set_Time.objects.filter(id=2).update(month='', day='', hour='', mins='')
models.Set_Time.objects.filter(id=4).update(day='0', hour='0', mins='0')
# Initialize original status infomation
models.TimeStatus.objects.filter(id=1).update(timing_status='false', cycle_status='false', text_status='已暂停',
                                              button_status='暂停')

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
            db_job_list = list(models.Rcv_server_data.objects.values('sensor_id', 'received_time_data'))
            # The list of sensor_id and sensor_time for scheduled tasks that already exist in the scheduler
            sche_job_id_list, sche_job_time_list = job_id_list()
            # Compare: when adding or updating tasks in the database, add or update schedluer tasks
            for db_job in db_job_list:
                received_time_data_dict = eval(db_job['received_time_data'])
                jobs_id = 'cron_time ' + db_job['sensor_id']
                db_job_id_list.append(db_job['sensor_id'])
                if db_job['sensor_id'] in sche_job_id_list:
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
            global latest_job_id  # 0005
            latest_job_id = scheduler.get_jobs()[0].id.split(' ')[1]
            # print(latest_job_id)
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


def judge_time(received_time_data_dict, sche_job_time_list):
        """
        判断时间是否冲突，判断方法：先对比mins，如果mins有重复时间或者有'*'，以对比mins的方法对比hour的值，
        如果hour有重复时间，对比month和day，一旦发现有重复时间，conform = False，并且跳出循环
        :param received_time_data_dict: 接收到的时间字典：{'day': '*', 'month': '2', 'mins': '0,30', 'hour': '6'}
        :param sche_job_time_list: 任务调度器中的任务时间：
                            [{'year': '*', 'month': '2,5', 'day': '*', 'mins': '0', 'hour': '6'},
                            {'year': '*', 'month': '1,5', 'day': '*', 'mins': '29', 'hour': '18'},
                            {'year': '*', 'month': '1', 'day': '*', 'mins': '29', 'hour': '18'},
                            {'year': '*', 'month': '*', 'day': '*', 'mins': '*', 'hour': '*'}]
        :return:
        """
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
    global i
    global latest_job_id
    global btn_polling
    global auto_operation
    if latest_job_id == '0000':
        # Polling sensor
        snr_num = models.Sensor_data.objects.values('sensor_id').all()
        snr_num_list = [item['sensor_id'] for item in snr_num]
        btn_polling = True  # Polling collection flag bit
        pause_all_sensor()
    else:
        # 单一传感器，手动采集数据/自动采集数据
        snr_num_list = [latest_job_id]
        if btn_sample:  # 如果是手动采样
            pause_all_sensor()
        else:
            auto_operation = True  # 自动采集标志位
    print('btn_polling', btn_polling)
    print('auto_operation', auto_operation)
    print('btn_sample', btn_sample)
    for snr_item in snr_num_list:
        time_now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
        msg_printer.print2File("\r\ntime task: " + str(time_now) + "\r\n")
        print("i=" + str(i) + ",  " + str(time_now) + ', ' + snr_item)
        tstp_test = tstp_start + i * tstp_step
        i = i + 1
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

    btn_polling = False
    auto_operation = False
    resume_all_sensor()
    print('btn_polling2', btn_polling)
    print('auto_operation2', auto_operation)
    print('btn_sample2', btn_sample)


def time_job1():
    """
    循环模式任务: interval
    :return:
    """
    global i
    global latest_job1_id
    if latest_job1_id == '0000':
        #轮询传感器
        snr_num = models.Sensor_data.objects.values('sensor_id').all()
        snr_num_list = [item['sensor_id'] for item in snr_num]
    else:
        #单一传感器
        snr_num_list = [latest_job_id]
    for snr_item in snr_num_list:
        time_now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
        msg_printer.print2File("\r\ntime task: " + str(time_now) + "\r\n")
        print("i=" + str(i) + ",  " + str(time_now) + ', ' + snr_item)
        tstp_test = tstp_start + i * tstp_step
        i = i + 1
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
            print('operation_status', operation_status)

        job_obj.pause()
        print('job_obj_pause', job_obj)


def resume_all_sensor():
    """轮询or手动触发结束，恢复所有传感器"""
    for job_obj in scheduler.get_jobs():
        print('operation_status', operation_status)
        if job_obj.id[-4:] == "0000" and not operation_status:
            print('job_obj_resume0000', job_obj)
            pass
        else:
            job_obj.resume()
            print('job_obj_resume', job_obj)


# 每分钟执行一次更新/添加
# try:
#     sche.add_job(auto_Timing_time, 'interval', minutes=0, seconds=10, id='interval_time')
#     sche.start()
# except Exception as e:
#     print(e)
#     sche.shutdown()


@login_required
def index(request):
    """
    首页
    :param request:
    :return:
    """
    origin_obj = Origin()
    latest_data_one = models.GWData.objects.values('id').last()['id']
    latest_data = models.GWData.objects.all().order_by('-id')[:5]
    sensor_nums = models.Rcv_server_data.objects.all().count()
    global add_sensor
    global del_sensor
    add_snr = add_sensor
    del_snr = del_sensor

    return render(request, 'index.html', locals())


@login_required
def config_time(request):
    """
    设置时间
    :param request:
    :return:
    """
    origin_obj = Origin()
    time_now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
    form = DataForm()
    # 最新的X条数据
    latest_data = models.GWData.objects.all().order_by('-id')[:5]
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
    latest_set_param = eval(models.Set_param.objects.filter(id=1).values('param').first()['param'])

    # scheduler调度器中已经存在的定时任务的sensor_id列表
    sche_job_id_list, sche_job_time_list = job_id_list()
    sche_job_id_dict = {}
    for item in sche_job_id_list:
        if item != "0000":
            sche_job_id_dict[item] = models.Sensor_data.objects.values('alias').get(sensor_id=item)['alias']

    context = {
        "time": time_now,
        "form": form,
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

    ret = {'status': False, 'message': '提交失败'}
    if request.method == "GET":
        form = DataForm()
        return render(request, 'gateway/config_time.html', locals())

    elif request.method == "POST":
        form = DataForm(request.POST)
        # print(form)
        if form.is_valid():
            mainURL = form.cleaned_data.get("url")
            if mainURL:
                cunt = models.URL.objects.filter(id=2).count()
                if cunt:
                    models.URL.objects.filter(id=2).update(mainURL=mainURL)
                    gwCtrl.get_url()
                else:
                    models.URL.objects.create(mainURL=mainURL)
                    gwCtrl.get_url()
                ret = {'status': True, 'message': '提交成功'}

        return HttpResponse(json.dumps(ret))


@login_required
def all_data_report(request):
    """
    全部数据
    :param request:
    :return:
    """
    origin_obj = Origin()
    data_obj = models.GWData.objects.all().order_by('-id')

    return render(request, 'gateway/all_data_report.html', locals())


@login_required
def thickness_report(request):
    """
    单个传感器厚度曲线
    :param request:
    :return:
    """
    # scheduler调度器中已经存在的定时任务的sensor_id列表
    sche_job_id_list, sche_job_time_list = job_id_list()
    sche_job_id_dict = {}
    for item in sche_job_id_list:
        if item != "0000":
            sche_job_id_dict[item] = models.Sensor_data.objects.values('alias').get(sensor_id=item)['alias']
    return render(request, 'gateway/thickness_report.html', locals())


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
    sensor_obj = models.Sensor_data.objects.all()
    sche_obj = scheduler.get_jobs()
    for i in sensor_obj:
        for ii in sche_obj:
            if i.sensor_id == ii.id.split(' ')[1]:
                i.next_run_time = str(ii.next_run_time).split('+')[0]

    return render(request, "gateway/all_sensor_data.html", locals())


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
                global latest_job_id
                for ii in time_list:
                    received_time_data_dict.update(ii)
                sche_job_time_list = []
                # 不验证正在修改的传感器的时间
                for job_obj in scheduler.get_jobs():
                    if job_obj.id.split(' ')[1] != '0000':
                        sche_job_time_list.append({'year': str(job_obj.trigger.fields[0]),
                                                   'month': str(job_obj.trigger.fields[1]),
                                                   'day': str(job_obj.trigger.fields[2]),
                                                   'hour': str(job_obj.trigger.fields[5]),
                                                   'mins': str(job_obj.trigger.fields[6])})
                conform = judge_time(received_time_data_dict, sche_job_time_list)
                if conform:
                    for item in time_list:
                        print('item', item)
                        models.Set_Time.objects.filter(id=2).update(**item)
                    start_Timing_time(2)
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
    定时时间
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


@login_required
@csrf_exempt
def manual_get(request):
    """
    手动触发任务
    :param request:
    :return:
    """
    result = {'status': False, 'message': "获取失败"}
    global btn_sample
    try:
        if request.method == "POST" and not btn_sample and not btn_polling and not auto_operation:
            btn_sample = True  # 手动采集标志位
            global latest_job_id
            latest_job_id = request.POST.get('sensor_id')
            print(latest_job_id)
            models.Set_param.objects.filter(id=1).update(menu_get_id=latest_job_id)
            if latest_job_id == '':
                result['message'] = "没有选择传感器"
            else:
                time_job()
                result = {'status': True, 'message': "获取成功"}
            btn_sample = False
            print('btn_sample2', btn_sample)
        else:
            if btn_polling:
                result['message'] = "请稍等，定时轮询模式正在采集数据..."
            elif auto_operation or btn_sample:
                result['message'] = "请稍等，已有传感器正在采集数据..."
    except Exception as e:
        print(e)
        btn_sample = False

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
        data_dict = models.GWData.objects.filter(id=nid).values('sensor_id', 'alias__alias', 'data', 'time_tamp', 'thickness').first()
        data_list = list(enumerate(eval(data_dict['data'])))
        temp = {
            'name': "--名称：" + data_dict['alias__alias'] + " --时间：" + data_dict['time_tamp'] + ' --厚度：' + data_dict['thickness'],
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
    data_temp = []
    id_temp = []
    try:
        data_dict = list(models.GWData.objects.filter(sensor_id=sensor_id).values('id', 'thickness'))[-101:]
        for thick in data_dict:
            data_temp.append(float(thick['thickness']))
            id_temp.append(thick['id'])

        data_list = list(zip(id_temp, data_temp))
        temp = {
            'name': "厚度数据集",
            'data': data_list
        }
        response.append(temp)
    except Exception as e:
        print(e)

    return HttpResponse(json.dumps(response))


@csrf_exempt
def receive_server_data(request):
    """
    接收服务器的数据
    :param request:
    :return:
    """
    sensor_id_list = list(models.Rcv_server_data.objects.values('sensor_id'))
    if request.method == 'POST':
        receive_data = request.POST.get('data')
        receive_data = eval(receive_data)
        response = {'status': False, 'msg': None, 'receive_data': receive_data}
        # sensor_id_list = [{'sensor_id': '10010001201908230001'}, {'sensor_id': '10010001201908230002'}, {'sensor_id': '10010001201908230003'}]
        # receive_data = [[{'time_data': {'month': '*', 'day': '*', 'hour': '16', 'mins': '37'}}, {'sensor_id': '9001'}, {'remove': 'false'}, {'alias': '传感器X号'}, ], ]
        # print(receive_data)
        for item in receive_data:
            # 参数parameter数量有误
            if len(item[0]['time_data']) != 4:
                response['msg'] = '参数个数有误，需要4个参数，给了%s个！' % len(item[0]['time_data'])
                return HttpResponse(json.dumps(response))
            # 参数值有误
            for k, v in item[0]['time_data'].items():  # {'month': '*', 'day': '*', 'hour': '16', 'mins': '37'}
                if v == '*':
                    pass
                else:
                    try:
                        v_list = v.split(',')
                        for vv in v_list:
                            isinstance(int(vv), int)
                    except Exception:
                        response['msg'] = '输入参数值有误，请重新输入！参数值只支持*和int类型'
                        return HttpResponse(json.dumps(response))

            if item[2]['remove'] == 'false':
                sche_job_time_list = []
                #不验证正在修改的传感器的时间
                for job_obj in scheduler.get_jobs():
                    if job_obj.id.split(' ')[1] != item[1]['sensor_id']:
                        sche_job_time_list.append({'year': str(job_obj.trigger.fields[0]),
                                                   'month': str(job_obj.trigger.fields[1]),
                                                   'day': str(job_obj.trigger.fields[2]),
                                                   'hour': str(job_obj.trigger.fields[5]),
                                                   'mins': str(job_obj.trigger.fields[6])})
                conform = judge_time(item[0]['time_data'], sche_job_time_list)
                if conform:
                    # 更新任务
                    if item[1] in sensor_id_list:
                        models.Rcv_server_data.objects.filter(sensor_id=item[1]['sensor_id']).update(
                                                                received_time_data=item[0]['time_data']
                                                            )
                        # # 更新sensor数据
                        # models.Sensor_data.objects.filter(sensor_id=item[1]['sensor_id']).update()
                        response['status'] = True
                        response['msg'] = '更新任务成功'
                    # 添加任务
                    else:
                        models.Rcv_server_data.objects.create(
                                                                sensor_id=item[1]['sensor_id'],
                                                                received_time_data=item[0]['time_data']
                                                            )
                        # 添加sensor数据
                        models.Sensor_data.objects.create(
                                                                sensor_id=item[1]['sensor_id'],
                                                                alias=item[3]['alias']
                                                            )
                        global add_sensor
                        add_sensor += 1
                        response['status'] = True
                        response['msg'] = '添加任务成功'
                    # 更新或者添加成功，同时同步数据库和调度器
                    auto_Timing_time()
                else:
                    response['msg'] = '输入时间和现有传感器时间冲突，请输入其他时间'

            # 删除任务
            elif item[2]['remove'] == 'true':
                if item[1] in sensor_id_list:
                    models.Rcv_server_data.objects.filter(sensor_id=item[1]['sensor_id']).delete()
                    # 删除sensor数据
                    models.Sensor_data.objects.filter(sensor_id=item[1]['sensor_id']).delete()
                    global del_sensor
                    del_sensor += 1
                    response['status'] = True
                    response['msg'] = '删除任务成功'
                    # 删除成功，同时同步数据库和调度器
                    auto_Timing_time()

        return HttpResponse(json.dumps(response))


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
        cmd_str = str(val_dict['sensor_id'][-4:] + " " + val_dict['cHz'] + " " + val_dict['gain'] + " " + val_dict[
            'avg_time'] + " " + val_dict['Hz'] + " " + val_dict['Sample_depth'] + " " + val_dict['Sample_Hz'])
        command = "set " + cmd_str
        print('command', command)
        set_val_response = serCtrl.getSerialresp(command)
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



# 每次加载程序或者刷新页面的时候马上更新数据库和调度器中的任务一次
auto_Timing_time()








