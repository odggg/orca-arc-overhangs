from pathlib import Path
import hashlib
import json
import zipfile
from wheel.wheelfile import WheelFile

ROOT = Path(__file__).parent
DIST = ROOT / "dist"
version = "0.3.0"
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

# Produce standard, installable platform wheels, not renamed .whl aliases.
# The code is pure Python; NumPy/Shapely resolve their own platform dependencies.
PLATFORMS = ("win_amd64", "win_arm64", "linux_x86_64", "linux_aarch64",
             "macosx_11_0_arm64", "macosx_10_13_x86_64")
platform_wheels = []
for platform in PLATFORMS:
    platform_wheel = DIST / f"{name}-{version}-py3-none-{platform}.whl"
    with zipfile.ZipFile(wheel) as source, WheelFile(str(platform_wheel), "w") as archive:
        for entry in source.namelist():
            if entry == info + "/RECORD":
                continue  # WheelFile regenerates RECORD including changed WHEEL metadata.
            data = source.read(entry)
            if entry == info + "/WHEEL":
                data = data.replace(b"Tag: py3-none-any", f"Tag: py3-none-{platform}".encode())
            archive.writestr(entry, data)
    platform_wheels.append(platform_wheel)

(ROOT / "LICENSE").write_bytes((ROOT / "upstream" / "LICENSE").read_bytes())

files = {
    "README.md": ROOT / "README.md",
    "README_DE.md": ROOT / "README_DE.md",
    "CHANGELOG.md": ROOT / "CHANGELOG.md",
    "RELEASE_NOTES.md": ROOT / "RELEASE_NOTES.md",
    "docs/PR1_REVIEW.md": ROOT / "docs/PR1_REVIEW.md",
    "VALIDATION.md": ROOT / "VALIDATION.md",
    "COMMUNITY_ISSUE_AUDIT.md": ROOT / "COMMUNITY_ISSUE_AUDIT.md",
    "THIRD_PARTY_NOTICES.md": ROOT / "THIRD_PARTY_NOTICES.md",
    "LICENSE": ROOT / "LICENSE",
    "build_plugin.py": ROOT / "build_plugin.py",
    "adapter.py.in": ROOT / "adapter.py.in",
    "tests.py": ROOT / "tests.py",
    "test_package.py": ROOT / "test_package.py",
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
files.update({"dist/" + file.name: file for file in platform_wheels})
manifest = {path: hashlib.sha256(file.read_bytes()).hexdigest() for path, file in files.items()}
package = ROOT / "Arc_Overhang_OrcaSlicer_2.5_v0.3.0.zip"
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
