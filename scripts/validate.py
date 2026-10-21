"""Validate repository YAML, local Argo CD sources, and Kustomize builds."""
import argparse
import re
import subprocess
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--kustomize", default="kustomize")
args = parser.parse_args()

documents = []
for path in ROOT.rglob("*"):
    if ".git" in path.parts or ".venv" in path.parts or "__pycache__" in path.parts:
        continue
    if path.suffix in (".yaml", ".yml"):
        documents.extend(
            (path, document)
            for document in yaml.safe_load_all(path.read_text())
            if document is not None
        )

kustomizations = sorted(
    path.parent for path in ROOT.rglob("kustomization.yaml")
    if ".git" not in path.parts and ".venv" not in path.parts
)
kustomization_dirs = {path.resolve() for path in kustomizations}
rendered_documents = []
for source_dir in kustomizations:
    directory = source_dir.relative_to(ROOT).as_posix()
    try:
        result = subprocess.run(
            [args.kustomize, "build", str(source_dir)],
            capture_output=True,
            check=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        raise ValueError(
            f"Kustomize build failed for {directory}:\n{error.stderr.strip()}"
        ) from error
    output = result.stdout
    rendered = list(yaml.safe_load_all(output))
    rendered = [resource for resource in rendered if resource is not None]
    if not rendered:
        raise ValueError(f"Empty rendered source: {directory}")
    rendered_documents.extend((source_dir, resource) for resource in rendered)

crd_schemas = {}
for _, resource in [*documents, *rendered_documents]:
    if resource.get("kind") != "CustomResourceDefinition":
        continue
    spec = resource["spec"]
    group = spec["group"]
    kind = spec["names"]["kind"]
    for version in spec["versions"]:
        schema = version.get("schema", {}).get("openAPIV3Schema")
        if schema:
            crd_schemas[(group, version["name"], kind)] = schema

for path, resource in [*documents, *rendered_documents]:
    if resource.get("kind") == "Application":
        source = resource.get("spec", {}).get("source", {})
        if source.get("repoURL") == "https://github.com/alandhaas/local-platform-gitops.git":
            source_path = ROOT / source["path"]
            if not source_path.is_dir():
                raise ValueError(f"Missing Argo CD source path in {path}: {source['path']}")
            if source_path.resolve() not in kustomization_dirs:
                raise ValueError(
                    f"Argo CD source has no recognized Kustomize entrypoint "
                    f"in {path}: {source['path']}"
                )

    if resource.get("kind") == "ImageUpdater":
        group, _, version = resource["apiVersion"].partition("/")
        schema = crd_schemas.get((group, version, resource["kind"]))
        if schema is None:
            raise ValueError(f"No matching ImageUpdater CRD schema found for {path}")
        jsonschema.validate(resource, schema)

for path in ROOT.rglob("*.md"):
    if ".git" in path.parts or ".venv" in path.parts or "__pycache__" in path.parts:
        continue
    for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", path.read_text()):
        if "://" in target or target.startswith("#"):
            continue
        if not (path.parent / target.split("#")[0]).exists():
            raise ValueError(f"Broken documentation link in {path}: {target}")

print(
    "YAML, Argo CD source paths, documentation links, Kustomize rendering, "
    "and ImageUpdater schema passed."
)
