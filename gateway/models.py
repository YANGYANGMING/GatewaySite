from django.db import models
from django.contrib.auth.models import User

class Set_Time(models.Model):
    """设置时间"""
    year = models.CharField(max_length=32, null=True, blank=True)
    month = models.CharField(max_length=32, null=True, blank=True)
    day_of_week = models.CharField(max_length=32, null=True, blank=True)
    day = models.CharField(max_length=32, null=True, blank=True)
    hour = models.CharField(max_length=32, null=True, blank=True)
    mins = models.CharField(max_length=32, null=True, blank=True)

class URL(models.Model):
    """发送的URL"""
    mainURL = models.URLField(null=True, blank=True, default="http://ling.2tag.cn/api/collect_data")
    mainHD = models.CharField(null=True, blank=True, max_length=32, default={'Content-Type': 'application/json'})
    algURL = models.URLField(null=True, blank=True, default="http://118.24.12.152:8099/analyzer/b64")
    algHD = models.CharField(null=True, blank=True, max_length=32, default={'Content-Type': 'application/json'})

class Post_Return(models.Model):
    """接收的信息"""
    """{'result': {}, 'statusCode': 200, 'message': {'msgType': 'tsuccess', 'msg': 'success'}, 'elapsedTime': 6}
    """
    result_all_data = models.CharField(max_length=128, null=True)

class GWData(models.Model):
    """网关数据"""
    com_version = models.CharField(max_length=32)
    sensor_id = models.CharField(max_length=32)
    time_tamp = models.CharField(max_length=32)
    temperature = models.IntegerField(null=True, blank=True)
    gain = models.IntegerField()
    battery = models.IntegerField()
    data_len = models.IntegerField()
    thickness = models.CharField(max_length=16, default='-999')
    data = models.TextField()
    alias = models.ForeignKey(to="Sensor_data", to_field="id", on_delete=models.CASCADE)

class TimeStatus(models.Model):
    """运行状态表"""
    timing_status = models.CharField(max_length=32)
    cycle_status = models.CharField(max_length=32)
    text_status = models.CharField(max_length=32)
    button_status = models.CharField(max_length=32)

class Rcv_server_data(models.Model):
    """接收到服务器的数据"""
    sensor_id = models.CharField(max_length=32)
    received_time_data = models.CharField(max_length=128)

class Set_param(models.Model):
    """手动获取的id、设置参数"""
    menu_get_id = models.CharField(max_length=32)
    param = models.CharField(max_length=64)

class Sensor_data(models.Model):
    """传感器详细数据信息"""
    alias = models.CharField(max_length=64, verbose_name="别名", unique=True, blank=True, null=True)
    sensor_id = models.CharField(max_length=32, unique=True)
    cHz = models.CharField(max_length=32, default='2')
    gain = models.CharField(max_length=32, default='60')
    avg_time = models.CharField(max_length=32, default='4')
    Hz = models.CharField(max_length=32, default='2')
    Sample_depth = models.CharField(max_length=32, default='2')
    Sample_Hz = models.CharField(max_length=32, default='500')

class UserProfile(models.Model):
    """用户信息表"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=64, verbose_name='姓名')
    role = models.ManyToManyField("Role", blank=True, null=True)

    def __str__(self):
        return self.name

class Role(models.Model):
    """角色表"""
    name = models.CharField(max_length=64, unique=True)

    def __str__(self):
        return self.name






