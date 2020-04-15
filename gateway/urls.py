from django.conf.urls import re_path
from gateway.views import views, account

urlpatterns = [
    re_path(r'^index$', views.index),
    re_path(r'^config-time$', views.config_time, name="config_time"),
    re_path(r'^all-data-report$', views.all_data_report, name="all_data_report"),
    re_path(r'^thickness-report$', views.thickness_report, name="thickness_report"),
    re_path(r'^all-sensor-data$', views.all_sensor_data, name="all_sensor_data"),
    re_path(r'^set-sensor-time$', views.set_sensor_time, name="set_sensor_time"),
    re_path(r'^user-add$', account.user_add, name="user_add"),
    re_path(r'^user-edit/(\d+)$', account.user_edit, name="user_edit"),
    re_path(r'^user-delete/(\d+)$', account.user_delete, name="user_delete"),
    re_path(r'^user-list$', account.user_list, name="user_list"),
    re_path(r'^add-sensor$', views.add_sensor_page),
    re_path(r'^set-gateway$', views.set_gateway_page, name="set_gateway_page"),
    re_path(r'^user-profile$', account.user_profile),
    re_path(r'^change-pwd$', account.change_pwd),

    re_path(r'^data-json-report-(\d+)$', views.data_json_report),
    re_path(r'^thickness-json-report$', views.thickness_json_report),
    re_path(r'^sensor-data-val-set$', views.sensor_data_val_set),

    re_path(r'^set-Timing-time$', views.set_Timing_time),
    re_path(r'^set-cycle-time$', views.set_cycle_time),
    re_path(r'^save-status$', views.save_status),

    re_path(r'^pause-Timing-time$', views.pause_Timing_time),
    re_path(r'^resume-Timing-time$', views.resume_Timing_time),
    re_path(r'^pause-cycle-time$', views.pause_cycle_time),
    re_path(r'^resume-cycle-time$', views.resume_cycle_time),

    re_path(r'^reset-Timing-time$', views.reset_Timing_time),
    re_path(r'^reset-Cycle-time$', views.reset_Cycle_time),


    re_path(r'^edit-sensor-time/(\d+)$', views.edit_sensor_time),
    re_path(r'^set-gateway-json$', views.set_gateway_json),


    # re_path(r'^receive-server-data$', views.receive_server_data),
    re_path(r'^receive-gw-data$', views.receive_gw_data),

    re_path(r'^manual-get/(.*)$', views.manual_get),





]
