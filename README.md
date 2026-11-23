# SADDLE Python SDK

A native Python implementation of the SADDLE v1 named-record container and resource metadata. Distributed history and approved sharing use the canonical TypeScript Automerge/Keyhive runtime through the independent `saddle` CLI. Binary records are preserved losslessly; no alternate Python history format is invented.

## Install and use

Python 3.11 or newer is required. Install this repository with `pip install .`. For history and sharing, install [saddle-cli](https://github.com/jocki-app/saddle-cli) and Node.js 26.10 or newer.

```python
from saddle import Archive, Runtime, companion_path

archive = Archive(companion_path("notes.md"))
print(archive.names())
print(archive.get_json("resource.json"))

runtime = Runtime()
runtime.configure("notes.md", "history", "enabled")
print(runtime.history("notes.md"))
runtime.reset_history("notes.md")
```

`Runtime(command=[...], profile=...)` accepts an explicit executable capability and private identity/cache location. Requests are JSON, use argument arrays without a shell, and do not execute commands received from peers. Invites require approved contact-card grants; an invitation alone is insufficient.

## Native archive API

`Archive(path)` exposes `names`, `read`, `write`, `get_json`, `set_json`, `inspect`, `verify`, `remove` and `compact`. Updates append checksummed records/indexes and publish an alternating durable commit slot. Replacement/deletion compacts discarded bytes; compaction streams existing chunks in bounded memory and preserves unknown records. Document payloads are opaque binary Automerge bytes. Optional heads and change counts remain atomically associated with them.

Low-level archive writes require a coordinated root writer lease when another application is active. The Python adapter serializes cooperating Python writers, but its lock is not a substitute for an application's granted root capability. Use the runtime's high-level metadata/history/sharing methods for live or versioned units so the canonical lease, epoch and retention coordinator are used. Never remove a shared history record directly: peers must agree to pruning.

`resource`, `new_resource`, `import_metadata`, `companion_path` and `effective_features` provide metadata and policy utilities. Inline Markdown frontmatter and JSON metadata are validated together; duplicate properties reject the entire result. The full document adapter remains available via `Runtime.metadata`.

## Verification

```sh
PYTHONPATH=src python -m unittest discover -s tests
SADDLE_CLI=/path/to/saddle-cli/bin/saddle.mjs SADDLE_NODE=/path/to/node PYTHONPATH=src python -m unittest discover -s tests
```

The second command additionally tests bidirectional TypeScript/Python archives, real history, metadata, cleanup and the single-file scope boundary. See the [SADDLE specification](https://github.com/jocki-app/saddle-specification).

GPL-3.0-only. See [LICENSE](LICENSE).
