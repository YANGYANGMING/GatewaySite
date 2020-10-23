import json, time
from socket import *
from utils.SM2 import *
from gateway.views import views
from gateway import models
from GatewaySite import settings


# ip_port = ('192.168.0.153', 8080)
ip_port = ('121.36.220.210', 8080)
# ip_port = ('39.98.229.50', 9696)
back_log = 5
buffer_size = 2048

OPERATION_CHOICE = {
    '1': 'SET',
    '2': 'GET',
    '3': 'UPDATA',
    '4': 'CAL'
}

OPERATION_TYPE_ACK_CHOICE = {
    '00': '命令无效',
    '11': '命令接收成功，并设置成功',
    '10': '命令接收成功，但设置失败',
    '21': '命令接收成功，查询结果如下',
    '20': '命令接收成功，但未查询到相关信息',
    '31': '命令接收成功，并更新成功',
    '30': '命令接收成功，但更新失败',
    '41': '命令接收成功，并校准成功',
    '40': '命令接收成功，但校准失败',
}

DATA = {
    "Current_T": "2020-8-3 13:18:28",
    "Sensor_Mac": "123-456-789",
    "Gauge_Cycle": "48:00:00",
    "Material_Type": "45",
    "Material_Temp": 35.00,
    "Environmental_Temp": 30.00,
    "Sound_Velocity": 3249.0,
    "Voltage": 6.0,
    "LIM_Voltage": 4.0,
    "Ultrasonic_Freq": 10.0,
    "Time_Cycle": "72:00:00",
    "Status": True,
    "Thickness": [
        {"Sensor_NO": "10010001201906019001", "Thickness": 5.35},
    ]
}


class HandleSocketOperation:
    def __init__(self):
        pass

    def GET(self, tcp_client, sensor_id, **params):
        """
        特检局要查询的传感器的信息
        :param tcp_client:
        :param sensor_id:
        :param params:
        :return:
        """
        print('GET.....................................')
        Sensor_Mac = sensor_id[-10:]
        cur_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
        sensor_obj = models.Sensor_data.objects.values('received_time_data', 'material', 'Hz', 'network_id', 'battery',
                                                       'alarm_battery').get(sensor_id=sensor_id)
        try:
            material_id = sensor_obj['material']
            # 转定时时间格式
            received_time_data = eval(sensor_obj['received_time_data'])
            Gauge_Cycle = str(int(received_time_data['days']) * 24 + int(received_time_data['hours'])) + ":00:00"
            # 计算true_sound_V
            material_obj = models.Material.objects.values('sound_V').get(id=material_id)
            sound_V = float(material_obj['sound_V'])
            # 超声频率
            Ultrasonic_Freq = float(sensor_obj['Hz']) * 1000
            # 此传感器采数量
            network_id = sensor_obj['network_id']
            Total_Numbers = models.GWData.objects.filter(network_id=network_id).count()
            # 电量 --> 电压
            battery = sensor_obj['battery']
            alarm_battery = sensor_obj['alarm_battery']
            operation_ack_data = {
                "OPERATION_TYPE_ACK": 21,
                "Current_T": cur_time,
                "Sensor_Mac": Sensor_Mac,
                "Gauge_Cycle": Gauge_Cycle,
                "Sound_Velocity": sound_V,
                "Voltage": 5.0 + round(float(battery) / 100, 1),
                "LIM_Voltage": 5.0 + round(float(alarm_battery) / 100, 1),
                "Ultrasonic_Freq": Ultrasonic_Freq,
                "Time_Cycle": "72:00:00",
                "Total_Numbers": Total_Numbers
            }
        except Exception as e:
            operation_ack_data = {
                "OPERATION_TYPE_ACK": 20,
                "Current_T": cur_time,
            }
        json_data = json.dumps(operation_ack_data).encode('utf-8')
        tcp_client.send(json_data)
        print("发送GET数据==", json_data)
        views.log.log(True, '回复特检局的GET请求，发送查询的数据到特检局', sensor_obj['network_id'], None)

    def SET(self, tcp_client, sensor_id, **params):
        print('SET.....................................')
        Gauge_Cycle = params['Gauge_Cycle'].split(':')
        received_time_data = {
                            'days': str(int(Gauge_Cycle[0]) // 24),
                            'hours': str(int(Gauge_Cycle[0]) % 24),
                            'minutes': str(int(Gauge_Cycle[1]))
                        }
        network_id = models.Sensor_data.objects.values('network_id').get(sensor_id=sensor_id)['network_id']
        if int(received_time_data['days']) == 0 and int(received_time_data['hours']) < 12:  # 采样周期不能小于12小时
            print('采样周期不能小于12小时!!!')
            cur_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
            operation_ack_data = {
                "Current_T": cur_time,
                "OPERATION_TYPE_ACK": 10
            }
        else:
            update_result = models.Sensor_data.objects.filter(sensor_id=sensor_id).update(received_time_data=received_time_data)
            data = {'id': 'client', 'header': 'update_administration_params', 'status': True, 'msg': '更新特检局设置的参数', 'network_id': network_id, 'received_time_data': received_time_data}
            try:
                views.client.publish('pub', json.dumps(data))  # 把特检局设置的参数发送给server
            except Exception as e:
                print(e)
            cur_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
            if update_result:
                operation_ack_data = {
                    "Current_T": cur_time,
                    "OPERATION_TYPE_ACK": 11
                }
            else:
                operation_ack_data = {
                    "Current_T": cur_time,
                    "OPERATION_TYPE_ACK": 10
                }
        json_data = json.dumps(operation_ack_data).encode('utf-8')
        tcp_client.send(json_data)
        print("发送SET数据==", json_data)
        views.log.log(True, '设置特检局发送过来的参数', network_id, None)

    def UPDATA(self, tcp_client, sensor_id, **params):
        pass

    def CAL(self, tcp_client, sensor_id, **params):
        pass


operation_func_obj = HandleSocketOperation()


def mysocket(send_data):
    """
    与管理局平台通讯
    :param send_data:
    :return:
    """
    tcp_client = socket(AF_INET, SOCK_STREAM)
    try:
        tcp_client.connect(ip_port)
        print('send...')
        json_data = json.dumps(send_data).encode('utf-8')
        tcp_client.send(json_data)
        sensor_obj = models.Sensor_data.objects.values('network_id').get(sensor_id=send_data['DATA']['Thickness'][0]['Sensor_NO'])
        views.log.log(True, '上传采集到的数据到特检局', sensor_obj['network_id'], None)

        sensor_id = send_data['DATA']['Thickness'][0]['Sensor_NO']
        print(sensor_id)

        # 接收消息
        print('recv...')
        while True:
            recv_response = tcp_client.recv(buffer_size).decode('utf-8')
            recv_response = json.loads(recv_response)
            print('recv_response == ', recv_response, tcp_client)

            operation = str(recv_response['RESPONSE_CODE'].get('operation', '0'))
            print("operation==========", operation)
            if operation == '0':
                tcp_client.close()
                break
            else:
                operation_type = OPERATION_CHOICE[operation]
                params = recv_response.get('BODY', {})
                print("params", params)

                getattr(operation_func_obj, operation_type)(tcp_client, sensor_id, **params)

    except Exception as e:
        print('通讯出错', e)
        views.log.log(False, '网关与特检局通讯出错', None, None)
        tcp_client.close()


# if __name__ == '__main__':
def sign_and_communicate_with_server(DATA):
    """
    签名、与服务器通讯
    :param DATA:
    :return:
    """
    len_para = int(Fp / 4)
    # private_key = '191421ea268b74310a37963b60c2735884c6cc6bdc92f5be2001464393d2d102'
    private_key = settings.private_key
    Pa = kG(int(private_key, 16), sm2_G, len_para)
    print('已知私钥计算公钥Pa: %s' % Pa)

    k = get_random_str(len_para)
    print('随机数为 = %s' % k)

    e = str(DATA)
    e = e.encode('utf-8')
    e = e.hex()  # 消息转化为16进制字符串
    # 签名数据无预处理情况下，需要先做预处理，预处理分两步
    ID = settings.ID  # 预处理第一步，Z=SM3(ENTL∣∣ID∣∣a∣∣b∣∣xG|yG|xA|yA)
    EN = len(ID) * 4
    ENTL = hex(EN).replace('0x', '').zfill(4)  # 两个字节标识用户id的比特数
    A = 'FFFFFFFEFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF00000000FFFFFFFFFFFFFFFC'  # 系统曲线参数a
    B = '28E9FA9E9D9F5E344D5A9E4BCF6509A7F39789F515AB8F92DDBCBD414D940E93'  # 系统曲线参数b
    D = '32C4AE2C1F1981195F9904466A39C9948FE30BBFF2660BE1715A4589334C74C7'  # 坐标xG
    E = 'BC3736A2F4F6779C59BDCEE36B692153D0A9877CC62A474002DF32E52139F0A0'  # 坐标yG
    ZZ = Hash_sm3('%s%s%s%s%s%s%s' % (ENTL, ID, A, B, D, E, Pa), 1)  # 预处理第一步，ID为签名者的标识，A/B/D/E为标准给定的值，Pa为公钥
    x = Hash_sm3('%s%s' % (ZZ, e), 1)  # 预处理第二步，ZZ与e（待签名数据）级联，得到x,即SM2入参
    print('预处理值= %s' % x)
    Sig = Sign(x, private_key, k, len_para, 1)  # Sign(E, DA, K,len_para,Hexstr = 0):  # 签名函数, E消息的hash，DA私钥，K随机数，均为16进制字符串
    print('签名数据= %s' % Sig)

    # 最后发送的数据
    UPLOAD_DATA = {"Digital_Signature": Sig, "DATA": DATA}
    # json_data = json.dumps(UPLOAD_DATA)
    # print(json_data)

    mysocket(UPLOAD_DATA)

