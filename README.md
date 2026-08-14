# namemask

**Mask Japanese PII locally before sending text to an external AI, then restore it.**

[![CI](https://github.com/sou-kurakata/namemask/actions/workflows/ci.yml/badge.svg)](https://github.com/sou-kurakata/namemask/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/namemask.svg)](https://pypi.org/project/namemask/)
[![Python](https://img.shields.io/pypi/pyversions/namemask.svg)](https://pypi.org/project/namemask/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/sou-kurakata/namemask/blob/main/LICENSE)

日本語版: **[README.ja.md](https://github.com/sou-kurakata/namemask/blob/main/README.ja.md)**

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
namemask --version
```

No dictionary file or model download is required — the deterministic layers work
out of the box.

The masked text goes to stdout (or `-o`); the detection report and warnings go
to **stderr**, so piping stays clean. Messages are in Japanese, like the text
namemask is built for:

```console
$ cat memo.txt
株式会社サンプル商事の田中様より、新規案件のご連絡。
連絡先は tanaka@example.co.jp、電話 03-1234-5678。

$ namemask mask memo.txt --no-ner --address -o masked.txt
mapping 保存: .session/mapping.json（生の機密。復元後は `unmask --wipe` で破棄推奨）
=== マスク結果: 4 件 ===
  [[組織_1]]      組織      株式会社サンプル商事   <- structural
  [[人名_1]]      人名      田中   <- structural
  [[メール_1]]     メール     tanaka@example.co.jp   <- regex
  [[電話_1]]      電話      03-1234-5678   <- regex
※ 外部AIへ送る前に、上記の検出内容を必ずレビューしてください。

$ cat masked.txt
[[組織_1]]の[[人名_1]]様より、新規案件のご連絡。
連絡先は [[メール_1]]、電話 [[電話_1]]。
```

The report lists every masked value and **which layer found it** (`structural`,
`regex`, `denylist`, `address`, …) — that is what you review before sending.

Review `masked.txt`, paste it into your AI of choice, save the reply, then:

```console
$ namemask unmask reply.txt -o restored.txt --wipe
mapping 破棄: .session/mapping.json

$ cat restored.txt
株式会社サンプル商事の田中様へ、以下の返信案です。
ご不明点は tanaka@example.co.jp または 03-1234-5678 までご連絡ください。
```

The mapping is written to `.session/mapping.json` **under the current directory**
(file mode `0600`, directory `0700`) and read back from there by default — `-m`
overrides the path, `--no-save` keeps it in memory only. `--wipe` destroys it
after restoring, and `namemask wipe` destroys it at any time. The mapping
contains the real values, so treat it as the secret it is; `.session/` is in
this repository's `.gitignore`, but add it to yours too.

Two flags are worth knowing before your first real run:

- **`--address` is opt-in.** Without it, addresses and postal codes are *not*
  masked. If your text contains either, pass it.
- **`--no-ner` silences a startup notice.** The CLI attempts the NER layer by
  default and prints `NER disabled: spacy import failed (ModuleNotFoundError).
  Deterministic layers remain.` when the `ner` extra is not installed. That is
  fail-safe behaviour, not an error — but if you do not intend to use NER,
  `--no-ner` skips it explicitly.

### Reviewing before you send

`--html` writes a **self-contained review page** — every detected entity
highlighted, with which layer detected it and why:

```console
$ namemask mask memo.txt --no-ner --address --html review.html -o masked.txt
レビューHTML: review.html（原文を含む生の機密。外部に出さないこと。レビュー後は削除推奨）
```

No CDN, no external JavaScript, no network access. The page contains your
original text, so it is created with mode `0600` — the same protection the
mapping gets (POSIX only; Windows relies on ACLs). Delete it once you are done
reviewing. The masked output written by `-o` is not treated as secret.

### Your client dictionary

The dictionary layer is what gets you **100% recall on the clients you already
know about**, including informal names that carry no legal-entity suffix. Point
`--clients` at a CSV (`name,type,aliases`, aliases `|`-separated):

```console
$ cat clients.csv
name,type,aliases
株式会社サンプル商事,ORGANIZATION,サンプル|Sample Trading

$ echo 'サンプルの新プロジェクトについて、Sample Trading 側と調整中。' \
    | namemask mask --no-ner --clients clients.csv --no-save
=== マスク結果: 2 件 ===
  [[組織_1]]      組織      サンプル   <- denylist
  [[組織_2]]      組織      Sample Trading   <- denylist
※ 外部AIへ送る前に、上記の検出内容を必ずレビューしてください。
[[組織_1]]の新プロジェクトについて、[[組織_2]] 側と調整中。
```

Surface variants are expanded automatically — full-width / half-width, spaces
and hyphens, the bare core name (`サンプル商事`), and the legal-entity suffix in
either position (`株式会社サンプル商事` / `サンプル商事株式会社`). You list the
canonical name, not every spelling. See
[`data/clients.sample.csv`](https://github.com/sou-kurakata/namemask/blob/main/data/clients.sample.csv). Your real dictionary is
a business secret: keep it out of version control (`data/clients.csv` is
already gitignored).

> **Known limitation — half-width katakana with a (han)dakuten is not covered.**
> Normalization is applied character by character to keep offsets exact, so a
> sequence that is split across code points in the source (`ﾌ` + `ﾟ`) is not
> recombined, and `ｻﾝﾌﾟﾙ` will not match a dictionary entry spelled `サンプル`.
> Half-width katakana **without** a dakuten matches fine. Until this is fixed
> ([#4](https://github.com/sou-kurakata/namemask/issues/4)), add the half-width
> spelling as an alias — the key side goes through the same folding, so it
> matches:
>
> ```console
> $ cat clients.csv
> name,type,aliases
> 株式会社サンプル商事,ORGANIZATION,サンプル|Sample Trading|ｻﾝﾌﾟﾙ
>
> $ echo 'ｻﾝﾌﾟﾙの件でご連絡しました。' \
>     | namemask mask --no-ner --clients clients.csv --no-save
> === マスク結果: 1 件 ===
>   [[組織_1]]      組織      ｻﾝﾌﾟﾙ   <- denylist
> ※ 外部AIへ送る前に、上記の検出内容を必ずレビューしてください。
> [[組織_1]]の件でご連絡しました。
> ```

### As a library

```python
from namemask.api import mask_text, unmask_text

result = mask_text("株式会社サンプル商事の田中様", use_ner=False)
print(result.masked_text)   # [[組織_1]]の[[人名_1]]様
print(result.mapping)       # {'[[組織_1]]': '株式会社サンプル商事', '[[人名_1]]': '田中'}

restored = unmask_text(ai_reply, result.mapping)
print(restored.text)        # placeholders replaced with the real values
print(restored.unresolved)  # tokens with no mapping entry — reported, never guessed
```

The library API keeps the mapping **in memory only** — nothing is written to
disk unless you write it yourself. `mask_text()` takes `clients_csv=`,
`use_address=True` and `use_llm=True` for the layers the CLI exposes as flags.

---

## Accuracy

Measured on a golden corpus of **99 hand-labelled cases** (fictional names only),
using the deterministic layers plus the address layer — no NER, no LLM
(`make eval`, which runs `python tests/eval.py --address`):

| Metric | Result |
|---|---|
| Precision | **1.00** |
| Overall recall (partial match) | **97.7%** |
| Known clients from dictionary (all surface variants) | **100%** (9/9) |
| Regex targets (email / phone / My Number, incl. full-width) | **100%** (79/79) |
| Organizations with a legal-entity suffix (株式会社 etc.) | **100%** (22/22) |
| Addresses and postal codes (requires `--address`) | **100%** (5/5) |
| Round-trip exact match | **100%** |

**Without `--address`, overall recall is 95.9%** and the address type scores
zero — the flag is not a refinement, it is a whole category of PII. The
remaining 6 misses are all unknown proper nouns: 4 person names in signature
blocks with no honorific, and 2 company names with no legal-entity suffix that
are absent from the dictionary. Both are what the optional NER layer and your
own dictionary exist for.

Per-layer recall contribution, measured by removing one layer at a time:
`structural` −36.4% · `regex` −29.4% · `denylist` −4.8% · `address` −1.9%.

These numbers are enforced as CI thresholds — if a change drops them, the build
fails. See [`docs/accuracy.md`](https://github.com/sou-kurakata/namemask/blob/main/docs/accuracy.md) for the methodology and the
full miss list.

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
   surface-variant expansion, matched on a second, folded shadow text.
5. **Address layer** (`--address`) — postal codes and prefecture-anchored
   addresses.
6. **Span merger** — boundary expansion, overlap resolution, type priority, and
   propagation of organization core names across the document.
7. **Replacement** — applied back-to-front on original coordinates. Identical
   surface forms always get the identical token.

Two **optional, additive** layers can be added on top. Neither ships with the
default install:

- **NER** (`pip install namemask[ner]`) — GiNZA / spaCy, for unknown proper
  nouns. Once installed the CLI uses it automatically; `--no-ner` skips it.
- **LLM verifier** (`--llm`) — a local Ollama model that may only *add* masks,
  never remove them. Restricted to loopback endpoints, off unless you ask for it.
  Ollama is a separate process, so there is no Python dependency to install.

Both are fail-safe: if the model is missing or errors, the deterministic floor
remains — the layer drops out, the pipeline does not. See
[`docs/design.md`](https://github.com/sou-kurakata/namemask/blob/main/docs/design.md).

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
  99 cases. Unknown proper nouns — especially rare surnames, informal company
  names, and project codenames — will be missed. Add them to your dictionary.
- **Always have a human review the masked output.** namemask is designed as a
  review aid, not an automated gate. That is why it never sends anything for
  you: there is no "mask and submit" command, by design. Read the stderr report
  or the `--html` page before you paste.
- **"Masked" does not mean "cleared for external use."** Some data categories
  must not go to an external AI even pseudonymized. That line is your
  organization's policy to draw, not this tool's.
- **Japanese only.** The structural and dictionary layers are built around
  Japanese orthography and business conventions.
- **The mapping file is raw secret data.** If you persist it, protect it and wipe
  it — `--wipe` after restoring, or `--encrypt` to store it AES-encrypted
  (`pip install namemask[crypto]`, passphrase via the `NAMEMASK_PASSPHRASE`
  environment variable).

No warranty of any kind — see [LICENSE](https://github.com/sou-kurakata/namemask/blob/main/LICENSE).

---

## Scope of this repository

This repository is the **detection engine and CLI**. That is deliberate — see
[ADR-0011](https://github.com/sou-kurakata/namemask/blob/main/docs/adr/0011-scope-oss-repo-to-core-and-cli.md).

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
| [`docs/design.md`](https://github.com/sou-kurakata/namemask/blob/main/docs/design.md) | Architecture and detection-layer design |
| [`docs/accuracy.md`](https://github.com/sou-kurakata/namemask/blob/main/docs/accuracy.md) | Golden corpus, evaluation method, measured results |
| [`docs/security.md`](https://github.com/sou-kurakata/namemask/blob/main/docs/security.md) | Threat model, invariants, vulnerability reporting |
| [`docs/adr/`](https://github.com/sou-kurakata/namemask/tree/main/docs/adr/) | Architecture Decision Records — why it is built this way |
| [`CONTRIBUTING.md`](https://github.com/sou-kurakata/namemask/blob/main/CONTRIBUTING.md) | How to contribute (read this before filing a detection miss) |

The ADRs are worth a look if you are evaluating namemask — every non-obvious
design decision is written down with the options that were rejected and why.

---

## Contributing

Contributions are welcome — especially **detection misses**. If namemask failed
to mask something, please file an issue with a reproduction case using
**fictional names only**. See [CONTRIBUTING.md](https://github.com/sou-kurakata/namemask/blob/main/CONTRIBUTING.md).

## License

MIT © sou-kurakata — see [LICENSE](https://github.com/sou-kurakata/namemask/blob/main/LICENSE).
