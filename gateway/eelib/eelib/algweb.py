import json
import base64

def deFormat(webdata):
    msg = "default"

    try:
        aa = base64.b64decode(webData)
    except Exception as e:
        msg = "b64decode error"
    else:
        msg = "b64decode ok"

    if(msg == "b64decode ok"):
        try:
            bb = json.loads(aa.decode('utf-8'))
        except Exception as e:
            msg = "json error"
        else:
            msg = "json ok"
    else:
        return {'messge': msg, 'data': ""}

    if(msg == "json ok"):
        return {'messge': 'ok', 'data': bb}
    else:
        return {'messge': msg, 'data': ""}


def checkParamExist(jsData):
    msg = "default"

    if 'com_version' not in jsData:
        msg = "com_version isn't exist"
    elif 'analyse_id' not in jsData:
        msg = "analyse_id isn't exist"
    elif 'gain' not in jsData:
        msg = "gain isn't exist"
    elif 'temperature' not in jsData:
        msg = "temperature isn't exist"
    elif 'normal_velocity' not in jsData:
        msg = "normal_velocity isn't exist"
    elif 'material' not in jsData:
        msg = "material isn't exist"
    elif 'ori_thickness' not in jsData:
        msg = "ori_thickness isn't exist"
    elif 'sensor_type' not in jsData:
        msg = "sensor_type isn't exist"
    elif 'ext_data' not in jsData:
        msg = "ext_data isn't exist"
    elif 'data_len' not in jsData:
        msg = "data_len isn't exist"
    elif 'data' not in jsData:
        msg = "data isn't exist"
    else:
        msg = "ok"

    return msg


def checkParamType(jsData):
    msg = "default"

    if(type(jsData['com_version']) != type('emat_com 0.1')):
        msg = 'com_version type error'
    elif(type(jsData['analyse_id']) != type('analyse_ccdd')):
        msg = 'analyse_id type error'
    elif(type(jsData['gain']) != type(90)):
        msg = 'gain type error'
    elif(type(jsData['temperature']) != type(80)):
        msg = 'temperature type error'
    elif(type(jsData['normal_velocity']) != type(3240)):
        msg = 'normal_velocity type error'
    elif(type(jsData['material']) != type('steel')):
        msg = 'material type error'
    elif(type(jsData['ori_thickness']) != type(10)):
        msg = 'ori_thickness type error'
    elif(type(jsData['sensor_type']) != type('EMAT')):
        msg = 'sensor_type type error'
    elif(type(jsData['ext_data']) != type("This is extend data.")):
        msg = 'ext_data type error'
    elif(type(jsData['data_len']) != type(2048)):
        msg = 'data_len type error'
    elif(type(jsData['data']) != type([2024, 1988])):
        msg = 'data type error'
    else:
        msg = 'ok'

    return msg
