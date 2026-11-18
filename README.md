# Local Kubernetes platform

This repository contains the GitOps configuration for a small Kubernetes
platform running locally on macOS. It uses [k3d](https://k3d.io/) to run K3s in
Docker and Argo CD to synchronize the platform with the resources stored in
Git.

## Local access

Open the Argo CD UI with:

```bash
make argocd-ui
```

While it is running, open <https://localhost:8080>. Sign in as `admin`; the
initial password command and certificate warning are described in
[Manual setup](docs/manual-setup.md#22-argo-cd-ui). Argo CD and the Traefik
port-forward both use local port `8080`, so they cannot run at the same time.

To access the auth API locally through Traefik, start the port-forward:

```bash
make traefik-forward
```

While it is running, access the auth API at
<http://local.platform.localhost:8080/auth/>. Traefik strips the `/auth`
prefix before forwarding requests to the API. Keep the terminal running and
press Ctrl-C to stop the port-forward.

Grafana is available through a separate port-forward:

```bash
make grafana-forward
```

While it is running, open <http://localhost:3000>. See the observability
documentation for the required local administrator secret.

## Documentation

- [Terraform and Multipass](infrastructure/terraform/multipass/README.md)
  describes the multi-node VM infrastructure and its learning workflow.
- [Manual setup](docs/manual-setup.md) describes the local steps and credentials
  which are not stored in Git.
- [PostgreSQL](docs/postgres.md) describes the database deployment and its
  administrator secret.
- [Applications](docs/app.md) describes the shared deployment pattern and the
  steps to follow when adding another service.
- [Helm migration](docs/helm.md) explains the shared API chart, how an
  application moves from Kustomize and how Image Updater changes with it.
- [Traefik](docs/traefik.md) describes local and public application routing.
- [Cloudflare Tunnel](docs/cloudflare.md) describes how the local platform is
  exposed publicly.
- [Observability](docs/observability.md) describes Prometheus, Grafana, Loki,
  Alloy, dashboards, storage and local access.
