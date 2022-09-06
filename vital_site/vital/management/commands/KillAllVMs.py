from django.core.management.base import BaseCommand, CommandError
from django.contrib.sessions.models import Session
import logging
import time
from django.utils import timezone
from vital.models import VLAB_User, Course, User_VM_Config, Available_Config
from vital.views import stop_vms_during_logout
from vital.utils import XenClient, audit
from subprocess import Popen, PIPE
from random import randint
from django.core.mail import send_mail
import os
import signal

logger = logging.getLogger(__name__)

class Command(BaseCommand):

    help = "Command to force remove VMs, networks of users who have not logged out properly " \
           "- Scheduled cron job that runs every 1 hour"

    def handle(self, *args, **options):
                kill = True 
                for user_id in range(479, 1502):
                    try:
                        print('session user_id:' +str(user_id))
                        user = VLAB_User.objects.get(id=user_id)
                        print("Checking session time for user : " + user.email)

                        started_vms = User_VM_Config.objects.filter(user_id=user_id)
                        for started_vm in started_vms:
                            print("Course : " + started_vm.vm.course.name)
                            print("Course auto shutdown period (mins): " + str(started_vm.vm.course.auto_shutdown_after))
                            print("VM: " + str(started_vm.vm.name))
                            print("VM up after session expiry: " + str(time_difference_in_minutes))

                            XenClient().stop_vm(started_vm.xen_server, user, started_vm.vm.course.id, started_vm.vm.id)
                            print("KILLING")

                            started_vm.delete()
                            
                            send_mail("Vital : Service Down", 'Hi ' + user.first_name+', \r\n\r\nVital will be back shortly '
                                                                                    '\r\n\r\nVital Admin',
                                    'no-reply-vital@nyu.edu', [user.email], fail_silently=False)
                    except Exception as e:
                        print(e)
                        pass

