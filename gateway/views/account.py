from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from utils.FormClass import *
from gateway import models
from gateway import permissions


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



# @permissions.check_permission
@login_required
def user_add(request):
    """
    增加用户
    :param request:
    :return:
    """
    if request.method == "GET":
        form_obj = UserAddForm()
        return render(request, "gateway/user_add.html", locals())
    elif request.method == "POST":
        form_obj = UserAddForm(data=request.POST)
        if form_obj.is_valid():
            temp = form_obj.save(commit=False)  # 暂时获取一个数据库对象，对其他字段进行赋值
            temp.password = make_password(form_obj.cleaned_data['password'])
            temp.save()  # 真正插入数据库
            return redirect('/gateway/user-list')


# @permissions.check_permission
@login_required
def user_edit(request, nid):
    """
    编辑用户
    :param request:
    :return:
    """
    obj = models.UserProfile.objects.filter(id=nid).first()
    if request.method == "GET":
        form_obj = UserEditForm(instance=obj)
        return render(request, "gateway/user_edit.html", locals())
    elif request.method == "POST":
        form_obj = UserEditForm(data=request.POST, instance=obj)
        if form_obj.is_valid():
            form_obj.save()
        return redirect('/gateway/user-list')


# @permissions.check_permission
@login_required
@csrf_exempt
def user_delete(request, nid):
    obj = models.UserProfile.objects.get(id=nid)

    if request.method == "POST":
        obj.delete()
        return redirect("/gateway/user-list")

    return render(request, "gateway/user_delete.html", locals())


@permissions.check_permission
@login_required
def user_list(request):
    """
    用户列表
    :param request:
    :return:
    """
    user_list = models.UserProfile.objects.all()

    return render(request, "gateway/user_list.html", locals())


@csrf_exempt
@login_required
def user_profile(request):
    """
    查看修改个人信息
    :param request:
    :return:
    """
    obj = models.UserProfile.objects.get(id=request.user.id)
    if request.method == "GET":
        form = UserProfileForm({'email': obj.email, 'name': obj.name, 'role': obj.role.values('name').first()['name'], 'last_login': str(obj.last_login)})
    if request.method == "POST":
        form = UserProfileForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            name = form.cleaned_data['name']
            models.UserProfile.objects.filter(id=request.user.id).update(email=email, name=name)
    return render(request, 'gateway/userprofile.html', locals())

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








