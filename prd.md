Absolutely. Below is the updated complete BUILD_PROMPT.md. The major upgrade is that the architecture now has conditional edges, critic + validator agents, deterministic Python tooling before LLM calls, and a UI that makes the actual decision graph visible rather than showing a fake linear pipeline.
# BUILD_PROMPT.md

# Live Multi-Agent PR Reviewer
## Autonomous AI Engineering Review & Intelligence Platform

---

# 1. PROJECT VISION

Build a **real-time, multi-agent Pull Request review platform** that behaves like a virtual software engineering team.

When a developer opens or updates a GitHub Pull Request, the system should automatically:

1. Receive the real GitHub webhook.
2. Fetch the real PR, diff, files, commits and metadata.
3. Understand the change.
4. Build a dynamic investigation plan.
5. Run multiple specialized agents in parallel.
6. Use deterministic Python/static-analysis tools wherever possible.
7. Use LLMs only when reasoning or interpretation is actually required.
8. Allow agents to communicate with each other.
9. Create conditional branches based on findings.
10. Validate findings.
11. Criticize findings.
12. Re-run investigations when necessary.
13. Detect contradictions between agents.
14. Produce a final review.
15. Allow human approval.
16. Post the actual review to GitHub.
17. Update Jira when appropriate.
18. Track the complete execution in Langfuse and LangSmith.
19. Visualize the entire execution in a futuristic React command center.

The platform should feel like:

> **A real autonomous engineering team working on a Pull Request in front of you.**

This is NOT a chatbot.

It is an **observable multi-agent engineering system**.

---

# 2. IMPORTANT PROJECT CONSTRAINT

This project is for a hackathon/demo environment.

It does NOT need to be deployed to production.

Prioritize:

- Real integrations
- Real GitHub repositories
- Real Pull Requests
- Real webhooks
- Real Jira
- Real CI
- Real code analysis
- Real agent communication
- Real-time visualization
- Token efficiency
- Beautiful frontend
- Modular architecture

Do NOT spend excessive effort on:

- Kubernetes
- Production cloud deployment
- Enterprise SSO
- High availability
- Multi-region infrastructure

Everything should run locally.

---

# 3. CORE PRINCIPLE

The architecture must follow:

```text
Deterministic Analysis
        ↓
Cheap Filtering
        ↓
Context Selection
        ↓
LLM Reasoning
        ↓
Validation
        ↓
Criticism
        ↓
Conditional Re-investigation
        ↓
Final Review

The system must NOT blindly use an LLM for everything.

4. LLM POLICY
Use Groq as the LLM provider.
However:
Do not call the LLM when a deterministic Python/library-based solution can answer the question reliably.
Examples:
Instead of asking an LLM:
"How many files changed?"

use:
git diff

Instead of:
"Which lines changed?"

use:
unidiff

Instead of:
"Is Python syntax valid?"

use:
ast

Instead of:
"How many functions exist?"

use:
ast
tree-sitter

Instead of:
"Is JSON valid?"

use:
json

Instead of:
"Is YAML valid?"

use:
yaml

Instead of:
"Are there obvious lint violations?"

use:
ruff
eslint
pylint
checkstyle

The LLM should focus on:
Reasoning
Interpretation
Ambiguous cases
Architecture
Business requirements
Security reasoning
Cross-file reasoning
Contradiction resolution
Code intent

5. HYBRID INTELLIGENCE ARCHITECTURE
The system should contain three layers.
┌─────────────────────────────────────┐
│        DETERMINISTIC LAYER          │
│                                     │
│ Python libraries                    │
│ AST                                 │
│ Tree-sitter                         │
│ Git diff                            │
│ Regex                               │
│ Linters                             │
│ Semgrep                             │
│ OSV                                 │
│ Trivy                               │
│ GitHub APIs                         │
│ Jira APIs                           │
│ CI APIs                             │
└──────────────────┬──────────────────┘
                   ↓
┌─────────────────────────────────────┐
│       MULTI-AGENT REASONING         │
│                                     │
│ ReAct Agents                        │
│ Parallel Analysis                   │
│ Agent Communication                 │
│ Dynamic Planning                    │
└──────────────────┬──────────────────┘
                   ↓
┌─────────────────────────────────────┐
│       VALIDATION / CRITICISM        │
│                                     │
│ Validators                          │
│ Critic Agents                       │
│ Evidence Verification               │
│ Conditional Re-routing              │
└─────────────────────────────────────┘


6. REAL AGENTIC GRAPH
The workflow must NOT be a simple linear pipeline.
It should behave like a conditional directed graph.
Example:
                        PR
                         │
                         ▼
                  ORCHESTRATOR
                         │
                         ▼
                  IMPACT ANALYZER
                         │
              ┌──────────┼──────────┐
              │          │          │
              ▼          ▼          ▼
          SECURITY     BUG       PERFORMANCE
            AGENT      AGENT        AGENT
              │          │          │
              │          │          │
              └──────────┼──────────┘
                         │
                         ▼
                    VALIDATOR
                         │
                 ┌───────┴────────┐
                 │                │
              VALID             INVALID
                 │                │
                 ▼                ▼
              CRITIC          RE-ANALYZE
                 │                │
                 │                └───────┐
                 │                        │
                 ▼                        │
          CONDITIONAL ROUTER ◄────────────┘
                 │
       ┌─────────┼─────────┐
       │         │         │
       ▼         ▼         ▼
   MORE TESTS  MORE CODE  MORE TOOLS
       │         │         │
       └─────────┼─────────┘
                 │
                 ▼
             FINAL REVIEW
                 │
                 ▼
          HUMAN APPROVAL
                 │
          ┌──────┴──────┐
          ▼             ▼
       GITHUB          JIRA


7. CONDITION EDGES — REQUIRED
Conditional edges are one of the most important features.
The frontend MUST visually show them.
An edge should have a condition.
Examples:
Security Agent
      │
      │ finding.severity >= HIGH
      ▼
Security Validator

or:
Test Agent
      │
      │ tests_failed == true
      ▼
Failure Investigator

or:
Requirement Agent
      │
      │ coverage < 80%
      ▼
Requirement Re-Analysis

or:
Dependency Agent
      │
      │ vulnerable_dependency == true
      ▼
Security Agent


8. CONDITION EDGE TYPES
Support:
ALWAYS
IF
ELSE
IF/ELSE
AND
OR
NOT
THRESHOLD
EVENT
AGENT_RESULT
TOOL_RESULT

Example:
confidence > 0.8

severity == "HIGH"

tests_failed == true

frontend_changed == true

database_changed == true

security_finding_count > 0


9. CONDITIONAL EDGE DATA MODEL
Each edge should have:
class ConditionalEdge:
    source_agent: str
    target_agent: str
    condition: str
    condition_type: str
    priority: int
    enabled: bool

Example:
{
  "source": "security_agent",
  "target": "security_validator",
  "condition": "security_findings > 0",
  "type": "IF",
  "priority": 1
}


10. EDGE EVALUATION
Do NOT use an LLM to evaluate simple conditions.
Use deterministic Python logic.
Example:
if result.findings > 0:
    route("security_validator")

For more complex conditions:
evaluate_condition(
    "severity == HIGH AND confidence > 0.8"
)

Use a safe condition evaluator.
Never execute arbitrary Python expressions from external input.

11. CONDITIONAL GRAPH VISUALIZATION
The React frontend must visualize:
Normal Edge
Agent A ─────────→ Agent B

Active Edge
Agent A ══════════→ Agent B

Conditional Edge
Agent A ──[severity > HIGH]──→ Agent B

Condition Passed
Agent A ══[✓ severity > HIGH]══→ Agent B

Condition Failed
Agent A ──[✗ severity > HIGH]──→ Agent B

Skipped Edge
Agent A - - -[condition false]- -→ Agent B

This should be clearly visible.

12. AGENT GRAPH INTERACTION
The graph must be interactive.
Users should be able to:
Zoom
Pan
Click agents
Click edges
Inspect conditions
Inspect messages
Inspect tool calls
Inspect execution duration
Inspect tokens
Inspect findings
Inspect validation
Inspect retries
Inspect failures
When clicking an edge:
CONDITIONAL EDGE

Security Agent
        ↓
Condition:

severity >= HIGH

Evaluated:

TRUE ✓

Result:

HIGH severity finding detected

Triggered:

Security Validator


13. REQUIRED AGENTS
Build the following specialized agents.

13.1 ORCHESTRATOR AGENT
Role:
AI engineering manager.
Responsibilities:
Receive webhook
Understand PR
Plan analysis
Determine relevant agents
Determine dependencies
Start parallel agents
Monitor execution
Evaluate conditions
Spawn new agents
Handle failures
Re-plan
Control token budgets
Aggregate findings
The orchestrator should NOT perform all analysis itself.

14. IMPACT ANALYZER
Before expensive LLM calls, perform deterministic impact analysis.
Determine:
Changed files
File types
Changed functions
Imports
Callers
Tests
APIs
Database files
Frontend files
Security-sensitive files
Use Python where possible.
Potential libraries:
pathlib
ast
tree-sitter
networkx
unidiff

Output:
{
  "frontend_changed": true,
  "backend_changed": true,
  "database_changed": false,
  "api_changed": true,
  "security_sensitive": true,
  "tests_changed": false
}

This output controls conditional edges.

15. CODE QUALITY AGENT
Analyze:
Maintainability
Complexity
Duplication
Naming
Error handling
Abstractions
Code smells
Use deterministic tools first.
LLM only interprets deeper design issues.

16. BUG DETECTION AGENT
Analyze:
Logic bugs
Null handling
Boundary conditions
State problems
Race conditions
Regression risks
Incorrect assumptions
Use:
AST
Control-flow information
Diff analysis
Static analysis

before LLM reasoning.

17. SECURITY AGENT
Analyze:
Authentication
Authorization
Injection
SQL injection
XSS
SSRF
Secrets
Path traversal
Command injection
Sensitive data exposure
Cryptography
Tools:
Semgrep
CodeQL
Trivy
OSV
GitHub Security APIs

LLM should interpret results and investigate ambiguous cases.

18. PERFORMANCE AGENT
Analyze:
N+1 queries
Complexity
Expensive loops
API calls
Memory
Blocking operations
Database queries
Caching
Use Python/static analysis where possible.

19. TEST AGENT
Analyze:
Existing tests
Missing tests
Edge cases
Regression risk
Test quality
Run actual tests where safe.
Output:
{
  "tests_found": 24,
  "tests_run": 24,
  "tests_passed": 21,
  "tests_failed": 3,
  "coverage": 71
}


20. DEPENDENCY AGENT
Analyze:
New packages
Version changes
Vulnerabilities
Compatibility
Transitive dependencies
Use:
OSV
GitHub Dependabot
pip
npm
Maven
Gradle

before LLM analysis.

21. ARCHITECTURE AGENT
Analyze:
Coupling
Cohesion
Layering
Dependency direction
Service boundaries
Design patterns
Scalability
Use dependency graphs generated using Python/networkx where possible.

22. API CONTRACT AGENT
Analyze:
API changes
Breaking changes
Request/response schemas
Validation
Error handling
Backward compatibility
Use OpenAPI parsing libraries where available.

23. DATABASE AGENT
Activate conditionally.
Condition:
database_changed == true

Analyze:
SQL
migrations
indexes
transactions
schema compatibility
queries

24. REQUIREMENT / JIRA AGENT
Retrieve the real Jira issue.
Analyze:
Description
Acceptance criteria
Linked issues
Comments
Status
Map:
Requirement
      ↓
PR Change
      ↓
Implementation
      ↓
Test

Produce:
Requirement Coverage


25. DOCUMENTATION AGENT
Analyze:
README
API docs
comments
changelog
OpenAPI
developer documentation
Only activate when relevant.

26. RELIABILITY AGENT
Analyze:
Retry
Timeout
Idempotency
Failure recovery
Error propagation
Resilience

27. OBSERVABILITY AGENT
Analyze:
Logging
Metrics
Tracing
Audit events
Error reporting

28. ACCESSIBILITY AGENT
Only activate when:
frontend_changed == true

Analyze:
Semantic HTML
ARIA
Keyboard navigation
Forms
Accessibility issues

29. CI INVESTIGATOR
Retrieve actual GitHub Actions.
Analyze:
Build
Tests
Lint
Security
Integration tests
Determine:
PR-caused failure
vs
Pre-existing failure
vs
Infrastructure failure


30. STATIC ANALYSIS AGENT
Run deterministic tools.
Potential tools:
Semgrep
Ruff
Pylint
ESLint
Checkstyle
SpotBugs
Trivy
OSV

The results should become evidence for other agents.

31. CODE IMPACT AGENT
Build a dependency/impact graph.
Example:
PaymentService
      │
      ├── PaymentController
      ├── PaymentRepository
      ├── UserService
      ├── PaymentTest
      └── AuditService

Use:
tree-sitter
AST
networkx
Git metadata

where possible.

32. VALIDATOR AGENT
This is a REQUIRED agent.
The validator verifies findings.
For every significant finding:
Finding
   ↓
Validator
   ↓
Evidence
   ↓
Confirmed / Rejected / Uncertain

Validator should use:
Deterministic tools
Source inspection
Tests
Static analysis
Dependency information
Use an LLM only when deterministic validation is insufficient.
Output:
{
  "finding_id": "F-102",
  "status": "CONFIRMED",
  "confidence": 0.94,
  "evidence_ids": ["E-22", "E-31"]
}


33. CRITIC AGENT
The Critic is different from the Validator.
Validator asks:
"Is this finding actually true?"
Critic asks:
"Is this finding useful, correctly classified, sufficiently evidenced, and appropriately prioritized?"
The Critic checks:
False positives
Duplicate findings
Severity
Confidence
Evidence quality
Line accuracy
Impact
Recommendation quality
Missing issues

34. CRITIC CONDITIONAL LOOP
Example:
Finding
   ↓
Validator
   ↓
Confirmed
   ↓
Critic
   ↓
Weak evidence?
   │
   ├── YES
   │     ↓
   │  Re-investigate
   │     ↓
   │  Validator
   │
   └── NO
         ↓
      Accept

This cycle must be visualized.

35. MULTI-AGENT DEBATE
Agents should be able to disagree.
Example:
Security Agent
     │
     │ Potential authorization bypass
     ▼
Bug Agent
     │
     │ "I disagree"
     ▼
Validator
     │
     │ inspect call chain
     ▼
Result

The disagreement must trigger a condition.
Example:
agent_conflict == true

routes to:
Conflict Resolver


36. CONFLICT RESOLUTION AGENT
Required.
Responsibilities:
Detect conflicting findings
Compare evidence
Ask agents for clarification
Use deterministic evidence
Resolve contradiction
Produce final confidence
Example:
Security Agent → HIGH

Bug Agent → LOW

      ↓

Conflict Resolver

      ↓

Validator

      ↓

Final:
MEDIUM


37. FINAL REVIEW AGENT
Generate final review only after:
Validation
+
Criticism
+
Conflict Resolution

Every finding must contain:
id
severity
category
file
line
title
description
evidence
impact
recommendation
confidence
detecting_agent
validator
critic_status


38. AGENT COMMUNICATION PROTOCOL
Agents communicate using structured messages.
Example:
{
  "message_id": "M-123",
  "sender": "security_agent",
  "receiver": "validator_agent",
  "type": "FINDING",
  "finding_id": "F-102",
  "summary": "Potential authorization bypass",
  "evidence_ids": ["E-10"],
  "confidence": 0.86,
  "timestamp": "..."
}

Do NOT pass massive raw contexts between agents.
Pass references.

39. SHARED EVIDENCE STORE
Create a central evidence store.
Evidence
│
├── Finding
├── File
├── Line
├── Tool
├── Agent
├── Timestamp
├── Confidence
└── Source

Example:
{
  "evidence_id": "E-203",
  "source": "semgrep",
  "file": "PaymentService.java",
  "line": 86,
  "result": "Authorization check missing"
}

Agents reference:
E-203

instead of passing the complete output.

40. TOKEN OPTIMIZATION
Token optimization is REQUIRED.
The system should actively minimize LLM usage.

40.1 Deterministic First
Before calling an LLM:
Can Python/library/tool answer this?

If yes:
Do not call LLM.


41. DIFF-FIRST STRATEGY
Initially provide only:
PR metadata
Diff
Changed files
Commit information

Do NOT send the entire repository.

42. CONTEXT ROUTING
Retrieve additional files only when needed.
Example:
Security Agent
       ↓
PaymentController.java
       ↓
Find authorization middleware
       ↓
Retrieve AuthorizationService.java


43. AGENT-SPECIFIC CONTEXT
Different agents receive different contexts.
Security
→ security-sensitive files

Performance
→ queries/API/algorithms

Testing
→ changed code + tests

Documentation
→ docs

Architecture
→ dependency graph


44. CONTEXT COMPRESSION
Implement:
Summarization
Deduplication
Relevant code extraction
Evidence references
Context caching
Previous result reuse

45. TOKEN BUDGETS
Every LLM agent must have:
max_input_tokens
max_output_tokens
timeout

Example:
security:
  max_input_tokens: 6000
  max_output_tokens: 2000

critic:
  max_input_tokens: 5000
  max_output_tokens: 1500


46. TOKEN BUDGET ROUTING
If an agent has insufficient context budget:
Full repository
      ↓
Relevant files
      ↓
Relevant functions
      ↓
Relevant lines
      ↓
Evidence

Progressively reduce context.

47. CACHE
Cache:
Repository summaries
File analysis
AST results
Dependency graphs
Tool results
Previous PR findings
If nothing changed:
Reuse result

instead of calling LLM again.

48. INCREMENTAL PR REVIEW
When a new commit arrives:
Previous Review
       ↓
New Commit
       ↓
Changed Files
       ↓
Impact Analysis
       ↓
Only affected agents rerun

Example:
Previous:

Security ✓
Architecture ✓
Performance ✓

New commit changes only README.

Rerun:

Documentation

Reuse:

Security
Architecture
Performance


49. REAL GITHUB INTEGRATION
Integrate GitHub API.
Support:
Repositories
Pull Requests
Files
Diffs
Commits
Branches
Reviews
Comments
Check Runs
Actions
Issues

Actual operations:
GET PR
GET FILES
GET DIFF
GET COMMITS
GET CHECKS
POST REVIEW
POST INLINE COMMENT
POST COMMENT


50. GITHUB WEBHOOKS
Support:
pull_request.opened
pull_request.reopened
pull_request.synchronize
pull_request.closed
pull_request.review_requested

Most important:
pull_request.synchronize

Every new commit should trigger incremental analysis.

51. WEBHOOK SECURITY
Validate:
X-Hub-Signature-256

using a secret.
Flow:
GitHub
   ↓
Webhook
   ↓
Signature Validation
   ↓
Valid?
 ┌─┴──┐
YES   NO
 ↓     ↓
Process Reject

This conditional edge must be visible.

52. JIRA INTEGRATION
Support:
Search
Get issue
Comments
Acceptance criteria
Status
Priority
Labels
Links
Add comment
Update status
Relationship:
JIRA-142
    ↕
PR #238
    ↕
Commit abc123


53. GITHUB ACTIONS
Retrieve real:
Build
Unit Tests
Integration Tests
Lint
Security
Deployment checks

Use actual results.

54. TOOL FRAMEWORK
Every tool must implement a common interface.
class Tool:
    name: str
    description: str

    async def execute(
        self,
        input: dict
    ) -> ToolResult:
        ...

Tool result:
class ToolResult:
    success: bool
    data: dict
    error: str | None
    duration_ms: int


55. PYTHON-FIRST TOOLING
Use Python libraries wherever possible.
Recommended:
pathlib
subprocess
ast
json
re
difflib
unidiff
tree-sitter
networkx
pydantic
asyncio
httpx
tenacity

For Git:
GitPython

For YAML:
PyYAML

For parsing:
tree-sitter

For schemas:
Pydantic


56. PARALLEL EXECUTION
Use asynchronous execution.
Python:
asyncio

Example:
results = await asyncio.gather(
    security_agent.run(),
    bug_agent.run(),
    performance_agent.run(),
    test_agent.run(),
    dependency_agent.run()
)

Do NOT run independent agents sequentially.

57. DEPENDENCY-AWARE EXECUTION
Parallelism should respect dependencies.
Example:
Impact Analysis
      ↓
+-----+-----+
|     |     |
Security Bug Performance
|     |     |
+-----+-----+
      ↓
   Validator
      ↓
     Critic

But:
Database Agent

should only start when:
database_changed == true


58. AGENT STATE MACHINE
Every agent has:
IDLE
QUEUED
RUNNING
THINKING_SUMMARY
CALLING_TOOL
WAITING
COMMUNICATING
VALIDATING
FAILED
COMPLETED
SKIPPED

The UI should visualize state changes in real time.

59. REAL-TIME EVENT SYSTEM
Use WebSockets or SSE.
Events:
WEBHOOK_RECEIVED
PR_LOADED
PLANNING_STARTED

AGENT_QUEUED
AGENT_STARTED
AGENT_THINKING_SUMMARY
AGENT_TOOL_STARTED
AGENT_TOOL_COMPLETED
AGENT_MESSAGE_SENT
AGENT_MESSAGE_RECEIVED
AGENT_COMPLETED
AGENT_FAILED
AGENT_SKIPPED

EDGE_EVALUATED
EDGE_TRIGGERED
EDGE_SKIPPED

FINDING_CREATED
FINDING_VALIDATED
FINDING_REJECTED
FINDING_CRITICIZED

REPLAN_STARTED
REPLAN_COMPLETED

REVIEW_GENERATED
APPROVAL_REQUIRED
GITHUB_UPDATED
JIRA_UPDATED


60. FRONTEND
Use:
React
TypeScript
Vite
Tailwind CSS
React Flow
Framer Motion
Recharts

Optional:
Monaco Editor
Lucide


61. FRONTEND DESIGN
The frontend should look like:
AI Engineering Mission Control
Not:
Generic admin dashboard.
Design:
Dark mode
Glass panels
Neon accents
Animated graph
Smooth transitions
Real-time activity
Interactive code
Futuristic typography
Subtle glow
Clear hierarchy
It should impress both:
Technical judges

and:
Non-technical judges


62. MAIN DASHBOARD
Display:
PR #238
REVIEWING

Agents Active       9
Tools Running       4
Findings            8
Validated           6
Critical            2

Token Usage         18,420
Estimated Savings   54%

Requirement Score   86%

All values must come from real execution.

63. AGENT GRAPH
Use React Flow.
Nodes:
Orchestrator
Impact Analyzer
Security
Bug
Performance
Testing
Architecture
Dependency
Requirements
Validator
Critic
Conflict Resolver
Final Reviewer

Edges should be dynamic.

64. CONDITIONAL EDGE UI
Example:
Security Agent
       │
       │ [severity >= HIGH]
       ▼
Security Validator

When active:
Security Agent
       ║
       ║ ✓ severity >= HIGH
       ▼
Security Validator

When false:
Security Agent
       ┊
       ┊ ✗ severity >= HIGH
       ┊

Animate active transitions.

65. CONDITION INSPECTOR
Click an edge.
Display:
EDGE INSPECTOR

Source:
Security Agent

Target:
Security Validator

Condition:
severity >= HIGH

Current Value:
HIGH

Evaluation:
TRUE ✓

Triggered:
14:32:03

Reason:
Security Agent produced
2 HIGH severity findings.


66. AGENT INSPECTOR
Click an agent.
Display:
SECURITY AGENT

Status:
CALLING TOOL

Objective:
Investigate authentication changes.

Context:
5,420 tokens

Budget:
6,000

Tools:
Semgrep
Repository Search

Findings:
2

Confidence:
91%

Latency:
2.4 seconds


67. SAFE REASONING DISPLAY
NEVER expose private chain-of-thought.
Instead show:
EXECUTION SUMMARY

Objective
↓
Decision
↓
Action
↓
Tool
↓
Observation
↓
Next Action

Example:
Objective:
Investigate authorization change.

Decision:
Authentication logic was modified.

Action:
Inspect middleware and endpoint call path.

Tool:
Repository Search.

Observation:
Authorization middleware is not used.

Next Action:
Send finding to Validator.


68. COMMUNICATION VIEW
Show real agent messages.
Security
   │
   │ Finding F-102
   ▼
Validator
   │
   │ Confirmed
   ▼
Critic
   │
   │ Evidence insufficient
   ▼
Security
   │
   │ Additional evidence
   ▼
Validator


69. TOOL MONITOR
Show:
Semgrep
RUNNING

OSV
SUCCESS

GitHub Actions
FAILED

Jira
SUCCESS

Include:
Start time
End time
Duration
Agent
Tool
Result
Error

70. CODE EXPLORER
Use Monaco Editor if possible.
Show:
Repository tree
Changed files
Diff
Code
Findings
Agent annotations
Click a finding to jump to the exact line.

71. FINDINGS DASHBOARD
Filters:
Severity
Category
Agent
Confidence
Validation
Status

Finding:
HIGH

Authorization bypass

PaymentService.java:86

Detected:
Security Agent

Validated:
Validator

Critic:
Confirmed

Confidence:
96%


72. VALIDATION VIEW
Show:
FINDING F-102

Detection
✓ Security Agent

Evidence
✓ Semgrep

Validation
✓ Validator

Criticism
✓ Critic

Final Status
CONFIRMED


73. TOKEN DASHBOARD
Show actual metrics:
TOTAL TOKENS
18,420

INPUT
14,820

OUTPUT
3,600

WITHOUT OPTIMIZATION
42,800

SAVED
24,380

CONTEXT REUSE
31%

LLM CALLS AVOIDED
18

Never hardcode these values.

74. LLM CALL SAVINGS
Track:
Potential LLM Call
        ↓
Deterministic Tool Available?
       / \
     YES  NO
      ↓    ↓
 Python   LLM

Record:
llm_call_avoided = true
reason = "AST analysis sufficient"

This should appear in the UI.

75. REPLAY MODE
Allow complete review replay.
Controls:
Play
Pause
Next
Restart
1x
2x
4x

Replay:
Webhook
Planning
Agents
Conditions
Tools
Communication
Validation
Criticism
Final review

76. CHAOS / FAILURE MODE
Implement optional demo failure injection.
Examples:
GitHub timeout
Jira timeout
Tool failure
Agent timeout
CI failure
Conflicting findings
Invalid webhook

The system should recover.
Example:
Tool Failure
     ↓
Retry
     ↓
Still Failed
     ↓
Fallback
     ↓
Re-plan
     ↓
Continue


77. HUMAN-IN-THE-LOOP
Before:
Posting review
Requesting changes
Approving PR
Updating Jira status
show:
AI RECOMMENDATION

REQUEST CHANGES

2 HIGH severity findings.

[Approve]
[Reject]
[Edit]


78. REAL GITHUB OUTPUT
Post actual review.
Example:
HIGH — Authorization Bypass

PaymentService.java:86

The endpoint executes the payment operation
without performing the authorization check used
by the surrounding payment flow.

Evidence:
E-203

Validated by:
Validator Agent

Confidence:
96%

Recommendation:
Reuse AuthorizationService.validateAccess()
before executing the transaction.


79. INCREMENTAL REVIEW
When a new commit arrives:
Previous findings
       ↓
New diff
       ↓
Impact analysis
       ↓
Finding relevance

Classify:
NEW
RESOLVED
UNCHANGED
STALE
INVALIDATED

Only rerun affected agents.

80. OBSERVABILITY
Use BOTH:
Langfuse
LangSmith

Track:
Agent calls
Groq calls
Tool calls
Tokens
Latency
Errors
Retries
Conditions
Agent communication
Validation
Criticism

81. TRACE STRUCTURE
Example:
PR #238
│
└── Orchestrator
    │
    ├── Impact Analyzer
    │
    ├── Security Agent
    │   ├── Semgrep
    │   └── Groq
    │
    ├── Bug Agent
    │   └── Groq
    │
    ├── Test Agent
    │   └── Pytest
    │
    ├── Requirement Agent
    │   ├── Jira
    │   └── Groq
    │
    ├── Validator
    │
    ├── Critic
    │
    └── Final Reviewer


82. METRICS
Track:
Review Duration
Agent Duration
Tool Duration
LLM Calls
LLM Calls Avoided
Input Tokens
Output Tokens
Tokens Saved
Cost
Agent Success Rate
Tool Success Rate
Findings
Validated Findings
Rejected Findings
False Positive Rate
Requirement Coverage
CI Status
Review Score


83. FAILURE HANDLING
Every agent/tool must support:
Timeout
Retry
Failure
Fallback
Error event
Trace

No silent failures.

84. SECURITY
Never expose:
GitHub tokens
Jira tokens
Groq keys
Langfuse keys
LangSmith keys
Use:
.env
.env.example

Never execute arbitrary PR code directly on the host without explicit isolation/approval.

85. MODULAR PROJECT STRUCTURE
Use this structure:
multi-agent-pr-reviewer/
│
├── backend/
│   │
│   ├── core/
│   │   ├── agents/
│   │   ├── orchestration/
│   │   ├── graph/
│   │   ├── conditions/
│   │   ├── communication/
│   │   ├── planning/
│   │   ├── execution/
│   │   ├── context/
│   │   ├── memory/
│   │   ├── evidence/
│   │   ├── events/
│   │   ├── validation/
│   │   ├── criticism/
│   │   ├── evaluation/
│   │   └── token_optimization/
│   │
│   ├── agents/
│   │   ├── orchestrator/
│   │   ├── impact_analyzer/
│   │   ├── code_review/
│   │   ├── bug_detection/
│   │   ├── security/
│   │   ├── performance/
│   │   ├── testing/
│   │   ├── dependency/
│   │   ├── architecture/
│   │   ├── api_contract/
│   │   ├── database/
│   │   ├── requirement/
│   │   ├── documentation/
│   │   ├── reliability/
│   │   ├── observability/
│   │   ├── accessibility/
│   │   ├── ci_investigator/
│   │   ├── static_analysis/
│   │   ├── code_impact/
│   │   ├── validator/
│   │   ├── critic/
│   │   ├── conflict_resolver/
│   │   └── final_review/
│   │
│   ├── tools/
│   │   ├── github/
│   │   ├── jira/
│   │   ├── git/
│   │   ├── repository/
│   │   ├── diff/
│   │   ├── ast/
│   │   ├── tree_sitter/
│   │   ├── dependency/
│   │   ├── semgrep/
│   │   ├── codeql/
│   │   ├── trivy/
│   │   ├── osv/
│   │   ├── eslint/
│   │   ├── ruff/
│   │   ├── pylint/
│   │   ├── checkstyle/
│   │   ├── spotbugs/
│   │   ├── test_runner/
│   │   └── github_actions/
│   │
│   ├── llm/
│   │   ├── base/
│   │   ├── groq/
│   │   └── routing/
│   │
│   ├── integrations/
│   │   ├── github/
│   │   ├── jira/
│   │   ├── webhook/
│   │   ├── websocket/
│   │   └── streaming/
│   │
│   ├── observability/
│   │   ├── langfuse/
│   │   ├── langsmith/
│   │   └── tracing/
│   │
│   └── api/
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard/
│   │   │   ├── AgentGraph/
│   │   │   ├── Communication/
│   │   │   ├── CodeExplorer/
│   │   │   ├── Findings/
│   │   │   ├── Validation/
│   │   │   ├── Conditions/
│   │   │   ├── Jira/
│   │   │   ├── CI/
│   │   │   ├── Tools/
│   │   │   ├── Traces/
│   │   │   ├── Metrics/
│   │   │   └── Replay/
│   │   │
│   │   ├── components/
│   │   │   ├── AgentGraph/
│   │   │   ├── ConditionalEdge/
│   │   │   ├── AgentInspector/
│   │   │   ├── ConditionInspector/
│   │   │   ├── CommunicationGraph/
│   │   │   ├── CodeViewer/
│   │   │   ├── DiffViewer/
│   │   │   ├── FindingCard/
│   │   │   ├── ValidationPanel/
│   │   │   ├── ToolMonitor/
│   │   │   ├── TokenDashboard/
│   │   │   ├── Timeline/
│   │   │   └── common/
│   │   │
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── store/
│   │   ├── types/
│   │   └── utils/
│   │
│   └── package.json
│
├── configs/
│   ├── agents.yaml
│   ├── tools.yaml
│   ├── graph.yaml
│   └── conditions.yaml
│
├── tests/
│
├── scripts/
│
├── docs/
│
├── .env.example
├── README.md
└── BUILD_PROMPT.md


86. CONFIGURATION-DRIVEN AGENTS
Agents should be configurable.
Example:
agents:

  security:
    enabled: true
    execution: parallel
    max_input_tokens: 6000
    max_output_tokens: 2000

  database:
    enabled: auto
    condition: "database_changed == true"

  accessibility:
    enabled: auto
    condition: "frontend_changed == true"

  performance:
    enabled: true
    execution: parallel


87. CONFIGURATION-DRIVEN GRAPH
Example:
edges:

  - source: impact_analyzer
    target: security_agent
    condition: "security_sensitive == true"

  - source: impact_analyzer
    target: database_agent
    condition: "database_changed == true"

  - source: security_agent
    target: validator
    condition: "security_findings > 0"

  - source: validator
    target: critic
    condition: "status == CONFIRMED"

  - source: validator
    target: reanalysis
    condition: "status == UNCERTAIN"

  - source: critic
    target: conflict_resolver
    condition: "agent_conflict == true"


88. DYNAMIC AGENT ACTIVATION
The orchestrator should be able to activate agents dynamically.
Example:
Security Agent
      ↓
Discovers database query
      ↓
Orchestrator
      ↓
Database Agent activated

This must generate:
AGENT_DYNAMICALLY_ACTIVATED

and the frontend must display the newly created node/edge.

89. AGENT SKIPPING
Agents should be skipped when unnecessary.
Example:
Accessibility Agent

SKIPPED

Reason:
No frontend changes detected.

This saves:
Tokens
Time
Compute

90. DEMO SCENARIO
Use a realistic payment/security PR.
Jira
JIRA-142

Implement secure payment authorization.

Acceptance Criteria:

1. Validate authenticated user
2. Verify resource ownership
3. Log payment attempt
4. Reject unauthorized requests
5. Add regression tests

PR
Developer introduces:
PaymentService.processPayment()

without an authorization check.
Tests do not cover the new behavior.

91. EXPECTED EXECUTION
GitHub Webhook
      ↓
Signature Validation
      ↓
PR Loaded
      ↓
Impact Analysis
      ↓
┌─────┬─────┬─────┬─────┐
│     │     │     │     │
Security Bug  Test Requirement
│     │     │     │
└─────┴─────┴─────┴─────┘
            ↓
        Findings
            ↓
         Validator
            ↓
      ┌─────┴─────┐
      │           │
   Confirmed    Uncertain
      │           │
      ▼           ▼
    Critic    Re-analysis
      │
      ▼
Conflict?
   │
 ┌─┴─┐
NO  YES
│     │
│   Conflict
│   Resolver
│     │
└──┬──┘
   ↓
Final Review
   ↓
Human Approval
   ↓
GitHub + Jira


92. NO FAKE DATA
This is extremely important.
Do NOT fake:
Agent messages
Tool calls
Token usage
Findings
GitHub responses
Jira responses
CI results
Conditions
Execution times
Langfuse traces
The frontend must represent actual backend events.

93. REAL-TIME VISUALIZATION RULE
If the backend emits:
AGENT_STARTED

the frontend activates the node.
If:
TOOL_STARTED

the tool appears as running.
If:
EDGE_EVALUATED

the condition edge updates.
If:
FINDING_VALIDATED

the finding becomes validated.
The UI must always represent the actual execution state.

94. TESTING REQUIREMENTS
Test:
Agents
Execution
Tool calls
Communication
Failure handling
Graph
Conditional edges
Conditions
Branching
Re-routing
Dynamic nodes
Token Optimization
Context selection
Deduplication
Cache
Token budgets
LLM call avoidance
Integrations
GitHub
Jira
Webhooks
GitHub Actions
Frontend
Real-time events
Agent graph
Conditional edges
Agent inspector
Replay

95. README REQUIREMENTS
The README must explain:
Problem
Solution
Architecture
Agent architecture
ReAct
Conditional edges
Parallelism
Validator
Critic
Conflict resolution
Token optimization
Python deterministic tooling
GitHub integration
Jira integration
Webhooks
CI
Langfuse
LangSmith
Frontend
Local setup
Demo instructions

96. ENVIRONMENT VARIABLES
Create .env.example.
# LLM
LLM_PROVIDER=groq
GROQ_API_KEY=
GROQ_MODEL=

# GitHub
GITHUB_TOKEN=
GITHUB_WEBHOOK_SECRET=
GITHUB_REPOSITORY=

# Jira
JIRA_BASE_URL=
JIRA_EMAIL=
JIRA_API_TOKEN=
JIRA_PROJECT_KEY=

# Langfuse
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=

# LangSmith
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=
LANGSMITH_TRACING=true


97. FINAL REQUIREMENTS
The completed system MUST have:
Agentic
Multiple ReAct agents
Parallel execution
Agent-to-agent communication
Dynamic agent activation
Dynamic re-planning
Conditional
Conditional edges
IF/ELSE routing
Threshold routing
Event-based routing
Condition visualization
Condition inspector
Validation
Validator agent
Critic agent
Conflict resolver
Evidence verification
Re-analysis loop
Efficiency
Python deterministic analysis
Static analysis tools
Context routing
Context compression
Evidence references
Caching
Token budgets
LLM call avoidance
Incremental reviews
Integrations
GitHub
GitHub Webhooks
GitHub Actions
Jira
Semgrep
OSV
Trivy
Other relevant tools
Observability
Langfuse
LangSmith
Token metrics
Latency
Cost
Agent traces
Tool traces
Frontend
React
TypeScript
React Flow
Real-time updates
Agent graph
Conditional edges
Communication graph
Code explorer
Findings
Validator view
Critic view
Tool monitor
Token dashboard
Replay

98. FINAL PRODUCT EXPERIENCE
The final experience should look like:
                   ┌──────────────────────┐
                    │    GITHUB PR #238    │
                    └──────────┬───────────┘
                               │
                               ▼
                     ┌─────────────────┐
                     │  ORCHESTRATOR   │
                     └────────┬────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
             CONDITIONAL            CONDITIONAL
                 EDGE                   EDGE
                    │                   │
                    ▼                   ▼
               SECURITY             DATABASE
                 AGENT                AGENT
                    │                   │
                    └─────────┬─────────┘
                              │
                              ▼
                         VALIDATOR
                              │
                    ┌─────────┴─────────┐
                    │                   │
               CONFIRMED             UNCERTAIN
                    │                   │
                    ▼                   ▼
                  CRITIC            RE-ANALYSIS
                    │                   │
                    └─────────┬─────────┘
                              │
                              ▼
                     CONFLICT RESOLVER
                              │
                              ▼
                       FINAL REVIEW
                              │
                              ▼
                       HUMAN APPROVAL
                              │
                     ┌────────┴────────┐
                     ▼                 ▼
                  GITHUB              JIRA

Every transition should be observable.
Every condition should be visible.
Every tool call should be traceable.
Every important finding should be validated.
Every expensive LLM call should have a reason.
Every agent should have a clear responsibility.
And the frontend should make the entire process understandable to someone who has never heard of multi-agent systems.

99. CORE DIFFERENTIATOR
The project should NOT market itself simply as:
"AI Pull Request Reviewer."
Instead position it as:
"An observable autonomous AI engineering team that dynamically investigates, validates, challenges, and reviews software changes using a conditional multi-agent graph."
The strongest demonstration should be the moment when the audience sees:
PR
 ↓
Parallel Agents
 ↓
Security finds issue
 ↓
Conditional Edge ACTIVATES
 ↓
Validator
 ↓
Validator says UNCERTAIN
 ↓
Conditional Edge ACTIVATES
 ↓
Re-analysis
 ↓
Evidence found
 ↓
Critic challenges severity
 ↓
Conflict Resolver
 ↓
Final Decision
 ↓
Human Approval
 ↓
Actual GitHub Review

while simultaneously seeing:
Agent Graph
+
Condition Edges
+
Agent Communication
+
Tool Calls
+
Code
+
Evidence
+
Validation
+
Token Usage
+
Langfuse/LangSmith Trace

in real time.
That is the core hackathon experience.

