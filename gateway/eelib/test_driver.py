import unittest

import serial

from .eelib.gateway import *
from .eelib.sensor import *


class Test_GatewayDriver(unittest.TestCase):

    @classmethod
    def setUpClass(self):
    # 必须使用@classmethod 装饰器,所有test运行前运行一次
        self.gser = serial.Serial("/dev/ttyS4",115200,timeout=1)
        # print(self.gser)
        self.serCtrl = SerialCtrl(self.gser)
        self.gwCtrl = GatewayCtrl() 
        self.gw0    = Gateway(self.gser)

    @classmethod
    def tearDownClass(self):
    # 必须使用 @ classmethod装饰器, 所有test运行完后运行一次
        if self.gser.isOpen():
            self.gser.close()

    def setUp(self):
        # 每个测试用例执行之前做操作
        pass

    def tearDown(self):
        # 每个测试用例执行之后做操作
        pass

    def test_localCalThickness(self):
        thick = self.gw0.localCalThickness()
        # print("thick:\r\n"+str(thick)+"\r\n")
        self.assertEqual(thick, 6.25)

    def test_remoteCalThickness(self):  
        r = self.gwCtrl.postSVRData()
        if(r.status==True):
            # print("postTestSVRData,return:\r\n"+str(r.result)+"\r\n")
            self.assertEqual(r.result['statusCode'], 200)
            self.assertEqual(r.result['message'], 'OK')

    def test_sendTestGWData(self):  
        r = self.gwCtrl.postGWData()
        if(r.status==True):
            # print("postTestGWData,return:\r\n"+str(r.result)+"\r\n")
            self.assertEqual(r.result['statusCode'], 200)
            self.assertEqual(r.result['message']['msg'], 'success')  

    def test_getSensorData(self):
        snrdata = self.serCtrl.getSensorData()
        if(snrdata.sensorID!=0):
            gwdata = snrdata.cvrt2gwData()
            svrdata = snrdata.cvrt2svrData()
            thick = self.gw0.localCalThickness(svrdata)
            # print("test_getSensorData,thick:"+str(thick)+"mm\r\n")
            # print("gwData:\r\n"+str(gwData)+"\r\n")
            # print("svrData:\r\n"+str(svrData)+"\r\n")
            self.assertEqual(gwdata['data_len'], 2048)
            self.assertEqual(svrdata['data_len'], 2048)
    
    def test_sendRealData(self):
        snrdata = self.serCtrl.getSensorData()
        if(snrdata.sensorID!=0):
            gwdata = snrdata.cvrt2gwData()
            r = self.gw0.postGWData(gwdata)
            if(r.status==True):
                # print("postRealGWData,return:\r\n"+str(r)+"\r\n")
                self.assertEqual(r.result['statusCode'], 200)
                self.assertEqual(r.result['message']['msg'], 'success')

    def test_sendRealData_addTime(self):
        time0 = 1485796200  # 2017-01-31 01:10:00
        # time0   = 1517332200 #2018-01-31 01:10:00
        # time0   = 1548868200 #2019-01-31 01:10:00
        time_apart = 60*60*24  # 1 day

        for i in range(0,1):
            snrdata = self.serCtrl.getSensorData()
            if(snrdata.sensorID!=0):
                gwdata = snrdata.cvrt2gwData()
                time_t = time0+i*time_apart
                r = self.gw0.postGWData(gwdata,time_t)
                if(r.status==True):
                    # print("postRealGWData,return:\r\n"+str(r)+"\r\n")
                    self.assertEqual(r.result['statusCode'], 200)
                    self.assertEqual(r.result['message']['msg'], 'success')

if __name__ == '__main__':
    unittest.main()
    # unittest.main(testRunner=HtmlTestRunner.HTMLTestRunner(output='report'))
    # test_suite = unittest.TestSuite()
    # test_suite.addTest(unittest.makeSuite(Test_GatewayDriver))
    # runner = HtmlTestRunner.HTMLTestRunner(output='report')
    # runner.run(test_suite)

