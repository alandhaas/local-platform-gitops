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
        spec = resource.get("spec", {})
        sources = spec.get("sources", [spec.get("source", {})])
        references = {
            source["ref"]: source for source in sources if source.get("ref")
        }

        for source in sources:
            if (
                source.get("repoURL")
                == "https://github.com/alandhaas/local-platform-gitops.git"
                and source.get("path")
            ):
                source_path = ROOT / source["path"]
                if not source_path.is_dir():
                    raise ValueError(
                        f"Missing Argo CD source path in {path}: {source['path']}"
                    )
                if source_path.resolve() not in kustomization_dirs:
                    raise ValueError(
                        f"Argo CD source has no recognized Kustomize entrypoint "
                        f"in {path}: {source['path']}"
                    )

            for value_file in source.get("helm", {}).get("valueFiles", []):
                if not value_file.startswith("$"):
                    continue
                match = re.fullmatch(r"\$([^/]+)/(.+)", value_file)
                if match is None or match.group(1) not in references:
                    raise ValueError(
                        f"Invalid Argo CD Helm values reference in {path}: {value_file}"
                    )
                values_source = references[match.group(1)]
                if (
                    values_source.get("repoURL")
                    == "https://github.com/alandhaas/local-platform-gitops.git"
                    and not (ROOT / match.group(2)).is_file()
                ):
                    raise ValueError(
                        f"Missing Argo CD Helm values file in {path}: {match.group(2)}"
                    )

    if resource.get("kind") == "ImageUpdater":
        group, _, version = resource["apiVersion"].partition("/")
        schema = crd_schemas.get((group, version, resource["kind"]))
        if schema is None:
            raise ValueError(f"No matching ImageUpdater CRD schema found for {path}")
        jsonschema.validate(resource, schema)

markdown_paths = [
    path for path in ROOT.rglob("*.md")
    if ".git" not in path.parts
    and ".venv" not in path.parts
    and "__pycache__" not in path.parts
]
ignored_result = subprocess.run(
    ["git", "check-ignore", "--stdin"],
    cwd=ROOT,
    input="".join(f"{path.relative_to(ROOT)}\n" for path in markdown_paths),
    capture_output=True,
    text=True,
)
if ignored_result.returncode not in (0, 1):
    raise ValueError(f"Unable to inspect ignored documentation:\n{ignored_result.stderr}")
ignored_markdown = {
    (ROOT / ignored_path).resolve()
    for ignored_path in ignored_result.stdout.splitlines()
}

for path in markdown_paths:
    if path.resolve() in ignored_markdown:
        continue
    for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", path.read_text()):
        if "://" in target or target.startswith("#"):
            continue
        if not (path.parent / target.split("#")[0]).exists():
            raise ValueError(f"Broken documentation link in {path}: {target}")

print(
    "YAML, Argo CD source paths and Helm values references, documentation links, "
    "Kustomize rendering, and ImageUpdater schema passed."
)
