# Cloudflare Tunnel

Cloudflare Tunnel makes the applications in the local cluster available on the
internet without opening an inbound port on the router. The `cloudflared` pod
creates an outbound connection to Cloudflare and forwards public requests to
Traefik inside the cluster.

```text
browser -> Cloudflare -> cloudflared -> Traefik -> application
```

## 1. Tunnel setup

The tunnel itself is created in Cloudflare and is not stored in this
repository. Create a remotely managed tunnel for the platform and add the
following published application route:

```text
Hostname: gym-tracker.tech
Service:  http://traefik.kube-system.svc.cluster.local:80
```

Cloudflare manages the public DNS record and TLS connection from the browser.
The tunnel forwards the original hostname to Traefik, which selects the
matching Ingress and application Service. The Traefik configuration is
described in [Traefik](traefik.md).

No public hostname for an application is needed separately while all
applications share `gym-tracker.tech` and use different paths.

## 2. Tunnel token

Cloudflare provides a token when the tunnel is created. The token allows a
connector to join the tunnel and must not be committed to Git or pasted into a
shell command.

Save it locally:

```zsh
mkdir -p "$HOME/.config/local-platform/cloudflare"
chmod 700 "$HOME/.config/local-platform/cloudflare"

read -r -s 'task_cloudflare_token?Cloudflare tunnel token: '
printf '\n'
(umask 077; printf '%s' "$task_cloudflare_token" > \
  "$HOME/.config/local-platform/cloudflare/tunnel-token")
unset task_cloudflare_token
```

After the Argo CD bootstrap has created the `cloudflare` namespace, create the
secret expected by the Deployment:

```bash
kubectl --context k3d-local-platform -n cloudflare \
  create secret generic cloudflared-token \
  --from-file=token="$HOME/.config/local-platform/cloudflare/tunnel-token" \
  --dry-run=client -o yaml |
kubectl --context k3d-local-platform -n cloudflare apply -f -
```

The Deployment may be unhealthy until this secret exists. Kubernetes will
start the pod after the secret is created.

## 3. Cloudflared deployment

The resources under `platform-cloudflare` create the `cloudflare` namespace
and one `cloudflared` replica. The Argo CD Application deploys these resources
and enables self-healing, while automatic pruning remains disabled.

The container runs a remotely managed tunnel using `TUNNEL_TOKEN` from the
Kubernetes secret. It makes outbound connections only, so it does not need a
Kubernetes Service or an Ingress of its own.

Automatic container updates are disabled with `--no-autoupdate`. The image
version is changed in Git instead. Port `2000` provides the readiness endpoint
and metrics used to check the connector.

The container also runs as a non-root user, has a read-only filesystem and
drops Linux capabilities because it does not need access to the Kubernetes API
or host network.

## 4. Public application routes

Cloudflare only brings traffic into the cluster. The public host, path, rate
limits and target Service are still defined by each application's Traefik
Ingress resources.

The current public paths are:

- `https://gym-tracker.tech/auth`;
- `https://gym-tracker.tech/personal-platform`.

When adding another path on the same hostname, only a new Traefik route is
needed. When adding a different hostname, add it to the Cloudflare Tunnel as
well as to the application's Ingress.

## 5. Check the tunnel

Check the Argo CD Application and wait for the Deployment:

```bash
kubectl --context k3d-local-platform -n argocd \
  get application platform-cloudflare

kubectl --context k3d-local-platform -n cloudflare \
  rollout status deployment/cloudflared
```

Check that the token secret exists without printing its value:

```bash
kubectl --context k3d-local-platform -n cloudflare \
  get secret cloudflared-token
```

View connector and tunnel errors:

```bash
kubectl --context k3d-local-platform -n cloudflare \
  logs deployment/cloudflared
```

Cloudflare also shows the connector status for the tunnel. If the connector is
healthy but a route returns an error, check the Traefik Ingress, Middleware and
application pod.

## 6. Rotate the token

Select **Rotate token** for the tunnel in Cloudflare and copy the new token from
the connector command. Overwrite the local token file and apply the secret
again with the command from section 2.

The old token cannot create new connections after it is rotated, but an
existing connector remains active until it restarts. Because the token is
loaded as an environment variable, restart the Deployment afterward:

```bash
kubectl --context k3d-local-platform -n cloudflare \
  rollout restart deployment/cloudflared

kubectl --context k3d-local-platform -n cloudflare \
  rollout status deployment/cloudflared
```

This platform currently has one `cloudflared` replica, so the restart can cause
a short interruption. If the previous token was compromised, also disconnect
the existing tunnel connections from Cloudflare after rotating it.

OBS: The Kubernetes secret disappears when the k3d cluster is deleted. The
local token file remains available and can be used to recreate it.
