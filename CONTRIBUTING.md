# Contributing to AIEASS

Thank you for helping make affective agent systems more transparent,
testable, and honest about their limits.

## Good contributions

- Additional agent lifecycle adapters
- Deterministic tests and upstream parity fixtures
- Benchmarks against a no-affect baseline
- Persistence, concurrency, and protocol hardening
- Documentation, reproducible examples, and accessibility improvements
- Careful research that distinguishes software control signals from human emotion

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[mcp,dev]"
python -m unittest discover -s tests -v
ruff check src tests examples
ruff format --check src tests examples
python -m build
```

Please keep the core deterministic and free of model or network calls. New
event templates should document their rationale and include tests. Changes to
the Helix compatibility profile must be opt-in unless they fix a security or
data-integrity problem.

## Licensing

Contributions must respect the mixed provenance described in `NOTICE.md`.
Do not remove upstream copyright or AGPL notices from derived material.
