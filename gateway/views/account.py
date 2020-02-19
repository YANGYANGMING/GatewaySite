from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django import forms
from django.forms import fields
from django.forms import widgets


@csrf_exempt
def acc_login(request):
    """登录"""
    error_msg = ''
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        rmb = request.POST.get('rmb')

        user = authenticate(username=username, password=password)
        if user:
            print("passed authentication")
            login(request, user)  # 把user封装到request.session中
            if rmb:
                request.session.set_expiry(60 * 60 * 24 * 30)
                print('rmb')
            return redirect('/gateway/index')  # 登录后跳转至next指定的页面，否则到首页
        else:
            error_msg = "用户名或密码错误!"

    return render(request, 'login.html', locals())

def acc_logout(request):
    """退出"""
    # request.session.clear()
    logout(request)
    return redirect('/login/')

def page_404(request):
    """404页面"""
    return render(request, '404.html')

class ChangepwdForm(forms.Form):
    old_pwd = fields.CharField(label='旧密码', max_length=32, widget=widgets.PasswordInput(attrs={'class': 'form-control'}))
    new_pwd = fields.CharField(label='新密码', max_length=32, widget=widgets.PasswordInput(attrs={'class': 'form-control'}))
    new_pwd_confirm = fields.CharField(label='重复新密码', max_length=32, widget=widgets.PasswordInput(attrs={'class': 'form-control'}))


@csrf_exempt
@login_required
def change_pwd(request):
    """修改密码"""
    result = {'message': ''}
    form = ChangepwdForm()
    if not request.user.is_authenticated:
        result['message'] = '未登录'
        print('未登录')
        return render(request, 'gateway/change_pwd.html', locals())

    elif request.method == "POST":
        form = ChangepwdForm(request.POST)
        if form.is_valid():
            old_pwd = form.cleaned_data['old_pwd']
            new_pwd = form.cleaned_data['new_pwd']
            new_pwd_confirm = form.cleaned_data['new_pwd_confirm']
            user = authenticate(username=request.user, password=old_pwd)
            if user: #旧密码正确
                if new_pwd == new_pwd_confirm: #两次新密码一致
                    user.set_password(new_pwd)
                    user.save()
                    print('更改成功')
                    return redirect('logout')
                else: #两次新密码不一致
                    result['message'] = '两次密码不一致'
                    return render(request, 'gateway/change_pwd.html', locals())
            else:
                result['message'] = '旧密码错误'
                return render(request, 'gateway/change_pwd.html', locals())

    return render(request, 'gateway/change_pwd.html', locals())








