# Applications

The backend applications follow the same deployment pattern. The Auth API is
used as the example in this document. For another application, its name, image,
port, database and migration command need to be changed.

## 1. Deployment pattern

Every backend application needs the following parts:

- a Deployment for the API container;
- a migration Job when the application owns a database;
- a ClusterIP Service;
- routing through Traefik;
- an Argo CD Application;
- an Image Updater resource.

The current resources are stored under `apps/<app-name>` and combined with
Kustomize. The repeated resources can later become Helm templates, with the
application-specific settings stored as chart values. The required Kubernetes
resources and application configuration remain the same.

The Deployment pulls from GHCR using `ghcr-pull`. It loads its database and
shared configuration through `envFrom`, and uses startup and readiness probes
to prevent traffic from reaching a container which is not ready.

The migration Job uses the same image and secrets. It runs as an Argo CD sync
hook with sync wave `-1`, before the normal application resources. Its command
remains application-specific.

The Service makes the application available inside the cluster at:

```text
<app-name>.apps.svc.cluster.local
```

Traefik connects the local and public routes to this Service. Its configuration
is described separately in [Traefik](traefik.md).

## 2. Argo CD and image updates

The Argo CD Application deploys the application into the `apps` namespace.
Self-healing is enabled and automatic pruning is disabled.

Image Updater watches the application's `main` tag in GHCR. When the digest
changes, it commits the new digest to this repository. Argo CD then deploys
that exact image.

At the moment, Image Updater writes the digest into the application's
`kustomization.yaml`. When the applications move to Helm, its write-back target
must be changed to the Helm values used for the image tag or digest.

## 3. Application database

Each application should have its own PostgreSQL role, database and Kubernetes
secret. The Auth API uses `auth_api` for both the role and database.

Open a PostgreSQL shell:

```bash
kubectl --context k3d-local-platform -n databases \
  exec -it postgres-0 -- psql -U postgres -d postgres
```

Create the role and database. The `\password` command asks for the application
password:

```sql
CREATE ROLE auth_api LOGIN;
\password auth_api
CREATE DATABASE auth_api OWNER auth_api;
REVOKE CONNECT, TEMPORARY ON DATABASE auth_api FROM PUBLIC;
\connect auth_api
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
\quit
```

Save the same password locally:

```zsh
mkdir -p "$HOME/.config/local-platform/postgres"

read -s 'AUTH_API_DB_PASSWORD?Enter the auth_api database password: '
printf '\n'

(umask 077; printf '%s' "$AUTH_API_DB_PASSWORD" > \
  "$HOME/.config/local-platform/postgres/auth-api-password")
unset AUTH_API_DB_PASSWORD
```

Create the secret expected by the Auth API Deployment and migration Job:

```bash
kubectl --context k3d-local-platform -n apps \
  create secret generic auth-api-db \
  --from-literal=PGHOST=postgres.databases.svc.cluster.local \
  --from-literal=PGPORT=5432 \
  --from-literal=PGDATABASE=auth_api \
  --from-literal=PGUSER=auth_api \
  --from-file=PGPASSWORD="$HOME/.config/local-platform/postgres/auth-api-password" \
  --dry-run=client -o yaml |
kubectl --context k3d-local-platform -n apps apply -f -
```

Repeat these steps for another application with a different role, database,
password file and Kubernetes secret name.

## 4. Shared application configuration

The Auth API creates and signs JWTs. Other APIs use the same secret to verify
those tokens. Generate the secret once and store it locally:

```bash
secret_file="$HOME/.config/local-platform/auth-api/jwt-secret"
umask 077
mkdir -p "$(dirname "$secret_file")"
if [ ! -s "$secret_file" ]; then
  openssl rand -hex 32 > "$secret_file"
fi

kubectl --context k3d-local-platform -n apps \
  create secret generic auth-api-secrets \
  --from-file="JWT_SECRET=$secret_file" \
  --dry-run=client -o yaml |
kubectl --context k3d-local-platform -n apps apply -f -
```

The browser origin is shared through the `client-url` ConfigMap. Change the URL
when the frontend is hosted somewhere else:

```bash
kubectl --context k3d-local-platform -n apps \
  create configmap client-url \
  --from-literal=CORS_ALLOWED_ORIGINS='https://personal-platform-webapp.vercel.app' \
  --dry-run=client -o yaml |
kubectl --context k3d-local-platform -n apps apply -f -
```

These values are not stored in Git and must be recreated after rebuilding the
cluster.

## 5. Check an application

Check the Argo CD Application, pods and migration Job:

```bash
kubectl --context k3d-local-platform -n argocd get application auth-api
kubectl --context k3d-local-platform -n apps get pods
kubectl --context k3d-local-platform -n apps get job auth-api-migrate
```

View application or migration logs when a deployment fails:

```bash
kubectl --context k3d-local-platform -n apps logs deployment/auth-api
kubectl --context k3d-local-platform -n apps logs job/auth-api-migrate
```

OBS: The application and migration Job will fail until their image pull and
configuration secrets exist. After creating the secrets, synchronize the Argo
CD Application again so the migration hook gets another attempt.
