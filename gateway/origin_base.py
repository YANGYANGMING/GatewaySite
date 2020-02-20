class Origin(object):
    def __init__(self):
        pass
    # list_display = ['id', 'com_version', 'sensor_id', 'time_tamp', 'gain', 'battery', 'data_len', 'temperature', 'thickness', 'data']
    list_display = ['id', '传感器ID', '电量', '温度', '厚度', '数据详情']
    sorted_list = ['battery']
    list_per_page = 2