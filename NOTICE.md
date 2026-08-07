# AIEASS provenance and licensing notice

## Repository licensing

The root `LICENSE` file is the Apache License 2.0 selected for original AIEASS
wrapper, integration, documentation, and newly authored support material.

The affect-field implementation is a derivative extraction of AGPL-licensed
Helix-AGI material. Those derived portions retain the GNU Affero General Public
License, version 3 or later. The complete upstream license text is included at
`LICENSES/AGPL-3.0-or-later.txt`.

Because the distributed Python package combines the affect core with the new
wrapper material, the package metadata identifies AGPL-3.0-or-later as the
effective distribution license. Apache-2.0 material remains available under
its Apache terms; the combined work must also satisfy the applicable AGPL
conditions.

## Upstream source

This package extracts the Plutchik affect subsystem from
[`munch2u-a11y/Helix-AGI`](https://github.com/munch2u-a11y/Helix-AGI), specifically:

- `core/affect_field.py`
- `core/affect_hook.py`
- `tests/test_affect_dampening.py`

Compatibility baseline:
`c599233b7a444e9a4e4271de401bd1589606909a` (2026-08-07).

Helix AGI is Copyright (c) 2026 Helix AGI Contributors.

## Material changes

- Removed lifecycle coupling to the Helix pulse loop, stability sentinel,
  spatial mind, preconscious layer, dashboard, and data-directory convention.
- Moved constants into an injectable `AffectConfig` while preserving defaults.
- Added direct affect-vector and deterministic operational-event inputs.
- Added validation, thread safety, per-session isolation, and atomic state saves.
- Added a framework-neutral JSONL protocol and optional MCP 2.x server.
- Made surfaced-memory ordering deterministic.
- Retained the upstream amplitude-floor-before-gate behavior by default and
  exposed an explicit corrected-gate configuration.
- Added golden regression values generated from the upstream implementation.

This notice is informational and does not replace either license text.
