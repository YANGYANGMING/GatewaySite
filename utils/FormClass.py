from django import forms
from django.forms import fields
from django.forms import widgets as wid


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


