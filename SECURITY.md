# Security Policy

## Reporting a vulnerability

**Do not open a public issue for a security vulnerability.**

Use GitHub's private reporting:
[Report a vulnerability](https://github.com/sou-kurakata/namemask/security/advisories/new)

Expect an initial response within 7 days. This is a small project maintained in
spare time; please allow reasonable time for a fix before public disclosure.

## In scope

namemask's security value is "confidential text does not leave the machine."
The following are in scope:

- **Data egress** — any path by which raw text, a mapping, or a token reaches the
  network. Including dependency telemetry.
- **Loopback bypass** — sending text to a non-loopback LLM endpoint without
  `llm.allow_remote: true` being explicitly set.
- **Secret leakage into artifacts** — raw text appearing in logs, exception
  messages, or a published distribution (e.g. test fixtures containing real data,
  or a dictionary file bundled into a wheel).
- **`--html` review output** — anything that makes the generated page reach the
  network (an injected external reference, an unescaped payload).
- **Mapping file handling** — incorrect permissions, writing outside the
  designated directory, or encryption that fails to detect tampering.
- **Restore-path integrity** — producing a plausible-but-wrong original value
  instead of reporting failure.

## Out of scope

- **Detection misses are not vulnerabilities.** namemask does not claim 100%
  recall (measured: 97.7%). Report a miss as a regular issue using the
  *Detection miss* template. See [Limitations](./README.md#limitations).
- Attacks requiring an attacker who already has local code execution or
  filesystem access as the same user.
- Weaknesses in third-party models (GiNZA, Ollama models) themselves.
- The absence of a feature (e.g. "there is no audit log").
- The local HTTP server and desktop application — those are **not part of this
  package** (see [ADR-0011](./docs/adr/)). Report those separately.

## A note on the threat model

namemask is a **review aid**, not an automated boundary. It is designed on the
assumption that a human reads the masked output before sending it anywhere.
See [`docs/security.md`](./docs/security.md) for the full threat model.
