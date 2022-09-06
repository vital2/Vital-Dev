#!/bin/bash

#reading from config file
host=$(awk -F ":" '/VITAL_DB_HOST/ {print $2}' /home/vital/config.ini | tr -d ' ')
pass=$(awk -F ":" '/VITAL_DB_PWD/ {print $2}' /home/vital/config.ini | tr -d ' ')
port=$(awk -F ":" '/VITAL_DB_PORT/ {print $2}' /home/vital/config.ini | tr -d ' ')
dbname=$(awk -F ":" '/VITAL_DB_NAME/ {print $2}' /home/vital/config.ini | tr -d ' ')

vlan=$1
if /sbin/ethtool bond0.$vlan | grep -q "Link detected: yes"; then
    echo "Online"
else
    echo "Not online"
    vconfig add bond0 $vlan
    ifconfig bond0.$vlan 10.$vlan.1.1 netmask 255.255.255.0 broadcast 10.$vlan.1.255 up
fi

requires_internet=$(PGPASSWORD=$pass psql -U postgres -d $dbname -h $host -p $port -t -c "SELECT n.has_internet_access from vital_course c join vital_network_configuration n on c.id=n.course_id where n.is_course_net=True and c.id="+$vlan)

echo "vlan $vlan Requires Internet $requires_internet"
#iptables -C FORWARD -i bond0.$vlan -s 10.$vlan.1.0/24 -j REJECT
# iptables -I FORWARD -i bond0.$vlan -s 10.$vlan.1.0/24 -j REJECT
