"""Publish the exact universal GitHub release wheel using OrcaCloud's OIDC API.

No stored OrcaCloud credential, package build, or plugin import is involved.
Reference: https://cloud.orcaslicer.com/wiki/#publish-from-github
"""
from __future__ import annotations
import argparse
import base64
import csv
import hashlib
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from email.parser import BytesParser

MAX_FILE_BYTES = 100 * 1024 * 1024
PUBLISH_URL = "https://api.orcaslicer.com/api/v1/plugin-publish/releases"

class PublishError(RuntimeError):
    pass

class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, target):
        redirected = super().redirect_request(request, fp, code, message, headers, target)
        if redirected and urllib.parse.urlsplit(target).netloc != urllib.parse.urlsplit(request.full_url).netloc:
            redirected.remove_header("Authorization")
        return redirected

class Client:
    def __init__(self, env=None, opener=None):
        self.env = os.environ if env is None else env
        self.opener = opener or urllib.request.build_opener(SafeRedirect())
        self.secrets = [value for value in (self.env.get("GITHUB_TOKEN"), self.env.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN")) if value]

    def safe(self, message):
        for secret in self.secrets:
            message = message.replace(secret, "<redacted>")
        return message

    def request(self, url, *, method="GET", token=None, body=None, content_type=None, accept="application/vnd.github+json"):
        headers = {"User-Agent": "orca-arc-overhang-publisher", "Accept": accept}
        if token:
            headers["Authorization"] = "Bearer " + token
        if content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=90) as response:
                data = response.read(MAX_FILE_BYTES + 1)
                status = response.status
        except urllib.error.HTTPError as error:
            detail = error.read(4096).decode("utf-8", errors="replace")
            raise PublishError(self.safe(f"HTTP {error.code}: {detail}")) from None
        except (urllib.error.URLError, TimeoutError) as error:
            raise PublishError("Network request failed; check the service status and retry the workflow.") from None
        if len(data) > MAX_FILE_BYTES:
            raise PublishError("The response exceeds OrcaCloud's 100 MB file limit.")
        return status, data

    def github_json(self, path):
        _, data = self.request("https://api.github.com" + path, token=self.env.get("GITHUB_TOKEN"))
        try:
            return json.loads(data)
        except (ValueError, UnicodeDecodeError):
            raise PublishError("GitHub returned an invalid JSON response.") from None

    def asset(self, repository, asset):
        _, data = self.request(f"https://api.github.com/repos/{repository}/releases/assets/{int(asset['id'])}",
                               token=self.env.get("GITHUB_TOKEN"), accept="application/octet-stream")
        if data.startswith(b"PK"):
            return data
        # Some anonymous API responses provide metadata instead of a redirect.
        # The fallback never sends a credential to the public download host.
        url = asset.get("browser_download_url", "")
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != "github.com" or not parsed.path.startswith(f"/{repository}/releases/download/"):
            raise PublishError("GitHub did not return a valid wheel download.")
        _, data = self.request(url, accept="application/octet-stream")
        return data

    def oidc_token(self):
        url = self.env.get("ACTIONS_ID_TOKEN_REQUEST_URL")
        credential = self.env.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN")
        if not url or not credential:
            raise PublishError("Publishing requires GitHub Actions with id-token: write. Use --dry-run for local checks.")
        parts = urllib.parse.urlsplit(url)
        if parts.scheme != "https":
            raise PublishError("The GitHub OIDC endpoint must use HTTPS.")
        query = [(key, value) for key, value in urllib.parse.parse_qsl(parts.query) if key != "audience"]
        query.append(("audience", "orcacloud"))
        endpoint = urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))
        _, data = self.request(endpoint, token=credential, accept="application/json")
        try:
            token = json.loads(data)["value"]
        except (KeyError, ValueError, TypeError):
            raise PublishError("GitHub did not return an OIDC identity token.") from None
        if not isinstance(token, str) or not token:
            raise PublishError("GitHub returned an empty OIDC identity token.")
        self.secrets.append(token)
        return token


def release_version(tag):
    match = re.fullmatch(r"v?((?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*))", tag)
    if not match:
        raise PublishError("Use a stable semantic release tag such as v0.3.1.")
    return match[1]


def select_asset(release, tag):
    version = release_version(tag)
    if release.get("tag_name") != tag or release.get("draft") or release.get("prerelease"):
        raise PublishError("Only the selected published, stable GitHub release may be uploaded.")
    name = f"orca_arc_overhang-{version}-py3-none-any.whl"
    assets = [asset for asset in release.get("assets", []) if asset.get("name") == name]
    if len(assets) != 1:
        raise PublishError(f"Release must contain exactly one asset named {name}.")
    asset = assets[0]
    if not isinstance(asset.get("size"), int) or not 0 < asset["size"] <= MAX_FILE_BYTES:
        raise PublishError("The universal wheel has an invalid size or exceeds 100 MB.")
    return version, asset


def validate_wheel(data, asset, version):
    if len(data) != asset["size"]:
        raise PublishError("Downloaded wheel size differs from GitHub's release metadata.")
    digest = hashlib.sha256(data).hexdigest()
    if asset.get("digest") and asset["digest"] != "sha256:" + digest:
        raise PublishError("Downloaded wheel checksum differs from the published release asset.")
    info = f"orca_arc_overhang-{version}.dist-info/"
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if archive.testzip() is not None:
                raise PublishError("The wheel archive is damaged.")
            metadata = BytesParser().parsebytes(archive.read(info + "METADATA"))
            wheel = BytesParser().parsebytes(archive.read(info + "WHEEL"))
            if metadata["Version"] != version or metadata["Name"] != "orca-arc-overhang":
                raise PublishError("Wheel name/version differs from the selected release tag.")
            if wheel.get_all("Tag") != ["py3-none-any"] or wheel["Root-Is-Purelib"].lower() != "true":
                raise PublishError("The selected asset is not a universal pure-Python wheel.")
            rows = list(csv.reader(io.StringIO(archive.read(info + "RECORD").decode("utf-8"))))
            recorded = set()
            for name, checksum, length in rows:
                recorded.add(name)
                if name == info + "RECORD":
                    continue
                body = archive.read(name)
                actual = "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(body).digest()).rstrip(b"=").decode()
                if checksum != actual or length != str(len(body)):
                    raise PublishError("Wheel RECORD integrity verification failed.")
            if recorded != set(archive.namelist()):
                raise PublishError("Wheel RECORD does not cover every archive member.")
    except (zipfile.BadZipFile, KeyError, ValueError, AttributeError, UnicodeDecodeError):
        raise PublishError("The release asset is not a valid universal Arc Overhang wheel.") from None
    return digest


def metadata_for(version, body):
    notes = (body or "").encode("utf-8")[:4000].decode("utf-8", errors="ignore")
    return {"version": version, **({"changelog": notes} if notes else {})}


def multipart(metadata, name, data):
    boundary = "orca-" + uuid.uuid4().hex
    encoded = json.dumps(metadata, ensure_ascii=False).encode("utf-8")
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n'.encode() + encoded
            + f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{name}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()
            + data + f'\r\n--{boundary}--\r\n'.encode())
    return body, "multipart/form-data; boundary=" + boundary


def publish(repository, tag, *, dry_run=False, client=None):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise PublishError("A valid owner/repository is required.")
    release_version(tag)  # reject an invalid ref before issuing any request
    client = client or Client()
    release = client.github_json(f"/repos/{repository}/releases/tags/{urllib.parse.quote(tag, safe='')}")
    version, asset = select_asset(release, tag)
    data = client.asset(repository, asset)
    digest = validate_wheel(data, asset, version)
    plan = {"repository": repository, "tag": tag, "version": version, "file": asset["name"], "sha256": digest}
    if dry_run:
        print(json.dumps({"dry_run": True, **plan}, indent=2))
        return {"dry_run": True, **plan}
    # Obtain the short-lived identity only after the immutable asset is validated.
    token = client.oidc_token()
    body, content_type = multipart(metadata_for(version, release.get("body")), asset["name"], data)
    status, result = client.request(PUBLISH_URL, method="POST", token=token, body=body, content_type=content_type, accept="application/json")
    if status != 201:
        raise PublishError(f"OrcaCloud returned HTTP {status}; expected 201.")
    message = client.safe(result.decode("utf-8", errors="replace"))
    print(json.dumps({"published": True, **plan}, indent=2))
    print("OrcaCloud response: " + message[:4096])
    return {"published": True, **plan}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", "odggg/orca-arc-overhangs"))
    parser.add_argument("--tag", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        publish(args.repository, args.tag, dry_run=args.dry_run)
    except PublishError as error:
        print("OrcaCloud publish failed: " + str(error), file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
