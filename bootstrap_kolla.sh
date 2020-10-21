#!/bin/bash

set -euxo pipefail

# Dependencies
#sudo apt-get update
#sudo apt-get -y install python3-dev libffi-dev gcc libssl-dev python3-pip python3-venv

# basedir and venv
sudo mkdir /opt/kolla
sudo chown $USER:$USER /opt/kolla
cd /opt/kolla
python3 -m venv venv
source venv/bin/activate
pip install -U pip
pip install -U 'ansible<2.9'
pip install kolla-ansible

# General Ansible config
sudo mkdir -p /etc/ansible
sudo chown $USER:$USER /etc/ansible
cat >>/etc/ansible/ansible.cfg <<__EOF__
[defaults]
host_key_checking=False
pipelining=True
forks=100
interpreter_python=/usr/bin/python3
__EOF__

# Openstack Ansible config:
#wget https://networkgenomics.com/try/mitogen-0.2.9.tar.gz
#tar -xvf mitogen-0.2.9.tar.gz -C /opt/kolla/
pip3 install -U https://github.com/dw/mitogen/archive/a60c6c1.zip


# Kolla specific Ansible configs
cat >>/opt/kolla/ansible.cfg <<__EOF__
[defaults]
strategy_plugins = /opt/kolla/venv/lib/python3.6/site-packages/ansible_mitogen/plugins/strategy
strategy = mitogen_linear
host_key_checking=False
pipelining=True
forks=100
interpreter_python=/usr/bin/python3
ansible_python_interpreter=/usr/bin/python3
__EOF__

# Fix: python_apt broken/old on pypi
git clone https://salsa.debian.org/apt-team/python-apt/ -b 1.8.6
cd python-apt
sudo apt-get -y install libapt-pkg-dev
python setup.py install
cd ..

# Configure kolla
sudo mkdir -p /etc/kolla
sudo chown $USER:$USER /etc/kolla
cp -r /opt/kolla/venv/share/kolla-ansible/etc_examples/kolla/* /etc/kolla
cp /opt/kolla/venv/share/kolla-ansible/ansible/inventory/* .

# Add nova config path
mkdir -p /etc/kolla/config/nova
cat >> /etc/kolla/config/nova/nova.conf <<__EOF__
[DEFAULT]
cpu_allocation_ratio = 16.0
ram_allocation_ratio = 1.5
reserved_host_memory_mb = 10240
allow_resize_to_same_host=True
scheduler_default_filters=AllHostsFilter
__EOF__
