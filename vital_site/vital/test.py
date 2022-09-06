import os
import sys
import logging
import xmlrpclib
import datetime
import socket
from models import Audit, Available_Config, User_Network_Configuration, Virtual_Machine, \
    User_VM_Config, Course, VLAB_User, Xen_Server, User_Bridge, Local_Network_MAC_Address
import ConfigParser
from decimal import *
from django.db import transaction
from influxdb import InfluxDBClient


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vital_site.settings")

logger = logging.getLogger(__name__)
config = ConfigParser.ConfigParser()
config.optionxform=str

# TODO change to common config file in shared location
config.read("/home/vital/config.ini")

server_configs = config.items('Servers')
user = VLAB_User.objects.get(first_name='Cron', last_name='User')

for key, server_url in server_configs:
    print "print details" + key + " " + server_url

