from itertools import chain
from subprocess import Popen, PIPE
from django.core.management.base import BaseCommand, CommandError
import logging
from datetime import datetime
from django.utils import timezone
from vital.models import VLAB_User, Registered_Course, User_Network_Configuration, Available_Config

logger = logging.getLogger("vital")


def remove_user_nets(user_id):
    user_nets = User_Network_Configuration.objects.filter(user_id=user_id)
    for net in user_nets:
        conf = Available_Config()
        conf.category = 'MAC_ADDR'
        conf.value = net.mac_id
        conf.save()
        net.delete()


def remove_sftp_account(user_id):
    user = VLAB_User.objects.get(id=user_id)
    logger.debug("Deleting SFTP account of user {0}:{1}".format(user.id, user.email))

    cmd = 'sudo /home/vital/vital2.0/source/virtual_lab/vital_site/scripts/sftp_account.sh remove '+ \
            user.sftp_account+' > /home/vital/vital2.0/log/sftp.log'
    p = Popen(cmd.split(), stdout=PIPE, stderr=PIPE)
    out, err = p.communicate()
    if not p.returncode == 0:
        raise Exception('ERROR : cannot delete sftp account. \n Reason : %s' % err.rstrip())
    logger.debug("SFTP account of user {0}:{1} deleted".format(user.id, user.email))


def remove_user(user_id, is_force_delete=False):
    registered_courses = Registered_Course.objects.filter(user_id=user_id)
    if registered_courses and not is_force_delete:
        registered_courses_ids = [course.course_id for course in registered_courses]
        raise Exception("User {0}:{1} is still registered for: {2}".format(user.id,user.email,registered_courses_ids))        
        
    remove_sftp_account(user_id)
    remove_user_nets(user_id)
    
    user = VLAB_User.objects.get(id=user_id)
    VLAB_User.objects.get(id=user_id).delete()
    logger.info("Deleted user {0}:{1}".format(user.id, user.email))


class Command(BaseCommand):
    help = "Actually delete an user. Forever. No regrets."

    def add_arguments(self, parser):
        parser.add_argument('user_id', nargs='+', type=str,
            help="ID of an user to delete, or an email if the flag --email is passed")
        parser.add_argument(
            '--email',
            action='store_true',
            help='pass this flag to remove user by email, not id',
        )

    def handle(self, *args, **options):
        query_by = options['user_id'][0]
        if options['email']:
            user = VLAB_User.objects.filter(email=query_by)
        else:
            user = VLAB_User.objects.filter(id=int(query_by))

        if not user:
            logger.info("User {0} not found".format(query_by))
        else:
            user = user[0]
            remove_user(user.id)

