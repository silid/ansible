#!/usr/bin/python

# (c) 2018, NetApp, Inc
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}

DOCUMENTATION = '''
module: na_ontap_dns
short_description: NetApp ONTAP Create, delete, modify DNS servers.
extends_documentation_fragment:
    - netapp.na_ontap
version_added: '2.7'
author: NetApp Ansible Team (ng-ansibleteam@netapp.com)
description:
- Create, delete, modify DNS servers.
options:
  state:
    description:
    - Whether the DNS servers should be enabled for the given vserver.
    choices: ['present', 'absent']
    default: present

  vserver:
    description:
    - The name of the vserver to use.
    required: true

  domains:
    description:
    - List of DNS domains such as 'sales.bar.com'. The first domain is the one that the Vserver belongs to.

  nameservers:
    description:
    - List of IPv4 addresses of name servers such as '123.123.123.123'.

'''

EXAMPLES = """
    - name: create DNS
      na_ontap_dns:
        state: present
        hostname: "{{hostname}}"
        username: "{{username}}"
        password: "{{password}}"
        vserver:  "{{vservername}}"
        domains: sales.bar.com
        nameservers: 10.193.0.250,10.192.0.250
"""

RETURN = """

"""
import traceback
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_native
import ansible.module_utils.netapp as netapp_utils
from ansible.module_utils.netapp_module import NetAppModule

HAS_NETAPP_LIB = netapp_utils.has_netapp_lib()


class NetAppOntapDns(object):
    """
    Enable and Disable dns
    """

    def __init__(self):
        self.argument_spec = netapp_utils.na_ontap_host_argument_spec()
        self.argument_spec.update(dict(
            state=dict(required=False, choices=['present', 'absent'], default='present'),
            vserver=dict(required=True, type='str'),
            domains=dict(required=False, type='list'),
            nameservers=dict(required=False, type='list')
        ))

        self.module = AnsibleModule(
            argument_spec=self.argument_spec,
            supports_check_mode=True
        )

        self.na_helper = NetAppModule()
        self.parameters = self.na_helper.set_parameters(self.module.params)

        if HAS_NETAPP_LIB is False:
            self.module.fail_json(msg="the python NetApp-Lib module is required")
        else:
            self.server = netapp_utils.setup_na_ontap_zapi(module=self.module, vserver=self.parameters['vserver'])
        return

    def create_dns(self):
        """
        Create DNS server
        :return: none
        """
        dns = netapp_utils.zapi.NaElement('net-dns-create')
        nameservers = netapp_utils.zapi.NaElement('name-servers')
        domains = netapp_utils.zapi.NaElement('domains')
        for each in self.parameters['nameservers']:
            ip_address = netapp_utils.zapi.NaElement('ip-address')
            ip_address.set_content(each)
            nameservers.add_child_elem(ip_address)
        dns.add_child_elem(nameservers)
        for each in self.parameters['domains']:
            domain = netapp_utils.zapi.NaElement('string')
            domain.set_content(each)
            domains.add_child_elem(domain)
        dns.add_child_elem(domains)
        try:
            self.server.invoke_successfully(dns, True)
        except netapp_utils.zapi.NaApiError as error:
            self.module.fail_json(msg='Error creating dns: %s' %
                                  (to_native(error)),
                                  exception=traceback.format_exc())

    def destroy_dns(self):
        """
        Destroys an already created dns
        :return:
        """
        try:
            self.server.invoke_successfully(netapp_utils.zapi.NaElement('net-dns-destroy'), True)
        except netapp_utils.zapi.NaApiError as error:
            self.module.fail_json(msg='Error destroying dns %s' %
                                      (to_native(error)),
                                  exception=traceback.format_exc())

    def get_dns(self):
        dns_obj = netapp_utils.zapi.NaElement('net-dns-get')
        try:
            result = self.server.invoke_successfully(dns_obj, True)
        except netapp_utils.zapi.NaApiError as error:
            if to_native(error.code) == "15661":
                # 15661 is object not found
                return None
            else:
                self.module.fail_json(msg=to_native(
                    error), exception=traceback.format_exc())

        # read data for modify
        attrs = dict()
        attributes = result.get_child_by_name('attributes')
        dns_info = attributes.get_child_by_name('net-dns-info')
        nameservers = dns_info.get_child_by_name('name-servers')
        attrs['nameservers'] = [each.get_content() for each in nameservers.get_children()]
        domains = dns_info.get_child_by_name('domains')
        attrs['domains'] = [each.get_content() for each in domains.get_children()]
        return attrs

    def modify_dns(self, dns_attrs):
        changed = False
        dns = netapp_utils.zapi.NaElement('net-dns-modify')
        if dns_attrs['nameservers'] != self.parameters['nameservers']:
            changed = True
            nameservers = netapp_utils.zapi.NaElement('name-servers')
            for each in self.parameters['nameservers']:
                ip_address = netapp_utils.zapi.NaElement('ip-address')
                ip_address.set_content(each)
                nameservers.add_child_elem(ip_address)
            dns.add_child_elem(nameservers)
        if dns_attrs['domains'] != self.parameters['domains']:
            changed = True
            domains = netapp_utils.zapi.NaElement('domains')
            for each in self.parameters['domains']:
                domain = netapp_utils.zapi.NaElement('string')
                domain.set_content(each)
                domains.add_child_elem(domain)
            dns.add_child_elem(domains)
        if changed:
            try:
                self.server.invoke_successfully(dns, True)
            except netapp_utils.zapi.NaApiError as error:
                self.module.fail_json(msg='Error modifying dns %s' %
                                      (to_native(error)), exception=traceback.format_exc())
        return changed

    def apply(self):
        # asup logging
        netapp_utils.ems_log_event("na_ontap_dns", self.server)

        dns_attrs = self.get_dns()
        changed = False
        if self.parameters['state'] == 'present':
            if dns_attrs is not None:
                changed = self.modify_dns(dns_attrs)
            else:
                self.create_dns()
                changed = True
        else:
            if dns_attrs is not None:
                self.destroy_dns()
                changed = True
        self.module.exit_json(changed=changed)


def main():
    """
    Create, Delete, Modify DNS servers.
    """
    obj = NetAppOntapDns()
    obj.apply()


if __name__ == '__main__':
    main()
