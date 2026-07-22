# Authority Grants

An authority grant is a written permission slip for one kind of agent work. It says what may run, where it may write, how long it may run, what checks it must pass, and whether it may make a local commit.

A person directly editing Markdown does not need a grant. A mutating agent session, managed inbox run, scheduled job, or autonomous apply always does. A grant never authorises a push, deletion of raw evidence, or work outside its selected lane contract.

## Use One Grant Per Job

Prefer a separate grant for each responsibility:

| Job | Mode | Lane | Action |
|---|---|---|---|
| Interactive agent editing under human supervision | `manual-assist` | `semantic` or `synthesize` | `edit-wiki-pages` |
| Scheduled index, graph, and lint upkeep | `scheduled-propose` | `maintain` | `deterministic-maintenance` |
| Managed inbox processing | `manual-assist` or `scheduled-propose` | `ingest` | `ingest-sources` |
| Scheduled preparation of a synthesis proposal | `scheduled-propose` | `synthesize` | `propose-synthesis` |
| Applying exact content from a committed proposal | `authorised-autonomous-apply` | `synthesize` or `semantic` | `edit-wiki-pages` |

Do not make a single broad grant for every job. The controller rejects actions, paths, page types, or inputs that exceed the selected lane, and narrow grants make human review much easier.

## Grant Lifecycle

1. Start from `schema/authorities/disabled-example.yml` or one of the examples below.
2. Save the file as `schema/authorities/AUTHORITY_ID.yml`. The filename and `authority_id` must match exactly.
3. Keep `enabled: false` while editing it.
4. Choose one mode, lane, and lane-compatible action. Read the corresponding contract in `schema/lanes/`.
5. List only the input roots, output paths, and page types that job needs. Required run-report paths must still be present.
6. Set short `issued_at` and `expires_at` times, conservative budgets, the lowest sufficient consequence tier, and an appropriate commit policy.
7. Review the complete file. Change `enabled` to `true` only when it is ready to use.
8. Commit the grant. Scheduled and autonomous work is bound to committed policy and authority from a clean Git base; an uncommitted grant does not create authority.
9. Run the workflow once under supervision before scheduling it.
10. Let the grant expire, or revoke it explicitly when the work no longer needs to run.

The examples below are intentionally disabled and use future placeholder dates so they cannot accidentally grant current authority. Replace the owner, dates, paths, page types, budgets, and identity for the actual wiki before enabling them.

## Example: Human-Supervised Page Editing

Save as `schema/authorities/manual-editor-example.yml`. This lets an interactive agent edit only Concept and Synthesis pages in two directories. The human reviews and commits the changes.

```yaml
schema_version: rb-wiki-authority-grant/0.2
authority_id: manual-editor-example
enabled: false
owner: example-human-reviewer
issued_at: "2099-01-01T00:00:00Z"
expires_at: "2099-01-02T00:00:00Z"
revoked_at: null
modes: [manual-assist]
lanes: [semantic]
actions: [edit-wiki-pages]
input_roots: []
writable_paths:
  - wiki/concepts/**
  - wiki/syntheses/**
  - reports/runs/**
  - reports/latest.json
page_types: [Concept, Synthesis]
required_checks: [quick-lint]
consequence_tier: routine
budgets:
  max_runtime_seconds: 300
  max_changed_paths: 10
  max_acquired_sources: 0
commit_policy: manual
commit_identity: null
governance_maintenance: false
```

Start an interactive session only after the reviewed grant is committed:

```bash
python3 tools/wiki_run.py start \
  --lane semantic \
  --mode manual-assist \
  --authority manual-editor-example
```

Give the returned envelope and token only to the cooperating agent performing that run. Heartbeat during long work and inspect status when needed. At finish, the controller runs quick lint itself and records the result:

```bash
python3 tools/wiki_run.py heartbeat --run-id RUN_ID --token RUN_TOKEN
python3 tools/wiki_run.py status --run-id RUN_ID
python3 tools/wiki_run.py finish --run-id RUN_ID --token RUN_TOKEN
```

With `commit_policy: manual`, a material result ends `manual-commit-required`. Review the diff and commit it yourself. If the task should not continue, use `cancel`; use `fail` when the agent encountered an actual failure.

## Example: Scheduled Deterministic Maintenance

Save as `schema/authorities/scheduled-maintainer-example.yml`. The new-wiki setup can generate the equivalent current, time-bounded grant with `--enable-scheduled-propose`.

```yaml
schema_version: rb-wiki-authority-grant/0.2
authority_id: scheduled-maintainer-example
enabled: false
owner: example-operator
issued_at: "2099-01-01T00:00:00Z"
expires_at: "2099-01-02T00:00:00Z"
revoked_at: null
modes: [scheduled-propose]
lanes: [maintain]
actions: [deterministic-maintenance]
input_roots: []
writable_paths:
  - wiki/index.md
  - .wiki_cache/graph.json
  - reports/lint/**
  - reports/runs/**
  - reports/latest.json
page_types: []
required_checks: [quick-lint]
consequence_tier: routine
budgets:
  max_runtime_seconds: 300
  max_changed_paths: 25
  max_acquired_sources: 0
commit_policy: forbidden
commit_identity: null
governance_maintenance: false
```

Run it once under supervision before creating a schedule:

```bash
python3 tools/wiki_cron.py nightly --authority scheduled-maintainer-example
python3 tools/wiki_cron.py weekly --authority scheduled-maintainer-example
```

Weekly maintenance writes a lint report, so `reports/lint/**` must remain in scope. With `commit_policy: forbidden`, the controller never creates a commit; if generated files change, the result is left for human review and commit.

## Example: Managed Inbox Processing

Save as `schema/authorities/scheduled-ingest-example.yml`. This example leaves committing to the human. Add `preserve-unsupported` only if preservation-only handling of unsupported formats has been explicitly reviewed.

```yaml
schema_version: rb-wiki-authority-grant/0.2
authority_id: scheduled-ingest-example
enabled: false
owner: example-source-curator
issued_at: "2099-01-01T00:00:00Z"
expires_at: "2099-01-02T00:00:00Z"
revoked_at: null
modes: [scheduled-propose]
lanes: [ingest]
actions: [ingest-sources]
input_roots: [inbox]
writable_paths:
  - sources/raw/**
  - sources/derived/**
  - sources/_source_registry.yml
  - wiki/references/**
  - wiki/index.md
  - .wiki_cache/graph.json
  - reports/ingest/**
  - reports/runs/**
  - reports/latest.json
page_types: [Reference]
required_checks: [quick-lint]
consequence_tier: routine
budgets:
  max_runtime_seconds: 300
  max_changed_paths: 25
  max_acquired_sources: 10
commit_policy: manual
commit_identity: null
governance_maintenance: false
```

```bash
python3 tools/wiki_cron.py inbox --authority scheduled-ingest-example
```

The command may be launched by a human or scheduler; either way, it is a managed operation. Do not call `tools/ingest.py` directly outside the controller.

This example automates the ingest operation but deliberately keeps a human commit checkpoint. Consider `scoped-auto` only after repeated supervised runs; it also requires a reviewed `commit_identity`. A scoped commit remains local and never authorises a push.

## Example: Scheduled Synthesis Proposal

Save as `schema/authorities/scheduled-synthesizer-example.yml`. It may write proposal and semantic-evidence artifacts, but it cannot edit ordinary wiki pages.

```yaml
schema_version: rb-wiki-authority-grant/0.2
authority_id: scheduled-synthesizer-example
enabled: false
owner: example-synthesis-reviewer
issued_at: "2099-01-01T00:00:00Z"
expires_at: "2099-01-02T00:00:00Z"
revoked_at: null
modes: [scheduled-propose]
lanes: [synthesize]
actions: [propose-synthesis]
input_roots: []
writable_paths:
  - reports/proposals/**
  - reports/semantic/**
  - reports/runs/**
  - reports/latest.json
page_types: []
required_checks: [quick-lint]
consequence_tier: routine
budgets:
  max_runtime_seconds: 300
  max_changed_paths: 10
  max_acquired_sources: 0
commit_policy: manual
commit_identity: null
governance_maintenance: false
```

```bash
python3 tools/wiki_run.py start \
  --lane synthesize \
  --mode scheduled-propose \
  --authority scheduled-synthesizer-example
```

The external agent must produce one contract-valid proposal and matching semantic output, then finish the session. Review and commit those artifacts before any apply run.

## Example: Bounded Autonomous Apply

Save as `schema/authorities/autonomous-synthesis-example.yml`. This example can apply only an exact committed proposal to Synthesis pages and may create a local scoped commit. The controller still rejects any other content or path.

```yaml
schema_version: rb-wiki-authority-grant/0.2
authority_id: autonomous-synthesis-example
enabled: false
owner: example-synthesis-reviewer
issued_at: "2099-01-01T00:00:00Z"
expires_at: "2099-01-02T00:00:00Z"
revoked_at: null
modes: [authorised-autonomous-apply]
lanes: [synthesize]
actions: [edit-wiki-pages]
input_roots: []
writable_paths:
  - wiki/syntheses/**
  - reports/semantic/**
  - reports/runs/**
  - reports/latest.json
page_types: [Synthesis]
required_checks: [quick-lint]
consequence_tier: routine
budgets:
  max_runtime_seconds: 300
  max_changed_paths: 5
  max_acquired_sources: 0
commit_policy: scoped-auto
commit_identity:
  name: Example Wiki Agent
  email: wiki-agent@local.invalid
governance_maintenance: false
```

```bash
python3 tools/wiki_cron.py apply --authority autonomous-synthesis-example
```

The command reads only committed proposal and handoff artifacts, rejects unsafe or stale candidates, and selects at most one by `created_at` and `proposal_id`. It constructs the run-bound semantic record itself and applies only the exact payload. A scheduled job must invoke this wrapper; it must not select a proposal, start a session, edit pages, construct semantic JSON, or run Git commands itself.

High-consequence work also requires a separate committed, unexpired approval bound to the proposal digest. The wrapper finds and validates that approval deterministically. The proposing agent may not draft its own approval during the apply run.

Routing files are deliberately absent from this grant. The constrained apply validates without rebuilding `wiki/index.md` or `.wiki_cache/graph.json`; scheduled maintenance owns those derived artifacts.

## Activation Checks

Before the first real run:

```bash
python3 tools/capabilities.py --json
python3 tools/wiki_doctor.py --json
git status --short
git show HEAD:schema/authorities/AUTHORITY_ID.yml
```

The first two commands check the wiki and runtime environment. The `git show` command confirms the exact grant exists in the clean base. The controller performs the authoritative grant, lane, identity, time, path, page-type, budget, consequence, and commit-policy validation at `start` before it permits the agent to mutate the wiki.

For a manual session smoke test, start the session and immediately cancel it with its token. For scheduled work, run the real command once while observing its output and resulting report before creating a recurring schedule.

## Expiry And Revocation

- Keep validity windows short and renew grants through normal review and Git history.
- An expired grant cannot start or close an authorised run outside its validity window.
- To revoke future use, set `enabled: false` or set `revoked_at` to a current UTC timestamp, then commit the change.
- If a run is already active, cancel or fail that session explicitly. Do not assume that editing a working-tree grant silently terminates a run bound to an earlier clean base.
- Never reuse another grant's filename while changing its internal `authority_id`; the controller requires an exact match.
- Never broaden a grant merely to get past a controller error. Read the named lane contract and correct the workflow or grant deliberately.

No authority grant permits `git push`. A human or separately controlled release process always owns publication to a remote repository.
