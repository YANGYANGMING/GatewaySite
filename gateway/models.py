from django.db import models
from django.contrib.auth.models import User

from django.contrib.auth.models import (
    BaseUserManager, AbstractBaseUser, PermissionsMixin
)


class UserProfileManager(BaseUserManager):
    def create_user(self, name, password=None):
        """
        Creates and saves a User with the given email, date of
        birth and password.
        """
        if not name:
            raise ValueError('Users must have a name')

        user = self.model(
            name=name,
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, name, password):
        """
        Creates and saves a superuser with the given email, date of
        birth and password.
        """
        user = self.create_user(
            password=password,
            name=name,
        )
        user.is_superuser = True
        user.save(using=self._db)
        return user


class UserProfile(AbstractBaseUser, PermissionsMixin):
    name = models.CharField(max_length=64, verbose_name="姓名", unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=True)
    role = models.ManyToManyField("Role", blank=True, null=True)

    objects = UserProfileManager()

    USERNAME_FIELD = 'name'

    def get_full_name(self):
        # The user is identified by their email address
        return self.name

    def get_short_name(self):
        # The user is identified by their email address
        return self.name

    def __str__(self):
        return self.name


    class Meta:
        permissions = (
            ('gateway_config_time_view', '可以访问配置时间页面'),
            ('gateway_manual_config_get_data_view', '可以手动取数'),
            ('gateway_all_data_report_view', '可以查看所有数据信息'),
            ('gateway_thickness_report_view', '可以查看所有传感器的厚度曲线'),
            ('gateway_edit_sensor_params_view', '可以查看所有传感器的参数'),
            ('gateway_set_sensor_params_view', '可以设置传感器的参数'),
            ('gateway_sensor_manage_view', '可以查看传感器管理页面'),
            ('gateway_edit_sensor_view', '可以查看传感器编辑页面'),
            ('gateway_edit_sensor_alarm_msg_view', '可以查看传感器编辑报警信息页面'),
            ('gateway_add_sensor_page_view', '可以查看传感器增加页面'),
            ('gateway_receive_gw_data_view', '可以保存对传感器进行增删改操作'),
            ('gateway_set_gateway_page_view', '可以可查看设置网关页面'),
            ('gateway_set_gateway_json_view', '可以保存设置网关操作'),
            ('gateway_system_settings_view', '可以查看系统设置页面'),
            ('gateway_delete_gateway_page_view', '可以查看删除网关页面'),
            ('gateway_delete_gateway_view', '可以执行删除网关操作'),
            ('gateway_user_list_view', '可以查看编辑用户列表'),
            ('gateway_user_add_view', '可以查看增加用户页面'),
            ('gateway_user_add_save', '可以保存增加用户操作'),
            ('gateway_user_edit_view', '可以查看编辑用户页面'),
            ('gateway_user_edit_save', '可以保存编辑用户操作'),
            ('gateway_user_delete_view', '可以查看删除用户页面'),
            ('gateway_user_delete_conform', '可以保存删除用户操作'),
        )


class Role(models.Model):
    """角色表"""
    name = models.CharField(max_length=64, unique=True)
    menus = models.ManyToManyField('Menus')

    def __str__(self):
        return self.name


class Menus(models.Model):
    """动态菜单"""
    name = models.CharField(max_length=64)
    url_type_choices = ((0, 'absolute'), (1, 'dynamic'))
    url_type = models.SmallIntegerField(choices=url_type_choices, default=0)
    url_name = models.CharField(max_length=128)

    def __str__(self):
        return self.name

    class Meta:
        unique_together = ('name', 'url_name')


class Set_Time(models.Model):
    """设置时间"""
    days = models.CharField(max_length=32, null=True, blank=True)
    hours = models.CharField(max_length=32, null=True, blank=True)
    minutes = models.CharField(max_length=32, null=True, blank=True)


class Gateway(models.Model):
    """网关信息"""
    name = models.CharField(max_length=64, unique=True)
    Enterprise = models.CharField(max_length=128, unique=True)
    network_id = models.CharField(max_length=32, unique=True)
    gw_status_choices = ((0, '离线'),
                         (1, '在线'),
                         )
    gw_status = models.SmallIntegerField(choices=gw_status_choices, default=1)
    def __str__(self):
        return self.name


class GWData(models.Model):
    """网关数据"""
    network_id = models.ForeignKey(to='Sensor_data', to_field='network_id', on_delete=models.CASCADE)
    com_version = models.CharField(max_length=32)
    time_tamp = models.CharField(max_length=32)
    temperature = models.IntegerField(null=True, blank=True)
    gain = models.IntegerField()
    battery = models.IntegerField()
    data_len = models.IntegerField()
    thickness = models.CharField(max_length=16, default='-999')
    data = models.TextField()

    def __str__(self):
        return str(self.network_id)


class TimeStatus(models.Model):
    """运行状态表"""
    timing_status = models.CharField(max_length=32)
    # cycle_status = models.CharField(max_length=32)
    text_status = models.CharField(max_length=32)
    button_status = models.CharField(max_length=32)


class Material(models.Model):
    """材料"""
    name = models.CharField(max_length=64, unique=True)
    sound_V = models.IntegerField()
    temperature_co = models.FloatField()


class Sensor_data(models.Model):
    """传感器详细数据信息"""
    alias = models.CharField(max_length=64, verbose_name="别名", unique=True)
    sensor_id = models.CharField(max_length=32, unique=True)
    network_id = models.CharField(max_length=32, unique=True)
    received_time_data = models.CharField(max_length=128)
    battery = models.CharField(max_length=32, default=100)
    cHz = models.CharField(max_length=32, default='2')
    gain = models.CharField(max_length=32, default='72')
    avg_time = models.CharField(max_length=32, default='4')
    Hz = models.CharField(max_length=32, default='4')
    Sample_depth = models.CharField(max_length=32, default='0')
    Sample_Hz = models.CharField(max_length=32, default='500')
    sensor_type_choices = ((0, 'ETM-100'),
                           )
    sensor_type = models.SmallIntegerField(choices=sensor_type_choices, default=0)
    Importance_choices = ((0, '一般'),
                          (1, '重要'),
                          )
    material = models.SmallIntegerField(default=1)
    Importance = models.SmallIntegerField(choices=Importance_choices, default=0)
    sensor_online_status_choices = ((1, '在线'),
                                    (0, '离线')
                                    )
    sensor_online_status = models.SmallIntegerField(choices=sensor_online_status_choices, default=1)
    sensor_run_status_choices = ((1, '开通'),
                                 (0, '禁止')
                                 )
    sensor_run_status = models.SmallIntegerField(choices=sensor_run_status_choices, default=1)
    date_of_installation = models.DateField(auto_now_add=True)
    initial_thickness = models.FloatField(default=10)
    alarm_thickness = models.FloatField(default=8)
    alarm_battery = models.FloatField(default=50)
    alarm_temperature = models.FloatField(default=310)
    alarm_corrosion = models.FloatField(default=0.3)
    longitude = models.FloatField(default=0, null=True, blank=True)
    latitude = models.FloatField(default=0, null=True, blank=True)
    area = models.TextField(verbose_name='所在区域', null=True, blank=True)
    location = models.TextField(verbose_name='所在位置', null=True, blank=True)
    location_img_path = models.TextField(verbose_name='所在位置图片路径', null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    assembly_crewman = models.CharField(max_length=32, null=True, blank=True)
    delete_status = models.CharField(max_length=32, default=0)

    Sensor_MAC = models.CharField(max_length=12, blank=True, null=True, verbose_name="传感器MAC")
    Time_Cycle = models.CharField(max_length=8, blank=True, null=True, verbose_name="时间校准周期")
    Environmental_Temp = models.FloatField(max_length=6, blank=True, null=True, verbose_name="环境温度")

    REG_COD = models.CharField(max_length=20, blank=True, null=True, verbose_name="注册代码")
    USE_COD = models.CharField(max_length=20, blank=True, null=True, verbose_name="使用登记证编号")
    EQP_TYPE = models.CharField(max_length=4, blank=True, null=True, verbose_name="设备种类")
    EQP_SORT = models.CharField(max_length=4, blank=True, null=True, verbose_name="设备类别")
    EQP_VART = models.CharField(max_length=4, blank=True, null=True, verbose_name="设备品类")
    EQP_MOD = models.CharField(max_length=60, blank=True, null=True, verbose_name="设备型号")
    FAC_COD = models.CharField(max_length=60, blank=True, null=True, verbose_name="设备出厂编号")
    Manufacturer = models.CharField(max_length=100, blank=True, null=True, verbose_name="制造单位名称")
    Manufacturer_COD = models.CharField(max_length=30, blank=True, null=True, verbose_name="制造单位组织机构代码")
    EQP_Date = models.DateField(max_length=10, blank=True, null=True, verbose_name="设备出厂日期")
    Installation_Unit = models.CharField(max_length=100, blank=True, null=True, verbose_name="设备安装单位")
    Installation_Date = models.DateField(max_length=10, blank=True, null=True, verbose_name="设备安装日期")
    Maintenance_Unit = models.CharField(max_length=100, blank=True, null=True, verbose_name="维护保养单位名称")
    USE_UNT = models.CharField(max_length=100, blank=True, null=True, verbose_name="使用单位名称")

    def __str__(self):
        return self.alias


class UploadData(models.Model):
    """
    上传数据到管理局和服务器
    """
    upload_data_to_administration_server = models.BooleanField(default=False)
    upload_data_to_local_server = models.BooleanField(default=True)


