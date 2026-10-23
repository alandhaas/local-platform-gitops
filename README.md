# Local Kubernetes platform

This repository runs a small Kubernetes platform locally on macOS. It uses
[k3d](https://k3d.io/) to run K3s in Docker and Argo CD to reconcile the
applications declared in Git.

To access the auth API locally through Traefik, start the port-forward:

```bash
make traefik-forward
```

While it is running, access the auth API at
<http://local.platform.localhost:8080/auth/>. Traefik strips the `/auth`
prefix before forwarding requests to the API. Keep the terminal running;
press Ctrl-C to stop the port-forward. Additional APIs can use other paths
under the same hostname.