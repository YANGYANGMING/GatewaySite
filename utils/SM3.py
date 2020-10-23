from math import ceil

IV = "7380166f 4914b2b9 172442d7 da8a0600 a96f30bc 163138aa e38dee4d b0fb0e4e"
IV = int(IV.replace(" ", ""), 16)
a = []
for i in range(0, 8):
    a.append(0)
    a[i] = (IV >> ((7 - i) * 32)) & 0xFFFFFFFF  # 0x表示16进制数 >>右移位
IV = a  # 将IV转换为十进制


# 移位函数
def rotate_left(b, k):
    return ((b << k) & 0xFFFFFFFF) | ((b & 0xFFFFFFFF) >> (32 - k))  # <<位左移


# 定义常量
T_j = []
for i in range(0, 16):
    T_j.append(0)
    T_j[i] = 0x79cc4519
for i in range(16, 64):
    T_j.append(0)
    T_j[i] = 0x7a879d8a


# 定义FF_j和GG_j布尔函数
def FF_j(X, Y, Z, j):
    if 0 <= j < 16:
        ret = X ^ Y ^ Z  # ^异或运算
    elif 16 <= j < 64:
        ret = (X & Y) | (X & Z) | (Y & Z)  # &与运输 |或运算
    return ret


def GG_j(X, Y, Z, j):
    if 0 <= j < 16:
        ret = X ^ Y ^ Z
    elif 16 <= j < 64:
        # ret = (X | Y) & ((2 ** 32 - 1 - X) | Z)
        ret = (X & Y) | ((~ X) & Z)  # ~非运算
    return ret


# 定义置换函数
def P_0(X):
    return X ^ (rotate_left(X, 9)) ^ (rotate_left(X, 17))


def P_1(X):
    return X ^ (rotate_left(X, 15)) ^ (rotate_left(X, 23))


def CF(V_i, B_i):
    # 消息扩展
    # 划分为16个w(i)
    W = []
    for i in range(16):
        weight = 0x1000000
        data = 0
        for k in range(i * 4, (i + 1) * 4):
            data = data + B_i[k] * weight
            weight = int(weight / 0x100)
        W.append(data)

    for j in range(16, 68):
        W.append(0)
        W[j] = P_1(W[j - 16] ^ W[j - 9] ^ (rotate_left(W[j - 3], 15))) ^ (rotate_left(W[j - 13], 7)) ^ W[j - 6]

    W_1 = []
    for j in range(0, 64):
        W_1.append(0)
        W_1[j] = W[j] ^ W[j + 4]

    A, B, C, D, E, F, G, H = V_i

    for j in range(0, 64):
        SS1 = rotate_left(((rotate_left(A, 12)) + E + (rotate_left(T_j[j], (j % 32)))) & 0xFFFFFFFF, 7)
        SS2 = SS1 ^ (rotate_left(A, 12))
        TT1 = (FF_j(A, B, C, j) + D + SS2 + W_1[j]) & 0xFFFFFFFF
        TT2 = (GG_j(E, F, G, j) + H + SS1 + W[j]) & 0xFFFFFFFF
        D = C
        C = rotate_left(B, 9)
        B = A
        A = TT1
        H = G
        G = rotate_left(F, 19)
        F = E
        E = P_0(TT2)

        A = A & 0xFFFFFFFF
        B = B & 0xFFFFFFFF
        C = C & 0xFFFFFFFF
        D = D & 0xFFFFFFFF
        E = E & 0xFFFFFFFF
        F = F & 0xFFFFFFFF
        G = G & 0xFFFFFFFF
        H = H & 0xFFFFFFFF
        """
        str1 = "%02d" % j
        if str1[0] == "0":
            str1 = ' ' + str1[1:]
        print str1,
        out_hex([A, B, C, D, E, F, G, H])
        """

    V_i_1 = [A ^ V_i[0], B ^ V_i[1], C ^ V_i[2], D ^ V_i[3], E ^ V_i[4], F ^ V_i[5], G ^ V_i[6], H ^ V_i[7]]
    return V_i_1


def hash_msg(msg):
    # 将msg填充为长度512的倍数
    len1 = len(msg)
    reserve1 = len1 % 64
    msg.append(0x80)

    reserve1 = reserve1 + 1
    # 56-64, add 64 byte
    range_end = 56
    if reserve1 > range_end:
        range_end = range_end + 64
    for i in range(reserve1, range_end):
        msg.append(0x00)
    bit_length = len1 * 8
    bit_length_str = [bit_length % 0x100]
    for i in range(7):
        bit_length = int(bit_length / 0x100)
        bit_length_str.append(bit_length % 0x100)  # bit_length_str=[24,0,0,0,0,0,0,0]
    for i in range(8):
        msg.append(bit_length_str[7 - i])  # 倒序插入msg中
    # print('填充后的字符串为：',msg)

    # 分组B(i)
    group_count = round(len(msg) / 64)  # 四舍五入
    B = []
    for i in range(0, group_count):
        B.append(msg[i * 64:(i + 1) * 64])

    V = [IV]
    for i in range(0, group_count):
        V.append(CF(V[i], B[i]))
    y = V[i + 1]

    result = ""
    for i in y:
        result = '%s%08x' % (result, i)
    return result


def str2byte(msg):  # 字符串转换成byte数组
    ml = len(msg)
    msg_byte = []
    msg_bytearray = msg.encode('utf-8')
    for i in range(ml):
        msg_byte.append(msg_bytearray[i])
    return msg_byte


def byte2str(msg):  # byte数组转字符串
    ml = len(msg)
    str1 = b""
    for i in range(ml):
        str1 += b'%c' % msg[i]
    return str1.decode('utf-8')


def hex2byte(msg):  # 16进制字符串转换成byte数组
    ml = len(msg)
    if ml % 2 != 0:
        msg = '0' + msg
    ml = int(len(msg) / 2)
    msg_byte = []
    for i in range(ml):
        msg_byte.append(int(msg[i * 2:i * 2 + 2], 16))
    return msg_byte


def byte2hex(msg):  # byte数组转换成16进制字符串
    ml = len(msg)
    hexstr = ""
    for i in range(ml):
        hexstr = hexstr + ('%02x' % msg[i])
    return hexstr


def Hash_sm3(msg, Hexstr):
    if Hexstr:
        msg_byte = hex2byte(msg)
    else:
        msg_byte = str2byte(msg)

    return hash_msg(msg_byte)



def KDF(Z, klen):  # Z为16进制表示的比特串（str），klen为密钥长度（单位byte）
    klen = int(klen)
    ct = 0x00000001
    rcnt = ceil(klen / 32)
    Zin = hex2byte(Z)
    Ha = ""
    for i in range(rcnt):
        msg = Zin + hex2byte('%08x' % ct)
        # print(msg)
        Ha = Ha + hash_msg(msg)
        # print(Ha)
        ct += 1
    return Ha[0: klen * 2]


if __name__ == '__main__':
    # x = '61626364'*16
    x = input('输入内容：')
    y = input('字符串为0，16进制数为1：')
    z = Hash_sm3(x, int(y))
    print(z)



