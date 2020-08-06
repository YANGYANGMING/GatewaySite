import paho.mqtt.client as mqtt
from utils import handle_func
from gateway import models
from GatewaySite import settings
from lib.log import Logger
import json


class MQTT_Client(object):

    def __init__(self):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)
        self.client.on_message = self.on_message
        self.client.on_subscribe = self.on_subscribe
        # self.client.on_log = self.on_log
        # self.client.tls_set(ca_certs=settings.ca_certs,
        #                     certfile=settings.certfile,
        #                     keyfile=settings.keyfile,
        #                     )
        # self.client.tls_insecure_set(True)
        # self.client.connect(settings.MQTT_HOST, 8883, 30)
        self.client.connect(settings.MQTT_HOST, 1883, 30)
        self.client.loop_start()

    # 在连接成功时的 callback，打印 result code
    def on_connect(self, client, userdata, flags, rc):
        print("Connected with result code " + str(rc))
        Logger().log(True, 'Connection Successful')
        topic = models.Gateway.objects.values('network_id')[0]['network_id']
        self.client.subscribe([('pub', 2), (topic, 2)])
        header = 'connect_status'
        result = {'status': True, 'gw_nework_id': topic, 'msg': 'Connection Successful'}
        handle_func.send_gwdata_to_server(client, 'pub', result, header)

    # 在连接断开时的 callback，打印 result code
    def on_disconnect(self, client, userdata, rc):
        print("Disconnection returned result:" + str(rc))
        Logger().log(False, 'Connection Disconnected!')

    # 接收到消息的回调方法
    def on_message(self, client, userdata, msg):
        payload = json.loads(msg.payload.decode())
        if payload['id'] == 'server':
            print('payload:', payload)
            handle_func.handle_recv_server(msg.topic, payload)

    def on_subscribe(self, client, userdata, mid, granted_qos):
        print('订阅成功.....')

    # def on_log(self, client, obj, level, string):
    #     print("Log:" + string)







