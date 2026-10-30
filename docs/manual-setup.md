# Manual setup

This file describes the steps which are not stored in Git. Most of these steps
only need to be repeated after creating a new cluster. Passwords, tokens and
private keys should not be committed to this repository.

## 1. Cluster infrastructure

The cluster specifications are stored in `infrastructure/k3d.yaml`. The
following command uses that file to create the cluster:

```bash
make cluster-up
```

The local cluster uses k3d, which runs a single k3s server node in Docker. Check
if the node is ready with:

```bash
make cluster-status
```

OBS: There are different options for running Kubernetes locally. Since I use a
Mac, I chose k3d. On a Linux server I would probably use k3s directly.

## 2. Argo CD

Argo CD runs inside Kubernetes in its own `argocd` namespace. It watches this
repository and applies the manifests to the cluster. Install it and check its
pods with:

```bash
make argocd-install
make argocd-status
```

### 2.1 Repository access

The repository must be available on GitHub before Argo CD can use it. For a
private repository, create a fine-grained GitHub token with read access to the
repository contents. In the Argo CD UI, add the repository under **Settings >
Repositories** using its HTTPS URL, my GitHub username and the token as the
password.

This token is stored by Argo CD in the cluster and is not part of this Git
repository.

### 2.2 Argo CD UI

Start a port-forward to the Argo CD server:

```bash
make argocd-ui
```

Keep the command running and visit <https://localhost:8080>. The browser may
warn about the local certificate. The username is `admin`. On macOS, fetch the
initial password with:

```bash
kubectl --context k3d-local-platform -n argocd \
  get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -D
```

The UI is useful for viewing sync status and errors. Changes to platform
resources should normally be made in Git instead of through the UI.

### 2.3 Bootstrap the platform

After Argo CD can read the repository, create the root application:

```bash
make argocd-bootstrap
```

The root application loads `clusters/local` and creates the applications and
namespaces defined there. Check the result with:

```bash
make gitops-status
```

## 3. Image updater credentials

Argo CD Image Updater reads image digests from GHCR and writes new digests back
to this repository. It therefore needs separate read access to GHCR and write
access to GitHub.

### 3.1 GitHub deploy key

Generate a dedicated SSH key on the local machine:

```bash
ssh-keygen -t ed25519 -C platform-image-updater \
  -f "$HOME/.ssh/local-platform-image-updater"
```

Copy the public key:

```bash
cat "$HOME/.ssh/local-platform-image-updater.pub"
```

Add it to the GitHub repository under **Settings > Deploy keys** and enable
write access. Store the private key in the `argocd` namespace:

```bash
kubectl --context k3d-local-platform -n argocd \
  create secret generic platform-git-write \
  --from-file=sshPrivateKey="$HOME/.ssh/local-platform-image-updater" \
  --dry-run=client -o yaml |
kubectl --context k3d-local-platform -n argocd apply -f -
```

The public key is added to GitHub; the private key stays on the local machine
and in the cluster.

### 3.2 GHCR token

Create a classic GitHub personal access token with `read:packages`. The same
token is used for two secrets:

- `ghcr-read` in `argocd` lets Image Updater inspect image digests.
- `ghcr-pull` in `apps` lets Kubernetes pull the application images.

Run the following command and paste the token when asked:

```zsh
(
  set -e
  read -r -s 'task_ghcr_token?GHCR read token: '
  printf '\n'
  [[ -n "$task_ghcr_token" ]] || exit 1
  set -o pipefail

  for task_namespace in argocd apps; do
    task_secret=ghcr-read
    if [[ "$task_namespace" == apps ]]; then
      task_secret=ghcr-pull
    fi

    kubectl --context k3d-local-platform -n "$task_namespace" \
      create secret docker-registry "$task_secret" \
      --docker-server=ghcr.io \
      --docker-username=alandhaas \
      --docker-password="$task_ghcr_token" \
      --dry-run=client -o yaml |
    kubectl --context k3d-local-platform -n "$task_namespace" apply -f -
  done
)
```

The `apps` namespace is created during the Argo CD bootstrap, so bootstrap the
platform before running this command.