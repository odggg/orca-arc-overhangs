"""Validate generated plugin packages after package_release.py."""
from pathlib import Path
from email.parser import BytesParser
import hashlib
import json
import sys
import zipfile
from packaging.utils import parse_wheel_filename
from wheel.wheelfile import WheelFile

ROOT = Path(__file__).parent
sys.path[:0] = [str(ROOT / "test-deps"), str(ROOT / "dist")]
import arc_overhang as plugin

source = (ROOT / "dist/arc_overhang.py").read_bytes()
assert (ROOT / "src/arc_overhang.py").read_bytes() == source
assert (ROOT / "src/adapter.py.in").read_bytes() == (ROOT / "adapter.py.in").read_bytes()
assert (ROOT / "config-preview.html").read_text(encoding="utf-8") == plugin.config_page()
assert (ROOT / "tab-preview.html").read_text(encoding="utf-8") == plugin.config_page(as_tab=True)
wheels = sorted((ROOT / "dist").glob(f"orca_arc_overhang-{plugin.VERSION}-*.whl"))
assert len(wheels) == 1, [file.name for file in wheels]
for file in wheels:
    name, version, _, tags = parse_wheel_filename(file.name)
    assert str(name) == "orca-arc-overhang" and str(version) == plugin.VERSION
    with WheelFile(str(file)) as archive:
        for entry in archive.namelist():
            archive.read(entry)  # WheelFile checks RECORD hashes while reading.
        assert archive.read("orca_arc_overhang/__init__.py") == source
        info = f"orca_arc_overhang-{plugin.VERSION}.dist-info/"
        metadata = BytesParser().parsebytes(archive.read(info + "METADATA"))
        assert metadata["Version"] == plugin.VERSION
        wheel_metadata = BytesParser().parsebytes(archive.read(info + "WHEEL"))
        assert set(wheel_metadata.get_all("Tag")) == {str(tag) for tag in tags}
with zipfile.ZipFile(ROOT / f"Arc_Overhang_OrcaSlicer_2.5_v{plugin.VERSION}.zip") as archive:
    assert archive.testzip() is None
    manifest = json.loads(archive.read("SHA256SUMS.json"))
    assert set(archive.namelist()) == set(manifest) | {"SHA256SUMS.json"}
    for entry, digest in manifest.items():
        assert hashlib.sha256(archive.read(entry)).hexdigest() == digest
        assert not entry.startswith(("archive/", "evidence/", "fixtures/", "docs/cloud-chat"))
    assert all("dist/" + file.name in manifest for file in wheels)
print("Package validation: one universal wheel, source/metadata/RECORD consistency, previews and ZIP manifest passed.")
