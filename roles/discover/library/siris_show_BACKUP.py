#!/usr/bin/env python

# Copyright 2016-2017 Paul Siri 
# paulsiri1@gmail.com
# 
#
# This module is intended for use only by by individuals with express written consent. Use or redistribution without consent is prohibited.
# This module contains proprietary adaptations of open-source code, and is a member of Paul Siri's "SIRIS-AUTOMATION" suite
#
# 

DOCUMENTATION = '''
---
module: siris_show
short_description: Fetches output from devices using show commands via SSH and tries (when textFSM templates are avilable) to return structured data
description:
    - This module connects to network devices using SSH and tries to
      return structured data (JSON) using TextFSM templates. If a template
      is not found, raw text is returned.  This module supports two drivers,
      namely netmiko/SSH and trigger/SSH. This also support netmiko/Telnet for IOS devices.
      Device support is dependent on netmiko and trigger.
      The ability to return structured data is dependent on TextFSM templates.
      You can still pass in optional param to the Trigger Commando init using the optional
      args param which is a dictionary. Many other params can be defined in the Trigger netdevices
      file when using trigger/SSH. Currently, this module requires passing in
      un/pwd even when a Trigger .tacacsrc file exists.
author: Paul Siri, adapted from Jason Edelman's ntc_show_command module (@jedelman8)
requirements:
    - netmiko
    - textfsm
    - terminal
    - trigger
options:
    connection:
        description:
            - connect to device using netmiko or read from offline file
              for testing.  ssh is the same as netmiko_ssh.
        required: false
        default: ssh
        choices: ['ssh', 'offline', 'netmiko_ssh', 'trigger_ssh', 'netmiko_telnet', 'telnet']
    platform:
        description:
            - Platform FROM the index file
        required: true
    template_dir:
        description:
            - path where TextFSM templates are stored. Default path is textfsm_templates
        required: false
        default: "./templates/textfsm_templates"
    index_file:
        description:
            - name of index file.  file location must be relative to
              the template_dir
        required: false
        default: index
    use_templates:
        description:
            - Boolean true/false to enable/disable use of TextFSM templates for parsing
        required: false
        default: true
        choices: ['true', 'false', 'yes', 'no']
    local_file:
        description:
            - Specify local file to save raw output to.  Useful for saving the actual output returned from device as it would appear from the terminal
        required: false
        default: null
    file:
        description:
            - If using connection=offline, this is the file (with path)
              of a file that contains raw text output, i.e.
              'show command' and then the contents of the file will
              be rendered with the the TextFSM template
        required: false
        default: null
    command:
        description:
            - Command to execute on target device
        required: true
    host:
        description:
            - IP Address or hostname (resolvable by Ansible control host)
        required: false
        default: null
    port:
        description:
            - Port to use to connect to the target device
        required: false
        default: 22 for SSH. 23 for Telnet
    delay:
        description:
            - Wait for command output from target device when using netmiko.
            - *** Extremely useful for working with devices that may be slow to return output, or for long-running commands that may take longer than expected to execute.
            - Netmiko will take the greater of the two values from "delay" and "global_delay_factor" to determine delay factor
        required: false
        default: 1
    global_delay_factor:
        description:
            - Sets delay between operations.
            - *** Extremely useful for working with devices that may be slow to return output, or for long-running commands that may take longer than expected to execute.
            - Netmiko will take the greater of the two values from "delay" and "global_delay_factor" to determine delay factor
        required: false
        default: 1
        choices: []
        aliases: []
    username:
        description:
            - Username used to login to the target device
        required: false
        default: null
    password:
        description:
            - Password used to login to the target device
        required: false
        default: null
    secret:
        description:
            - Password used to enter a privileged mode on the target device when using netmiko
        required: false
        default: null
    use_keys:
        description:
            - Boolean true/false if ssh key login should be attempted when nsing netmiko
        required: false
        default: false
    key_file:
        description:
            - Path to private ssh key used for login when using netmiko
        required: false
        default: null
'''
EXAMPLES = '''

# get vlan data using netmiko
- siris_show:
    connection=ssh
    platform=cisco_nxos
    command='show vlan'
    template_dir: '/home/ntc/ntc-templates/template'
    host={{ inventory_hostname }}
    username={{ username }}
    password={{ password }}

# get snmp community using netmiko
- siris_show:
    connection=ssh
    platform=cisco_nxos
    command='show snmp community'
    template_dir: '/home/ntc/ntc-templates/template'
    host={{ inventory_hostname }}
    username={{ username }}
    password={{ password }}
    secret:{{ secret }}

# FEEDING SINGLE DEVICE TO TRIGGER USING HOST PARAM
-  siris_show:
    connection: trigger_ssh
    host: "{{ inventory_hostname }}"
    platform: cisco_nxos
    command: 'show version'
    template_dir: '/home/ntc/ntc-templates/template'
    username: "{{ username }}"
    password: "{{ password }}"

# FEEDING SINGLE DEVICE TO TRIGGER USING LIST
-  siris_show:
    connection: trigger_ssh
    trigger_device_list:
      - "{{ inventory_hostname }}"
    platform: cisco_nxos
    command: 'show version'
    template_dir: '/home/ntc/ntc-templates/template'
    username: "{{ username }}"
    password: "{{ password }}"

# FEEDING LIST OF DEVICES TO TRIGGER
- siris_show:
    connection: trigger_ssh
    trigger_device_list:
      - n9k1
      - n9k2
    platform: cisco_nxos
    command: 'show version'
    template_dir: '/home/ntc/ntc-templates/template'
    username: "{{ username }}"
    password: "{{ password }}"
  run_once: true

# FEEDING SINGLE DEVICE TO NETIMKO
-  siris_show:
    connection: netmiko_ssh
    platform: cisco_nxos
    command: 'show version'
    template_dir: '/home/ntc/ntc-templates/template'
    host: "{{ inventory_hostname }}"
    username: "{{ username }}"
    password: "{{ password }}"

'''

import os.path
import socket

HAS_NETMIKO = True
# Make sure the system has Netmiko installed
try:
    from netmiko import ConnectHandler
except:
    HAS_NETMIKO = False

# Check whether the system has textFSM.  If true, testFSM templates will be used to parse data.
HAS_TEXTFSM = True
try:
    from clitable import CliTableError
    import clitable
except:
    try:
        from textfsm.clitable import CliTableError
        import textfsm.clitable as clitable
    except:
        HAS_TEXTFSM = False

HAS_TRIGGER = True
try:
    from trigger.cmds import Commando
except:
    HAS_TRIGGER = False


def clitable_to_dict(cli_table):
    """Converts TextFSM cli_table object to list of dictionaries
    """
    objs = []
    for row in cli_table:
        temp_dict = {}
        for index, element in enumerate(row):
            temp_dict[cli_table.header[index].lower()] = element
        objs.append(temp_dict)

    return objs


def get_structured_data(rawoutput, module):
    index_file = module.params['index_file']
    template_dir = module.params['template_dir']
    cli_table = clitable.CliTable(index_file, template_dir)

    attrs = dict(
        Command=module.params['command'],
        Platform=module.params['platform']
    )
    try:
        cli_table.ParseCmd(rawoutput, attrs)
        structured_data = clitable_to_dict(cli_table)
    except CliTableError as e:
        # Invalid or Missing template
        # module.fail_json(msg='parsing error', error=str(e))
        # rather than fail, fallback to return raw text
        structured_data = [rawoutput]

    return structured_data


def parse_raw_output(rawoutput, module):
    """Returns a dict if using netmiko and list of dicts if using trigger
    """
    structured_data_response_list = []
    structured_data = {}
    if isinstance(rawoutput, dict):
        for device, command_output in rawoutput.items():

            raw_txt = command_output[module.params['command']]
            sd = get_structured_data(raw_txt, module)
            temp = dict(device=device, response=sd)
            structured_data_response_list.append(temp)
    else:
        structured_data = get_structured_data(rawoutput, module)

    return structured_data or structured_data_response_list


def main():

    module = AnsibleModule(
        argument_spec=dict(
            connection=dict(choices=['ssh', 'offline', 'netmiko_ssh',
                            'trigger_ssh', 'netmiko_telnet', 'telnet'], default='netmiko_ssh'),
            platform=dict(required=True),
            file=dict(required=False),
            local_file=dict(required=False),
            index_file=dict(default='index'),
            template_dir=dict(default='templates/textfsm_templates'),
            use_templates=dict(required=False, default=True, type='bool'),
            trigger_device_list=dict(type='list', required=False),
            command=dict(required=False),
            commands_file=dict(required=False),
            host=dict(required=False),
            port=dict(required=False),
            delay=dict(default=1, required=False),
            global_delay_factor=dict(default=1, required=False),
            username=dict(required=False, type='str'),
            password=dict(required=False, type='str'),
            secret=dict(required=False, type='str'),
            use_keys=dict(required=False, default=False, type='bool'),
            key_file=dict(required=False, default=None),
            optional_args=dict(required=False, type='dict', default={}),
        ),
        required_together=(
            ['password', 'username'],
        ),
        mutually_exclusive=(
            ['host', 'trigger_device_list'],
        ),
        supports_check_mode=False
    )

    if not HAS_TEXTFSM:
        module.fail_json(msg='This module requires TextFSM')

    connection = module.params['connection']
    platform = module.params['platform']
    device_type = platform.split('-')[0]
    raw_file = module.params['file']
    local_file = module.params['local_file']
    index_file = module.params['index_file']
    template_dir = module.params['template_dir']
    command = module.params['command']
    commands_file = module.params['commands_file']
    username = module.params['username']
    password = module.params['password']
    secret = module.params['secret']
    use_templates = module.params['use_templates']
    use_keys = module.params['use_keys']
    key_file = module.params['key_file']
    delay = int(module.params['delay'])
    global_delay_factor = int(module.params['global_delay_factor'])
    trigger_device_list = module.params['trigger_device_list']
    optional_args = module.params['optional_args']
    host = module.params['host']

    if (connection in ['ssh', 'netmiko_ssh', 'netmiko_telnet', 'telnet'] and
            not module.params['host']):
        module.fail_json(msg='specify host when connection='
                             'ssh/netmiko_ssh/netmiko_telnet')

    if connection in ['netmiko_telnet', 'telnet'] and platform != 'cisco_ios':
        module.fail_json(msg='only cisco_ios supports '
                             'telnet/netmiko_telnet connection')

    if platform == 'cisco_ios' and connection in ['netmiko_telnet', 'telnet']:
        device_type = 'cisco_ios_telnet'

    if module.params['port']:
        port = int(module.params['port'])
    else:
        if device_type == 'cisco_ios_telnet':
            port = 23
        else:
            port = 22

    if connection != 'offline':
        if not host and not trigger_device_list:
            module.fail_json(msg='specify host or trigger_device_list based on connection')

    if connection == 'offline' and not raw_file:
        module.fail_json(msg='specifiy file if using connection=offline')

    if template_dir.endswith('/'):
        template_dir.rstrip('/')

    if use_templates:
        if not os.path.isfile(template_dir + '/' + index_file):
            module.fail_json(msg='could not find or read index file')

        if raw_file and not os.path.isfile(raw_file):
            module.fail_json(msg='could not read raw text file')

    rawtxt = ''
    if connection in ['ssh', 'netmiko_ssh', 'netmiko_telnet', 'telnet']:
        if not HAS_NETMIKO:
            module.fail_json(msg='This module requires Netmiko.')

        device = ConnectHandler(
            device_type=device_type,
            ip=host,
            port=port,
            username=username,
            password=password,
            secret=secret,
            use_keys=use_keys,
            key_file=key_file,
            global_delay_factor=global_delay_factor
        )
        if secret:
            device.enable()

# Additional section to send commands from file and record raw output (if desired)
        if command:
            rawtxt = device.send_command_timing(command, delay_factor=delay, max_loops=5000)
        else:
            try:
                if commands_file:
                    if os.path.isfile(commands_file):
                        with open(commands_file, 'r') as f:
                            rawtxt = device.send_config_set(f.readlines(), delay_factor=delay, max_loops=5000)
#                            output += device.send_config_set(f.readlines(), delay_factor=delay, max_loops=5000)
            except IOError:
                module.fail_json(msg="Unable to locate: {}".format(commands_file))


    elif connection == 'trigger_ssh':
        if not HAS_TRIGGER:
            module.fail_json(msg='This module requires trigger.')
        kwargs = {}
        kwargs['production_only'] = False
        kwargs['force_cli'] = True
        if optional_args:
            kwargs.update(optional_args)

        if host:
            commando = Commando(devices=[host], commands=[command],
                                creds=(username, password), **kwargs)
            commando.run()
            rawtxt = commando.results[host][command]
        elif trigger_device_list:
            commando = Commando(devices=trigger_device_list, commands=[command],
                                creds=(username, password), **kwargs)
            commando.run()

    elif connection == 'offline':
        with open(raw_file, 'r') as data:
            rawtxt = data.read()

    if local_file:
        with open(local_file, 'w') as f:
            f.write(rawtxt)

    results = {}
    results['response'] = []
    results['response_list'] = []

    if use_templates:
        if rawtxt:
            results['response'] = parse_raw_output(rawtxt, module)
        elif trigger_device_list:
            results['response_list'] = parse_raw_output(commando.results, module)
    elif rawtxt:
        results['response'] = [rawtxt]
    elif trigger_device_list:
        results['response'] = [commando.results]



    module.exit_json(**results)


from ansible.module_utils.basic import *
if __name__ == "__main__":
    main()