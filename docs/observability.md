# Observability

The local platform uses Prometheus for metrics, Loki for logs, Grafana for
visualization and Grafana Alloy for log collection. The components are
installed from pinned Helm charts by Argo CD. Chart configuration and custom
dashboards remain in this Git repository.

```text
Kubernetes metrics -> Prometheus -----> Grafana
Kubernetes pod logs -> Alloy -> Loki --> Grafana
Kubernetes events --> Alloy -> Loki ---^
```

This configuration is intended for a single-node local development cluster.
It is not a production high-availability design.

## 1. Argo CD applications

The root application creates the `observability` namespace and four child
applications:

- `prometheus-stack` installs `kube-prometheus-stack` chart `92.21.2`;
- `loki` installs the Grafana Community Loki chart `21.0.0`;
- `alloy` installs the Grafana Alloy chart `1.15.0`;
- `observability-dashboards` installs dashboards stored in this repository.

The applications use Argo CD multiple sources. The first source is the remote
Helm chart and the source named `values` points to this repository. The
`$values/...` path loads the version-controlled configuration from
`observability/values`.

Automatic self-healing is enabled. Automatic pruning remains disabled, like
the other applications in this repository. Deleting a manifest from Git does
not automatically delete the corresponding cluster resource.

## 2. Components

### 2.1 Prometheus and Grafana

The
[`kube-prometheus-stack`](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack)
chart installs Prometheus Operator, Prometheus, kube-state-metrics,
node-exporter and Grafana. Alertmanager is disabled because this local
configuration does not define alert delivery.

Prometheus keeps metrics for seven days, with an 8 GB size limit, on a 10 GiB
persistent volume. It discovers `ServiceMonitor` and `PodMonitor` resources in
all namespaces. The scheduler, controller-manager, etcd and kube-proxy monitors
are disabled because k3s embeds these components and does not expose the
endpoints expected by the chart.

Grafana uses a 2 GiB persistent volume. The chart provisions Prometheus as the
default data source and Loki as an additional data source. It also installs the
Kubernetes dashboards supplied by `kube-prometheus-stack`.

### 2.2 Loki

Loki runs as one
[monolithic replica](https://grafana.com/docs/loki/latest/setup/install/helm/install-monolithic/),
which is the simplest deployment mode for a local cluster. It stores log
chunks and its TSDB index on a 10 GiB persistent volume, and deletes logs after
seven days. Distributed Loki components and the memcached caches are disabled
to keep resource usage appropriate for a local single-node cluster.

Loki authentication is disabled. The Loki gateway is only a ClusterIP Service
and must not be exposed publicly in this configuration.

### 2.3 Alloy

Loki does not collect logs itself. [Alloy](https://grafana.com/docs/alloy/latest/)
runs as one Deployment, discovers pods through the Kubernetes API, reads their
logs and sends them to the internal Loki gateway. It adds the `namespace`,
`pod`, `container`, `node`, `app` and `cluster` labels where those values are
available. Alloy also sends Kubernetes events to Loki.

API-based collection avoids privileged host filesystem mounts. A single Alloy
replica prevents the same pod logs from being ingested more than once.

### 2.4 Dashboards

Grafana's dashboard sidecar watches labeled ConfigMaps in the `observability`
namespace. Loki supplies its own operational dashboards. The repository adds
`Local Platform Overview`, which contains:

- total cluster CPU and memory usage;
- running pods and container restarts;
- CPU and memory usage by namespace;
- searchable pod logs filtered by namespace and pod.

The dashboard source is
`observability/dashboards/local-platform-overview.json`. Changes to the JSON
are applied by Argo CD and loaded automatically by Grafana.

## 3. Create the Grafana administrator secret

The Grafana password is deliberately not stored in Git. After the root Argo CD
application has created the `observability` namespace, create local credential
files:

```bash
mkdir -p "$HOME/.config/local-platform/grafana"
chmod 700 "$HOME/.config/local-platform/grafana"

printf 'admin' > "$HOME/.config/local-platform/grafana/admin-user"
chmod 600 "$HOME/.config/local-platform/grafana/admin-user"

python3 - <<'PY'
from pathlib import Path
import secrets

password_file = Path.home() / '.config/local-platform/grafana/admin-password'
if not password_file.exists():
    with password_file.open('x') as output:
        password_file.chmod(0o600)
        output.write(secrets.token_urlsafe(32))
else:
    password_file.chmod(0o600)
PY
```

Create or update the Secret expected by the Grafana StatefulSet:

```bash
kubectl --context k3d-local-platform -n observability \
  create secret generic grafana-admin \
  --from-file=admin-user="$HOME/.config/local-platform/grafana/admin-user" \
  --from-file=admin-password="$HOME/.config/local-platform/grafana/admin-password" \
  --dry-run=client -o yaml |
kubectl --context k3d-local-platform -n observability apply -f -
```

The credential files make it possible to recreate the Secret after rebuilding
the cluster. Changing the Secret does not automatically change a password that
Grafana has already stored in its database. Use Grafana's password change flow
for an existing installation.

## 4. Synchronize and check the stack

Commit and push the changes before expecting Argo CD to see them. If the root
application is already installed, it creates the new applications during its
next sync. Otherwise follow [Manual setup](manual-setup.md) to install Argo CD
and bootstrap the platform.

Check the Argo CD applications, pods and persistent volume claims:

```bash
make observability-status
```

All four applications should become `Synced` and `Healthy`. The Grafana pod can
remain pending until the `grafana-admin` Secret exists. Loki or Alloy may show a
temporary connection error while the applications start independently; they
retry after Loki becomes ready.

Check individual rollouts when needed:

```bash
kubectl --context k3d-local-platform -n observability \
  rollout status statefulset/prometheus-prometheus-stack-kube-prom-prometheus

kubectl --context k3d-local-platform -n observability \
  rollout status statefulset/loki

kubectl --context k3d-local-platform -n observability \
  rollout status deployment/alloy
```

## 5. Open Grafana

Start the local port-forward:

```bash
make grafana-forward
```

Keep the command running and open <http://localhost:3000>. Sign in with the
username and password stored under `$HOME/.config/local-platform/grafana`.
Open **Dashboards** and select **Local Platform Overview**.

Grafana Explore can be used for queries which are not part of a dashboard:

- select `Prometheus` and use PromQL for metrics;
- select `Loki` and use LogQL for logs;
- start with `{cluster="local-platform"}` to view all collected logs;
- use `{namespace="apps"}` to view only application logs.

## 6. Add application metrics

Cluster metrics work without application changes. For application metrics, the
application must expose a Prometheus-compatible HTTP endpoint and provide a
`ServiceMonitor`. Its `port` value refers to the name of a Service port, not a
numeric container port.

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: example-api
  namespace: apps
spec:
  selector:
    matchLabels:
      app: example-api
  endpoints:
    - port: http
      path: /metrics
      interval: 30s
```

No release label is required because this Prometheus installation selects all
`ServiceMonitor` and `PodMonitor` resources in the cluster. Verify discovered
targets in Grafana's Prometheus data source or by port-forwarding the Prometheus
Service and opening its **Status > Targets** page.

## 7. Storage and retention

The stack requests approximately 22 GiB of persistent storage:

- 10 GiB for Prometheus metrics;
- 10 GiB for Loki logs;
- 2 GiB for Grafana settings and users.

K3s local-path volumes live with the k3d cluster. Persistent volumes protect
data across pod restarts, but deleting the complete cluster can remove all
metrics, logs and Grafana state. This setup is not a backup.

Prometheus and Loki both retain data for seven days. Prometheus can remove data
earlier when it reaches its 8 GB size limit. Change retention and volume sizes
in the files under `observability/values`; increasing an existing StatefulSet
volume may require a manual PVC resize or recreation, depending on the storage
class.

## 8. Chart upgrades and validation

Chart versions are pinned in `clusters/local/applications`. Upgrade one chart
at a time, read its release notes, update the version and render it locally
before pushing:

```bash
helm template prometheus-stack kube-prometheus-stack \
  --repo https://prometheus-community.github.io/helm-charts \
  --version 92.21.2 \
  --namespace observability \
  --values observability/values/kube-prometheus-stack.yaml > /tmp/prometheus-stack.yaml

helm template loki loki \
  --repo https://grafana-community.github.io/helm-charts \
  --version 21.0.0 \
  --namespace observability \
  --values observability/values/loki.yaml > /tmp/loki.yaml

helm template alloy alloy \
  --repo https://grafana.github.io/helm-charts \
  --version 1.15.0 \
  --namespace observability \
  --values observability/values/alloy.yaml > /tmp/alloy.yaml

make validate
```

The Loki OSS chart is hosted by the Grafana Community. Do not switch its
repository URL back to Grafana's Enterprise Logs chart repository when
upgrading.

## 9. Troubleshooting

Check application sync errors first:

```bash
kubectl --context k3d-local-platform -n argocd \
  describe application prometheus-stack
kubectl --context k3d-local-platform -n argocd describe application loki
kubectl --context k3d-local-platform -n argocd describe application alloy
```

Check component logs:

```bash
kubectl --context k3d-local-platform -n observability \
  logs deployment/alloy
kubectl --context k3d-local-platform -n observability \
  logs statefulset/loki
kubectl --context k3d-local-platform -n observability \
  logs statefulset/prometheus-prometheus-stack-prometheus -c prometheus
```

If Grafana has no logs, confirm that Alloy can reach `loki-gateway` and that
Loki is ready. If Grafana has no custom dashboard, check the generated
ConfigMap and dashboard sidecar:

```bash
kubectl --context k3d-local-platform -n observability \
  get configmap local-platform-overview
kubectl --context k3d-local-platform -n observability \
  logs statefulset/prometheus-stack-grafana -c grafana-sc-dashboard
```

OBS: The Helm chart applications depend on remote chart repositories. Argo CD
needs outbound network access when it renders a chart version that is not
already cached.
