# Adversarial Reproduction Matrix

These eight review failures are preserved as named, repeatable regression targets. Run commands use the declared test environment from `wiki-template/` unless the path starts at the repository root.

| Confirmed review failure | Regression target | Command |
|---|---|---|
| Scheduled maintenance could edit and auto-commit an ordinary page | `test_lane_runtime_enforcement.py` | `python -m unittest -v tests/test_lane_runtime_enforcement.py` |
| Requested authority filename could alias a different internal identity | `test_authority_identity_binding.py` | `python -m unittest -v tests/test_authority_identity_binding.py` |
| A duplicate later `pass` could mask an earlier failed external check | `test_external_check_integrity.py` | `python -m unittest -v tests/test_external_check_integrity.py` |
| External-session contention was overwritten from blocked to failed | `test_external_session_contention.py` | `python -m unittest -v tests/test_external_session_contention.py` |
| Branch movement followed by index refresh failure lost the commit identity | `test_post_cas_fault_injection.py` | `python -m unittest -v tests/test_post_cas_fault_injection.py` |
| Cron exceptions after start stranded a running journal and lock | `test_cron_exception_safety.py` | `python -m unittest -v tests/test_cron_exception_safety.py` |
| Migration could read through a symlinked parent and disclose external content | `tests/test_migration_parent_symlink_safety.py` | `python -m unittest -v tests/test_migration_parent_symlink_safety.py` from the repository root |
| Provenance accepted orphan raw files and unregistered/duplicate References | `test_provenance_reverse_reconciliation.py` | `python -m unittest -v tests/test_provenance_reverse_reconciliation.py` |

The Phase 1 targets are implemented first. Later phase targets remain part of the release gate and must be added red-before-green in their owning phase; this matrix is not evidence that an unimplemented target passes.
