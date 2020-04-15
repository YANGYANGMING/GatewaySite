from django.db import models
from django.contrib.auth.models import User

from django.contrib.auth.models import (
    BaseUserManager, AbstractBaseUser, PermissionsMixin
)


class UserProfileManager(BaseUserManager):
    def create_user(self, email, name, password=None):
        """
        Creates and saves a User with the given email, date of
        birth and password.
        """
        if not email:
            raise ValueError('Users must have an email address')

        user = self.model(
            email=self.normalize_email(email),
            name=name,
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, name, password):
        """
        Creates and saves a superuser with the given email, date of
        birth and password.
        """
        user = self.create_user(
            email,
            password=password,
            name=name,
        )
        user.is_superuser = True
        user.save(using=self._db)
        return user


class UserProfile(AbstractBaseUser, PermissionsMixin):
    # user = models.OneToOneField(User, on_delete=models.CASCADE)
    email = models.EmailField(
        verbose_name='email address',
        max_length=255,
        unique=True,

    )
    name = models.CharField(max_length=64, verbose_name="姓名")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=True)
    # is_admin = models.BooleanField(default=False)
    role = models.ManyToManyField("Role", blank=True, null=True)

    objects = UserProfileManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    def get_full_name(self):
        # The user is identified by their email address
        return self.email

    def get_short_name(self):
        # The user is identified by their email address
        return self.email

    def __str__(self):
        return self.email

    # def has_perm(self, perm, obj=None):
    #     "Does the user have a specific permission?"
    #     # Simplest possible answer: Yes, always
    #     return True
    #
    # def has_module_perms(self, app_label):
    #     "Does the user have permissions to view the app `app_label`?"
    #     # Simplest possible answer: Yes, always
    #     return True

    # @property
    # def is_staff(self):
    #     "Is the user a member of staff?"
    #     # Simplest possible answer: All admins are staff
    #     return self.is_admin

    class Meta:
        permissions = (
            ('gateway_config_time_view', '可以访问配置时间页面'),
            ('gateway_config_time_operate_view', '可以操作配置时间页面'),
            ('gateway_all_data_report_view', '可以查看所有数据信息'),
            ('gateway_thickness_report_view', '可以查看所有传感器的厚度曲线'),
            ('gateway_all_sensor_data_view', '可以查看所有传感器的参数'),
            ('gateway_set_sensor_time_view', '可以查看所有传感器的设置运行时间'),
            ('gateway_user_list_view', '可以查看编辑用户列表'),
            # ('gateway_user_add_view', '可以新增用户'),
        )

# class UserProfile(models.Model):
#     """用户信息表"""
#     user = models.OneToOneField(User, on_delete=models.CASCADE)
#     name = models.CharField(max_length=64, verbose_name='姓名')
#     role = models.ManyToManyField("Role", blank=True, null=True)
#
#     def __str__(self):
#         return self.name


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
    year = models.CharField(max_length=32, null=True, blank=True)
    month = models.CharField(max_length=32, null=True, blank=True)
    # day_of_week = models.CharField(max_length=32, null=True, blank=True)
    day = models.CharField(max_length=32, null=True, blank=True)
    hour = models.CharField(max_length=32, null=True, blank=True)
    mins = models.CharField(max_length=32, null=True, blank=True)


class Gateway(models.Model):
    """网关信息"""
    name = models.CharField(max_length=64, null=True, blank=True)
    Enterprise = models.CharField(max_length=128, null=True, blank=True)
    network_id = models.CharField(max_length=32, unique=True)
    gw_status_choices = ((0, '离线'),
                         (1, '在线'),
                         )
    gw_status = models.SmallIntegerField(choices=gw_status_choices, default=1)
    def __str__(self):
        return self.name


class Post_Return(models.Model):
    """接收的信息"""
    """{'result': {}, 'statusCode': 200, 'message': {'msgType': 'tsuccess', 'msg': 'success'}, 'elapsedTime': 6}
    """
    result_all_data = models.CharField(max_length=128, null=True)


class GWData(models.Model):
    """网关数据"""
    network_id = models.ForeignKey(to='Sensor_data', to_field='network_id', on_delete=models.DO_NOTHING)
    com_version = models.CharField(max_length=32)
    time_tamp = models.CharField(max_length=32)
    temperature = models.IntegerField(null=True, blank=True)
    gain = models.IntegerField()
    battery = models.IntegerField()
    data_len = models.IntegerField()
    thickness = models.CharField(max_length=16, default='-999')
    data = models.TextField()

    def __str__(self):
        return self.network_id


class GW_network_id(models.Model):
    """网关网络号"""
    network_id = models.CharField(max_length=32)


class TimeStatus(models.Model):
    """运行状态表"""
    timing_status = models.CharField(max_length=32)
    cycle_status = models.CharField(max_length=32)
    text_status = models.CharField(max_length=32)
    button_status = models.CharField(max_length=32)


class Set_param(models.Model):
    """手动获取的id、设置参数"""
    menu_get_id = models.CharField(max_length=32)
    param = models.CharField(max_length=64)


class Sensor_data(models.Model):
    """传感器详细数据信息"""
    alias = models.CharField(max_length=64, verbose_name="别名", unique=True)
    sensor_id = models.CharField(max_length=32, unique=True)
    network_id = models.CharField(max_length=32, unique=True)
    received_time_data = models.CharField(max_length=128)
    battery = models.CharField(max_length=32, default=100)
    cHz = models.CharField(max_length=32, default='2')
    gain = models.CharField(max_length=32, default='60')
    avg_time = models.CharField(max_length=32, default='4')
    Hz = models.CharField(max_length=32, default='2')
    Sample_depth = models.CharField(max_length=32, default='2')
    Sample_Hz = models.CharField(max_length=32, default='500')
    sensor_type_choices = ((0, '常温'),
                           (1, '高温'),
                           )
    sensor_type = models.SmallIntegerField(choices=sensor_type_choices, default=0)
    Importance_choices = ((0, '一般'),
                          (1, '重要'),
                          )
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
    initial_thickness = models.CharField(max_length=32, null=True, blank=True)
    alarm_thickness = models.CharField(max_length=32, null=True, blank=True)
    alarm_battery = models.CharField(max_length=32, null=True, blank=True)
    area = models.TextField(verbose_name='所在区域', null=True, blank=True)
    location = models.TextField(verbose_name='所在位置', null=True, blank=True)
    location_img_path = models.TextField(verbose_name='所在位置图片路径', null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    assembly_crewman = models.CharField(max_length=32, null=True, blank=True)
    delete_status = models.CharField(max_length=32, default=0)

    def __str__(self):
        return self.alias




