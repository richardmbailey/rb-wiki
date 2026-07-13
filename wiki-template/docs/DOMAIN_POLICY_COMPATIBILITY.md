# Domain policy compatibility

Core RB Wiki policy is subject-neutral. Existing subject-specific source hierarchies, admissibility rules, ontology labels, assessment requirements, reviewer roles, or approval thresholds belong in `schema/domain_policy.yml`, not in controller branches or generic prompts.

Start from the disabled generic example and enable only reviewed local rules. A domain policy may narrow `allowed_source_types`, raise an action's minimum consequence tier, require additional assessment notes, constrain reviewer roles, or declare local ontology metadata. It cannot turn off raw immutability, provenance, authority, Git reconciliation, or high-consequence payload binding; the schema fixes those invariants to `true`, and the controller rejects a domain threshold below the core consequence policy.

Conversion procedure:

1. Move named-domain terminology and source hierarchy into the adapter.
2. Map intended uses and action classes to `routine`, `material`, or `high-consequence` based on possible impact—not the domain or source identity alone.
3. Preserve generic core invariants unchanged.
4. Validate the adapter and test one allowed and one rejected scenario before enabling it.
5. Keep human approval roles local; never encode a named organisation in the public template.

Unknown or ambiguous legacy policy must remain disabled and be routed to manual review rather than guessed.
