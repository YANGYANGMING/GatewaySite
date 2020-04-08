import paho.mqtt.client as mqtt
from utils.handle_func import handle_recv_server_cmd
import json


class MQTT_Client(object):

    def __init__(self):
        self.HOST = "121.36.220.210"
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        self.client.connect(self.HOST, 1883, 30)
        self.client.loop_start()

    def on_connect(self, client, userdata, flags, rc):
        print("Connected with result code " + str(rc))
        # 连接成功回调
        result, mid = client.subscribe([("0.0.1.0", 2), ('pub', 2)])

    # 在连接断开时的 callback，打印 result code
    def on_disconnect(self, client, userdata, rc):
        print("Disconnection returned result:" + str(rc))

    # 接收到消息的回调方法
    def on_message(self, client, userdata, msg):
        payload = json.loads(msg.payload.decode())
        # print(msg.topic)
        # print(payload)
        if payload['id'] == 'server':
            print('接收到消息的回调')
            handle_recv_server_cmd(msg.topic, payload)





