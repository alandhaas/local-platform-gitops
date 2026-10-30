# PostgreSQL

PostgreSQL runs inside the local Kubernetes cluster and provides databases for
the backend applications. The Kubernetes resources are stored in Git, while
the administrator password and the contents of the database are not.

## 1. Argo CD application

The `databases` namespace is created together with the other local namespaces
in `clusters/local/namespaces/apps.yaml`.

The Argo CD application is defined in
`clusters/local/applications/postgres.yaml`. It watches `apps/postgres` and
deploys those resources into the `databases` namespace. Automatic self-healing
is enabled, but automatic pruning is disabled.

## 2. PostgreSQL resources

The resources are combined by `apps/postgres/kustomization.yaml`. It also pins
the PostgreSQL container image to a digest, so a new image is only used after
the digest in Git is changed.

### 2.1 StatefulSet

PostgreSQL runs as a single-replica StatefulSet. It starts with the following
default values:

- administrator: `postgres`
- initial database: `postgres`
- data directory: `/var/lib/postgresql/18/docker`

The administrator password is read from the `postgres-admin` secret. The pod
will not start until that secret exists.

Startup and readiness probes use `pg_isready` to check PostgreSQL. The pod
requests 250 millicores and 256 MiB of memory, with a memory limit of 1 GiB.

### 2.2 Storage

The database uses a 10 GiB persistent volume claim named `postgres-data`. The
custom StorageClass uses k3s local-path storage and has a `Retain` reclaim
policy.

Argo CD is instructed not to prune or delete the StorageClass and persistent
volume claim. This protects the resources during a normal Argo CD sync, but it
does not provide a backup. Deleting the complete k3d cluster can still remove
the locally stored database data.

### 2.3 Services

The `postgres` ClusterIP Service is used by clients inside the cluster. Its
complete internal hostname is:

```text
postgres.databases.svc.cluster.local
```

The `postgres-headless` Service gives the StatefulSet its stable network
identity. Both Services use port `5432` and are only available inside the
cluster.

### 2.4 Network access

The NetworkPolicy allows PostgreSQL connections from the `apps` and
`databases` namespaces on TCP port `5432`. Pods in other namespaces cannot
connect to PostgreSQL while the cluster's network policy enforcement is active.

## 3. Administrator password

The administrator password is deliberately not stored in Git. Generate it
once and save it under the local user configuration directory:

```bash
mkdir -p "$HOME/.config/local-platform/postgres"
chmod 700 "$HOME/.config/local-platform/postgres"

python3 - <<'PY'
from pathlib import Path
import secrets

password_file = Path.home() / '.config/local-platform/postgres/admin-password'
if not password_file.exists():
    with password_file.open('x') as output:
        password_file.chmod(0o600)
        output.write(secrets.token_hex(32))
else:
    password_file.chmod(0o600)
PY
```

The script keeps an existing password. This is important because replacing the
file would not change the password in an already initialized database.

After the `databases` namespace exists, create the secret expected by the
StatefulSet:

```bash
kubectl --context k3d-local-platform -n databases \
  create secret generic postgres-admin \
  --from-file=POSTGRES_PASSWORD="$HOME/.config/local-platform/postgres/admin-password" \
  --dry-run=client -o yaml |
kubectl --context k3d-local-platform -n databases apply -f -
```

The local password file makes it possible to recreate the Kubernetes secret
after rebuilding the cluster.

OBS: Changing only the Kubernetes secret does not rotate the password of an
existing PostgreSQL installation. The password must also be changed inside
PostgreSQL.

## 4. Check PostgreSQL

Wait until the StatefulSet is ready:

```bash
kubectl --context k3d-local-platform -n databases \
  rollout status statefulset/postgres
```

View the PostgreSQL logs when the pod does not start:

```bash
kubectl --context k3d-local-platform -n databases logs postgres-0
```

Open a PostgreSQL shell inside the pod:

```bash
kubectl --context k3d-local-platform -n databases \
  exec -it postgres-0 -- psql -U postgres -d postgres
```

Application roles, databases and passwords should be documented with the
application which uses them. They are not part of the general PostgreSQL
installation.
