# Publish GitHub releases to OrcaCloud

This follows [OrcaCloud trusted publishing](https://cloud.orcaslicer.com/wiki/#publish-from-github).

## One-time connection

In OrcaCloud, open **Shared Plugins → Edit plugin → GitHub publishing** for
[Arc Overhangs](https://cloud.orcaslicer.com/app/plugins/plugin-hub/3408ada1-7b45-45a2-9059-feb746a26496).
Enter **odggg/orca-arc-overhangs** and click **Connect**. A repository must be linked
to exactly one plugin. No OrcaCloud API key or repository secret is needed.

## Normal releases

1. Build and check the release as usual, including its universal wheel.
2. Create a stable GitHub release with a semantic version tag, for example `v0.3.2`.
3. Attach `orca_arc_overhang-0.3.2-py3-none-any.whl` and finish the release notes
   **before publishing the release**.
4. Publishing starts the **Publish to OrcaCloud** workflow automatically.

The workflow downloads the exact universal wheel from that release, verifies its
size, GitHub SHA-256 digest (when provided), embedded version, universal wheel tag
and every RECORD entry, then uploads that same file. It does not rebuild the
package, select old files from `dist/`, or upload platform wheels/source archives.
The Cloud version comes from the release tag without `v`; the changelog comes
from the release notes, limited to 4,000 UTF-8 bytes without splitting characters.
Draft and prerelease releases are not published. Ordinary pushes and PRs do not
publish anything. No plugin runtime or version change is part of this setup.

## Existing releases and verification

Under GitHub **Actions → Publish to OrcaCloud → Run workflow**, choose `main` and
enter an existing stable release tag. This manual run only downloads and validates
its asset. It has no OIDC permission and cannot upload to OrcaCloud.

OrcaCloud requires a **release-event** identity. In our integration check, a manual
upload of `v0.3.1` returned HTTP 401 despite obtaining a GitHub OIDC token. The
workflow therefore deliberately restricts uploads to newly published releases.
An older tag that predates this workflow is not moved or recreated to trigger it.

A Cloud release must have a version greater than the current Cloud version.
Repeating an already successful upload is rejected by OrcaCloud. A successful
upload returns HTTP 201. HTTP 401 means the release identity or the repository's
connection was rejected. Check the workflow log and the plugin's public version.

## Authentication and checks

The publish job has only `contents: read` and `id-token: write`; manual validation
has only `contents: read`. GitHub's temporary job
identity is requested with audience `orcacloud` after validating the wheel.
GitHub's automatic job token reads release metadata/assets; it is never sent to
OrcaCloud or to a cross-host download redirect. Uploads are serialized and are
not automatically retried. Credentials are not stored or printed.

Local checks (Python standard library only):

```sh
python -m unittest discover -s tests -p test_orcacloud_publish.py -v
python scripts/publish_orcacloud.py --tag v0.3.1 --dry-run
```

The first command also runs in the regular GitHub checks. The second requires
network access to GitHub; the actual upload requires a GitHub Actions OIDC job.
