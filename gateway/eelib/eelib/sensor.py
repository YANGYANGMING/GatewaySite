
import time
from gateway import models
from .message import *


class EMATData():
    def __init__(self):
        self.length = 0  # 2Bytes
        self.res1 = 0  # 2Bytes
        self.res2 = 0  # 1Bytes
        self.gain = 0  # 1Bytes
        self.ADSampleDiv = 0  # 1Bytes
        self.Battery = 0  # 1Bytes
        self.networkID = -1  # 4Bytes
        self.YPos = 0  # 4Bytes
        self.data = []  # 2048个2Bytes

class SensorData(EMATData):
    """传感器数据"""
    def __init__(self):
        # EMATData.__init__(self)
        super(SensorData, self).__init__()
        self.sensorID = 0  # 4Bytes

    #转换为网关数据，字典型，网关发送给服务端的数据
    def cvrt2gwData(self, com_version="emat_com 0.1"):
        # gwData = collections.OrderedDict()
        gwData = {}
        try:
            if (com_version == "emat_com 0.1"):
                gwData["com_version"] = com_version
                gwData["sensor_id"] = str(self.sensorID)
                gwData["network_id"] = str(self.networkID)
                gwData["time_tamp"] = time.time()
                gwData["temperature"] = self.res1
                gwData["gain"] = self.gain
                gwData["battery"] = self.Battery
                gwData["data_len"] = len(self.data)
                gwData["data"] = self.data

        except Exception as e:
            print(e)

        return gwData

    #转换为算法数据，字典型，服务端发送给算法端的数据
    def cvrt2svrData(self, com_version="emat_com 0.1"):
        # svrData = collections.OrderedDict()
        svrData = {}
        if (com_version == "emat_com 0.1"):
            svrData["com_version"] = com_version
            svrData["analyse_id"] = ""
            svrData["gain"] = self.gain
            svrData["temperature"] = -999
            svrData["normal_velocity"] = 3240
            svrData["material"] = "steel"
            svrData["ori_thickness"] = 10
            svrData["sensor_type"] = "EMAT"
            svrData["ext_data"] = "This extend data."
            svrData["data_len"] = len(self.data)
            svrData["data"] = self.data

        return svrData


# 串口：发送指令，读取数据
class SerialCtrl():
    def __init__(self, gser):
        self.serialPort = gser

    def atInstruct(self, inst, data1, data2):
        cmd = str(inst) + " " + str(data1) + " " + str(data2) + "\r\n"
        self.serialPort.write(cmd.encode('ascii'))

    def atCMD(self, data):
        cmd = str(data) + "\r\n"
        if not self.serialPort.isOpen():
            self.serialPort.open()
        self.serialPort.write(cmd.encode('ascii'))

    def getSerialData(self, command, timeout):
        """发送命令，并读取串口返回的数据"""
        serdata = ''
        time_start = time.time()
        self.atCMD(command)
        try:
            # 先清空串口缓存
            self.serialPort.flushInput()
            while ((time.time() - time_start) < timeout):
                serdata = self.serialPort.readline().decode('ascii')
                if (serdata != ''):
                    break
        except Exception as e:
            print(e)
            self.serialPort.close()
        return serdata

    def ser2snrData(self, serdata):
        """串口数据转换成传感器数据"""
        snrdata = SensorData()

        tmp = serdata.split(";")
        aa = []
        for i in range(0, len(tmp) - 1):
            bb = tmp[i].split("=")
            aa.append(bb)
        buff = dict(aa)
        # print('buff', buff)
        # print("buff:\r\n"+str(buff)+"\r\n")

        if (buff != {}):
            snrdata.sensorID = int(buff.get('sensorID', 0))
            snrdata.length = int(buff.get('length', 0))
            snrdata.res1 = int(buff.get('res1', 0))
            snrdata.res2 = int(buff.get('res2', 0))
            snrdata.gain = int(buff.get('gain', 0))
            snrdata.ADSampleDiv = int(buff.get('ADSampleDiv', 0))
            snrdata.Battery = int(buff.get('Battery', 0))
            snrdata.YPos = int(buff.get('YPos', 0))

            snrdata.networkID = str(buff.get('networkID', -1))

            data_t = buff.get('Data', '')
            cc = data_t.split(",")
            # print("cc:\r\n"+str(cc)+"\r\n")
            if (cc != []):
                for i in range(0, len(cc) - 1):
                    snrdata.data.append(int(cc[i]))
        return snrdata

    def getSensorData(self, network_id):
        """获取传感器数据"""
        snrdata = SensorData()

        """获取串口数据"""
        command = 'get 83 ' + network_id.rsplit('.', 1)[1]
        print('cmd', command)
        serdata = self.getSerialData(command, timeout=28)
        # print('serdata:', serdata)
        if(serdata!=''):
            snrdata = self.ser2snrData(serdata)

        return snrdata
