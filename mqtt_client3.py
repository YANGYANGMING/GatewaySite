import paho.mqtt.client as mqtt

import json

sub_list = [("0.0.3.0", 2), ('pub', 2)]

def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))
    # 连接成功回调
    result, mid = client.subscribe(sub_list)
    # print('result:', result)
    # print('mid:', mid)
    # client.publish("chat", json.dumps({"say": "Hello,anyone!"}))


# 接收到消息的回调方法
def on_message(client, userdata, msg):
    payload = json.loads(msg.payload.decode())
    print(msg.topic)
    print(payload)
    # print(msg.topic + ":" + payload)


if __name__ == '__main__':
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    HOST = "121.36.220.210"

    client.connect(HOST, 1883, 30)
    # client.loop_forever()

    # user = input("请输入名称:")
    # client.user_data_set(user)

    client.loop_start()

    while True:
        str = input()
        if str:
            client.publish("0.0.3.0", json.dumps({"say": str}), 2)