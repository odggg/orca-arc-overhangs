# Publish GitHub releases to OrcaCloud

This follows [OrcaCloud trusted publishing](https://cloud.orcaslicer.com/wiki/#publish-from-github).

## One-time connection

In OrcaCloud, open **Shared Plugins → Edit plugin → GitHub publishing** for
[Arc Overhangs](https://cloud.orcaslicer.com/app/plugins/plugin-hub/3408ada1-7b45-45a2-9059-feb746a26496).
Enter **odggg/orca-arc-overhangs** and click **Connect**. A repository must be linked
to exactly one plugin. No OrcaCloud API key is needed.

For automatic GitHub releases, create a fine-grained personal access token owned
by `odggg`, restricted to **only `orca-arc-overhangs`**, with **Contents: Read and
write**. Save it as the repository Actions secret **`RELEASE_TOKEN`**. Choose an
expiry date and renew the secret before it expires. Do not commit or paste the
token into an issue, chat, or workflow file.

This token is used only to publish a completed GitHub release. Builds and asset
uploads use the normal job token; the OrcaCloud upload uses its existing OIDC
identity. The release workflow stops before building if the secret is missing.

## Normal releases

1. Set the plugin version and add its notes to `CHANGELOG.md`.
2. Push the matching stable tag, for example `v0.4.2`. Alternatively, run
   **Actions → Release** with an existing tag that contains the release workflow.
3. The workflow builds and checks the plugin, then creates a release draft with
   only `orca_arc_overhang-0.4.2-py3-none-any.whl` and that version's changelog.
4. It verifies the uploaded wheel's name, size, SHA-256 and release notes, then
   publishes the completed draft automatically using `RELEASE_TOKEN`.
5. That publication starts **Publish to OrcaCloud** automatically. No manual
   Publish click is needed.

The draft step prevents the Cloud workflow from starting before the WHL upload
finishes. GitHub's built-in job token cannot trigger another workflow; the
dedicated token produces the release event required by OrcaCloud.
See [GitHub's workflow triggering rules](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).
Existing releases are not rebuilt or overwritten. If publication fails after
the upload, the draft remains available for inspection; resolve the error before
publishing it manually or removing that draft and retrying the workflow.

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
