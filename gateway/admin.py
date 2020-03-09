from django.contrib import admin
from gateway import models

admin.site.register(models.Sensor_data)
admin.site.register(models.UserProfile)
admin.site.register(models.Rcv_server_data)
admin.site.register(models.GWData)
admin.site.register(models.Post_Return)
admin.site.register(models.Role)
admin.site.register(models.Set_param)
admin.site.register(models.TimeStatus)
admin.site.register(models.Set_Time)
admin.site.register(models.URL)