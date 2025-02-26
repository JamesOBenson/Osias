#!/usr/bin/python3

import argparse
import utils
import setup_configs
import maas_virtual
import maas_base
import ast
from osias_variables import *
from ipaddress import IPv4Network


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-i",
        "--sshkey",
        type=str,
        required=False,
        help="The path to the SSH key used to access the target node",
    )
    parser.add_argument(
        "-c",
        "--command",
        type=str,
        required=False,
        help="The command that will be run on the target node",
    )
    parser.add_argument(
        "-n",
        "--target_node",
        type=str,
        required=False,
        help="The target node IP address that will the specified script will run on",
    )
    parser.add_argument(
        "--config",
        type=str,
        required=False,
        help="The config file in toml format defining all servers and their IPs",
    )
    parser.add_argument(
        "--file_path",
        type=str,
        required=False,
        help="path of files to be copied from the deployment node",
    )
    parser.add_argument(
        "--MAAS_URL",
        type=str,
        required=False,
        help="The URL of the remote API, e.g. http://example.com/MAAS/ or "
        + "http://example.com/MAAS/api/2.0/ if you wish to specify the "
        + "API version.",
    )
    parser.add_argument(
        "--MAAS_API_KEY",
        type=str,
        required=False,
        help="The credentials, also known as the API key, for the remote "
        + "MAAS server. These can be found in the user preferences page "
        + "in the web UI; they take the form of a long random-looking "
        + "string composed of three parts, separated by colons.",
    )
    parser.add_argument(
        "--DOCKER_REGISTRY_PASSWORD",
        type=str,
        required=False,
        help="The password for the docker registry.",
    )
    parser.add_argument(
        "--VM_PUBLIC_CIDR",
        type=str,
        required=False,
        help="The smaller test subnet of public IP's that are reserved for the VM's and openstack deployment.",
    )
    parser.add_argument(
        "--VM_PROFILE",
        type=str,
        required=False,
        help="Dictionary of values containing the following which over-write the defaults listed in osias_variables.py",
    )
    parser.add_argument(
        "operation",
        type=str,
        choices=[
            "cleanup",
            "reboot_servers",
            "reprovision_servers",
            "create_virtual_servers",
            "bootstrap_networking",
            "bootstrap_openstack",
            "bootstrap_ceph",
            "pre_deploy_openstack",
            "deploy_ceph",
            "deploy_openstack",
            "post_deploy_openstack",
            "test_setup",
            "test_refstack",
            "test_stress",
            "delete_virtual_machines",
            "complete_openstack_install",
            "copy_files",
            "run_command",
        ],
        help="Operation to perform",
    )

    args = parser.parse_args()
    print(args)

    return args


def bootstrap_networking(servers_public_ip):
    utils.run_script_on_server("bootstrap_networking.sh", servers_public_ip)


def cleanup(servers_public_ip, storage_nodes_public_ip):
    utils.run_script_on_server(
        "cleanup.sh", servers_public_ip[0], args=["cleanup_master"]
    )
    utils.run_script_on_server(
        "cleanup.sh", storage_nodes_public_ip, args=["cleanup_storage_nodes"]
    )
    utils.run_script_on_server("cleanup.sh", servers_public_ip, args=["cleanup_nodes"])
    utils.run_cmd_on_server("sudo -s rm -fr /home/ubuntu/*", servers_public_ip)


def bootstrap_openstack(
    servers_public_ip,
    controller_nodes,
    network_nodes,
    storage_nodes_private_ip,
    compute_nodes,
    monitoring_nodes,
    docker_registry,
    docker_registry_username,
    docker_registry_password,
    vm_cidr,
):
    utils.copy_file_on_server("requirements.txt", servers_public_ip[0])
    utils.run_script_on_server("bootstrap_kolla.sh", servers_public_ip[0])
    setup_configs.setup_kolla_configs(
        controller_nodes,
        network_nodes,
        storage_nodes_private_ip,
        compute_nodes,
        monitoring_nodes,
        servers_public_ip,
        docker_registry,
        docker_registry_username,
        vm_cidr,
    )
    utils.run_script_on_server("configure_kolla.sh", servers_public_ip[0])
    ssh_priv_key, ssh_public_key = utils.create_new_ssh_key()
    utils.run_script_on_server(
        "bootstrap_ssh_access.sh",
        servers_public_ip,
        args=[ssh_priv_key, ssh_public_key],
    )
    if docker_registry_password:
        utils.run_script_on_server(
            "bootstrap_openstack.sh",
            servers_public_ip[0],
            args=[docker_registry_password],
        )
    else:
        utils.run_script_on_server("bootstrap_openstack.sh", servers_public_ip[0])
    setup_configs.setup_nova_conf(compute_nodes)
    utils.run_script_on_server("setup_nova_conf.sh", servers_public_ip[0])


def bootstrap_ceph(servers_public_ip, storage_nodes_data_ip):
    utils.run_script_on_server(
        "bootstrap_ceph.sh", servers_public_ip[0], args=[storage_nodes_data_ip[0]]
    )


def deploy_ceph(servers_public_ip, storage_nodes_data_ip):
    setup_configs.setup_ceph_node_permisions(storage_nodes_data_ip)
    utils.run_script_on_server(
        "configure_ceph_node_permissions.sh", servers_public_ip[0]
    )
    utils.run_script_on_server("deploy_ceph.sh", servers_public_ip[0])


def reprovision_servers(maas_url, maas_api_key, servers_public_ip):
    utils.run_cmd("maas login admin {} {}".format(maas_url, maas_api_key))
    servers = maas_base.maas_base()
    servers.set_public_ip(servers_public_ip)
    servers.deploy()


def create_virtual_servers(maas_url, maas_api_key, vm_profile, ceph_enabled=False):
    utils.run_cmd(f"maas login admin {maas_url} {maas_api_key}")
    servers = maas_virtual.maas_virtual()
    if isinstance(ceph_enabled, str):
        if ast.literal_eval(ceph_enabled):
            CEPH = "true"
        else:
            CEPH = "false"
    else:
        CEPH = "false"
    server_list = []
    servers_public_ip = []
    public_IP_pool = [str(ip) for ip in IPv4Network(vm_profile["vm_deployment_cidr"])]
    public_ips = {}
    # Keeps the limit of VM's created from 1-7 VM's.
    num_Servers = sorted([1, int(vm_profile["Number_of_VM_Servers"]), 7])[1]
    for i in range(num_Servers):
        public_VM_IP = public_IP_pool.pop(0)
        servers_public_ip.append(public_VM_IP)
        vm_profile["Public_VM_IP"] = public_VM_IP
        server_id = servers.create_virtual_machine(vm_profile)
        server_list.append(server_id)
        public_ips[server_id] = {"public": public_VM_IP}
    servers.set_public_ip(public_ips=servers_public_ip)
    servers.deploy(server_list)
    machines_info = servers.get_machines_info()
    internal_ips = servers.get_machines_interface_ip(
        server_list, machines_info, "eno1", "internal"
    )
    data_ips = servers.get_machines_interface_ip(
        server_list, machines_info, "eno3", "data"
    )
    temp_dict = utils.merge_nested_dictionaries(public_ips, internal_ips)
    final_dict = utils.merge_nested_dictionaries(temp_dict, data_ips)
    VIP_IP = str(list(IPv4Network(vm_profile["vm_deployment_cidr"]))[-1])
    POOL_START = str(list(IPv4Network(vm_profile["vm_deployment_cidr"]))[num_Servers])
    POOL_END = list(IPv4Network(vm_profile["vm_deployment_cidr"]))[-2]
    optional_vars = f"""DOCKER_REGISTRY = "{DOCKER_REGISTRY_IP}"
    DOCKER_REGISTRY_USERNAME = "{DOCKER_REGISTRY_USERNAME}"
    VM_CIDR = "{vm_profile['vm_deployment_cidr']}"
    VIP_IP = "{VIP_IP}"
    POOL_START = "{POOL_START}"
    POOL_END = "{POOL_END}"
    DNS_IP = "{vm_profile['DNS_IP']}"
    CEPH = {CEPH}
    """
    multinode = utils.create_multinode(final_dict, optional_vars)
    print(f"Generated multinode is: {multinode}")
    f = open("MULTINODE.env", "w")
    f.write(f"{multinode}")
    f.close()


def delete_virtual_machines(servers_public_ip, maas_url, maas_api_key):
    utils.run_cmd("maas login admin {} {}".format(maas_url, maas_api_key))
    servers = maas_virtual.maas_virtual()
    servers.set_public_ip(servers_public_ip)
    servers.delete_virtual_machines()


def post_deploy_openstack(servers_public_ip, pool_start_ip, pool_end_ip, dns_ip):
    if not utils.is_vm_pool_enabled(pool_start_ip, pool_end_ip):
        utils.run_script_on_server(
            "post_deploy_openstack.sh",
            servers_public_ip[0],
            args=[dns_ip],
        )
    else:
        utils.run_script_on_server(
            "post_deploy_openstack.sh",
            servers_public_ip[0],
            args=[dns_ip, pool_start_ip, pool_end_ip],
        )


def main():
    args = parse_args()

    if args.config:
        config = utils.parser(args.config)
        controller_nodes = config.get_server_ips(node_type="control", ip_type="private")
        network_nodes = config.get_server_ips(node_type="network", ip_type="private")
        if config.bool_check_ips_exist(node_type="storage", ip_type="data"):
            storage_nodes_data_ip = config.get_server_ips(
                node_type="storage", ip_type="data"
            )
        else:
            storage_nodes_data_ip = config.get_server_ips(
                node_type="storage", ip_type="private"
            )
        storage_nodes_private_ip = config.get_server_ips(
            node_type="storage", ip_type="private"
        )
        storage_nodes_public_ip = config.get_server_ips(
            node_type="storage", ip_type="public"
        )
        compute_nodes = config.get_server_ips(node_type="compute", ip_type="private")
        monitoring_nodes = config.get_server_ips(node_type="monitor", ip_type="private")
        servers_public_ip = config.get_all_public_ips()
        ceph_enabled = config.get_variables(variable="CEPH")
        docker_registry = config.get_variables(variable="DOCKER_REGISTRY")
        docker_registry_username = config.get_variables(
            variable="DOCKER_REGISTRY_USERNAME"
        )
        VM_CIDR = config.get_variables(variable="VM_CIDR")
        POOL_START_IP = config.get_variables(variable="POOL_START")
        POOL_END_IP = config.get_variables(variable="POOL_END")
        DNS_IP = config.get_variables(variable="DNS_IP")

        if args.operation != "create_virtual_servers":
            if not VM_CIDR or not POOL_START_IP or not POOL_END_IP or not DNS_IP:
                raise Exception(
                    "ERROR: Mandatory parms in the Multinode file are missing.\n"
                    + "Please ensure that the following parms are set to a valid value:\n"
                    + "[VM_CIDR] and [POOL_START_IP] and [POOL_END_IP] and [DNS_IP]."
                )

        cmd = "".join((args.operation, ".sh"))

        if args.operation == "cleanup":
            cleanup(servers_public_ip, storage_nodes_public_ip)
        elif args.operation == "reprovision_servers":
            if args.MAAS_URL and args.MAAS_API_KEY:
                reprovision_servers(args.MAAS_URL, args.MAAS_API_KEY, servers_public_ip)
            else:
                raise Exception(
                    "ERROR: MAAS_API_KEY and/or MAAS_URL argument not specified.\n"
                    + "If operation is specified as [reprovision_servers] then "
                    + "the optional arguments [--MAAS_URL] and [--MAAS_API_KEY] have to be set."
                )
        elif args.operation == "bootstrap_networking":
            utils.copy_file_on_server("base_config.sh", servers_public_ip)
            bootstrap_networking(servers_public_ip)
        elif args.operation == "bootstrap_ceph":
            if ceph_enabled:
                bootstrap_ceph(servers_public_ip, storage_nodes_data_ip)
            else:
                print("'Bootstrap_Ceph' is skipped due to CEPH being DISABLED.")
        elif args.operation == "bootstrap_openstack":
            bootstrap_openstack(
                servers_public_ip,
                controller_nodes,
                network_nodes,
                storage_nodes_private_ip,
                compute_nodes,
                monitoring_nodes,
                docker_registry,
                docker_registry_username,
                args.DOCKER_REGISTRY_PASSWORD,
                VM_CIDR,
            )
        elif args.operation == "deploy_ceph":
            if ceph_enabled:
                deploy_ceph(servers_public_ip, storage_nodes_data_ip)
            else:
                print("'Deploy_Ceph' is skipped due to CEPH being DISABLED.")
        elif args.operation == "reboot_servers":
            utils.run_cmd_on_server("sudo -s shutdown -r 1", servers_public_ip)
            utils.run_cmd_on_server("echo Server is UP!", servers_public_ip)
        elif args.operation == "post_deploy_openstack":
            post_deploy_openstack(servers_public_ip, POOL_START_IP, POOL_END_IP, DNS_IP)
        elif args.operation == "test_refstack":
            if utils.is_vm_pool_enabled(POOL_START_IP, POOL_END_IP):
                utils.run_script_on_server(
                    "test_refstack.sh",
                    servers_public_ip[0],
                    args=[DNS_IP, "VM_POOL_ENABLED"],
                )
            else:
                utils.run_script_on_server(
                    "test_refstack.sh",
                    servers_public_ip[0],
                    args=[DNS_IP, "VM_POOL_DISABLED"],
                )
        elif args.operation in [
            "pre_deploy_openstack",
            "deploy_openstack",
            "test_setup",
            "test_stress",
        ]:
            utils.run_script_on_server(cmd, servers_public_ip[0])
        elif args.operation == "delete_virtual_machines":
            if args.MAAS_URL and args.MAAS_API_KEY:
                delete_virtual_machines(
                    servers_public_ip, args.MAAS_URL, args.MAAS_API_KEY
                )
            else:
                raise Exception(
                    "ERROR: MAAS_API_KEY and/or MAAS_URL argument not specified.\n"
                    + "If operation is specified as [delete_virtual_machines] then "
                    + "the optional arguments [--MAAS_URL] and [--MAAS_API_KEY] have to be set."
                )
        elif args.operation == "copy_files":
            if args.file_path:
                client = utils.create_ssh_client(servers_public_ip[0])
                client.scp_from(args.file_path)
            else:
                raise Exception(
                    "ERROR: file_path argument not specified.\n"
                    + "If operation is specified as [copy_files] then the "
                    + "optional arguments [--file_path] has to be set."
                )
        elif args.operation == "complete_openstack_install":
            utils.run_script_on_server("bootstrap_networking.sh", servers_public_ip)
            bootstrap_openstack(
                servers_public_ip,
                controller_nodes,
                network_nodes,
                storage_nodes_private_ip,
                compute_nodes,
                monitoring_nodes,
                docker_registry,
                docker_registry_username,
                args.DOCKER_REGISTRY_PASSWORD,
                VM_CIDR,
            )
            if ceph_enabled:
                bootstrap_ceph(servers_public_ip, storage_nodes_data_ip)
                deploy_ceph(servers_public_ip, storage_nodes_data_ip)
            utils.run_script_on_server("pre_deploy_openstack.sh", servers_public_ip[0])
            utils.run_script_on_server("deploy_openstack.sh", servers_public_ip[0])
            utils.run_script_on_server(
                "post_deploy_openstack.sh",
                servers_public_ip[0],
                args=[DNS_IP, POOL_START_IP, POOL_END_IP],
            )
            utils.run_script_on_server("test_setup.sh", servers_public_ip[0])
            utils.run_script_on_server("test_refstack.sh", servers_public_ip[0])
    elif args.operation == "create_virtual_servers":
        if args.MAAS_URL and args.MAAS_API_KEY:
            VM_PROFILE = utils.merge_dictionaries(
                VM_Profile, ast.literal_eval(args.VM_PROFILE)
            )
            ceph_enabled = VM_PROFILE.get("CEPH")
            required_keys = ["vm_deployment_cidr"]
            utils.check_required_keys_not_null(required_keys, VM_PROFILE)
            create_virtual_servers(
                args.MAAS_URL, args.MAAS_API_KEY, VM_PROFILE, ceph_enabled
            )
        else:
            raise Exception(
                "ERROR: MAAS_API_KEY and/or MAAS_URL argument not specified.\n"
                + "If operation is specified as [create_virtual_servers] then "
                + "the optional arguments [--MAAS_URL] and [--MAAS_API_KEY] have to be set."
            )
    elif args.operation == "run_command":
        # If command is specified then only perform it
        if args.command and args.target_node:
            utils.run_cmd_on_server(args.command, args.target_node)
        else:
            raise Exception(
                "ERROR: command and target_node arguments not specified.\n"
                + "If operation is specified as [run_command] then the "
                + "optional arguments [--command] and [--target_node] have to be set."
            )


if __name__ == "__main__":
    main()
