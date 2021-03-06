from django.conf.urls import re_path
from gateway.views import views, account

urlpatterns = [
    re_path(r'^index$', views.index),
    re_path(r'^config-time$', views.config_time, name="config_time"),
    re_path(r'^all-data-report$', views.all_data_report, name="all_data_report"),
    re_path(r'^thickness-report$', views.thickness_report, name="thickness_report"),
    re_path(r'^edit-sensor-params$', views.edit_sensor_params, name="edit_sensor_params"),
    re_path(r'^sensor-manage$', views.sensor_manage, name="sensor_manage"),
    re_path(r'^set-gateway$', views.set_gateway_page, name="set_gateway_page"),
    re_path(r'^add-sensor/(.*)$', views.add_sensor_page, name="add_sensor_page"),
    re_path(r'^system-settings$', views.system_settings, name="system_settings"),
    re_path(r'^delete-gateway/(.*)$', views.delete_gateway, name="delete_gateway"),
    re_path(r'^user-add$', account.user_add, name="user_add"),
    re_path(r'^user-edit/(\d+)$', account.user_edit, name="user_edit"),
    re_path(r'^user-delete/(\d+)$', account.user_delete, name="user_delete"),
    re_path(r'^user-list$', account.user_list, name="user_list"),
    re_path(r'^user-profile$', account.user_profile),
    re_path(r'^change-pwd$', account.change_pwd),

    re_path(r'^get-user-permissions-json$', account.get_user_permissions_json),

    re_path(r'^data-json-report-(\d+)$', views.data_json_report),
    re_path(r'^thickness-json-report$', views.thickness_json_report),
    re_path(r'^set-sensor-params$', views.set_sensor_params, name="set_sensor_params"),

    re_path(r'^set-Timing-time$', views.set_timing_time),
    re_path(r'^save-status$', views.save_status),

    re_path(r'^pause-Timing-time$', views.pause_Timing_time),
    re_path(r'^resume-Timing-time$', views.resume_Timing_time),
    re_path(r'^reset-Timing-time$', views.reset_Timing_time),

    re_path(r'^edit-sensor/(\d+)$', views.edit_sensor, name="edit_sensor"),
    re_path(r'^edit-sensor-alarm-msg/(\d+)$', views.edit_sensor_alarm_msg, name="edit_sensor_alarm_msg"),
    re_path(r'^get-gateway-networkid$', views.get_gateway_networkid),
    re_path(r'^set-gateway-networkid$', views.set_gateway_networkid),
    re_path(r'^test-signal-strength/(.*)$', views.test_signal_strength),
    re_path(r'^set-gateway-json$', views.set_gateway_json, name="set_gateway_json"),
    re_path(r'^judge-username-exist-json$', views.judge_username_exist_json),

    re_path(r'^show-soundV-json$', views.show_soundV_json),
    re_path(r'^CAL-Sound-T-json$', views.CAL_Sound_T_json),
    re_path(r'^CAL-Sound-V-json$', views.CAL_Sound_V_json),

    re_path(r'^refresh-gw-status$', views.refresh_gw_status),

    re_path(r'^receive-gw-data$', views.receive_gw_data, name="receive_gw_data"),

    re_path(r'^manual-get/(.*)$', views.manual_get, name="manual_get"),

    re_path(r'^check-sensor-params-is-exists$', views.check_sensor_params_is_exists),
    re_path(r'^check-GW-alias$', views.check_GW_alias),

    re_path(r'^control-upload-data-to-administration$', views.control_upload_data_to_administration),
    re_path(r'^control-upload-data-to-local-server$', views.control_upload_data_to_local_server),


]
