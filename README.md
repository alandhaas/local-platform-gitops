# Local Kubernetes platform

This repository runs a small Kubernetes platform locally on macOS. It uses
[k3d](https://k3d.io/) to run K3s in Docker and Argo CD to reconcile the
applications declared in Git.