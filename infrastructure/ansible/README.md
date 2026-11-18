# K3s and Argo CD with Ansible

Terraform owns the Multipass virtual machines. Ansible connects to those
machines over SSH, installs K3s, joins the agents and installs Argo CD. The
platform team separately owns the root Application and cluster configuration.

## Prerequisites

The default Terraform configuration authorizes `~/.ssh/id_ed25519.pub` for the
Ubuntu user. Override `ansible_public_key_path` in `terraform.tfvars` and set
`ANSIBLE_SSH_PRIVATE_KEY_FILE` when using a different key.

Changing the authorized key changes cloud-init and therefore replaces existing
Multipass instances. Always review `terraform plan` before applying.

Install Ansible with Homebrew and verify the executable used by the Makefile:

```bash
brew install ansible
make ansible-check
```

## Inventory

`inventory/terraform.py` reads `terraform output -json nodes` and creates the
`k3s_server` and `k3s_agents` groups. Inspect it before running a playbook:

```bash
make ansible-inventory
```

The inventory fails when Terraform has no current node addresses. This avoids
silently configuring stale or manually created machines.

## Install K3s

```bash
make ansible-k3s
```

The playbook installs the pinned K3s version, keeps the generated agent token
out of logs, joins both workers and writes the administrator kubeconfig to
`~/.kube/k3s-multipass.yaml`.

Use it without changing the default kubectl context:

```bash
KUBECONFIG="$HOME/.kube/k3s-multipass.yaml" kubectl get nodes -o wide
```

## Bootstrap Argo CD

```bash
make ansible-argocd
```

This playbook only installs the pinned Argo CD version and waits for it to be
ready. It does not create a root Application or anything beneath `clusters/`.
The platform team supplies and applies that GitOps configuration separately.
