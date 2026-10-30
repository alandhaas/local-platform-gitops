# Local Kubernetes platform

This repository contains the GitOps configuration for a small Kubernetes
platform running locally on macOS. It uses [k3d](https://k3d.io/) to run K3s in
Docker and Argo CD to synchronize the platform with the resources stored in
Git.

## Local access

To access the auth API locally through Traefik, start the port-forward:

```bash
make traefik-forward
```

While it is running, access the auth API at
<http://local.platform.localhost:8080/auth/>. Traefik strips the `/auth`
prefix before forwarding requests to the API. Keep the terminal running and
press Ctrl-C to stop the port-forward.

## Documentation

- [Manual setup](docs/manual-setup.md) describes the local steps and credentials
  which are not stored in Git.
- [PostgreSQL](docs/postgres.md) describes the database deployment and its
  administrator secret.
- [Applications](docs/app.md) describes the shared deployment pattern and the
  steps to follow when adding another service.
- [Traefik](docs/traefik.md) describes local and public application routing.
- [Cloudflare Tunnel](docs/cloudflare.md) describes how the local platform is
  exposed publicly.
