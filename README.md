# Live Multi-Agent PR Reviewer — Core MVP

An observable, autonomous AI engineering review system: a conditional multi-agent graph that
investigates a GitHub Pull Request, validates and criticizes its own findings, and produces a
real code review — with every agent, tool call, condition, and token spent visible in a live
React Flow dashboard.

This is **not** a chatbot wrapped around an LLM. It is a graph of specialized agents that run
deterministic Python analysis first and only call an LLM when genuine reasoning is required.

> Full target architecture is documented in [`prd.md`](./prd.md). This repository implements the
> **Core MVP slice** of that spec — see [Scope](#scope) below for what's built vs. deferred.

---

## Problem

PR review is expensive human attention spent on things a computer can check deterministically
(lint violations, missing tests, obvious security patterns) *and* things that need real judgment
(is this authorization check actually missing, is this the right architectural boundary). Most
"AI PR reviewer" tools either hallucinate findings from a single LLM call over the diff, or are
opaque about what they actually checked.

## Solution

A **conditional agent graph**, not a linear pipeline:

```
Orchestrator → Impact Analyzer (deterministic)
                     │
        ┌──────┬─────┼─────┬──────┬─── ... 23 agents total ───┐
        ▼      ▼     ▼     ▼      ▼                            ▼
   Security  Bug   Test  Perf  Reliability  ...  Accessibility(if frontend_changed)
        └──────┴─────┼─────┴──────┴────────────────────────────┘
                      ▼
                  Validator            (bounded self-loop re-analysis)
                      ▼
                   Critic              (bounded loop back to Validator on weak evidence)
                      ▼
             Conflict Resolver         (deterministic cross-agent overlap detection)
                      ▼
               Debate Agent            (LLM-mediated arbitration, only when a genuine conflict exists)
                      ▼
               Final Review
                      ▼
              Human Approval
                      ▼
              GitHub Publish
```

Every arrow above is a **conditional edge** — evaluated deterministically (never by an LLM) and
visible in the frontend as it fires. Every agent runs deterministic tools *before* ever
considering an LLM call, and every avoided LLM call is tracked and shown in the Token Dashboard.

---

## Scope

**Built (this repo):**
- Real conditional graph engine with a safe, sandboxed condition evaluator (no `eval`)
- Event bus + WebSocket streaming of every state change, backed by SQLite so history survives a
  backend restart
- Shared evidence store + structured agent-to-agent message protocol (references, not blobs)
- All 22 named spec agents plus a 23rd, Debate Agent: Orchestrator, Impact Analyzer, Security, Bug
  Detection, Test, Performance, Documentation, Dependency, Reliability, API Contract, Database,
  Observability, Architecture, Code Impact, Static Analysis, Accessibility, CI Investigator,
  Requirement (Jira), Validator, Critic, Conflict Resolver, Debate, Final Review — see
  [`STATUS.md`](./STATUS.md) for what each one actually does and which are conditionally activated
- Multi-agent debate: when Conflict Resolver's deterministic clustering finds two agents disagreeing
  sharply on severity at the same location, Debate Agent exchanges each side's evidence as real
  agent-to-agent messages (visible in the Communication Feed), then asks an impartial arbiter LLM
  whether they describe the same underlying issue (reconcile to one severity) or are genuinely
  independent findings that just happen to be nearby (leave both untouched) — zero conflicts this
  run means zero LLM calls, a tracked avoided call rather than a skipped feature
- Deterministic tools: git-diff/unidiff parsing, Python AST analysis, regex security/secret/
  accessibility heuristics, `networkx` import/call-graph analysis, ruff, semgrep, pylint (all
  three real-subprocess with graceful not-installed fallback), static + optional real pytest
  execution
- Real GitHub webhook receiver with HMAC signature verification, real PR/file/diff/CI-workflow-run
  fetching, and real review posting — all with a clearly-labeled mock fallback when no
  `GITHUB_TOKEN` is set (GitHub Actions results reuse this same client/token, no separate
  integration)
- Groq LLM integration with the same real/mock fallback pattern; mock mode never fabricates
  findings, it only transforms evidence already produced by deterministic tools
- Real/mock Jira integration: `get_issue`, `search_issues`, `add_comment`, `transition_status` —
  the full read/write surface, not just acceptance-criteria reads — behind the same
  env-var-presence pattern as GitHub/Groq. A dedicated Jira publisher posts the review outcome
  (comment + status transition) back to the linked ticket on approval/rejection, symmetric with the
  GitHub publisher
- OSV.dev dependency-vulnerability lookup (real network call, no API key), a real ESLint pass on
  plain JS/JSX frontend files, and a real Trivy config/IaC scan on changed Dockerfiles/
  docker-compose files (all graceful-not-installed-fallback, same shape as ruff/semgrep/pylint)
- Langfuse and LangSmith tracing, both optional and not mutually exclusive — a `CompositeTracingClient`
  fans one span per agent run out to whichever are configured, falling back to a genuine no-op when
  neither is
- Dynamic agent activation: CI Investigator is never part of the static up-front fan-out — it's
  activated mid-graph via a real `EVENT`-type edge when wave-1 confirms a HIGH/CRITICAL finding
- Incremental PR re-review: a follow-up push to an already-reviewed PR re-analyzes only the files
  that changed since the last push (`core/orchestration/incremental.py`) and classifies prior
  findings as NEW/RESOLVED/UNCHANGED/STALE/INVALIDATED, carrying still-open ones forward
- A real, SQLite-backed previous-tool-result cache (identical deterministic-tool calls, e.g. ruff on
  unchanged file content, skip re-execution) and a runtime-toggleable chaos/failure-injection demo
  mode (`POST /api/chaos/enable`) that deterministically fails and then recovers a tool call so the
  retry path is actually observable, not just implemented
- React + TypeScript + React Flow dashboard: live agent graph with 5 distinct edge visual states,
  agent inspector, condition inspector, dedicated Validation/Conditions/Traces/Metrics pages,
  a Code Explorer (real changed-file repo tree, Monaco-rendered file content, jump-to-line from a
  finding), a Replay page that reuses the live dashboard's own components — agent graph, inspectors,
  findings, token dashboard — against a historical event timeline instead of the live WebSocket
  feed, findings view, token dashboard, tool monitor, communication feed, human-approval gate

**Explicitly deferred to a later pass** (clean extension points left in `configs/` and the agent
registry): CodeQL/Checkstyle/SpotBugs (Java-only or infra this project's diff-scoped subprocess
pattern doesn't fit — see `STATUS.md`) and multi-agent debate.

---

## Architecture

### Hybrid intelligence layers

1. **Deterministic layer** — `backend/backend/tools/`: AST parsing, diff parsing, regex
   heuristics, ruff, semgrep, pytest. Pure Python/subprocess, no LLM.
2. **Multi-agent reasoning** — `backend/backend/agents/` + `backend/backend/core/agents/`: each
   agent is a template-method (`BaseAgent.run()`) that *cannot* skip step 1 and only calls the LLM
   when its own `needs_llm()` decision says deterministic evidence was inconclusive.
3. **Validation/criticism** — `backend/backend/agents/validator`, `.../critic`: the Validator asks
   "is this finding true" (evidence exists, file:line matches the diff); the Critic asks "is this
   finding useful" (deduplicated, sufficiently evidenced, correctly prioritized). Both loops are
   bounded to one retry so the graph always terminates.

### Conditional graph engine

`backend/backend/core/graph/engine.py` runs the graph defined in `configs/graph.yaml`.
`backend/backend/core/conditions/safe_evaluator.py` evaluates conditions like
`security_agent.findings_count > 0` by parsing them to an AST and walking a small node-type
whitelist by hand — it never calls `eval()`/`exec()`, so a malicious or malformed condition string
cannot execute arbitrary code.

### Token optimization

Every agent's `needs_llm()` call is the single decision point for whether an LLM call happens.
When it returns `False`, a `TokenUsageRecord(llm_call_avoided=True, avoided_reason=...)` is
recorded and streamed to the frontend — this is what the Token Dashboard's "LLM Calls Avoided"
metric is built from, not a hardcoded estimate.

### GitHub integration

Real webhook (`POST /webhooks/github`) with `X-Hub-Signature-256` HMAC verification
(`backend/backend/integrations/github/webhook_security.py`), real `httpx` calls to the GitHub REST
API for PR/files/commits/review-posting when `GITHUB_TOKEN` is set. Without a token, a
`MockGitHubClient` serves `tests/fixtures/demo_pr/` instead — diffs are still computed for real via
`difflib`, nothing is pre-baked.

### Frontend

React + TypeScript + Vite + Tailwind + React Flow + Framer Motion + Zustand + Recharts + Monaco
(`@monaco-editor/react`, code-split via `React.lazy`). The event-handling logic itself lives in one
pure reducer (`frontend/src/store/eventReducer.ts`); the live Zustand store and a second, replay-only
store both apply it to the same event vocabulary, so historical replay and live viewing derive
identical UI state from identical logic — never a separate reimplementation. Dashboard components
(`AgentGraphView`, `FindingsPage`, `TokenDashboard`, the inspector panels) take an optional
`hooks: ReducerStoreHooks` prop (`frontend/src/store/storeHooks.ts`) so the same component renders
against either store; every pixel of agent/edge/finding state on screen is derived from a real
backend event, never hardcoded.

---

## Local setup

### Prerequisites
- Python 3.11+
- Node.js 20+
- (optional) `ruff` and `semgrep` on PATH for richer deterministic findings — the system degrades
  gracefully without them

### Backend

```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]" 2>/dev/null || pip install -e .
cp ../.env.example ../.env       # fill in keys later; empty is fine to start
uvicorn backend.api.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Visit http://localhost:5173.

### Run the tests

```bash
cd backend
pytest
```

---

## Demo

With both servers running and **no API keys set** (mock mode), click **"Trigger Demo Review"** in
the header — this runs the full graph against the local fixture
(`tests/fixtures/demo_pr/`, a payment-authorization PR modeled on spec §90 where
`PaymentService.process_payment()` is added without the authorization check its sibling methods
use). Watch the Agent Graph tab light up node-by-node; click any node or edge to inspect it.

Alternatively, exercise the real webhook path end-to-end from the command line:

```bash
cd backend
python ../scripts/simulate_webhook.py
```

This builds a real `pull_request.synchronize` payload, signs it with `GITHUB_WEBHOOK_SECRET` if
set, POSTs it to `/webhooks/github`, and streams the live WebSocket event feed to your terminal —
auto-approving the review when it reaches the human-approval gate so you see the full pipeline
including the (mock or real) GitHub publish step.

## Environment variables

See [`.env.example`](./.env.example). Every external integration works with these unset — the
system runs in mock mode and says so loudly in the logs and the UI.
