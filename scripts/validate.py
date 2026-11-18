"""Run simple offline Kustomize and Helm validation."""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise SystemExit(result.stderr or result.stdout)

# The image-updater Kustomization downloads its pinned upstream base. Keep this
# validation offline and validate only Kustomizations fully stored in this repo.
for kustomization in sorted(ROOT.rglob("kustomization.yaml")):
    if ".git" in kustomization.parts or "image-updater" in kustomization.parts:
        continue
    source = kustomization.parent.relative_to(ROOT)
    print(f"Kustomize: {source}", flush=True)
    run(["kubectl", "kustomize", str(source)])

chart = Path("charts/platform-api")
for values in sorted((ROOT / "apps").glob("*/values.yaml")):
    relative_values = values.relative_to(ROOT)
    release = values.parent.name
    print(f"Helm: {release}", flush=True)
    run(["helm", "lint", str(chart), "--values", str(relative_values)])
    run(
        [
            "helm",
            "template",
            release,
            str(chart),
            "--namespace",
            "apps",
            "--values",
            str(relative_values),
        ]
    )

print("Validation passed.")
