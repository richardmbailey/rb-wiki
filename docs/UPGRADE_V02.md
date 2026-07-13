# Upgrading an RB Wiki to v0.2

v0.2 adds safe YAML/JSON Schema contracts, recoverable single-writer operations, strict profile 0.2 Reference lifecycle metadata, typed reports, artifact-driven semantic lanes, and consequence-sensitive approvals. Existing profile 0.1 ordinary pages remain readable.

From this toolkit, inspect an existing wiki without changing it:

```bash
python3 wiki-template/tools/wiki_migrate.py --dry-run \
  --root /path/to/existing-wiki --template wiki-template
```

The JSON plan lists exact paths/fields, hashes, preserved local overrides, manual-review items, risks, approvals, validation, and a unified patch. The tool has no apply mode. To review a patch externally:

```bash
python3 wiki-template/tools/wiki_migrate.py --dry-run --patch-only \
  --root /path/to/existing-wiki --template wiki-template > rb-wiki-v01-to-v02.patch
cd /path/to/existing-wiki
git apply --check /path/to/rb-wiki-v01-to-v02.patch
```

Review the complete patch and commit/backup state before using `git apply`. The generator never includes `sources/raw/` and skips paths declared in `wiki-manifest.yml` under `local_overrides`. It rejects traversal, symlinked operational inputs/targets, and oversized legacy text rather than following them. Ambiguous Reference metadata, unknown manifest fields, or divergent consequence/domain policy enter `manual-review` instead of being guessed.

After explicit external application, run:

```bash
python3 -m pip install -e .
python3 tools/wiki_doctor.py --json
python3 tools/provenance.py validate
python3 tools/lint.py --quick
python3 -m unittest discover -s tests -v
```

The next migration dry-run should be `no-op` apart from intentionally preserved local overrides. Authority grants are not enabled by migration. Review local semantic policy into the domain adapter before enabling it.
