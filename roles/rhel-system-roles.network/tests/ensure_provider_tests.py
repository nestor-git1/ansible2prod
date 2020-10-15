#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
""" Check that there is a playbook to run all role tests with both providers
"""
# vim: fileencoding=utf8

import glob
import os
import sys


GET_NM_VERSION = """
    - block:
        - name: Install NetworkManager
          package:
            name: NetworkManager
            state: present
        - name: Get NetworkManager version
          command: rpm -q --qf "%{version}" NetworkManager
          args:
            warn: false
          register: NetworkManager_version
          when: true
      when:
        - ansible_distribution_major_version != '6'
"""

MINIMUM_NM_VERSION_CHECK = """
    - NetworkManager_version.stdout is version({minimum_nm_version}, '>=')
"""

RUN_PLAYBOOK_WITH_NM = """# SPDX-License-Identifier: BSD-3-Clause
# This file was generated by ensure_provider_tests.py
---
# set network provider and gather facts
- hosts: all
  name: Run playbook '{test_playbook}' with nm as provider
  tasks:
    - name: Set network provider to 'nm'
      set_fact:
        network_provider: nm
{get_nm_version}

# workaround for: https://github.com/ansible/ansible/issues/27973
# There is no way in Ansible to abort a playbook hosts with specific OS
# releases Therefore we include the playbook with the tests only if the hosts
# would support it.
# The test requires or should run with NetworkManager, therefore it cannot run
# on RHEL/CentOS 6
- import_playbook: {test_playbook}
  when:
    - ansible_distribution_major_version != '6'
{minimum_nm_version_check}"""

MINIMUM_VERSION = "minimum_version"
NM_ONLY_TESTS = {
    "playbooks/tests_ethtool_features.yml": {
        MINIMUM_VERSION: "'1.20.0'",
        "comment": "# NetworkManager 1.20.0 introduced ethtool settings support",
    },
    "playbooks/tests_reapply.yml": {},
    "playbooks/tests_states.yml": {},
    "playbooks/tests_802_1x.yml": {},
}

IGNORE = [
    # checked by tests_regression_nm.yml
    "playbooks/tests_checkpoint_cleanup.yml",
]

RUN_PLAYBOOK_WITH_INITSCRIPTS = """# SPDX-License-Identifier: BSD-3-Clause
# This file was generated by ensure_provider_tests.py
---
- hosts: all
  name: Run playbook '{test_playbook}' with initscripts as provider
  tasks:
    - name: Set network provider to 'initscripts'
      set_fact:
        network_provider: initscripts

- import_playbook: {test_playbook}
"""


def create_nm_playbook(test_playbook):
    fileroot = os.path.splitext(os.path.basename(test_playbook))[0]
    nm_testfile = fileroot + "_nm.yml"

    minimum_nm_version = NM_ONLY_TESTS.get(test_playbook, {}).get(MINIMUM_VERSION)
    nm_version_check = ""
    if minimum_nm_version:
        nm_version_check = MINIMUM_NM_VERSION_CHECK.format(
            minimum_nm_version=minimum_nm_version
        )

    nominal_nm_testfile_data = RUN_PLAYBOOK_WITH_NM.format(
        test_playbook=test_playbook,
        get_nm_version=minimum_nm_version and GET_NM_VERSION or "",
        minimum_nm_version_check=nm_version_check,
    )

    return nm_testfile, nominal_nm_testfile_data


def create_initscripts_playbook(test_playbook):
    fileroot = os.path.splitext(os.path.basename(test_playbook))[0]
    init_testfile = fileroot + "_initscripts.yml"

    nominal_data = RUN_PLAYBOOK_WITH_INITSCRIPTS.format(test_playbook=test_playbook)

    return init_testfile, nominal_data


def check_playbook(generate, testfile, test_playbook, nominal_data):
    is_missing = False
    returncode = None
    if generate:
        print(testfile)
        with open(testfile, "w") as ofile:
            ofile.write(nominal_data)

    if not os.path.isfile(testfile) and not generate:
        is_missing = True
    else:
        with open(testfile) as ifile:
            testdata = ifile.read()
            if testdata != nominal_data:
                print(f"ERROR: Playbook does not match nominal value: {testfile}")
                returncode = 1

    return is_missing, returncode


def main():
    testsfiles = glob.glob("playbooks/tests_*.yml")
    missing = []
    returncode = 0

    # Generate files when specified
    generate = bool(len(sys.argv) > 1 and sys.argv[1] == "generate")

    if not testsfiles:
        print("ERROR: No tests found")
        returncode = 1

    for test_playbook in testsfiles:
        if test_playbook in IGNORE:
            continue

        nm_testfile, nominal_nm_testfile_data = create_nm_playbook(test_playbook)

        is_missing, new_returncode = check_playbook(
            generate=generate,
            testfile=nm_testfile,
            test_playbook=test_playbook,
            nominal_data=nominal_nm_testfile_data,
        )
        if is_missing:
            missing.append(test_playbook)
        if new_returncode:
            returncode = new_returncode

        if test_playbook not in NM_ONLY_TESTS:
            init_testfile, nominal_init_testfile_data = create_initscripts_playbook(
                test_playbook
            )
            is_missing, new_returncode = check_playbook(
                generate=generate,
                testfile=init_testfile,
                test_playbook=test_playbook,
                nominal_data=nominal_init_testfile_data,
            )
            if is_missing:
                missing.append(test_playbook)
            if new_returncode:
                returncode = new_returncode

    if missing:
        print("ERROR: No NM or initscripts tests found for:\n" + ", \n".join(missing))
        print("Try to generate them with '{} generate'".format(sys.argv[0]))
        returncode = 1

    return returncode


if __name__ == "__main__":
    sys.exit(main())
