# Quantis documentation

The [root README](../README.md) is **what exists and how to run it**. This folder
holds design, progress evidence, and caveats — not duplicated on the landing page.

| Doc | What it is for |
|---|---|
| [PLAN.md](PLAN.md) | Design rationale, stack decisions, and remaining phases |
| [PROGRESS.md](PROGRESS.md) | What is built and verified, with row counts and tests |
| [LIMITATIONS.md](LIMITATIONS.md) | Data/model caveats — for people extending or evaluating the system |
| [../frontend/README.md](../frontend/README.md) | How to run the Next.js dashboard |
| [../design/README.md](../design/README.md) | Approved UI mockups |

When a phase lands, update **PROGRESS.md** and the matching **Status** note in
`PLAN.md`. Do not put the roadmap or limitation write-ups back into the README.

## TODO — Sphinx site (Phase 11, last)

Ship a real docs build so the repo demonstrates **dev practice**, not only a
portfolio README:

- Sphinx + autodoc + Napoleon (Google/NumPy docstrings already in `src/quantis/`)
- MyST so these markdown pages are included, not rewritten as `.rst`
- `sphinx-apidoc` over `src/quantis` → API reference
- `uv` `docs` extra: `sphinx`, `sphinx-autodoc-typehints`, `myst-parser`
- Build: `uv run sphinx-build -b html docs docs/_build/html`
- Optional later: GitHub Pages from CI

**Do not start this until Phases 4–7 exist.** An empty autodoc tree is worse than
waiting. Until then, keep writing docstrings — Sphinx will harvest them.
