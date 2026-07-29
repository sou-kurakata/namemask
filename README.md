# namemask

**Mask Japanese PII locally before sending text to an external AI, then restore it.**

[![CI](https://github.com/sou-kurakata/namemask/actions/workflows/ci.yml/badge.svg)](https://github.com/sou-kurakata/namemask/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/namemask.svg)](https://pypi.org/project/namemask/)
[![Python](https://img.shields.io/pypi/pyversions/namemask.svg)](https://pypi.org/project/namemask/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)

日本語版: **[README.ja.md](./README.ja.md)**

---

## Why

You want to use ChatGPT / Claude / Gemini on internal Japanese business text —
a meeting note, a customer email, a contract draft. But it contains client
company names, personal names, phone numbers and addresses that must not leave
your machine.

namemask pseudonymizes those entities **locally**, gives you the masked text to
paste into the AI, and restores the real names in the AI's reply.

```
your text ──[namemask mask]──> masked text ──> external AI ──> reply
                                                                 │
your text with real names <──[namemask unmask]───────────────────┘
```

**Zero network access. No telemetry. Nothing is uploaded — namemask never talks
to the AI for you.** You copy and paste, so you always see what leaves your machine.

---

## Quickstart

```bash
pip install namemask
```

No dictionary file or model download is required — the deterministic layers work
out of the box.

```console
$ cat memo.txt
株式会社サンプル商事の田中様より、新規案件のご連絡。
連絡先は tanaka@example.co.jp、電話 03-1234-5678。

$ namemask mask memo.txt -o masked.txt
$ cat masked.txt
[[組織_1]]の[[人名_1]]様より、新規案件のご連絡。
連絡先は [[メール_1]]、電話 [[電話_1]]。
```

Review `masked.txt`, paste it into your AI of choice, save the reply, then:

```console
$ namemask unmask reply.txt -m .session/mapping.json -o restored.txt --wipe
```

`--wipe` destroys the mapping file afterwards. The mapping contains the real
values, so treat it as the secret it is.

### Reviewing before you send

`--html` writes a **self-contained review page** — every detected entity
highlighted, with which layer detected it and why:

```console
$ namemask mask memo.txt --html review.html -o masked.txt
```

No CDN, no external JavaScript, no network access. Note that the page contains
your original text, so treat it like the mapping.

<!-- TODO(P2-5): confirm the exact CLI output above against the installed version
     before publishing. Placeholder format is [[<label>_<n>]] (core/replacer.py). -->

### As a library

```python
from namemask import mask_text, unmask_text

result = mask_text("株式会社サンプル商事の田中様", use_ner=False)
print(result.masked_text)   # [[組織_1]]の[[人名_1]]様
print(result.mapping)       # {"[[組織_1]]": "株式会社サンプル商事", ...}

restored = unmask_text(ai_reply, result.mapping)
print(restored.text)
```

The library API keeps the mapping **in memory only** by default.

---

## Accuracy

Measured on a golden corpus of **91 hand-labelled cases** (fictional names only),
using the deterministic layers plus the address layer — no NER, no LLM:

| Metric | Result |
|---|---|
| Precision | **1.00** |
| Overall recall (partial match) | **97.7%** |
| Known clients from dictionary (all surface variants) | **100%** |
| Regex targets (email / phone / My Number, incl. full-width) | **100%** |
| Organizations with a legal-entity suffix (株式会社 etc.) | **100%** |
| Round-trip exact match | **100%** |

These numbers are enforced as CI thresholds — if a change drops them, the build
fails. See [`docs/accuracy.md`](./docs/accuracy.md) for the methodology, the
per-layer ablation, and the remaining false negatives.

---

## How it works

namemask is **not** a general PII framework wrapper. It is a thin, deterministic
pipeline built specifically for Japanese business text:

1. **Normalization** — an NFKC shadow copy with a character map, so full-width
   and half-width variants match while offsets still point at the original text.
2. **Regex layer** — email, phone (incl. 5-digit area codes), My Number with
   check-digit validation.
3. **Structural layer** — the main recall driver. Legal-entity suffixes
   (`株式会社` / `有限会社` / `㈱` …) anchor organizations; honorifics
   (`様` / `さん` / `部長` …) anchor person names.
4. **Dictionary layer** — your known client list via Aho-Corasick, with automatic
   surface-variant expansion, matched on a folded shadow text.
5. **Address layer** — postal codes and prefecture-anchored addresses.
6. **Span merger** — boundary expansion, overlap resolution, type priority, and
   propagation of organization core names across the document.
7. **Replacement** — applied back-to-front on original coordinates. Identical
   surface forms always get the identical token.

Two **optional, additive, off-by-default** layers can be added on top:

- **NER** (`pip install namemask[ner]`) — GiNZA / spaCy, for unknown proper nouns.
- **LLM verifier** (`pip install namemask[llm]`) — a local Ollama model that may
  only *add* masks, never remove them. Restricted to loopback endpoints.

Both are fail-safe: if the model is missing or errors, the deterministic floor
remains. See [`docs/design.md`](./docs/design.md).

---

## Design guarantees

These are invariants, not goals. They are enforced by tests.

- **Reversible.** `unmask(mask(x))` reproduces the original text exactly.
- **Consistent.** The same surface form always maps to the same token, document-wide.
- **Original text is never rewritten.** Normalization happens on a shadow copy;
  replacement always targets original coordinates.
- **Deterministic.** Same input, same output. No agent loop drives the core.
- **Recall-first.** A miss is a leak; an over-mask is an inconvenience. When in
  doubt, namemask masks.
- **No values are invented.** Unresolvable tokens are reported, never guessed.
- **Zero outbound network traffic.** Including telemetry. The LLM endpoint is
  restricted to loopback unless you explicitly opt out.

---

## Limitations

**Please read this before relying on namemask.**

- **namemask does not guarantee 100% recall.** The measured figure is 97.7% on
  91 cases. Unknown proper nouns — especially rare surnames, informal company
  names, and project codenames — will be missed.
- **Always have a human review the masked output.** namemask is designed as a
  review aid, not an automated gate. The optional local UI deliberately provides
  no "send without reviewing" path.
- **"Masked" does not mean "cleared for external use."** Some data categories
  must not go to an external AI even pseudonymized. That line is your
  organization's policy to draw, not this tool's.
- **Japanese only.** The structural and dictionary layers are built around
  Japanese orthography and business conventions.
- **The mapping file is raw secret data.** If you persist it, protect it and wipe
  it (`--wipe`, or `--encrypt` for AES-encrypted storage).

No warranty of any kind — see [LICENSE](./LICENSE).

---

## Scope of this repository

This repository is the **detection engine and CLI**. That is deliberate — see
[ADR-0011](./docs/adr/).

An interactive review UI (un-mask a false positive, add a missed entity by
selecting text) and a Windows desktop build exist as a separate project and are
not part of this package. If you want an interactive loop today, use `--html` to
review, edit the input, and re-run — or drive `mask_text()` from your own code.

Interested in a `namemask serve` subcommand? Open an issue; demand is what will
decide whether the UI is folded back in for v0.2.0.

---

## Documentation

| | |
|---|---|
| [`docs/design.md`](./docs/design.md) | Architecture and detection-layer design |
| [`docs/accuracy.md`](./docs/accuracy.md) | Golden corpus, evaluation method, measured results |
| [`docs/security.md`](./docs/security.md) | Threat model, invariants, vulnerability reporting |
| [`docs/adr/`](./docs/adr/) | Architecture Decision Records — why it is built this way |
| [`CONTRIBUTING.md`](./CONTRIBUTING.md) | How to contribute (read this before filing a detection miss) |

The ADRs are worth a look if you are evaluating namemask — every non-obvious
design decision is written down with the options that were rejected and why.

---

## Contributing

Contributions are welcome — especially **detection misses**. If namemask failed
to mask something, please file an issue with a reproduction case using
**fictional names only**. See [CONTRIBUTING.md](./CONTRIBUTING.md).

## License

MIT © sou-kurakata — see [LICENSE](./LICENSE).
