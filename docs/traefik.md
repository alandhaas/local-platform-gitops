# Traefik

Traefik is the ingress controller for the local platform. It receives HTTP
requests and forwards them to the correct Kubernetes Service based on the host
and path in an Ingress resource.

Traefik is included with k3s and runs in the `kube-system` namespace. It is
therefore not installed by one of the Argo CD applications in this repository.

## 1. Request routes

Local requests reach Traefik through a port-forward:

```text
browser -> localhost:8080 -> Traefik -> Ingress -> Service -> application pod
```

Public requests first pass through the Cloudflare Tunnel:

```text
browser -> Cloudflare -> cloudflared -> Traefik -> Ingress -> Service -> pod
```

The `cloudflared` pod is managed separately under `platform-cloudflare`. Its
tunnel token and public hostname configuration are described in
[Cloudflare Tunnel](cloudflare.md).

## 2. Local access

Forward local port `8080` to port `80` of the Traefik Service:

```bash
make traefik-forward
```

Keep the command running while using the applications. The local Ingress
resources use the hostname `local.platform.localhost`. For example:

```text
http://local.platform.localhost:8080/auth/
http://local.platform.localhost:8080/personal-platform/
```

The `.localhost` domain resolves to the local machine, so no entry in
`/etc/hosts` is needed.

## 3. Ingress resources

An Ingress connects a hostname and path to an application Service. All current
application Ingress resources select Traefik with:

```yaml
ingressClassName: traefik
```

The local routes use `local.platform.localhost`. The public routes use
`gym-tracker.tech` and the `web` entrypoint. The Service name and port in the
Ingress must match the application's Service.

The current application routes are:

- `/auth` to `auth-api` on port `8000`;
- `/personal-platform` to `personal-platform-api` on port `8080`.

When the application manifests move to Helm, the host, path, Service port and
Middleware names can become chart values instead of being repeated in separate
Ingress files.

## 4. Middlewares

Traefik Middlewares change a request before it reaches the Service. They are
custom resources using `traefik.io/v1alpha1`.

An Ingress attaches a Middleware through an annotation. A namespaced
Middleware reference follows this format:

```text
<namespace>-<middleware-name>@kubernetescrd
```

For example, the `auth-api-strip-prefix` Middleware in the `apps` namespace is
referenced as:

```text
apps-auth-api-strip-prefix@kubernetescrd
```

### 4.1 Strip prefix

The applications share one hostname and are separated by paths. A strip-prefix
Middleware removes that routing path when the application does not expect it.
For example:

```text
/auth/login -> /login
```

Whether the prefix should be removed depends on the routes implemented by the
application. Local and public Ingress resources must attach the Middleware
consistently when they should behave the same way.

### 4.2 Rate limits

The public routes use rate-limit Middlewares to reduce repeated requests. The
Auth API has separate limits for sensitive routes such as login, registration
and token refresh. Those routes use a higher router priority so they are chosen
before the general `/auth` route.

The Auth API rate limit identifies clients through the `CF-Connecting-IP`
header added by Cloudflare. The Personal Platform API currently applies one
general limit to its public route.

Middleware order matters when more than one Middleware is attached. For
example, the Personal Platform API applies its public rate limit and then
removes the path prefix.

## 5. Check Traefik

Check the Traefik pod and Service:

```bash
kubectl --context k3d-local-platform -n kube-system get pods -l app.kubernetes.io/name=traefik
kubectl --context k3d-local-platform -n kube-system get service traefik
```

Check the routes and Middlewares in the `apps` namespace:

```bash
kubectl --context k3d-local-platform -n apps get ingress
kubectl --context k3d-local-platform -n apps get middleware
```

Describe a route when its host or path does not work:

```bash
kubectl --context k3d-local-platform -n apps describe ingress auth-api
```

View the Traefik logs for routing and Middleware errors:

```bash
kubectl --context k3d-local-platform -n kube-system logs deployment/traefik
```

OBS: A working application pod is not enough for external access. The Service
selector, Service port, Ingress backend and Middleware references must also
match.
