
## 概述
eelib运行于python3环境,封装了操作网关模块的python代码，通过串口控制模块。lib是实际的库，lib外的py文件用于测试，使用的示例可以参考post2server.py。

## 1 安装环境
安装运行环境，2种方式：
1.真实环境安装
2.virtualenv安装，虚拟环境安装在eelib目录下，名为.env(关系到.gitignore中的忽略)，运行命令
```
pip3 install -r requirements.txt
```

## 3 运行示例
```
python3 post2server.py
```

## 4 其他
在树莓派环境中:
/eelib/post2server.py文件中，使用
```
gser = serial.Serial("/dev/ttyAMA0",115200,timeout=1)
```
/eelib/lib/alg/emat/emat.py文件中，使用
```
ETGminiX1_file = os.path.dirname(os.path.abspath(__file__)) + '/thicknessgauge_armv7l.so'
```

在linux环境中，以上2处视情况使用:
```
gser = serial.Serial("/dev/ttyUSB0",115200,timeout=1)
```
```
ETGminiX1_file = os.path.dirname(os.path.abspath(__file__)) + '/thicknessgauge_x86_64.so'
```

