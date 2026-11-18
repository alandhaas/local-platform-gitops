#!/usr/bin/env python3
"""Build Ansible inventory from the Multipass Terraform outputs."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


TERRAFORM_DIR = Path(__file__).resolve().parents[2] / "terraform" / "multipass"


def terraform_nodes() -> dict[str, dict[str, object]]:
    result = subprocess.run(
        ["terraform", f"-chdir={TERRAFORM_DIR}", "output", "-json", "nodes"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def inventory() -> dict[str, object]:
    nodes = terraform_nodes()
    private_key = os.environ.get(
        "ANSIBLE_SSH_PRIVATE_KEY_FILE", "~/.ssh/id_ed25519"
    )
    groups: dict[str, object] = {
        "k3s_cluster": {"children": ["k3s_server", "k3s_agents"]},
        "k3s_server": {"hosts": []},
        "k3s_agents": {"hosts": []},
        "_meta": {"hostvars": {}},
    }

    hostvars = groups["_meta"]["hostvars"]
    for name, node in sorted(nodes.items()):
        addresses = node.get("ipv4", [])
        if not addresses:
            raise RuntimeError(f"Terraform has no IPv4 address for {name}")
        role = node["role"]
        group = "k3s_server" if role == "server" else "k3s_agents"
        groups[group]["hosts"].append(name)
        hostvars[name] = {
            "ansible_host": addresses[0],
            "ansible_user": "ubuntu",
            "ansible_ssh_private_key_file": private_key,
            "k3s_role": role,
        }

    return groups


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] == "--list":
        print(json.dumps(inventory()))
    elif len(sys.argv) == 3 and sys.argv[1] == "--host":
        print("{}")
    else:
        raise SystemExit("usage: terraform.py --list | --host HOST")


if __name__ == "__main__":
    main()
