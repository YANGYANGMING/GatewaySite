from django.shortcuts import render, redirect, HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import Group
from utils.check_click_method import check_click_method
from utils.FormClass import *
from gateway import models
from gateway import permissions
from gateway.views.views import log
from utils import handle_func
import json


@csrf_exempt
def acc_login(request):
    """登录"""
    result = {'status': False, 'msg': ''}
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        rmb = request.POST.get('rmb')

        user = authenticate(username=username, password=password)
        if user:
            print("passed authentication")
            login(request, user)  # 把user封装到request.session中
            if rmb:
                request.session.set_expiry(60 * 60 * 24 * 15)
                print('rmb')
                result = {'status': True, 'msg': '登录成功！'}
                log.log(result['status'], result['msg'], user=str(request.user))
            return redirect('/gateway/index')  # 登录后跳转至next指定的页面，否则到首页
        else:
            result['msg'] = "用户名或密码错误!"
            log.log(result['status'], result['msg'], user=str(request.user))

    return render(request, 'login.html', locals())


def acc_logout(request):
    """退出"""
    # request.session.clear()
    result = {'status': True, 'msg': '退出成功！'}
    log.log(result['status'], result['msg'], user=str(request.user))
    logout(request)
    return redirect('/login/')


def page_404(request):
    """404页面"""
    return render(request, '404.html')


@login_required
@permissions.check_permission
def user_add(request):
    """
    增加用户
    :param request:
    :return:
    """
    user_obj = models.UserProfile.objects.get(id=request.user.id)
    if request.method == "GET":
        roles_obj = models.Role.objects.values('id', 'name').all().exclude(name__in=['管理员'])
        groups_obj = Group.objects.values('id', 'name').all().exclude(name__in=['管理员权限'])

        cur_user_role_permissions_list = list(
            Group.objects.values('permissions__id', 'permissions__name').filter(user=request.user.id))
        cur_user_manual_assign_permissions_list = models.UserProfile.objects.get(
            id=request.user.id).user_permissions.values('id', 'name').all()
        cur_user_all_permissions_list = []
        for item in cur_user_manual_assign_permissions_list:
            item_temp = {}
            item_temp['permissions__id'] = item['id']
            item_temp['permissions__name'] = item['name']
            cur_user_all_permissions_list.append(item_temp)
        # 当前登录用户所拥有的角色权限和被手动分配的权限的总和
        cur_user_all_permissions_list += cur_user_role_permissions_list

        cur_role_list = [item['name'] for item in
                         models.UserProfile.objects.get(id=request.user.id).role.values('name')]

        return render(request, "gateway/user_add.html", locals())

    elif request.method == "POST":
        result = {'status': False, 'msg': '增加用户失败'}
        name = request.POST.get('name')
        password = make_password(request.POST.get('password'))
        role = request.POST.getlist('role')
        groups = request.POST.getlist('groups')
        user_permissions = request.POST.getlist('user_permissions')
        is_active = False if not request.POST.get('is_active') else True
        # create user
        try:
            create_user_obj = models.UserProfile.objects.create(name=name, password=password, is_active=is_active)
            create_user_obj.role.add(*role)
            create_user_obj.groups.add(*groups)
            create_user_obj.user_permissions.add(*user_permissions)
            result = {'status': True, 'msg': '增加用户成功'}
        except Exception as e:
            print(e)
        log.log(result['status'], result['msg'], user=str(request.user))

        return redirect('/gateway/user-list')


@csrf_exempt
@login_required
@permissions.check_permission
@check_click_method
def user_edit(request, nid):
    """
    编辑用户
    :param request:
    :return:
    """
    user_obj = models.UserProfile.objects.filter(id=nid)
    if request.method == "GET":
        # 在编辑用户页面显示选中的用户权限
        cur_user_all_permissions_list, selected_user_permissions_list = handle_func.show_selected_permissions(request, Group, nid)

        roles_obj = models.Role.objects.values('id', 'name').exclude(name__in=['管理员'])
        groups_obj = Group.objects.values('id', 'name').exclude(name__in=['管理员权限'])
        cur_name = user_obj.values('name')[0]['name']
        cur_role = user_obj[0].role.values('id').all()
        role_list = [item['id'] for item in cur_role]
        cur_group = user_obj[0].groups.values('id').all()
        group_list = [item['id'] for item in cur_group]
        is_active = user_obj.values('is_active')[0]['is_active']

        return render(request, "gateway/user_edit.html", locals())

    elif request.method == "POST":
        result = {'status': False, 'msg': '编辑用户失败'}
        name = request.POST.get('name')
        role = request.POST.getlist('role')
        groups = request.POST.getlist('groups')
        user_permissions = request.POST.getlist('user_permissions')
        is_active = False if not request.POST.get('is_active') else True
        cur_gateway = models.Gateway.objects.values('id').all()
        gateway = [item['id'] for item in cur_gateway]

        # update user
        try:
            user_obj.update(name=name, is_active=is_active)
            user_obj[0].role.set(role)
            user_obj[0].groups.set(groups)
            user_obj[0].user_permissions.set(user_permissions)
            result = {'status': True, 'msg': '编辑用户成功'}
        except Exception as e:
            print(e)
        log.log(result['status'], result['msg'], user=str(request.user))

        return redirect('/gateway/user-list')


@csrf_exempt
@login_required
@permissions.check_permission
def user_delete(request, nid):
    obj = models.UserProfile.objects.get(id=nid)
    role = obj.role.values('name')[0]['name']
    if request.method == "POST":
        obj.delete()
        result = {'status': True, 'msg': '删除用户成功'}
        log.log(result['status'], result['msg'], user=str(request.user))
        return redirect("/gateway/user-list")

    return render(request, "gateway/user_delete.html", locals())


@login_required
@permissions.check_permission
def user_list(request):
    """
    用户列表
    :param request:
    :return:
    """
    user_list = models.UserProfile.objects.all().values('id', 'name', 'role__name', 'last_login', 'is_active')

    return render(request, "gateway/user_list.html", locals())


@csrf_exempt
@login_required
def user_profile(request):
    """
    查看个人信息
    :param request:
    :return:
    """
    obj = models.UserProfile.objects.get(id=request.user.id)
    if request.method == "GET":
        form = UserProfileForm({'name': obj.name, 'role': obj.role.values('name').first()['name'], 'last_login': str(obj.last_login)})
    return render(request, 'gateway/userprofile.html', locals())

@csrf_exempt
@login_required
def change_pwd(request):
    """修改密码"""
    result = {'status': False, 'msg': ''}
    form = ChangepwdForm()
    if not request.user.is_authenticated:
        result['status'] = False
        result['msg'] = '未登录'
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
                    result['status'] = True
                    result['msg'] = '修改密码成功'
                    log.log(result['status'], result['msg'], user=str(request.user))
                    return redirect('logout')
                else: #两次新密码不一致
                    result['status'] = False
                    result['msg'] = '两次密码不一致'
                    log.log(result['status'], result['msg'], user=str(request.user))
                    return render(request, 'gateway/change_pwd.html', locals())
            else:
                result['status'] = False
                result['msg'] = '旧密码错误'
                log.log(result['status'], result['msg'], user=str(request.user))
                return render(request, 'gateway/change_pwd.html', locals())

    return render(request, 'gateway/change_pwd.html', locals())


@csrf_exempt
def get_user_permissions_json(request):
    """
    获取用户选中权限组的权限
    :param request:
    :return:
    """
    group_list = json.loads(request.POST.get('groups_list'))
    print(group_list)
    all_permissions_list = []
    for item in group_list:
        group_obj = Group.objects.get(id=item)
        permissions_list = [i['id'] for i in group_obj.permissions.values('id')]
        all_permissions_list += permissions_list

    return HttpResponse(json.dumps(all_permissions_list))






