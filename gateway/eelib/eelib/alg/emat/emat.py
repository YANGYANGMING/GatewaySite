import os
from ctypes import *


ETGminiX1_file = os.path.dirname(os.path.abspath(__file__)) + '/thicknessgauge_x86_64.so'
# ETGminiX1_file = os.path.dirname(os.path.abspath(__file__)) + '/thicknessgauge_armv7l.so'
# ETGminiX1_file = os.path.dirname(os.path.abspath(__file__)) + '/ThicknessMeasure_SimilarEhco.so'
ETGminiX1 = CDLL(ETGminiX1_file)

maxSize = 2048

class WaveData(Structure):
    _fields_ = [
        ("data", c_int32*maxSize),
    ]


def calThickness(data, gain_db, pluse_num=2, nSize=2048, vel_mps=3240, freq_Hz=40e6):
    thick_mm = -19

    if (nSize <= maxSize):
        wdata = WaveData()
        for i in range(0, nSize):
            wdata.data[i] = data[i]
        # double MeasureEchoPosition(int32_t* SignalIn, int PulseNum, int GaindB)
        ETGminiX1.MeasureEchoPosition.argtypes = [c_void_p, c_int, c_int, c_int]
        ETGminiX1.MeasureEchoPosition.restype = c_double
        ret = ETGminiX1.MeasureEchoPosition(byref(wdata.data), pluse_num, gain_db, nSize)
        thick_mm = round(ret*vel_mps/freq_Hz/2*1000,3)

    return thick_mm


# # # 新版算法
# import os
# from ctypes import *
#
# # ETGminiX1_file = os.path.dirname(os.path.abspath(__file__)) + '/thicknessgauge_x86_64.so'
# # ETGminiX1_file = os.path.dirname(os.path.abspath(__file__)) + '/thicknessgauge_armv7l.so'
# ETGminiX1_file = os.path.dirname(os.path.abspath(__file__)) + '/ThicknessMeasure_SimilarEhco.so'
# ETGminiX1 = CDLL(ETGminiX1_file)
#
# maxSize = 2048
#
#
# class WaveData(Structure):
#     _fields_ = [
#         ("data", c_int16 * maxSize),
#     ]
#
#
# class Params(Structure):
#     _fields_ = [
#         ("params", c_int32 * 1)
#     ]
#
#
# def calThickness(data, gain_db, nSize=2048, vel_mps=3240, freq_Hz=40e6):
#     thick_mm = -19
#
#     if (nSize <= maxSize):
#         wdata = WaveData()
#         for i in range(0, nSize):
#             wdata.data[i] = data[i]
#         PeakIndex1 = Params()
#         PeakIndex2 = Params()
#         PeakNum = Params()
#         # double MeasureEchoPosition(int32_t* SignalIn, int PulseNum, int GaindB)
#         # double MeasureEchoPosition_SimilarEhco(const int16_t* Data_D, int GainDB, int nSize, int* PeakIndex1, int* PeakIndex2, int* PeakNum)
#         ETGminiX1.MeasureEchoPosition_SimilarEhco.argtypes = [c_void_p, c_int, c_int, c_void_p, c_void_p, c_void_p]
#         ETGminiX1.MeasureEchoPosition_SimilarEhco.restype = c_double
#         ret = ETGminiX1.MeasureEchoPosition_SimilarEhco(byref(wdata.data), gain_db, nSize, byref(PeakIndex1.params),
#                                                         byref(PeakIndex2.params), byref(PeakNum.params))
#         thick_mm = round(ret * vel_mps / freq_Hz / 2 * 1000, 3)
#
#     return thick_mm