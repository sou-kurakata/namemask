# Contributing to namemask

日本語 / English are both fine in issues and PRs.
Feel free to write in Japanese — the maintainer is a Japanese speaker.

---

## Before anything else: never commit real data

namemask handles confidential text. **A single real name in this repository
destroys the tool's credibility.**

- **Use fictional names only** — in tests, docs, comments, issue bodies, and
  commit messages. No real people, companies, addresses, phone numbers, or emails.
- Never commit `data/clients.csv` or `data/persons.csv` (gitignored).
- Never commit `.session/` or `*.mapping.json` — a mapping file contains the raw
  secret values.
- Use `example.com` / `example.co.jp` for emails, and clearly invented company
  names like `株式会社サンプル商事`.

If you accidentally push real data, tell the maintainer immediately via a
[security advisory](https://github.com/sou-kurakata/namemask/security/advisories/new)
rather than a public issue.

---

## Reporting a detection miss (the most valuable contribution)

namemask does not achieve 100% recall, so misses are expected and reports are
genuinely welcome. To be actionable, a report needs a **reproduction case built
from fictional names**:

```markdown
## Input (fictional names only)
弊社の担当は㈲テスト設計の佐々木さんです。

## Expected
㈲テスト設計 → ORGANIZATION
佐々木        → PERSON

## Actual
㈲テスト設計 → detected
佐々木        → NOT detected

## Environment
namemask 0.1.0 / Python 3.12 / no dictionary / --address off
```

Use the **Detection miss** issue template — it asks for exactly this.

> If your real-world miss can't be reproduced with fictional names, describe the
> *shape* of the problem (e.g. "surname written in hiragana, followed by 課長")
> without pasting the real text.

---

## Development setup

```bash
git clone https://github.com/sou-kurakata/namemask.git
cd namemask
make install
make test
make eval
```

This repository is the **detection engine and CLI only** — see
[ADR-0011](./docs/adr/). The interactive review UI and the Windows desktop build
live in a separate project. PRs adding a web server, a frontend framework, or
PyInstaller packaging here will be declined; open an issue instead so the scope
decision can be revisited deliberately.

Optional layers need extra setup and are **skipped in CI**:

```bash
pip install -e ".[ner]" && python -m spacy download ja_ginza   # NER
# LLM: run Ollama locally, then `make test-all`
```

---

## Invariants — changes that will not be accepted

These are enforced by tests and are not open to negotiation. See
[`docs/security.md`](./docs/security.md) and [`docs/adr/`](./docs/adr/).

1. **Reversibility.** `unmask(mask(x))` must reproduce the original exactly.
2. **Consistency.** The same surface form must always get the same token.
3. **The original text is never rewritten.** Normalize on a shadow copy only.
4. **Determinism.** No agent loop or nondeterministic model in the core path.
5. **The LLM layer may only add masks**, never remove or alter them.
6. **No values are invented.** Unresolvable tokens are reported, not guessed.
7. **Zero outbound network traffic**, telemetry included. The LLM endpoint stays
   loopback-only unless `llm.allow_remote` is explicitly set.
8. **No raw text in logs or exception messages.**
9. **The mapping is raw secret data.** In-memory by default for the library API;
   restricted directory, 0o700/0o600, gitignored, and a stderr warning when the
   CLI persists it.
10. **`--html` output stays self-contained.** No CDN, no external JavaScript.

If you believe an invariant is wrong, **open an issue proposing an ADR** rather
than a PR that changes behaviour.

---

## Changing a detector

Detection accuracy is the core value of this project, so detector changes have a
higher bar:

1. **Add the case to the golden corpus first** (`tests/golden/corpus.json`,
   fictional names). Watch it fail.
2. Implement the change.
3. **Run `make eval` and put the before/after numbers in the PR description.**
   Recall, precision, and the per-layer ablation.
4. CI enforces thresholds (precision ≥ 1.00 exact-layer, overall recall ≥ 95%,
   round-trip 100%). **A PR that lowers these will not merge.**
5. Over-masking is acceptable; under-masking is not. When trading off, choose recall.

Adding cases that *lower* recall is welcome — it makes a real gap visible. Say so
in the PR so the threshold discussion happens deliberately, not accidentally.

---

## Testing

| Layer | Tool | Notes |
|---|---|---|
| Core / detectors | pytest | must pass on Ubuntu py3.10–3.12, and Windows / macOS py3.12 |
| Round-trip properties | hypothesis | property-based, always runs |
| Evaluation harness | `tests/eval.py` | CI threshold gate |
| NER / LLM | pytest markers `ner` / `llm` | skipped in CI, run locally |
| Install smoke test | CI `smoke` job | `pip install .` then round-trip with no dictionary |

Write the acceptance test before the implementation (existing project policy).

---

## Architecture Decision Records

Any non-obvious design decision gets an ADR **before** implementation.
Copy [`docs/adr/template.md`](./docs/adr/template.md), take the next number, and
record the options you rejected and why. The index is
[`docs/adr/README.md`](./docs/adr/README.md).

## Documentation policy

`docs/design.md` describes the **current** design only. Do not append history
("changed in P3.5", "reflects M2 review") — that belongs in an ADR. Do not create
versioned design documents (`design-v2.md`); edit the existing one.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/): `feat:` `fix:`
`docs:` `test:` `refactor:` `chore:` `perf:`. English or Japanese, either is fine.

## License

By contributing you agree that your contribution is licensed under the
[MIT License](./LICENSE).
