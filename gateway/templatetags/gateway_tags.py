from django.template import Library
from django.utils.safestring import mark_safe


register = Library()

@register.simple_tag
def render_run_time(received_time_data):
    ele = ''
    received_time_data = eval(received_time_data)
    if int(received_time_data['days']):
        ele += '%s天' % received_time_data['days']
    if int(received_time_data['hours']):
        ele += '%s小时' % received_time_data['hours']
    if int(received_time_data['minutes']):
        ele += '%s分钟' % received_time_data['minutes']

    return mark_safe(ele)
