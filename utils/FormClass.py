from django import forms
from django.forms import fields
from django.forms import widgets as wid
from django.forms import ModelForm
from gateway import models

class DataForm(forms.Form):
    url = fields.URLField(
        required=False,
        widget=wid.Input(attrs={'class': 'form-control', 'placeholder': 'http://ling.2tag.cn/api/collect_data'})
    )


class ChangepwdForm(forms.Form):
    old_pwd = fields.CharField(label='旧密码', max_length=32, widget=wid.PasswordInput(attrs={'class': 'form-control'}))
    new_pwd = fields.CharField(label='新密码', max_length=32, widget=wid.PasswordInput(attrs={'class': 'form-control'}))
    new_pwd_confirm = fields.CharField(label='重复新密码', max_length=32, widget=wid.PasswordInput(attrs={'class': 'form-control'}))


class UserProfileForm(forms.Form):
    name = fields.CharField(label='用户名', max_length=32,
                            widget=wid.TextInput(attrs={'class': 'form-control col-lg-offset-1'}))
    role = fields.CharField(label='角色', max_length=32,
                            widget=wid.TextInput(attrs={'class': 'form-control col-lg-offset-1'}))
    last_login = fields.CharField(label='最后登录时间', max_length=32,
                                  widget=wid.TextInput(attrs={'class': 'form-control col-lg-offset-1'}))


class UserEditForm(ModelForm):
    class Meta:
        model = models.UserProfile  #对应的Model中的类
        fields = '__all__'      #字段，如果是'__all__',就是表示列出所有的字段
        exclude = ['password', 'last_login']          #排除的字段
        labels = None           #提示信息
        help_texts = None       #帮助提示信息
        # widgets = None          #自定义插件
        error_messages = None   #自定义错误信息

#widgets用法
        widgets = {
            "password": wid.Input(attrs={'class': 'form-control', 'style': 'width: 50%'}),
            "last_login": wid.Input(attrs={'class': 'form-control', 'style': 'width: 50%'}),
            "name": wid.Input(attrs={'class': 'form-control', 'style': 'width: 50%'}),
        }


class UserAddForm(ModelForm):
    class Meta:
        model = models.UserProfile  #对应的Model中的类
        fields = '__all__'      #字段，如果是'__all__',就是表示列出所有的字段
        exclude = ['last_login']          #排除的字段
        labels = None           #提示信息
        help_texts = None       #帮助提示信息
        # widgets = None          #自定义插件
        error_messages = None   #自定义错误信息

#widgets用法
        widgets = {
            "password": wid.Input(attrs={'class': 'form-control', 'style': 'width: 50%'}),
            "last_login": wid.Input(attrs={'class': 'form-control', 'style': 'width: 50%'}),
            "name": wid.Input(attrs={'class': 'form-control', 'style': 'width: 50%'}),
        }
