import paho.mqtt.client as mqtt
from utils import handle_func
from utils import handle_recv_server
from gateway import models
import json


class MQTT_Client(object):

    def __init__(self):
        self.HOST = "121.36.220.210"
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        self.client.on_subscribe = self.on_subscribe
        # self.client.on_log = self.on_log
        self.client.connect(self.HOST, 1883, 30)
        self.client.loop_start()


    # 在连接成功时的 callback，打印 result code
    def on_connect(self, client, userdata, flags, rc):
        print("Connected with result code " + str(rc))
        topic = models.Gateway.objects.values('network_id')[0]['network_id']
        self.client.subscribe([('pub', 2), (topic, 2)])
        header = 'connected'
        result = {'status': True, 'mag': 'Successful connection'}
        handle_func.send_gwdata_to_server(client, topic, result, header)

    # 在连接断开时的 callback，打印 result code
    def on_disconnect(self, client, userdata, rc):
        print("Disconnection returned result:" + str(rc))

    # 接收到消息的回调方法
    def on_message(self, client, userdata, msg):
        payload = json.loads(msg.payload.decode())
        if payload['id'] == 'server':
            print('接收到消息的回调')
            print('msg.topic:', msg.topic)
            print('payload:', payload)
            handle_recv_server.handle_recv_server(msg.topic, payload)

    def on_subscribe(self, client, userdata, mid, granted_qos):
        print('订阅成功.....')

    # def on_log(self, client, obj, level, string):
    #     print("Log:" + string)







