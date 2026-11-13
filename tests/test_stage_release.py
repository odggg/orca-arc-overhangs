"""Release selection must not publish old or platform-specific packages."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import stage_release
from publish_orcacloud import PublishError
from test_orcacloud_publish import wheel


class StageReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "dist").mkdir()
        (self.root / "adapter.py.in").write_text('VERSION = "0.3.1"\n')
        (self.root / "CHANGELOG.md").write_text(
            "# Changelog\n\n## Unreleased\nFuture work\n\n## 0.3.1 - 2026-01-01\n\n- Fix import.\n\n## 0.3.0\nOld\n")
        self.asset = self.root / "dist/orca_arc_overhang-0.3.1-py3-none-any.whl"
        self.asset.write_bytes(wheel())

    def test_only_matching_any_wheel_and_matching_notes(self):
        for name in ("orca_arc_overhang-0.3.0-py3-none-any.whl",
                     "orca_arc_overhang-0.3.1-py3-none-win_amd64.whl", "source.zip"):
            (self.root / "dist" / name).write_bytes(b"not selected")
        result = stage_release.stage(self.root, "v0.3.1")
        self.assertEqual(list(result.parent.iterdir()), [result])
        self.assertEqual(result.read_bytes(), self.asset.read_bytes())
        self.assertEqual((self.root / "release-notes.md").read_text(), "- Fix import.\n")

    def test_invalid_or_mismatched_tags_do_not_stage(self):
        for tag in ("main", "v0.3.1-rc1", "v01.3.1", "v0.3.2", "v0.3.1\n"):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                stage_release.stage(self.root, tag)
        self.assertFalse((self.root / "release-assets").exists())

    def test_damaged_or_wrong_version_wheel_is_rejected(self):
        for data in (b"invalid zip", wheel(version="0.3.2"), wheel(bad_record=True)):
            self.asset.write_bytes(data)
            with self.assertRaises(PublishError):
                stage_release.stage(self.root, "v0.3.1")
        self.assertFalse((self.root / "release-assets").exists())

    def test_missing_notes_is_rejected(self):
        (self.root / "CHANGELOG.md").write_text("## Unreleased\nFuture\n")
        with self.assertRaises(ValueError):
            stage_release.stage(self.root, "v0.3.1")
        self.assertFalse((self.root / "release-assets").exists())

    def test_existing_staging_directory_is_not_reused(self):
        folder = self.root / "release-assets"
        folder.mkdir()
        stale = folder / "old.whl"
        stale.write_bytes(b"old")
        with self.assertRaises(FileExistsError):
            stage_release.stage(self.root, "v0.3.1")
        self.assertEqual(list(folder.iterdir()), [stale])
