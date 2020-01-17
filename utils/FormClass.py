from django import forms
from django.forms import fields
from django.forms import widgets


class DataForm(forms.Form):
    url = fields.URLField(
        required=False,
        widget=widgets.Input(attrs={'class': 'layui-input', 'placeholder': 'http://ling.2tag.cn/api/collect_data'})
    )