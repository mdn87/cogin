# Local human review console

The collection console presents one anonymous patch at a time, counts selected
changed lines, saves drafts, requires reasons and a blind attestation, and locks
submitted scores through the existing validator. It serves neither the
controller mapping nor capture directories. Access uses a private token on
loopback with Host/Origin checks; source code and request payloads render as text.

The supervised tab starts one Claude or Codex task at a time and forwards only
an explicit Allow once or Deny click for the current request. Stale decisions
are rejected; stopping or timing out sends no grant. Capture manifests identify
the browser channel and hash its host code and assets. The terminal workflow
remains supported. agy has no supported headless approval response channel.

Validation on 2026-10-24:

- 62 harness tests passed, including real Chromium interaction with a synthetic
  review package: line selection, autosave, reload, explicit zero, submission,
  locked reload, and a simulated approval request denied through the page.
- Synthetic native CLI processes exercised the browser decision provider for
  allow, deny, and stop; they are transport tests, not human measurements.
- HTTP checks reject missing tokens, foreign origins, and private-file paths.
  Manual score forms and stale drafts are preserved. Chromium rendered an
  HTML-like request as inert text, with no page errors.
- Desktop and 390-pixel mobile screenshots were inspected. The mobile page had
  no horizontal document overflow. Screenshots remain in ignored audit artifacts.
- The real six-case package loaded with 107, 119, 111, 128, 141, and 167 changed
  lines. No real review was submitted and no live supervised task was launched
  during validation. Historical v2 trial artifacts remain unchanged.

Submission and session completion prepare private derived reports and a
collection summary. Dias publication still requires controller validation;
the console does not silently update the board. Actual human scores remain
uncollected. These interface checks establish neither a model ranking nor a
live positive-approval qualification.

See the [operator guide](../../src/agent-cli-harness/HUMAN_REVIEW.md) to start the
console or use the existing terminal collection workflow.
