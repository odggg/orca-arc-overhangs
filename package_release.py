from pathlib import Path
import hashlib
import json
import zipfile
import re
from wheel.wheelfile import WheelFile

ROOT = Path(__file__).parent
DIST = ROOT / "dist"
version = re.search(r'^VERSION = "([^"\n]+)"', (DIST / "arc_overhang.py").read_text(encoding="utf-8"), re.M)[1]
name = "orca_arc_overhang"
info = name + "-" + version + ".dist-info"
wheel = DIST / f"{name}-{version}-py3-none-any.whl"
metadata = f"""Metadata-Version: 2.1
Name: orca-arc-overhang
Version: {version}
Summary: Native Arc Overhang slicing pipeline plugin for OrcaSlicer 2.5
Author: Kelsch, Nicolai Wachenschwan, Steven McCulloch; Orca 2.5 adaptation
License: GPL-3.0
Requires-Python: >=3.12
Requires-Dist: numpy>=1.26,<3
Requires-Dist: shapely>=2.0,<3
Project-URL: Original integration, https://github.com/Kelsch/arc-overhang-orcaslicer-integration

Native OrcaSlicer 2.5 plugin. Experimental; see README_DE.md and VALIDATION.md.
"""
with WheelFile(str(wheel), "w") as archive:
    archive.writestr(name + "/__init__.py", (DIST / "arc_overhang.py").read_bytes())
    archive.writestr(info + "/METADATA", metadata)
    archive.writestr(info + "/WHEEL", "Wheel-Version: 1.0\nGenerator: Arc Overhang packager\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
    archive.writestr(info + "/top_level.txt", name + "\n")
    for file in ("README_DE.md", "VALIDATION.md", "THIRD_PARTY_NOTICES.md"):
        archive.writestr(info + "/" + file, (ROOT / file).read_bytes())
    archive.writestr(info + "/LICENSE", (ROOT / "upstream/LICENSE").read_bytes())
with zipfile.ZipFile(wheel) as archive:
    assert archive.testzip() is None
    assert info + "/RECORD" in archive.namelist()
    assert len([n for n in archive.namelist() if n.endswith(".dist-info/METADATA")]) == 1

# The plugin is pure Python. Publish one universal wheel; dependencies resolve
# their own platform packages. Keep older releases in Git/tags.

(ROOT / "LICENSE").write_bytes((ROOT / "upstream" / "LICENSE").read_bytes())

files = {
    "README.md": ROOT / "README.md",
    "README_DE.md": ROOT / "README_DE.md",
    "CHANGELOG.md": ROOT / "CHANGELOG.md",
    "RELEASE_NOTES.md": ROOT / "RELEASE_NOTES.md",
    "docs/PR1_REVIEW.md": ROOT / "docs/PR1_REVIEW.md",
    "docs/UX_DESIGN.md": ROOT / "docs/UX_DESIGN.md",
    "docs/GITHUB_PUBLISHING.md": ROOT / "docs/GITHUB_PUBLISHING.md",
    ".github/workflows/publish-orcacloud.yml": ROOT / ".github/workflows/publish-orcacloud.yml",
    "scripts/publish_orcacloud.py": ROOT / "scripts/publish_orcacloud.py",
    "tests/test_orcacloud_publish.py": ROOT / "tests/test_orcacloud_publish.py",
    "docs/ui/overview.png": ROOT / "docs/ui/overview.png",
    "docs/ui/guide.png": ROOT / "docs/ui/guide.png",
    "docs/ui/dark.png": ROOT / "docs/ui/dark.png",
    "VALIDATION.md": ROOT / "VALIDATION.md",
    "COMMUNITY_ISSUE_AUDIT.md": ROOT / "COMMUNITY_ISSUE_AUDIT.md",
    "THIRD_PARTY_NOTICES.md": ROOT / "THIRD_PARTY_NOTICES.md",
    "LICENSE": ROOT / "LICENSE",
    "build_plugin.py": ROOT / "build_plugin.py",
    "adapter.py.in": ROOT / "adapter.py.in",
    "tests.py": ROOT / "tests.py",
    "test_package.py": ROOT / "test_package.py",
    "test_browser.js": ROOT / "test_browser.js",
    "package.json": ROOT / "package.json",
    "pnpm-lock.yaml": ROOT / "pnpm-lock.yaml",
    "tests/ui_gcode_baselines.json": ROOT / "tests/ui_gcode_baselines.json",
    "ui/config.html": ROOT / "ui/config.html",
    "ui/styles.css": ROOT / "ui/styles.css",
    "ui/config.js": ROOT / "ui/config.js",
    "test_ui.js": ROOT / "test_ui.js",
    "test_audit.py": ROOT / "test_audit.py",
    "test_tab.js": ROOT / "test_tab.js",
    "tab-preview.html": ROOT / "tab-preview.html",
    "config-preview.html": ROOT / "config-preview.html",
    "package_release.py": ROOT / "package_release.py",
    "requirements-dev.txt": ROOT / "requirements-dev.txt",
    "dist/arc_overhang.py": DIST / "arc_overhang.py",
    "src/adapter.py.in": ROOT / "src/adapter.py.in",
    "src/arc_overhang.py": ROOT / "src/arc_overhang.py",
    "dist/" + wheel.name: wheel,
    "upstream/LICENSE": ROOT / "upstream/LICENSE",
    "upstream/softfever_slicer_post_processing_script.py": ROOT / "upstream/softfever_slicer_post_processing_script.py",
    "examples/synthetic_before.gcode": ROOT / "examples/synthetic_before.gcode",
    "examples/synthetic_after.gcode": ROOT / "examples/synthetic_after.gcode",
    "icon.png": ROOT / "icon.png",
}
manifest = {path: hashlib.sha256(file.read_bytes()).hexdigest() for path, file in files.items()}
package = ROOT / f"Arc_Overhang_OrcaSlicer_2.5_v{version}.zip"
with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path, file in files.items():
        archive.write(file, path)
    archive.writestr("SHA256SUMS.json", json.dumps(manifest, indent=2) + "\n")
with zipfile.ZipFile(package) as archive:
    assert archive.testzip() is None
    for path, digest in manifest.items():
        assert hashlib.sha256(archive.read(path)).hexdigest() == digest
    assert not any(path.startswith(("archive/", "docs/cloud-chat")) for path in archive.namelist())
print(json.dumps({"package": str(package), "bytes": package.stat().st_size,
                  "wheel": str(wheel), "files": len(files) + 1}, indent=2))
