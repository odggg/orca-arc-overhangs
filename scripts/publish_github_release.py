"""Publish a completed draft with a token that triggers downstream workflows."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.request


def publish(root, tag, release_id, request):
    if not re.fullmatch(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", tag):
        raise ValueError("A stable version tag is required.")
    if not re.fullmatch(r"[1-9]\d*", str(release_id)):
        raise ValueError("A valid draft release ID is required.")
    endpoint = f"releases/{release_id}"
    release = request(endpoint)
    if release.get("tag_name") != tag or release.get("draft") is not True or release.get("prerelease"):
        raise ValueError("Expected the newly created stable release draft.")
    name = f"orca_arc_overhang-{tag[1:]}-py3-none-any.whl"
    assets = release.get("assets", [])
    if len(assets) != 1 or assets[0].get("name") != name or assets[0].get("state") != "uploaded":
        raise ValueError("The draft must contain exactly one fully uploaded universal wheel.")
    data = (root / "release-assets" / name).read_bytes()
    asset = assets[0]
    if asset.get("size") != len(data) or asset.get("digest") != "sha256:" + hashlib.sha256(data).hexdigest():
        raise ValueError("The uploaded asset does not match the validated local wheel.")
    notes = (root / "release-notes.md").read_text(encoding="utf-8")
    if release.get("body", "").strip() != notes.strip():
        raise ValueError("Release notes do not match the prepared changelog.")
    result = request(endpoint, {"draft": False})
    if result.get("draft") is not False or result.get("tag_name") != tag or not result.get("published_at"):
        raise ValueError("GitHub did not confirm publication. Check the release before retrying.")
    return result["html_url"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--release-id", required=True)
    args = parser.parse_args()
    token = os.environ.get("GH_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("The dedicated release token and repository are required.")

    def request(endpoint, body=None):
        req = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/{endpoint}",
            data=json.dumps(body).encode() if body is not None else None,
            method="PATCH" if body is not None else "GET",
            headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                     "Content-Type": "application/json", "User-Agent": "arc-overhang-release"})
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)

    print(publish(Path(__file__).resolve().parents[1], args.tag, args.release_id, request))


if __name__ == "__main__":
    main()
