
import base64
import requests
import json
import os

from .sensor import *
from .alg.emat.emat import *
from .message import *

from gateway import models
from utils import handle_func

# url_dict = models.URL.objects.filter(id=1).values('mainURL', 'mainHD', 'algURL', 'algHD').first()

test_gwdata_file  = os.path.dirname(os.path.abspath(__file__)) + '/test_data/gatewaydata.txt'
test_svrdata_file = os.path.dirname(os.path.abspath(__file__)) + '/test_data/serverdata.txt'

test_gwdata = {}
test_svrdata = {}
with open(test_gwdata_file, "r") as f1:
    test_gwdata = json.load(f1)
with open(test_svrdata_file, "r") as f2:
    test_svrdata = json.load(f2)


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

    # def get_url(self):
    #     global url_dict
    #     url_dict_obj = models.URL.objects.filter(id=1)
    #     if url_dict_obj:
    #         url_dict = url_dict_obj.values('mainURL', 'mainHD', 'algURL', 'algHD')[0]
    #     else:
    #         url_dict = url_dict_obj
    #     return url_dict
    #
    # def postGWData(self, gwdata=test_gwdata, tstp=0, url_t=url_dict['mainURL'], hd_t=eval(url_dict['mainHD'])):
    #     # print(url_t)
    #     ret = Message(st=False)
    #
    #     if(tstp==0):
    #         gwdata['times_tamp'] = int(tstp)
    #     data_t = self.fmtEncode(gwdata)
    #     r = requests.post(url=url_t, data=data_t, headers=hd_t)
    #     if(r.status_code==200):
    #         ret.status = True
    #         ret.result = r.json()
    #     return ret
    #
    # def postSVRData(self, svrdata=test_svrdata, url_t=url_dict['algURL'], hd_t=eval(url_dict['algHD'])):
    #     ret = Message(st=False)
    #     data_t = self.fmtEncode(svrdata)
    #     r = requests.post(url=url_t, data=data_t, headers=hd_t)
    #     if(r.status_code==200):
    #         ret.status = True
    #         ret.result = self.fmtDecode(r.text)
    #
    #     return ret

class Gateway(GatewayCtrl):

    def __init__(self, gser):
        self.serCtrl = SerialCtrl(gser)
        self.delete_data = Delete_data()

    def localCalThickness(self, svrdata=test_svrdata):
        thick_mm = -19
        if(svrdata["data_len"] == 2048):
            thick_mm = calThickness(data=svrdata['data'], gain_db=svrdata['gain'])
        return thick_mm

    def sendData2Server(self, latest_job_id, tstp=0):
        """获取发送给服务器的网关数据"""
        ret = Message(st=False)
        gwData = {}
        """snrdata是串口发送过来的原始数据"""
        snrdata = self.serCtrl.getSensorData(latest_job_id)  # snrdata对象
        # print(snrdata.sensorID)
        # print(snrdata.data)

        if(snrdata.sensorID == 0):
            ret.status = False
            ret.message = 'no sensor data'
        else:
            ret.status = True
            gwData = snrdata.cvrt2gwData()
            # print(gwData)
            # r = self.postGWData(gwData, tstp)
            # 更改times_tamp为time_tamp,并把gwData['times_tamp']转换成结构化时间，为从数据库取数比较做准备
            localTime = time.localtime(gwData['times_tamp'])
            strTime = time.strftime("%Y-%m-%d %H:%M:%S", localTime)
            gwData['times_tamp'] = strTime
            gwData['time_tamp'] = gwData.pop('times_tamp')

            #把厚度写入网关数据中
            thickness = self.localCalThickness(svrdata=gwData)
            gwData['thickness'] = thickness
            # 转换network_id
            network_id = handle_func.str_dec_hex(gwData['network_id'])
            gwData['network_id'] = models.Sensor_data.objects.filter(network_id=network_id)[0]
            gwData.pop('sensor_id')
            # 把网关数据写入数据库
            models.GWData.objects.create(**gwData)
            # 检查网关数据是否超限
            self.delete_data.count_gwdata()
            #
            gwData['network_id'] = network_id

            print('gwData==', gwData)

            # if(r.status==True):
            #     ret.status = True
            #     ret.result = r.result
            # else:
            #     ret.status = False
            #     ret.message = 'post failed'

        return ret, gwData

