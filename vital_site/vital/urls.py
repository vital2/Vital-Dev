from django.conf.urls import url

from . import views

app_name = 'vital'
urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^courses/register/$', views.register_for_course, name='course_register'),
    url(r'^courses/(?P<course_id>[0-9]+)/deregister/$', views.unregister_from_course, name='course_deregister'),
    url(r'^courses/(?P<course_id>[0-9]+)/vms/$', views.course_vms, name='course_vms'),
    url(r'^courses/(?P<course_id>[0-9]+)/virtual_machines/$', views.virtual_machines, name='virtual_machines'),
    url(r'^courses/(?P<course_id>[0-9]+)/detail/$', views.course_detail, name='course_detail'),
    url(r'^console/(?P<vm_id>[0-9]+)/$', views.console, name='console'),
    url(r'^courses/registered/$', views.registered_courses, name='registered_courses'),
    url(r'^courses/advising/$', views.advising_courses, name='advising_courses'),
    url(r'^users/register/$', views.register, name='user_register'),
    url(r'^users/activate/$', views.activate, name='user_activate'),
    url(r'^users/resend/$', views.resend, name='resend_code'),
    url(r'^users/(?P<user_id>[0-9]+)/vms/(?P<vm_id>[0-9]+)/release-vm/$', views.release_vm, name='user_releaseVM'),
    url(r'^login/$', views.login, name='login'),
    url(r'^logout/$', views.logout, name='logout'),
    url(r'^users/reset-password/$', views.reset_password, name='user_reset_password'),
    url(r'^users/forgot-password/$', views.forgot_password, name='user_forgot_password'),
    url(r'^courses/(?P<course_id>[0-9]+)/vms/(?P<vm_id>[0-9]+)/start/$', views.start_vm, name='start_vm'),
    url(r'^courses/(?P<course_id>[0-9]+)/vms/(?P<vm_id>[0-9]+)/stop/$', views.stop_vm, name='stop_vm'),
    url(r'^courses/(?P<course_id>[0-9]+)/vms/(?P<vm_id>[0-9]+)/rebase/$', views.rebase_vm, name='rebase_vm'),
]
