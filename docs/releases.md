# Releases

Run `python scripts/version.py 0.2.0`, test, review and commit the version, then push the commit and `v0.2.0` tag. Use a Python prerelease such as `0.2.0rc1` for a candidate. Package versions are independent of the SADDLE v1 format.

`release.yml` tests Python 3.11/3.13 on Linux, macOS and Windows, validates the tag, builds and checks the wheel/source distribution, and publishes both with SHA-256 checksums to GitHub Releases. Install a downloaded wheel with `pip install saddle_sdk-VERSION-py3-none-any.whl`.

For PyPI publication, configure a [trusted publisher](https://docs.pypi.org/trusted-publishers/adding-a-publisher/) (or a pending publisher for the first package) for owner `jocki-app`, repository `saddle-python-sdk`, workflow `release.yml`, environment `pypi`. Then set GitHub variable `PYPI_PUBLISH=true`. The workflow uses short-lived OIDC credentials, not a committed token. GitHub packages are still published when PyPI is disabled.

The native archive/metadata implementation needs Python and PyYAML. Distributed history/sharing additionally requires the separately installed SADDLE CLI and Node; the wheel does not bundle a second CRDT runtime. Never replace a published version; release a new version for corrections.
