KUBE_CONTEXT ?= k3d-local-platform
KUSTOMIZE ?= kustomize
PYTHON ?= python3

.PHONY: cluster-up cluster-status

cluster-up:
	k3d cluster create --config infrastructure/k3d.yaml

cluster-status:
	kubectl --context $(KUBE_CONTEXT) get nodes

ARGOCD_VERSION := v3.5.3

.PHONY: argocd-install argocd-status argocd-ui

argocd-install:
	kubectl --context $(KUBE_CONTEXT) create namespace argocd --dry-run=client -o yaml | kubectl --context $(KUBE_CONTEXT) apply -f -
	kubectl --context $(KUBE_CONTEXT) apply --server-side -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/$(ARGOCD_VERSION)/manifests/install.yaml
	kubectl --context $(KUBE_CONTEXT) rollout status deployment/argocd-server -n argocd --timeout=300s

argocd-status:
	kubectl --context $(KUBE_CONTEXT) get pods -n argocd

argocd-ui:
	kubectl --context $(KUBE_CONTEXT) port-forward -n argocd svc/argocd-server 8080:443

.PHONY: argocd-bootstrap gitops-status

argocd-bootstrap:
	kubectl --context $(KUBE_CONTEXT) apply -f bootstrap/argocd/root-app.yaml

gitops-status:
	kubectl --context $(KUBE_CONTEXT) get applications -n argocd
	kubectl --context $(KUBE_CONTEXT) get namespace apps

.PHONY: validate
validate:
	$(PYTHON) scripts/validate.py --kustomize $(KUSTOMIZE)
