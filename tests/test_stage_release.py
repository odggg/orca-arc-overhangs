"""Release selection must not publish old or platform-specific packages."""
from pathlib import Path
import copy
import hashlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import stage_release
import publish_github_release
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


class PublishCompletedDraftTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        folder = self.root / "release-assets"
        folder.mkdir()
        name = "orca_arc_overhang-0.3.1-py3-none-any.whl"
        data = wheel()
        (folder / name).write_bytes(data)
        (self.root / "release-notes.md").write_text("- Fix import.\n")
        self.draft = {"tag_name": "v0.3.1", "draft": True, "prerelease": False,
                      "body": "- Fix import.\n", "assets": [{"name": name, "state": "uploaded",
                      "size": len(data), "digest": "sha256:" + hashlib.sha256(data).hexdigest()}]}
        self.calls = []

    def request(self, endpoint, body=None):
        self.calls.append((endpoint, body))
        if body is None:
            return copy.deepcopy(self.draft)
        return {"tag_name": "v0.3.1", "draft": False, "published_at": "2026-01-01T00:00:00Z",
                "html_url": "https://github.com/example/repo/releases/tag/v0.3.1"}

    def test_publish_only_after_uploaded_wheel_and_notes_match(self):
        publish_github_release.publish(self.root, "v0.3.1", "123", self.request)
        self.assertEqual(self.calls, [("releases/123", None), ("releases/123", {"draft": False})])

    def test_wrong_or_already_published_release_never_publishes(self):
        for change in ({"tag_name": "v0.3.2"}, {"draft": False}, {"prerelease": True},
                       {"body": "Wrong notes"}, {"assets": []},
                       {"assets": self.draft["assets"] * 2}):
            original = copy.deepcopy(self.draft)
            self.draft.update(change)
            self.calls.clear()
            with self.subTest(change=change), self.assertRaises(ValueError):
                publish_github_release.publish(self.root, "v0.3.1", "123", self.request)
            self.assertEqual(self.calls, [("releases/123", None)])
            self.draft = original

    def test_incomplete_or_modified_upload_never_publishes(self):
        for change in ({"state": "starter"}, {"size": 1}, {"digest": None},
                       {"digest": "sha256:wrong"}, {"name": "platform.whl"}):
            original = copy.deepcopy(self.draft)
            self.draft["assets"][0].update(change)
            self.calls.clear()
            with self.subTest(change=change), self.assertRaises(ValueError):
                publish_github_release.publish(self.root, "v0.3.1", "123", self.request)
            self.assertEqual(self.calls, [("releases/123", None)])
            self.draft = original

    def test_invalid_tag_or_id_never_contacts_github(self):
        for tag, release_id in (("main", "123"), ("v0.3.1", "../other")):
            with self.assertRaises(ValueError):
                publish_github_release.publish(self.root, tag, release_id, self.request)
        self.assertEqual(self.calls, [])
