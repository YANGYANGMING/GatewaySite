import os, time
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "GatewaySite.settings")
django.setup()
from gateway import models



