# App Factory

App Factory is the mechanism within AVA for turning a business stakeholder's idea into a deployable agentic application. A business user fills out a plain-language questionnaire in the Control Plane UI; the factory generates all the Python, React, Terraform, and sample data for the use case and deploys it to AWS AgentCore Runtime end-to-end.

---

## How it works

```
Business user
    │  (fills questionnaire on /applications/app-factory)
    ▼
Control Plane backend  ─▶  DynamoDB (SUBMISSION#<uuid>)
    │  (on Deploy)
    ▼
Step Functions (ava-cp-dev-982569-deployment)
    │  orchestrates validate → package → build → monitor → capture
    ▼
CodeBuild (runs applications/app_factory/deploy.sh)
    │
    ├─ Phase 1   python3 -m app_factory.builder          (code generation)
    ├─ Phase 1.5 scoped source-zip to S3
    ├─ Phase 1.6 docs capture to /tmp/docs_outputs.json
    ├─ Phase 2a  terraform apply  (infra: ECR, data S3, IAM)
    ├─ Phase 2b  docker build + push to ECR
    ├─ Phase 2c  terraform apply  (runtime: AgentCore CFN stack)
    ├─ Phase 2c.5 publish_to_registry.py                 (Agent Registry, non-fatal)
    └─ Phase 2d  terraform apply  (UI: CloudFront + API GW + Lambdas)
```

Total runtime 15–25 min. Every phase state transition lands in DynamoDB so the UI can show live progress.

---

## Builder architecture — `builder.py`

`builder.py` coordinates generation through `bedrock_runtime.py`, a direct Amazon
Bedrock Converse executor. It needs no Claude CLI or Anthropic SDK.

| Agent | Model default | Turn limit |
|---|---|---:|
| Orchestrator | GLM 4.7 | 60 |
| agent-builder | GLM 4.7 | 40 |
| ui-builder | GLM 4.7 | 30 |
| infra-builder | GLM 4.7 | 20 |
| data-builder | GLM 4.7 Flash | 15 |
| docs-builder | GLM 4.7 Flash | 10 |
| validator | GLM 4.7 | 20 |

File tools, shell build commands, parallel specialist delegation and the existing
hooks are supported. Required specialists and artifact checks prevent a plain
model completion from being treated as a successful build. Generation errors,
missing artifacts, invalid schemas and final import errors stop the deployment script.

Configuration (environment variables):
- `APP_FACTORY_MODEL_ID=zai.glm-4.7`
- `APP_FACTORY_FAST_MODEL_ID=zai.glm-4.7-flash`
- `AWS_REGION=us-east-1`
- `APP_FACTORY_MAX_OUTPUT_TOKENS=8192` (per model response)
- `APP_FACTORY_MAX_CALLS=160` (shared across agents)
- `APP_FACTORY_MAX_TOTAL_TOKENS=500000` (checked before calls; in-flight calls may exceed it)
- `APP_FACTORY_TIMEOUT_SECONDS=1200`
- `APP_FACTORY_WORKSPACE` (optional alternative root containing `applications/fsi_foundry/`)

Run generation in an isolated build workspace: the Bash tool executes build
commands there, and file-tool path checks are not an operating-system shell sandbox.

Prompts live in `prompts/*.py`, one module per subagent. Shared path constants are in `paths.py`; ANSI console helpers and `log()` are in `console.py`.

---

## Hook-based enforcement — `hooks.py`

Prompts are probabilistic. Hooks are deterministic. Every file write and every data-builder completion is checked by the executor by `hooks.py`:

**PreToolUse** — fires on every `Write|Edit`, denies with a reason if matched:
- **A** `.json` file inside `/documents/`, `/uploads/`, `/attachments/`
- **B** `.pdf` write whose body doesn't start with `%PDF-`
- **C** agent file with `s3_retriever_tool` in its `tools=[]` list
- **D** `orchestrator.py` missing a `_prefetch_data` method
- **E** absolute `from use_cases.<id>.src.<framework>.` import
- **F** UI `.tsx` using `item.severity`, `item.message`, or `JSON.stringify(item)` fallbacks
- **G** orchestrator prefetching `content_base64` into agent input_text

**PostToolUse** (after an `Agent` call to `data-builder`) — cross-file consistency when the data-builder declares itself done:
- **Gate 1**   every `profile.json` must live at `<entity_id>/profile.json`
- **Gate 1.5** every `s3_key` must start with an existing entity_id
- **Gate 2**   every `document_key` must resolve to a real file on disk

Any gate denial becomes an error tool result so the orchestrator can request a repair within the remaining budget.

---

## Directory layout

```
app_factory/
├── __init__.py            # package marker — run as `python3 -m app_factory.builder`
├── builder.py             # runner, CLI, DynamoDB I/O, post-gen patch passes
├── bedrock_runtime.py     # Converse loop, tools, delegation, hooks, budgets
├── paths.py               # REPO_ROOT, FSI_FOUNDRY, REFERENCE_USE_CASE, UI_TEMPLATE
├── console.py             # ANSI color helpers + log() / log_tool_use()
├── hooks.py               # PreToolUse rules A–G + SubagentStop gates 1 / 1.5 / 2
├── prompts/
│   ├── orchestrator.py    # parent system prompt
│   ├── agent_builder.py
│   ├── ui_builder.py
│   ├── infra_builder.py
│   ├── data_builder.py
│   ├── docs_builder.py
│   └── validator.py
├── deploy.sh              # CodeBuild buildspec — all phases listed above
├── scripts/
│   └── publish_to_registry.py   # A2A agent card publish (non-fatal)
├── ui-template/           # React scaffolding the ui-builder customizes per use case
└── README.md              # this file
```

---

## Running locally

```bash
# From applications/ (so Python finds the package on sys.path)
cd applications/
python3 -m app_factory.builder --dry-run                      # prints orchestrator prompt only
python3 -m app_factory.builder --answers-file answers.json    # runs full generation
python3 -m app_factory.builder --submission-id <uuid>         # fetches answers from DynamoDB
```

Requires:
- `boto3>=1.43.0` and `botocore[crt]` (the latter supports AWS CLI login profiles)
- Python 3.11+, Node/npm and the generated application's dependencies
- Optional `reportlab` / `Pillow` for sample PDF/image generation
- AWS credentials with Bedrock access

CodeBuild stages everything automatically; see `deploy.sh` for the phase-by-phase flow.

---

## Related

- [FSI Foundry](../fsi_foundry/) — shared foundations every generated use case sits on top of
- [Control Plane backend](../../platform/control_plane/backend/) — the FastAPI service that accepts submissions and triggers deploys
- [Reference Implementations](../reference_implementations/) — hand-written end-to-end solutions (pre-App-Factory)
- [AVA Overview](../../README.md) — full project overview

## Validation of the GLM adapter

On 2026-09-09, 20 offline tests passed. A live, bounded smoke test used GLM 4.7
to generate Python, Flash to create its README, and GLM to review both. The
function passed deterministic checks. The run used 11 calls, 6,936 input tokens
and 908 output tokens. This proves the executor integration, not a full generated
FSI deployment. No AWS resources were created by this test.

From the repository root:

```bash
python -m pytest applications/app_factory/tests -q
AWS_PROFILE=default AWS_REGION=us-east-1 python -m applications.app_factory.tests.smoke_bedrock
```

The smoke test makes billable Bedrock calls and writes only to a new `/tmp`
workspace. It exposes no Bash tool. `--model` and `--fast-model` on the builder
CLI can override the corresponding model environment variables.
