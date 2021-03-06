"""GatewaySite URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf.urls import include
from django.urls import path, re_path
from gateway.views import account
from django.views.generic import RedirectView
from django.views import static ##新增
from django.conf import settings ##新增
from django.conf.urls import url ##新增

urlpatterns = [
    path('admin/', admin.site.urls),
    re_path(r'^gateway/', include('gateway.urls')),
    re_path(r'^login/$', account.acc_login),
    re_path(r'^gateway/logout$', account.acc_logout, name='logout'),
    re_path(r'^$', RedirectView.as_view(url='gateway/index')),

    re_path(r'\S', account.page_404),
##　以下是新增
    # url(r'^static/(?P<path>.*)$', static.serve,
    #     {'document_root': settings.STATIC_ROOT}, name='static'),
]
