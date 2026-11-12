# Arc Overhang 0.3.2

- Added automatic publishing from GitHub releases to Orca Cloud using secure, short-lived GitHub credentials. No stored Orca Cloud API key is required.
- Publish one universal **any WHL**, with the version and changelog taken directly from the GitHub release.
- Validate the package checksum, embedded version and wheel integrity before uploading.
- Added a manual release-package check and documentation for the publishing workflow.
- Added 14 publishing regression tests.

Print behavior, print-order options, settings and the graphical workbench are unchanged from 0.3.1.

Thanks to **@persano** for the contributed print-order and Hilbert fixes, optional Wave mode and further improvements included in earlier releases.
