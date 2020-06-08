from django.template import Library
from django.utils.safestring import mark_safe


register = Library()

@register.simple_tag
def render_run_time(received_time_data):
    ele = ''
    received_time_data = eval(received_time_data)
    if received_time_data['month'] == '*':
        ele += '每月-'
    else:
        ele += '%s月-' % received_time_data['month']
    if received_time_data['day'] == '*':
        ele += '每日-'
    else:
        ele += '%s日-' % received_time_data['day']
    if received_time_data['hour'] == '*':
        ele += '每小时-'
    else:
        ele += '%s点-' % received_time_data['hour']
    if received_time_data['mins'] == '*':
        ele += '每分钟-'
    else:
        ele += '%s分整' % received_time_data['mins']

    return mark_safe(ele)
