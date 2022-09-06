from itertools import chain
from django.core.management.base import BaseCommand, CommandError
import logging
from datetime import datetime
from django.utils import timezone
from vital.models import VLAB_User, Registered_Course, User_Network_Configuration, Available_Config
from vital.management.commands.RemoveUser import remove_user

logger = logging.getLogger("vital")


class Command(BaseCommand):
    help = "Will mark users who have not logged into their accounts for a specified number of days." \
            "By default will only show the users that would not survive the purge" \
            "Pass flag --delete to actually purge them from Vital. Forever. No regrets." \
            "Users marked faculty/admin/staff will not be removed."

    def add_arguments(self, parser):
        parser.add_argument('days_to_expire', nargs='+', type=int,
            help="Number of days since last login to become a candidate for deletion")
        parser.add_argument(
            '--delete',
            action='store_true',
            help='Actually delete them. Like Stalin would have done...',
        )

    def handle(self, *args, **options):
        days_to_expire = options['days_to_expire'][0]
        expiration_date = timezone.now() - timezone.timedelta(days=days_to_expire)
        passive_users = VLAB_User.objects.filter(last_login__lte=expiration_date)        
        non_activated_users = VLAB_User.objects.filter(created_date__lte=expiration_date, last_login__isnull=True)        
        for user in chain(passive_users, non_activated_users):
            if user.first_name == 'Cron':
                continue
            registered_courses = Registered_Course.objects.filter(user_id=user.id)
            if registered_courses:
                registered_courses_ids = [course.course_id for course in registered_courses]                
                logger.warning("User {0}:{1} is inactive, but is still registered for: {2}".format(user.id,user.email,registered_courses_ids))
                continue

            is_special = any((user.is_staff, user.is_admin, user.is_faculty))
            if is_special:
                logger.warning("User {0}:{1} is inactive, but is special to us (by his role flags)".format(user.id,user.email))
                continue

            if options['delete']:
                logger.info("Deleted user {0}:{1} for {2} days inactivity.".format(user.id,user.email,days_to_expire))
                remove_user(user.id)
            else:
                logger.info("Consider deleting user {0}:{1} for {2} days inactivity.".format(user.id,user.email,days_to_expire))
