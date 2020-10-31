
import base64
import json
import os

from .sensor import *
from .alg.emat.emat import *
from .message import *

from gateway import models
from ..count_db import Delete_data
from utils import handle_func


class GatewayCtrl():
    def __init__(self):
        pass

    def fmtEncode(self, data_t):
        js_data = json.dumps(data_t)
        b64_data = base64.b64encode(js_data.encode('utf-8'))
        return b64_data

    def fmtDecode(self, b64_data):
        data_t = base64.b64decode(b64_data)
        js_data = json.loads(data_t.decode('utf-8'))
        return js_data


class Gateway(GatewayCtrl):

    def __init__(self, gser):
        self.serCtrl = SerialCtrl(gser)
        self.delete_data = Delete_data()

    def localCalThickness(self, svrdata, Sound_V):
        """
        计算厚度值
        :param svrdata:
        :param Sound_V:
        :return:
        """
        thick_mm = -19
        if(svrdata["data_len"] == 2048):
            # thick_mm = calThickness(data=svrdata['data'], gain_db=svrdata['gain'], Sound_V=Sound_V)
            thick_mm, Sound_T, PeakIndex1, PeakIndex2 = calThickness(data=svrdata['data'], gain_db=60, Sound_V=Sound_V)
        return thick_mm

    def handle_deviation_data(self, data):
        """
        处理数据偏滞
        :param data:
        :return:
        """
        if len(data) == 2048:
            sum_data = sum(data)
            average = sum_data // len(data)
            difference = average - 2048
            print('difference', difference)
            new_data = []
            for item in data:
                if item - difference > 0:
                    new_data.append(item - difference)
                else:
                    new_data.append(0)
            return new_data
        return data

    def sendData2Server(self, network_id):
        """获取发送给服务器的网关数据"""
        ret = Message(st=False)
        gwData = {}
        """snrdata是串口发送过来的原始数据"""
        snrdata = self.serCtrl.getSensorData(network_id)  # snrdata对象
        # print(snrdata.sensorID)
        # print(snrdata.data)

        if(snrdata.sensorID == 0):
            ret.status = False
            ret.message = 'no sensor data'
        else:
            ret.status = True
            gwData = snrdata.cvrt2gwData()
            # print(gwData)
            # 处理偏滞
            processed_data = self.handle_deviation_data(gwData['data'])
            gwData['data'] = processed_data
            # 把gwData['time_tamp']转换成结构化时间，为从数据库取数比较做准备
            localTime = time.localtime(gwData['time_tamp'])
            strTime = time.strftime("%Y-%m-%d %H:%M:%S", localTime)
            gwData['time_tamp'] = strTime
            # 转换network_id
            network_id = handle_func.str_dec_hex(gwData['network_id'])
            material_id = models.Sensor_data.objects.values('material').get(network_id=network_id)['material']
            # 取出该材料的声速
            Material_obj = models.Material.objects.values('sound_V', 'temperature_co').get(id=material_id)
            sound_V = Material_obj['sound_V']
            temperature_co = Material_obj['temperature_co']
            temperature = gwData['temperature']
            true_sound_V = sound_V - ((temperature - 25) * temperature_co)
            print('true_sound_V', true_sound_V)
            # 计算厚度值，并把厚度写入网关数据中
            thickness = self.localCalThickness(svrdata=gwData, Sound_V=true_sound_V)
            gwData['thickness'] = thickness
            sensor_data_obj = models.Sensor_data.objects.filter(network_id=network_id)
            gwData['network_id'] = sensor_data_obj[0]
            gwData.pop('sensor_id')
            # 把网关数据写入数据库
            models.GWData.objects.create(**gwData)
            # 更新最新电量到对应传感器
            sensor_data_obj.update(battery=gwData['battery'], sensor_online_status=1)
            # 检查网关数据是否超限
            self.delete_data.count_gwdata()
            # 发送gwData给server端的时候需要把数据类型为querySet对象的gwData['network_id']转化为字符串'0.0.1.1'
            gwData['network_id'] = network_id

            print('gwData==', gwData)

        return ret, gwData

