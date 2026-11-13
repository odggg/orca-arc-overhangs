"""Stage one verified universal wheel and the matching changelog section."""
import argparse
import ast
from pathlib import Path
import re

from publish_orcacloud import validate_wheel


def stage(root, tag):
    if not re.fullmatch(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", tag):
        raise ValueError("Use a stable version tag such as v0.4.2.")
    version = tag[1:]
    tree = ast.parse((root / "adapter.py.in").read_text(encoding="utf-8"))
    declared = next(ast.literal_eval(node.value) for node in tree.body
                    if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == "VERSION"
                            for target in node.targets))
    if declared != version:
        raise ValueError(f"Tag {tag} does not match plugin version {declared}.")
    name = f"orca_arc_overhang-{version}-py3-none-any.whl"
    data = (root / "dist" / name).read_bytes()
    validate_wheel(data, {"size": len(data)}, version)
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    section = re.search(r"^## " + re.escape(version) + r"(?: -[^\n]*)?\n(.*?)(?=^## |\Z)",
                        changelog, re.M | re.S)
    if not section or not section[1].strip():
        raise ValueError(f"Add release notes for {version} to CHANGELOG.md first.")
    destination = root / "release-assets"
    # Do not reuse a directory that might contain old versions or platform wheels.
    destination.mkdir()
    (destination / name).write_bytes(data)
    (root / "release-notes.md").write_text(section[1].strip() + "\n", encoding="utf-8")
    return destination / name


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    print(stage(Path(__file__).resolve().parents[1], args.tag))
