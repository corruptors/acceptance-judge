# AcceptanceJudge

A reusable **acceptance-adjudication primitive** for GenLayer: it decides, by
validator consensus, whether a delivered piece of work meets the acceptance
criteria that two parties agreed on in advance.

Freelance milestones, bounty deliverables, grant reports, contest entries —
all of them end with the same subjective question: *"did the work actually
satisfy what was asked?"* A normal smart contract cannot answer that. A
single backend or a single AI call can, but neither counterparty has a reason
to trust it. AcceptanceJudge puts exactly that decision on-chain, where
GenLayer's validators independently re-check the evidence and agree on the
outcome.

## How it works

1. **Open a case** — the client records a title, the worker's address, and
   1–8 acceptance criteria. Criteria are short natural-language statements
   written to be independently checkable from evidence alone, e.g.
   *"The page states the total number of entries reviewed"*.
2. **Submit evidence** — the worker attaches evidence as inline text and/or
   a public URL. Evidence can be replaced freely until a verdict exists.
3. **Evaluate** — anyone triggers evaluation. The leader fetches the URL
   evidence (rendered as text), judges every criterion against the evidence,
   and returns a structured verdict. Validators independently repeat the
   judgement and vote on it (see *Consensus design*).
4. **Verdict** — derived deterministically from the agreed verdict vector:
   `ACCEPTED` only if **every** criterion is met, otherwise `REJECTED`.
   Per-criterion results, the leader's reasons, and a summary are stored
   on-chain for audit.
5. **Appeal** — either party may send a decided case back exactly once,
   for re-evaluation against fresh evidence.

## Consensus design

The interesting part of an Intelligent Contract is not the prompt — it is
what validators are asked to agree on.

- **Verdict-vector equivalence.** Validators never compare prose. Each
  validator re-runs the evaluation and agrees with the leader only if the
  boolean verdict vector (one bool per criterion, in order) is identical.
  Reasons and summaries are stored for transparency but deliberately
  excluded from equivalence: two honest validators phrase reasons
  differently, but a criterion is either demonstrably met by the evidence
  or it is not. This keeps consensus strict exactly where money-relevant
  state changes depend on it, and tolerant where wording naturally varies.
- **Classified failures.** An unreachable evidence URL is deterministic —
  leader and validator raise the same `EVIDENCE_UNREACHABLE` error and
  agree, so the transaction settles as a clean failure instead of churning.
  Malformed LLM output is *not* agreed on: the validator disagrees, which
  rotates the leader rather than locking in a broken verdict.
- **Untrusted evidence.** Evidence is supplied by the worker — the party
  with the most to gain from a favourable verdict. The evaluation prompt
  wraps evidence in data tags and instructs the model to treat it strictly
  as data to be judged, never as instructions. Prompt-injection text inside
  evidence therefore has to fool a strict rubric *and* a majority of
  independent validators, not one model call.
- **Minimal non-determinism.** Everything except the per-criterion
  judgement is deterministic contract code: state transitions, the
  all-criteria rule, appeal limits, and access control.

## State design

| Field | Notes |
|---|---|
| `client` / `worker` | The two parties; set at case creation / by parameter |
| `criteria` | `DynArray[str]`, 1–8 items, ≤280 chars each |
| `evidence_url` / `evidence_text` | Worker's evidence; URL is fetched and rendered as text at evaluation time |
| `status` | `OPEN` → `SUBMITTED` → `DECIDED` (appeal returns to `OPEN`) |
| `verdict` | `ACCEPTED` / `REJECTED`, derived from the agreed vector |
| `met` / `reasons` / `summary` | The agreed verdict vector + leader's audit trail |
| `appeals_used` | Capped at 1 |

## Using it from another contract or app

Any escrow, marketplace, or grant contract can treat a case verdict as its
release condition: open a case when work is commissioned, read
`get_case(case_id)["verdict"]` after evaluation, and settle funds on
`ACCEPTED`. The primitive owns no funds itself, which keeps it composable
and auditable.

## Develop

```bash
pip install genlayer-test genvm-linter pytest   # or use the project venv
genvm-lint check contracts/acceptance_judge.py
pytest tests/direct/ -v
```

Direct-mode tests mock the LLM (the same mocked answer serves leader and
validators, so the verdict-vector consensus path is exercised
deterministically) and cover: criteria validation, worker-only evidence,
evaluation gating, accept and reject flows, and the single-appeal rule.

Deploy with the GenLayer CLI (`genlayer deploy`) to Studionet for a quick
check, then to Testnet Bradbury for production-like validation.

## Licence

MIT
