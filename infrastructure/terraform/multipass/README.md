# Multipass infrastructure with Terraform

This Terraform root creates the Ubuntu virtual machines that will form the
local K3s cluster. The first stage provisions one server and two agent nodes;
it deliberately does not install K3s yet.

Terraform owns the VM lifecycle. Cloud-init performs first-boot operating
system setup. Later, K3s will create the Kubernetes cluster and Argo CD will
manage the workloads from `clusters/k3s-local`.

## What this stage teaches

- `required_providers` pins the external APIs Terraform can use;
- input variables describe changeable configuration;
- a typed map models nodes with different sizes and roles;
- `for_each` creates one resource instance per map entry;
- `templatefile` renders per-node cloud-init;
- references between resources create the dependency graph;
- outputs expose useful information without shell parsing.

The Multipass provider is community maintained rather than an official
Canonical provider. This configuration uses the zone-aware provider because
Multipass 1.17 adds availability zones to its CLI output. Its version is
constrained in `versions.tf`, and `terraform init` records the selected
versions in `.terraform.lock.hcl`.

## Workflow

Initialize providers and inspect the configuration:

```bash
make terraform-init
make terraform-format
make terraform-validate
make terraform-plan
```

Review the plan before creating anything, then run:

```bash
terraform -chdir=infrastructure/terraform/multipass apply
```

Inspect the result:

```bash
terraform -chdir=infrastructure/terraform/multipass output
multipass list
multipass exec k3s-server-1 -- cloud-init status --wait
multipass exec k3s-server-1 -- cat /etc/local-platform-node
```

Terraform state and rendered cloud-init files stay local and are ignored by
Git. Commit `.terraform.lock.hcl`; it makes provider selection repeatable.

Do not manually delete a managed VM with `multipass delete`. Terraform would
still believe it owns that VM until the next refresh. Use `terraform plan` to
observe drift and Terraform commands to change managed infrastructure.
