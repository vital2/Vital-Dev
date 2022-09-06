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

logger = logging.getLogger(__name__)
config = ConfigParser.ConfigParser()
config.optionxform=str

# TODO change to common config file in shared location
config.read("/home/vital/config.ini")


def audit(request, action):
    logger.debug('In audit')
    if request.user.id is not None:
        audit_record = Audit(done_by=request.user.id, action=action)
        #logger.info("user {}: action".format(request.user.id, action)
    else:
        audit_record = Audit(done_by=0, action=action)
        logger.error('An action is being performed without actual user id.')
    audit_record.save()


def get_notification_message():
    try:
        config_val = Available_Config.objects.get(category='NOTIFICATION_MESSAGE')
        message = config_val.value
    except Available_Config.DoesNotExist as e:
        message = None
    return message


def is_number(s):
    try:
        int(s)
        return True
    except ValueError:
        return False

def get_spice_options():
    """
    Just to define the Spice options dictionary as a function.
    returns: Dictionary conatining the various Spice Options.
    """
    spice_opts = {
	# 'vcpus': 4,
        'vnc': 0,
        'vga': 'cirrus',
        'spice': 1,
        # 'spicehost': '0.0.0.0',
        'spiceport': 0,
        'spicedisable_ticketing': 1,
        'spicevdagent': 1,
        'spice_clipboard_sharing': 1
    }
    return spice_opts

def get_free_tcp_port():
    """
    Starts a socket connection to grab a free port (Involves a race
        condition but will do for now)
    :return: An open port in the system
    """
    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp.bind(('', 0))
    _, port = tcp.getsockname()
    tcp.close()
    return port

class XenClient:

    def __init__(self):
        pass

    def list_student_vms(self, server, user, course_id):
        vms = SneakyXenLoadBalancer().get_server(server).list_vms(user)
        prefix = str(user.id) + '_' + str(course_id)
        return [vm for vm in vms if vm['name'].startswith(prefix)]

    def list_all_vms(self, server, user):
        return SneakyXenLoadBalancer().get_server(server).list_vms(user)

    def list_vm(self, server,  user, course_id, vm_id):
        logger.debug('>>>>>>>>IN LIST VM>>>>>>')
        vm = SneakyXenLoadBalancer().get_server(server).list_vm(user, str(user.id) + '_' + str(course_id) + '_' + str(vm_id))
        vm['xen_server'] = server
        return vm

    def register_student_vms(self, user, course):
        # choosing best server under assumption that VM conf and dsk will be on gluster
        xen = SneakyXenLoadBalancer().get_best_server(user, course.id)
        logger.debug('Number of VMs in course: ' + str(len(course.virtual_machine_set.all())))
        for vm in course.virtual_machine_set.all():
            networks = vm.network_configuration_set.all().order_by('name')
            vif = ''

            with transaction.atomic():
            #ap4414 EDIT : MAC address allotment to be identical across student NW's
                for network in networks:
                    flag = True
                    cnt = 0
                    # hack to handle concurrent requests
                    while flag:
                        # EDIT : Across all student local networks, each VM VIFs will have has same MAC#
                        val = "00"
                        cnt += 1
                        user_net_config = User_Network_Configuration()
                        if network.is_course_net:
                            available_config = Available_Config.objects.filter(category='MAC_ADDR').order_by('id').first()
                            locked_conf = Available_Config.objects.select_for_update().filter(id=available_config.id)
                            if locked_conf is not None:
                                val = locked_conf[0].value
                                locked_conf.delete()
                                vif = vif + '\'mac=' + val + ', bridge=' + network.name + '\'' + ','
                                user_net_config.bridge, obj_created = User_Bridge.objects.get_or_create(name=network.name, created=True)
                        else:
                            locked_conf = Local_Network_MAC_Address.objects.get( network_configuration = network.id)
                            val = locked_conf.mac_id
                            if locked_conf is not None:
                                net_name = str(user.id) + '_' + str(course.id) + '_' + network.name
                                vif = vif + '\'mac=' + val + ', bridge=' + net_name + '\'' + ','
                                user_net_config.bridge, obj_created = User_Bridge.objects.get_or_create(name=net_name)

                        user_net_config.user_id = user.id
                        user_net_config.mac_id = val
                        user_net_config.vm = vm
                        user_net_config.course = course
                        user_net_config.is_course_net = network.is_course_net
                        user_net_config.save()
                        flag = False

                        if cnt >= 100:
                            raise Exception('Server Busy : Registration incomplete')

            vif = vif[:len(vif) - 1]
            logger.debug('Registering with vif:' + vif + ' for user ' + user.email)
            logger.error(str(user.id) + '_' + str(course.id) + '_' + str(vm.id)+'#'+ str(course.id) + '_' + str(vm.id)+'#'+ vif)
            xen.setup_vm(user, str(user.id) + '_' + str(course.id) + '_' + str(vm.id), str(course.id) + '_' + str(vm.id), vif)
            logger.debug('Registered user ' + user.email)

    def unregister_student_vms(self, user, course):
        # choosing best server under assumption that VM conf and dsk will be on gluster
        xen = SneakyXenLoadBalancer().get_best_server(user, course.id)
        logger.debug("Unregistering course " + course.name)
        logger.debug("Removing VMs..")
        for virtualMachine in course.virtual_machine_set.all():
            xen.cleanup_vm(user, str(user.id) + '_' + str(course.id) + '_' + str(virtualMachine.id))

        logger.debug("Removing User Network configs..")
        # ap4414 EDIT : releasing only the MAC assigned to course_net vif#
        net_confs_to_delete = User_Network_Configuration.objects.filter(user_id=user.id, course=course, is_course_net=True)
        for conf in net_confs_to_delete:
            available_conf = Available_Config()
            available_conf.category = 'MAC_ADDR'
            available_conf.value = conf.mac_id
            available_conf.save()
            conf.delete()
        logger.debug("Removing User bridges..")
        bridges_to_delete = User_Bridge.objects.filter(name__startswith=str(user.id) + '_' + str(course.id))
        for bridge in bridges_to_delete:
            bridge.delete()

    def start_vm(self, user, course_id, vm_id):
        logger.debug('XenClient - in start_vm')
        xen = SneakyXenLoadBalancer().get_best_server(user, course_id)
        net_confs = User_Network_Configuration.objects.filter(user_id=user.id, vm__id=vm_id,
                                                              course__id=course_id, bridge__created=False)
        with transaction.atomic():
            for conf in net_confs:
                try:
                    xen.create_bridge(user, conf.bridge.name)
                except Exception as e:
                    logger.error(str(e))
                    if 'cannot create the bridge' in str(e) and 'already exists' in str(e):
                        pass
                    else:
                        raise e
                conf.bridge.created = True
                conf.bridge.save()

            display_server = config.get('VITAL', 'DISPLAY_SERVER')

            if display_server == 'SPICE':
                vm_options = ';'.join('{}="{}"'.format(key, val) for (
                    key, val) in get_spice_options().iteritems())
                logger.debug('VM OPTIONS : %s', vm_options)
                # vm_options = ''
            elif display_server == 'VNC':
                vm_options = ''
            else:
                logger.error('ERROR : Invalid Display Server found - %s.' \
                    'Starting with NoVNC', display_server)
                display_server = 'VNC'
                vm_options = ''

            vm = xen.start_vm(user, str(user.id) + '_' + str(course_id) + '_' + str(vm_id), vm_options)
            vm['xen_server'] = xen.name
            vm['display_type'] = display_server
            return vm

    def remove_network_bridges(self, server, user, course_id, vm_id):
        xen = SneakyXenLoadBalancer().get_server(server)

        with transaction.atomic():
            net_confs = User_Network_Configuration.objects.filter(user_id=user.id, vm__id=vm_id, is_course_net=False,
                                                                  course__id=course_id, bridge__created=True)
            for conf in net_confs:
                bridge = conf.bridge
                logger.debug('Checking bridge '+bridge.name)
                attached_to_bridge = bridge.user_network_configuration_set.filter(user_id=user.id, course__id=course_id)
                logger.debug('No of nets attached - ' + str(len(attached_to_bridge)))
                attached = False
                for net in attached_to_bridge:
                    # logger.debug(str(net.vm.id)+'<>'+str(vm_id))
                    if net.vm.id != int(vm_id):
                        try:
                            vm = User_VM_Config.objects.get(vm__id=net.vm.id, user_id=user.id)
                            attached = True
                            logger.debug('Active VM attached -'+str(vm.id))
                            break
                        except User_VM_Config.DoesNotExist as e:
                            pass
                if not attached:
                    logger.debug('Removing bridge -' + bridge.name)
                    xen.remove_bridge(user, bridge.name)
                    bridge.created = False
                    bridge.save()

    def stop_vm(self, server, user, course_id, vm_id):
        xen = SneakyXenLoadBalancer().get_server(server)
        xen.stop_vm(user, str(user.id) + '_' + str(course_id) + '_' + str(vm_id))

    def rebase_vm(self, user, course_id, vm_id):
        xen = SneakyXenLoadBalancer().get_best_server(user, course_id)
        virtual_machine = Virtual_Machine.objects.get(id=vm_id)
        course = Course.objects.get(id=course_id)
        net_confs = User_Network_Configuration.objects.filter(user_id=user.id, vm=virtual_machine,
                                                              course=course).order_by('id')
        vif = ''
        for conf in net_confs:
            vif = vif + '\'mac=' + conf.mac_id + ', bridge=' + conf.bridge.name + '\','
            logger.debug('Updating Conf with vif:' + vif + ' for user ' + user.email)
        vif = vif[:len(vif)-1]
        xen.cleanup_vm(user, str(user.id) + '_' + str(course_id) + '_' + str(vm_id))
        xen.setup_vm(user, str(user.id) + '_' + str(course_id) + '_' + str(vm_id), str(course_id) + '_' + str(vm_id),
                     vif)

    def save_vm(self, server, user, course_id, vm_id):
        xen = SneakyXenLoadBalancer().get_server(server)
        xen.save_vm(user, str(user.id) + '_' + str(course_id) + '_' + str(vm_id))

    def restore_vm(self, server, user, course_id, vm_id):
        xen = SneakyXenLoadBalancer().get_server(server)
        xen.restore_vm(user, str(user.id) + '_' + str(course_id) + '_' + str(vm_id), str(course_id) + '_' + str(vm_id))


class XenServer:

    def __init__(self, name, url):
        self.name = name
        self.proxy = xmlrpclib.ServerProxy(url)

    def list_vms(self, user):
        return self.proxy.xenapi.list_all_vms(user.email, user.password)

    def list_vm(self, user, vm_name):
        return self.proxy.xenapi.list_vm(user.email, user.password, vm_name)

    def setup_vm(self, user, vm_name, base_name, vif=None):
        self.proxy.xenapi.setup_vm(user.email, user.password, vm_name, base_name, vif)

    def cleanup_vm(self, user, vm_name):
        self.proxy.xenapi.cleanup_vm(user.email, user.password, vm_name)

    def stop_vm(self, user, vm_name):
        self.proxy.xenapi.stop_vm(user.email, user.password, vm_name)

    def start_vm(self, user, vm_name, vm_options=''):
        return self.proxy.xenapi.start_vm(user.email, user.password, vm_name, vm_options)

    def save_vm(self, user, vm_name):
        return self.proxy.xenapi.save_vm(user.email, user.password, vm_name)

    def restore_vm(self, user, vm_name, base_vm):
        return self.proxy.xenapi.restore_vm(user.email, user.password, vm_name, base_vm)

    def kill_zombie_vm(self, user, vm_id):
        return self.proxy.xenapi.kill_zombie_vm(user.email, user.password, vm_id)

    def create_bridge(self, user, name):
        self.proxy.xenapi.create_bridge(user.email, user.password, name)

    def remove_bridge(self, user, name):
        self.proxy.xenapi.remove_bridge(user.email, user.password, name)

    def vm_exists(self, user, vm_name):
        return self.proxy.xenapi.vm_exists(user.email, user.password, vm_name)

    def bridge_exists(self, user, name):
        return self.proxy.xenapi.bridge_exists(user.email, user.password, name)

    def is_bridge_up(self, user, name):
        return self.proxy.xenapi.is_bridge_up(user.email, user.password, name)

    def get_dom_details(self, user):
        return self.proxy.xenapi.get_dom_details(user.email, user.password)

class SneakyXenLoadBalancer:

    def get_best_server(self, user, course_id):
        """
        Retrieves best server for user and course
        - checks if user has a VM for the specified course already started
            - if yes returns same server
            - if not, then checks server with best stats
                - if more than 1 servers have same stat then pick the first
        :param user: user object
        :param course_id: id of course
        :return: best XenServer instance
        """
        course = Course.objects.get(id=course_id)
        vm_confs = User_VM_Config.objects.filter(user_id=user.id, vm_id__in=course.virtual_machine_set.all())

        if len(vm_confs) > 0:
            logger.debug('Using same server as other VM')
            xen_name = vm_confs[0].xen_server
            return XenServer(xen_name, config.get("Servers", xen_name))
        else:
            logger.debug('Using best server')
            xen_server = Xen_Server.objects.filter(status='ACTIVE').order_by('utilization').first()
            return XenServer(xen_server.name, config.get("Servers", xen_server.name))
        # name = 'vlab-dev-xen2'
        # return XenServer(name, config.get("Servers", name))

    def get_server(self, name):
        return XenServer(name, config.get("Servers", name))

    def sneak_in_server_stats(self):
        # heart beat - 5 seconds stats collection
        # this is exposed as a custom django command that will be executed on server start
        # vital/management/commands
        server_configs = config.items('Servers')
        # user = VLAB_User.objects.get(first_name='Naman', last_name='Kapoor')
        user = VLAB_User.objects.get(first_name='tom', last_name='reddington')
       # logger.error("cron user fetched")
        for key, server_url in server_configs:
            logger.error(key+" "+server_url)
            server = Xen_Server.objects.get(name=key)
            #logger.error("server fetched: :"+server)
            try:
                #logger.error("inside try")
                tmp = XenServer(key,server_url)
                #logger.error("vm fetched")
                vms = tmp.list_vms(user)
                #vms = XenServer(key, server_url).list_vms(user)
                # used_memory = sum(list([int(vm['memory']) for vm in vms if vm['name']]))
                #logger.error("vms fetched")
                used_memory = 0
                students = set()
                courses = set()
                for vm in vms:
                    #logger.error("inside vm in vms")
                    if 'Domain' not in vm['name'] and vm['name'].count('_') == 2:
                        student = vm['name'][0:vm['name'].find('_')]
                        # logic to identify vms started by students
                        # coz students vm names are formatted as "studentid_courseid_vmid"
                        if is_number(student):
                            students.add(student)
                            val = vm['name'][vm['name'].find('_') + 1:]
                            courses.add(val[0:val.find('_')])
                    used_memory += int(vm['memory'])

                server.used_memory = used_memory
                server.no_of_students = len(students)
                server.no_of_courses = len(courses)
                server.no_of_vms = len(vms)
                server.utilization = Decimal(server.used_memory)/Decimal(server.total_memory)
                server.status = 'ACTIVE'
            except Exception as e:
                logger.error(key+str(e))
                server.used_memory = 0
                server.no_of_students = 0
                server.no_of_courses = 0
                server.no_of_vms = 0
                server.utilization = 0.0
                server.status = 'INACTIVE'
            finally:
                server.save()
                #self.send_stats_to_influxdb(server)

    def send_stats_to_influxdb(self, server):
        """
        Send Stats to InfluxDB for Grafana Visualization
        :param server: server instance with all the values from the xen Machines
        """
        timestr = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
        json_body = [
            {
                "measurement": "used_memory",
                "tags": {
                    "host": server.name
                },
                "time": timestr,
                "fields": {
                    "value": server.used_memory
                }
            },
            {
                "measurement": "no_of_students",
                "tags": {
                    "host": server.name
                },
                "time": timestr,
                "fields": {
                    "value": server.no_of_students
                }
            },
            {
                "measurement": "no_of_courses",
                "tags": {
                    "host": server.name
                },
                "time": timestr,
                "fields": {
                    "value": server.no_of_courses
                }
            },
            {
                "measurement": "no_of_vms",
                "tags": {
                    "host": server.name
                },
                "time": timestr,
                "fields": {
                    "value": server.no_of_vms
                }
            },
            {
                "measurement": "utilization",
                "tags": {
                    "host": server.name
                },
                "time": timestr,
                "fields": {
                    "value": round(server.utilization, 5)
                }
            },
            {
                "measurement": "status",
                "tags": {
                    "host": server.name
                },
                "time": timestr,
                "fields": {
                    "value": server.status
                }
            }
        ]

        c = InfluxDBClient(host='vlab_server', port=8086)
        c.switch_database('xen_stats')
        c.write_points(json_body)
        c.close()

    def get_xen_dom_details(self):
        # heart beat - 1 Minute stats collection
        # this is exposed as a custom django command that will be executed on server start
        # vital/management/commands
        server_configs = config.items('Servers')
        user = VLAB_User.objects.get(first_name='Cron', last_name='User')
        for key, server_url in server_configs:
            server = Xen_Server.objects.get(name=key)
            try:
                dom_detail_arr = []
                vms = XenServer(key, server_url).get_dom_details(user)
                for vm in vms:
                    if 'Domain' not in vm['name'] and vm['name'].count('_') == 2:
                        # Parse the data and format the same into a a json
                        # logger.debug('Dom Details : {}'.format(vm))
                        vm_details = vm['name'].split('_')
                        student = VLAB_User.objects.get(id = vm_details[0])
                        student_name = '{} {}'.format(student.first_name, student.last_name)
                        if 'b' in vm['state']:
                            vm_state = 'Blocked'
                        elif 'r' in vm['state']:
                            vm_state = 'Running'
                        elif 'p' in vm['state']:
                            vm_state = 'Paused'
                        else:
                            vm_state = 'Unknown'

                        tags = {}
                        tags['host'] = server.name
                        tags['student'] = student_name
                        tags['course'] = Course.objects.get(id = vm_details[1]).name
			tags['vm_name'] = Virtual_Machine.objects.get(id = vm_details[2]).name
                        tags['state'] = vm_state
                        fields = {}
                        fields['cpu_secs'] = long(vm['cpu_secs'])
                        fields['cpu_per'] = float(vm['cpu_per'])
                        fields['memory'] = long(vm['mem'])
                        fields['mem_per'] = float(vm['mem_per'])
                        fields['vcpus'] = int(vm['vcpus'])
                        fields['networks'] = int(vm['nets'])
                        timestr = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
                        dom_detail = {}
                        dom_detail['measurement'] = 'vm_details'
                        dom_detail['tags'] = tags
                        dom_detail['time'] = timestr
                        dom_detail['fields'] = fields

                        dom_detail_arr.append(dom_detail)

                if dom_detail_arr:
                    c = InfluxDBClient(host='128.238.77.36', port=8086)
                    c.switch_database('xen_dom_stats')
                    c.write_points(dom_detail_arr)
                    c.close()
 
            except Exception as e:
                logger.error(key+ ' ' + str(e))
