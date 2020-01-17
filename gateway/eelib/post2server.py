# import serial
# import time
# import os
#
# from .eelib.gateway import *
# from .eelib.message import *
#
# msg_file = os.path.dirname(os.path.abspath(__file__)) + '/message.txt'
# msg_printer = MessagePrinter(msg_file)
#
# # gser = serial.Serial("/dev/ttyUSB0",115200,timeout=1)
# # gser = serial.Serial("/dev/ttyAMA0",115200,timeout=1)
# gser = serial.Serial("/dev/ttyS3", 115200, timeout=1)
# gw0 = Gateway(gser)
# gw0.localCalThickness()
#
# time0 = 1420077600  # 2015-01-01 10:00:00
# # time0 = 1485796200  # 2017-01-31 01:10:00
# # time0   = 1517332200 #2018-01-31 01:10:00
# # time0   = 1548868200 #2019-01-31 01:10:00
# time_apart = 60 * 60 * 24  # 1 day
#
#
# def main():
#
#     print(
#         "Pleae select mode 1 or 2, mode 1 for printing full message, mode 2 for less."
#     )
#     while True:
#         mode = int(input("select mode 1 or 2 :"))
#         if ((mode == 1) or (mode == 2)):
#             break
#
#     for i in range(0, 100000):
#         print("\r\ni=" + str(i))
#         msg_printer.print2File("\r\ni=" + str(i) + "\r\n")
#         time_now = time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(time.time()))
#         msg_printer.print2File("Test time: " + str(time_now) + "\r\n")
#
#         if (mode == 1):
#             print("Test time: " + str(time_now) + "\r\n")
#
#         time_t = time0 + i * time_apart
#         r = gw0.sendData2Server(time_t)
#         if (r.status == True):
#             msg_printer.print2File("post,return:\r\n" + str(r.result))
#             if (mode == 1):
#                 print("post,return:\r\n" + str(r.result))
#         else:
#             msg_printer.print2File(r.message)
#             if (mode == 1):
#                 print("post,return:\r\n" + str(r.result))
#
#
# if __name__ == '__main__':
#     main()