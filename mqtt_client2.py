# #-*-coding:utf-8-*-
#
# # 导入 paho-mqtt 的 Client：
# import paho.mqtt.client as mqtt
# import time
# unacked_sub = [] #未获得服务器响应的订阅消息 id 列表
#
# # 用于响应服务器端 CONNACK 的 callback，如果连接正常建立，rc 值为 0
# def on_connect(client, userdata, flags, rc):
#     print("Connection returned with result code:" + str(rc))
#
#
# # 用于响应服务器端 PUBLISH 消息的 callback，打印消息主题和内容
# def on_message(client, userdata, msg):
#     print("Received message, topic:" + msg.topic + "payload:" + str(msg.payload))
#
# # 在连接断开时的 callback，打印 result code
# def on_disconnect(client, userdata, rc):
#     print("Disconnection returned result:"+ str(rc))
#
# # 在订阅获得服务器响应后，从为响应列表中删除该消息 id
# def on_subscribe(client, userdata, mid, granted_qos):
#     unacked_sub.remove(mid)
#
#
# # 构造一个 Client 实例
# client = mqtt.Client()
# client.on_connect = on_connect
# client.on_disconnect= on_disconnect
# client.on_message = on_message
# client.on_subscribe = on_subscribe
#
# # 连接 broker
# # connect() 函数是阻塞的，在连接成功或失败后返回。如果想使用异步非阻塞方式，可以使用 connect_async() 函数。
# client.connect("192.168.0.89", 1883, 60)
#
# client.loop_start()
#
# # 订阅单个主题
# result, mid = client.subscribe("hello", 0)
# unacked_sub.append(mid)
# # 订阅多个主题
# result, mid = client.subscribe([("temperature", 0), ("humidity", 0)])
# unacked_sub.append(mid)
#
# while len(unacked_sub) != 0:
#     time.sleep(1)
#
# client.publish("hello", payload = "Hello world!")
# client.publish("temperature", payload = "24.0")
# client.publish("humidity", payload = "65%")
#
# # 断开连接
# time.sleep(5) #等待消息处理结束
# client.loop_stop()
# client.disconnect()




import paho.mqtt.client as mqtt
import threading, time
#
# def client_mqtt():
#
#     # 连接成功回调
#     def on_connect(client, userdata, flags, rc):
#         print('Connected with result code '+str(rc))
#         # client.subscribe('testtopic/#')
#         client.subscribe('mtopic/#')
#
#     # 消息接收回调
#     def on_message(client, userdata, msg):
#         print(msg.topic+" + "+str(msg.payload))
#
#     client = mqtt.Client()
#
#     # 指定回调函数
#     client.on_connect = on_connect
#     client.on_message = on_message
#
#     # 建立连接
#     # client.connect('192.168.0.164', 1883, 60)
#     client.connect('121.36.220.210', 1883, 60)
#     # 发布消息
#     client.publish('mtopic', payload='Hello World', qos=0)
#
#     client.loop_forever()
#
# client_mqtt()
# for item in range(10):
#     client = threading.Thread(target=client_mqtt)
#     client.start()



#
# HOST = "121.36.220.210"
# # HOST = "192.168.0.89"
# PORT = 1883
#
# def test():
#     client = mqtt.Client()
#     client.connect(HOST, PORT, 60)
#     client.publish("mtopic", "hello world 2", 2)
#     client.loop_forever()
#
# if __name__ == '__main__':
#     test()
#     # for item in range(2):
#     #     client = threading.Thread(target=test)
#     #     client.start()


############################################################

import json

sub_list = [("0.0.2.0", 2), ('pub', 2)]

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
            client.publish("0.0.2.0", json.dumps({"say": str}), 2)


