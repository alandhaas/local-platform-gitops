# Helm and the application migration

Helm turns a set of Kubernetes templates into reusable releases. In this
repository, APIs share the same Deployment, Service, Ingress and Traefik
Middleware structure, so those resources belong in one chart while each API's
differences belong in a values file.

`nutrition-api` is the first application migrated from repeated Kustomize
manifests to the shared `charts/platform-api` chart. The other APIs still use
Kustomize and can move one at a time.

## How the Helm release is assembled

The important files have separate responsibilities:

- `charts/platform-api/Chart.yaml` identifies and versions the chart;
- `charts/platform-api/values.yaml` defines safe chart defaults;
- `charts/platform-api/templates/` contains the reusable Kubernetes resources;
- `apps/nutrition-api/values.yaml` contains the application-specific image,
  port, secrets, routes, probes and resource limits;
- `clusters/local/applications/nutrition-api.yaml` tells Argo CD to render the
  chart with that values file.

The Argo CD Application uses multiple sources. Its first source is the chart.
The second source has `ref: values`, which makes the values repository
available as `$values`. Therefore this entry:

```yaml
valueFiles:
  - $values/apps/nutrition-api/values.yaml
```

means: render the shared chart using the committed values for `nutrition-api`.
`releaseName` and `fullnameOverride` keep the generated resource names stable
during the migration.

## Migration pattern

Migrate an application in this order:

1. Compare its existing manifests with the resources supported by the chart.
2. Add every application-specific setting to `apps/<name>/values.yaml`.
3. Render the chart locally and compare its resource names, selectors, ports,
   environment sources, probes, routes and annotations with the old output.
4. Change the Argo CD Application from a Kustomize path to the chart and values
   sources.
5. Change Image Updater from a Kustomize target to the Helm values file.
6. Remove the old manifests only after the rendered chart covers them.

Render and validate before committing:

```bash
helm lint charts/platform-api --values apps/nutrition-api/values.yaml
helm template nutrition-api charts/platform-api \
  --namespace apps \
  --values apps/nutrition-api/values.yaml
make validate
```

Rendering is the key learning step: Helm does not apply resources here. It
produces ordinary Kubernetes YAML, which Argo CD compares and synchronizes.

## Image updates after migration

Image Updater no longer edits the `images` block in a `kustomization.yaml`.
For a Helm application it writes the digest to the values file:

```yaml
writeBackTarget: helmvalues:/apps/nutrition-api/values.yaml
```

The manifest target maps the discovered image to `image.repository` and
`image.tag`. Argo CD then sees the Git commit, renders the chart again and
deploys the pinned digest.

## Migration Jobs are a separate concern

Moving manifests from Kustomize to Helm is a configuration migration. A
database migration Job is a workload that must still be represented by the
chart when an API owns a database. The shared chart does not currently include
a migration Job, so an application that needs one must not be migrated until
the chart supports its command, secrets and Argo CD hook annotations.

This distinction prevents a successful Helm render from accidentally removing
the database migration step.

