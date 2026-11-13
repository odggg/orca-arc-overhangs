"""Release integrity and trusted-publishing boundary tests; no external services."""
import base64
import contextlib
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest
import urllib.error
import urllib.parse
import urllib.request
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import publish_orcacloud as p


def wheel(version="0.3.1", tag="py3-none-any", bad_record=False, extra=False):
    root = "orca_arc_overhang-0.3.1.dist-info/"
    files = {"arc_overhang.py": b"# synthetic test fixture", root + "METADATA":
             f"Metadata-Version: 2.1\nName: orca-arc-overhang\nVersion: {version}\n".encode(),
             root + "WHEEL": f"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: {tag}\n".encode()}
    record = io.StringIO(newline="")
    writer = csv.writer(record)
    for name, data in files.items():
        checksum = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        writer.writerow([name, "sha256=" + ("wrong" if bad_record else checksum), len(data)])
    writer.writerow([root + "RECORD", "", ""])
    files[root + "RECORD"] = record.getvalue().encode()
    if extra:
        files["unrecorded.py"] = b"# unexpected"
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return output.getvalue()


def release(data):
    return {"tag_name": "v0.3.1", "draft": False, "prerelease": False, "body": "Release notes ☃",
            "assets": [{"id": 123, "name": "orca_arc_overhang-0.3.1-py3-none-any.whl",
                        "size": len(data), "digest": "sha256:" + hashlib.sha256(data).hexdigest()}]}


class FakeClient:
    def __init__(self, data=None, status=201):
        self.data = wheel() if data is None else data
        self.release = release(self.data)
        self.calls = []
        self.status = status

    def github_json(self, path):
        self.calls.append(("release", path))
        return self.release

    def asset(self, repository, asset):
        self.calls.append(("asset", asset["name"]))
        return self.data

    def oidc_token(self):
        self.calls.append(("oidc",))
        return "temporary-identity"

    def request(self, url, **kwargs):
        self.calls.append(("upload", url, kwargs))
        return self.status, b'{"ok":true}'

    def safe(self, value):
        return value.replace("temporary-identity", "<redacted>")


class Response(io.BytesIO):
    status = 200


class Opener:
    def __init__(self, data=b"{}", error=None):
        self.data, self.error, self.requests = data, error, []

    def open(self, request, timeout):
        self.requests.append(request)
        if self.error:
            raise self.error
        return Response(self.data)


class PublishingTests(unittest.TestCase):
    def setUp(self):
        self.data = wheel()
        self.release = release(self.data)
        self.asset = self.release["assets"][0]

    def test_selects_only_exact_current_universal_wheel(self):
        self.release["assets"] += [{"name": name} for name in [
            "orca_arc_overhang-0.3.1-py3-none-win_amd64.whl",
            "orca_arc_overhang-0.3.0-py3-none-any.whl", "sources.zip"]]
        version, asset = p.select_asset(self.release, "v0.3.1")
        self.assertEqual(version, "0.3.1")
        self.assertIs(asset, self.asset)

    def test_rejects_ambiguous_or_missing_wheel_and_invalid_release(self):
        cases = [{"assets": []}, {"assets": [self.asset, self.asset]}, {"draft": True},
                 {"prerelease": True}, {"tag_name": "v0.3.2"},
                 {"assets": [{**self.asset, "size": p.MAX_FILE_BYTES + 1}]}]
        for change in cases:
            with self.subTest(change=change), self.assertRaises(p.PublishError):
                p.select_asset({**self.release, **change}, "v0.3.1")

    def test_rejects_invalid_refs_before_network(self):
        for tag in ["main", "v0.3.1-rc1", "v00.3.1", "v0.3.1\n", "../v0.3.1"]:
            client = FakeClient()
            with self.subTest(tag=tag), self.assertRaises(p.PublishError):
                p.publish("odggg/orca-arc-overhangs", tag, client=client)
            self.assertEqual(client.calls, [])

    def test_checks_wheel_hash_and_every_record_entry(self):
        self.assertEqual(p.validate_wheel(self.data, self.asset, "0.3.1"), hashlib.sha256(self.data).hexdigest())
        invalid = [b"broken", wheel(version="0.3.2"), wheel(tag="cp312-none-win_amd64"),
                   wheel(bad_record=True), wheel(extra=True)]
        for data in invalid:
            with self.subTest(size=len(data)), self.assertRaises(p.PublishError):
                p.validate_wheel(data, release(data)["assets"][0], "0.3.1")
        for asset in [{**self.asset, "size": 1}, {**self.asset, "digest": "sha256:wrong"}]:
            with self.assertRaises(p.PublishError):
                p.validate_wheel(self.data, asset, "0.3.1")

    def test_utf8_changelog_limit_and_empty_notes(self):
        notes = p.metadata_for("0.3.1", "😀" * 1001)["changelog"]
        self.assertLessEqual(len(notes.encode()), 4000)
        self.assertEqual(notes, "😀" * 1000)
        self.assertEqual(p.metadata_for("0.3.1", None), {"version": "0.3.1"})

    def test_dry_run_does_not_obtain_identity_or_upload(self):
        client = FakeClient()
        with contextlib.redirect_stdout(io.StringIO()):
            plan = p.publish("odggg/orca-arc-overhangs", "v0.3.1", dry_run=True, client=client)
        self.assertTrue(plan["dry_run"])
        self.assertEqual([call[0] for call in client.calls], ["release", "asset"])

    def test_uploads_one_validated_wheel_and_release_notes(self):
        client = FakeClient()
        with contextlib.redirect_stdout(io.StringIO()) as output:
            plan = p.publish("odggg/orca-arc-overhangs", "v0.3.1", client=client)
        self.assertTrue(plan["published"])
        self.assertEqual([call[0] for call in client.calls], ["release", "asset", "oidc", "upload"])
        _, url, args = client.calls[-1]
        self.assertEqual(url, p.PUBLISH_URL)
        self.assertEqual(args["token"], "temporary-identity")
        self.assertEqual(args["method"], "POST")
        self.assertEqual(args["body"].count(b'name="files"'), 1)
        self.assertIn(self.data, args["body"])
        self.assertIn(json.dumps(p.metadata_for("0.3.1", client.release["body"]), ensure_ascii=False).encode(), args["body"])
        self.assertNotIn("temporary-identity", output.getvalue())

    def test_bad_asset_never_obtains_identity(self):
        client = FakeClient(wheel(bad_record=True))
        with self.assertRaises(p.PublishError):
            p.publish("odggg/orca-arc-overhangs", "v0.3.1", client=client)
        self.assertEqual([call[0] for call in client.calls], ["release", "asset"])

    def test_requires_created_response(self):
        with self.assertRaisesRegex(p.PublishError, "expected 201"):
            p.publish("odggg/orca-arc-overhangs", "v0.3.1", client=FakeClient(status=200))

    def test_oidc_audience_and_missing_permissions(self):
        opener = Opener(b'{"value":"identity-secret"}')
        client = p.Client({"GITHUB_EVENT_NAME": "release", "ACTIONS_ID_TOKEN_REQUEST_URL": "https://example.test/token?a=1&audience=old",
                           "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "request-secret"}, opener)
        self.assertEqual(client.oidc_token(), "identity-secret")
        request = opener.requests[0]
        self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query), {"a": ["1"], "audience": ["orcacloud"]})
        self.assertEqual(request.get_header("Authorization"), "Bearer request-secret")
        self.assertEqual(client.safe("identity-secret request-secret"), "<redacted> <redacted>")
        with self.assertRaisesRegex(p.PublishError, "id-token"):
            p.Client({}, Opener()).oidc_token()

    def test_manual_workflow_cannot_request_upload_identity(self):
        opener = Opener()
        client = p.Client({"GITHUB_EVENT_NAME": "workflow_dispatch",
                           "ACTIONS_ID_TOKEN_REQUEST_URL": "https://example.test/token",
                           "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "request-secret"}, opener)
        with self.assertRaisesRegex(p.PublishError, "release-event"):
            client.oidc_token()
        self.assertEqual(opener.requests, [])

    def test_http_errors_redact_all_credentials(self):
        error = urllib.error.HTTPError(p.PUBLISH_URL, 401, "Unauthorized", {}, io.BytesIO(b"github-secret request-secret identity-secret"))
        client = p.Client({"GITHUB_TOKEN": "github-secret", "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "request-secret"}, Opener(error=error))
        client.secrets.append("identity-secret")
        with self.assertRaises(p.PublishError) as raised:
            client.request(p.PUBLISH_URL, token="identity-secret")
        self.assertEqual(str(raised.exception), "HTTP 401: <redacted> <redacted> <redacted>")

    def test_cross_host_redirect_strips_credentials(self):
        request = urllib.request.Request("https://api.github.com/asset", headers={"Authorization": "Bearer secret"})
        handler = p.SafeRedirect()
        cross = handler.redirect_request(request, None, 302, "Found", {}, "https://release-assets.githubusercontent.com/file")
        same = handler.redirect_request(request, None, 302, "Found", {}, "https://api.github.com/other")
        self.assertIsNone(cross.get_header("Authorization"))
        self.assertEqual(same.get_header("Authorization"), "Bearer secret")

    def test_anonymous_download_fallback_never_receives_github_token(self):
        class AssetClient(p.Client):
            def request(self, url, **kwargs):
                self.calls.append((url, kwargs))
                return 200, b"{}" if len(self.calls) == 1 else b"PKwheel"
        client = AssetClient({"GITHUB_TOKEN": "github-secret"})
        client.calls = []
        asset = {**self.asset, "browser_download_url": "https://github.com/odggg/orca-arc-overhangs/releases/download/v0.3.1/file.whl"}
        self.assertEqual(client.asset("odggg/orca-arc-overhangs", asset), b"PKwheel")
        self.assertEqual(client.calls[0][1]["token"], "github-secret")
        self.assertNotIn("token", client.calls[1][1])

if __name__ == "__main__":
    unittest.main()
