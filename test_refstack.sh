#!/bin/bash

# shellcheck source=/dev/null
source "$HOME"/base_config.sh

source /etc/kolla/admin-openrc.sh

DNS_IP=$1
VM_POOL=$2
TEMPEST_VERSION=$3
REFSTACK_TEST_VERSION=$4
PYTHON_VERSION=$5

openstack role create ResellerAdmin

openstack user create swiftop --password a_big_secret
openstack project create --enable openstack
openstack role add Member --user swiftop --project openstack
openstack role add ResellerAdmin --user swiftop --project openstack

TENANT=$(openstack project list -f value -c ID --user swiftop)
openstack network create --project "${TENANT}" mynet
openstack subnet create --project "${TENANT}" --subnet-range 192.168.100.0/24 --dns-nameserver "${DNS_IP}" --network mynet mysubnet
openstack router create --enable --project "${TENANT}" myrouter
openstack router add subnet myrouter mysubnet

git clone https://opendev.org/osf/refstack-client.git
cd refstack-client || exit
./setup_env -t "${TEMPEST_VERSION}" -p "${PYTHON_VERSION}"

cp "$HOME"/accounts.yaml "$HOME"/refstack-client/etc/accounts.yaml
cp "$HOME"/tempest.conf "$HOME"/refstack-client/etc/tempest.conf

source .venv/bin/activate
#refstack-client test -c etc/tempest.conf -v -- --regex tempest.api.identity.v3.test_tokens.TokensV3Test.test_create_token
# Fix the github error <AttributeError: module jsonschema has no attribute compat>
pip install --upgrade jsonschema 

if [[ "$VM_POOL" == "VM_POOL_DISABLED" ]]; then
    wget "https://refstack.openstack.org/v1/guidelines/${REFSTACK_TEST_VERSION}.json/tests?target=platform&type=required&alias=true&flag=false" -O /tmp/platform."${REFSTACK_TEST_VERSION}"-test-list.txt
    
    tests=(
    tempest.api.compute.images.test_images_oneserver.ImagesOneServerTestJSON
    tempest.api.compute.servers.test_create_server.ServersTestJSON
    tempest.api.compute.servers.test_create_server.ServersTestManualDisk
    tempest.api.compute.servers.test_delete_server.DeleteServersTestJSON.test_delete_active_server
    tempest.api.compute.servers.test_instance_actions.InstanceActionsTestJSON
    tempest.api.compute.servers.test_list_server_filters.ListServerFiltersTestJSON
    tempest.api.compute.servers.test_list_servers_negative.ListServersNegativeTestJSON
    tempest.api.compute.servers.test_multiple_create.MultipleCreateTestJSON.test_multiple_create
    tempest.api.compute.servers.test_server_actions.ServerActionsTestJSON
    tempest.api.compute.servers.test_servers.ServersTestJSON.test_create_specify_keypair
    tempest.api.compute.servers.test_servers.ServersTestJSON.test_create_with_existing_server_name
    tempest.api.compute.servers.test_servers.ServersTestJSON.test_update_access_server_address
    tempest.api.compute.servers.test_servers.ServersTestJSON.test_update_server_name
    tempest.api.compute.servers.test_servers_negative.ServersNegativeTestJSON    
    )
    for test in "${tests[@]}"; do
        sed -i "/$test/d" /tmp/platform."${REFSTACK_TEST_VERSION}"-test-list.txt
    done

    refstack-client test -c etc/tempest.conf -v --test-list "/tmp/platform.${REFSTACK_TEST_VERSION}-test-list.txt"
else
    refstack-client test -c etc/tempest.conf -v --test-list "https://refstack.openstack.org/api/v1/guidelines/${REFSTACK_TEST_VERSION}/tests?target=platform&type=required&alias=true&flag=false"
fi
