#!/bin/bash

set -euxo pipefail

sudo ceph orch host ls
sleep 30
sudo ceph orch device ls --refresh
sudo ceph orch apply osd --all-available-devices

sudo ceph osd pool create volumes
sudo rbd pool init volumes

sudo ceph osd pool create images
sudo rbd pool init images

sudo ceph osd pool create backups
sudo rbd pool init backups

sudo ceph osd pool create vms
sudo rbd pool init vms

#sudo ceph osd pool create metrics
#sudo rbd pool init metrics

# Get cinder-backup ready
sudo mkdir -p /etc/kolla/config/cinder/cinder-backup
sudo chown -R ubuntu:ubuntu /etc/kolla/config/
sudo cp /etc/ceph/ceph.conf /etc/kolla/config/cinder/cinder-backup/ceph.conf
sudo ceph auth get-or-create client.cinder-backup mon 'profile rbd' osd 'profile rbd pool=backups' mgr 'profile rbd pool=backups' > /etc/kolla/config/cinder/cinder-backup/ceph.client.cinder-backup.keyring
sudo ceph auth get-or-create client.cinder mon 'profile rbd' osd 'profile rbd pool=volumes, profile rbd pool=vms, profile rbd-read-only pool=images' mgr 'profile rbd pool=volumes, profile rbd pool=vms' > /etc/kolla/config/cinder/cinder-backup/ceph.client.cinder.keyring
sudo sed -i $'s/\t//g' /etc/kolla/config/cinder/cinder-backup/ceph.conf
sudo sed -i $'s/\t//g' /etc/kolla/config/cinder/cinder-backup/ceph.client.cinder.keyring
sudo sed -i $'s/\t//g' /etc/kolla/config/cinder/cinder-backup/ceph.client.cinder-backup.keyring

# Get cinder-volume ready
sudo mkdir -p /etc/kolla/config/cinder/cinder-volume
sudo chown -R ubuntu:ubuntu /etc/kolla/config/
sudo cp /etc/ceph/ceph.conf /etc/kolla/config/cinder/cinder-volume/ceph.conf
sudo ceph auth get-or-create client.cinder > /etc/kolla/config/cinder/cinder-volume/ceph.client.cinder.keyring
sudo sed -i $'s/\t//g' /etc/kolla/config/cinder/cinder-volume/ceph.conf
sudo sed -i $'s/\t//g' /etc/kolla/config/cinder/cinder-volume/ceph.client.cinder.keyring

# Get glance ready
sudo mkdir -p /etc/kolla/config/glance
sudo chown -R ubuntu:ubuntu /etc/kolla/config/
sudo cp /etc/ceph/ceph.conf /etc/kolla/config/glance/ceph.conf
sudo ceph auth get-or-create client.glance mon 'profile rbd' osd 'profile rbd pool=images' mgr 'profile rbd pool=images' > /etc/kolla/config/glance/ceph.client.glance.keyring
sudo sed -i $'s/\t//g' /etc/kolla/config/glance/ceph.conf
sudo sed -i $'s/\t//g' /etc/kolla/config/glance/ceph.client.glance.keyring

# Get nova ready
sudo mkdir -p /etc/kolla/config/nova
sudo chown -R ubuntu:ubuntu /etc/kolla/config/
sudo cp /etc/ceph/ceph.conf /etc/kolla/config/nova/ceph.conf
sudo ceph auth get-or-create client.cinder > /etc/kolla/config/nova/ceph.client.cinder.keyring
sudo sed -i $'s/\t//g' /etc/kolla/config/nova/ceph.conf
sudo sed -i $'s/\t//g' /etc/kolla/config/nova/ceph.client.cinder.keyring

# Get Gnocchi ready
#sudo mkdir -p  /etc/kolla/config/gnocchi
#sudo chown -R ubuntu:ubuntu /etc/kolla/config/
#sudo cp /etc/ceph/ceph.conf /etc/kolla/config/gnocchi/ceph.conf
#sudo ceph auth get-or-create client.gnocchi mon 'profile rbd' osd 'profile rbd pool=metrics' mgr 'profile rbd pool=metrics' > /etc/kolla/config/gnocchi/ceph.client.gnocchi.keyring
#sudo sed -i $'s/\t//g' /etc/kolla/config/gnocchi/ceph.conf
#sudo sed -i $'s/\t//g' /etc/kolla/config/gnocchi/ceph.client.gnocchi.keyring
