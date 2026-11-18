KUBE_CONTEXT ?= k3d-local-platform
PYTHON ?= python3
TERRAFORM_DIR ?= infrastructure/terraform/multipass

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

.PHONY: traefik-forward grafana-forward

traefik-forward:
	kubectl --context $(KUBE_CONTEXT) port-forward -n kube-system svc/traefik 8080:80

grafana-forward:
	kubectl --context $(KUBE_CONTEXT) port-forward -n observability \
		svc/prometheus-stack-grafana 3000:80

.PHONY: argocd-bootstrap gitops-status observability-status

argocd-bootstrap:
	kubectl --context $(KUBE_CONTEXT) apply -f bootstrap/argocd/root-app.yaml

gitops-status:
	kubectl --context $(KUBE_CONTEXT) get applications -n argocd
	kubectl --context $(KUBE_CONTEXT) get namespace apps

observability-status:
	kubectl --context $(KUBE_CONTEXT) -n argocd get applications \
		prometheus-stack loki alloy observability-dashboards
	kubectl --context $(KUBE_CONTEXT) -n observability get pods,pvc

.PHONY: validate
validate:
	$(PYTHON) scripts/validate.py

.PHONY: terraform-init terraform-format terraform-validate terraform-plan

terraform-init:
	terraform -chdir=$(TERRAFORM_DIR) init

terraform-format:
	terraform -chdir=$(TERRAFORM_DIR) fmt -recursive

terraform-validate:
	terraform -chdir=$(TERRAFORM_DIR) validate

terraform-plan:
	terraform -chdir=$(TERRAFORM_DIR) plan
