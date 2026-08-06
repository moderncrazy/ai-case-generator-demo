# Requirement Delivery V2 Phase 1 Implementation Plan

> [!WARNING]
> 本计划已废弃，不得执行。当前 V2 直接替换 V1，不使用功能开关、兼容接口、SQLite 或旧表增量方案；后续实施计划必须以已批准 PRD、当前总体架构和 ADR 0001—0024 为依据重新编写。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a feature-flagged V2 requirement pipeline that turns confirmed project facts into versioned, traceable, quality-gated requirement outlines, requirement modules, and PRDs without silently inventing business scope.

**Architecture:** Keep LangGraph as the execution engine, but move business truth, artifact lifecycle, validation, and routing policy into a new `src/delivery` deep module with deterministic interfaces. V2 authors and semantic reviewers return structured candidates; only the PM control plane may approve immutable artifact versions and advance the workflow. Existing V1 graphs, database columns, APIs, and UI remain available while V2 is introduced behind `delivery_v2_enabled=false`.

**Tech Stack:** Python 3.12+, Pydantic 2, LangGraph 1.1+, LangChain, Piccolo ORM with SQLite, Jinja2, FastAPI, standard-library `unittest`.

## Global Constraints

- Do not add a production or test dependency; use the libraries already present in `requirements.txt` and Python's `unittest`.
- Activate a Python 3.12 project virtual environment before execution; every `python` command below refers to that environment's interpreter.
- Keep `delivery_v2_enabled` disabled by default, so current projects continue through V1 unless explicitly enabled.
- Approved artifacts are immutable; updates create a new version and never overwrite an approved row.
- LLM output may propose a draft or finding but may not approve an artifact, mutate the workflow cursor, or write project truth directly.
- Structure, scope, traceability, versions, and state transitions are deterministic; semantic reviewers provide evidence-bearing findings only.
- A business-behavior assumption always blocks approval and requires human escalation.
- Requirement outline, module, and PRD content must not contain database, HTTP contract, deployment, or framework design.
- V2 API additions are additive; existing V1 response shapes and endpoints stay backward compatible.
- Persist JSON using canonical UTF-8 JSON (`orjson.dumps(..., option=orjson.OPT_SORT_KEYS)`) so hashes and evaluation results are reproducible.
- Use stable IDs with the prefixes from the approved design: `GOAL-`, `ACTOR-`, `CAP-`, `SCN-`, `BR-`, `STATE-`, `AC-`, `NFR-`, `DEC-`, and `RFI-`.

---

## File Map

| Area | Files | Responsibility |
|---|---|---|
| Core contracts | `src/delivery/contracts.py`, `src/delivery/ids.py` | Stable Pydantic contracts, enums, IDs, hashes, and lifecycle vocabulary |
| Project truth | `src/delivery/truth.py` | Controlled fact, decision, question, scope, and workflow-cursor updates |
| Evidence intake | `src/delivery/intake.py` | Evidence-preserving fact extraction and authorized truth ingestion |
| Persistence | `src/models/business/delivery_project.py`, `src/models/business/artifact.py`, `src/models/business/rfi.py`, `src/repositories/delivery_repository.py` | Optimistic project-truth storage, immutable artifacts, and RFIs |
| PM control plane | `src/delivery/control/intent.py`, `src/delivery/control/policy.py`, `src/graphs/v2/nodes.py`, `src/graphs/v2/routes.py` | Intent parsing, authorization, escalation, dispatch, pause, and resume |
| Requirement contracts | `src/delivery/requirements/contracts.py` | Structured outline, module, and PRD schemas |
| Quality | `src/delivery/quality.py`, `src/delivery/requirements/validators.py` | Deterministic validation, reviewer finding aggregation, and approval gates |
| Requirement stages | `src/delivery/requirements/context.py`, `src/delivery/requirements/runner.py`, `src/graphs/v2/requirement/graph.py` | Context projection and bounded author/validate/review/revise execution |
| Prompts and rendering | `template/prompts/v2/*.md.j2`, `src/delivery/requirements/render.py` | Contract-bound generation/review prompts and backward-compatible Markdown |
| Integration | `src/config.py`, `src/graphs/graph.py`, `src/graphs/state.py`, `src/graphs/nodes.py`, `src/graphs/routes.py`, `src/services/interface/project_document_interface_service.py`, `src/routes/project_document.py` | Feature flag, graph entry, persisted V2 reads, and additive API access |
| Evaluation | `tests/fixtures/golden/user_center/*.json`, `tests/delivery/*`, `scripts/evaluate_requirement_v2.py` | Golden-project regressions, defect injection, and comparison reports |

---

### Task 1: Establish the V2 Contract Kernel

**Files:**
- Create: `src/delivery/__init__.py`
- Create: `src/delivery/contracts.py`
- Create: `src/delivery/ids.py`
- Create: `tests/__init__.py`
- Create: `tests/delivery/__init__.py`
- Test: `tests/delivery/test_contracts.py`

**Interfaces:**
- Consumes: Pydantic `BaseModel`, `Field`, `model_validator`; standard-library `Enum`, `hashlib`, and `uuid`.
- Produces: `ArtifactEnvelope`, `ArtifactStatus`, `ArtifactType`, `EvidenceRef`, `FactRecord`, `DecisionRecord`, `OpenQuestion`, `ProjectTruth`, `TraceLink`, `WorkflowCursor`, `IntentEnvelope`, `IntentType`, `PMAction`, `PMActionType`, `RFIRequest`, `StageResult`, `ValidationReport`, `ReviewFinding`, `CoverageReport`, `stable_id(prefix, natural_key)`, and `content_hash(value)`.

- [ ] **Step 1: Write contract and lifecycle tests**

```python
from unittest import TestCase
from pydantic import ValidationError

from src.delivery.contracts import ArtifactEnvelope, ArtifactStatus, ArtifactType, FactRecord, FactKind
from src.delivery.ids import stable_id


class ContractTest(TestCase):
    def test_stable_id_is_reproducible_and_prefixed(self):
        self.assertEqual(stable_id("CAP", "用户管理"), stable_id("CAP", "用户管理"))
        self.assertRegex(stable_id("CAP", "用户管理"), r"^CAP-[A-F0-9]{12}$")

    def test_confirmed_fact_requires_evidence(self):
        with self.assertRaises(ValidationError):
            FactRecord(id="BR-1", kind=FactKind.CONFIRMED, statement="不使用 Token", evidence=[])

    def test_approved_artifact_requires_successful_reports(self):
        with self.assertRaises(ValidationError):
            ArtifactEnvelope(
                artifact_id="artifact-1", type=ArtifactType.REQUIREMENT_OUTLINE,
                project_id="project-1", schema_version="2.0", version=1,
                status=ArtifactStatus.APPROVED,
                scope=["CAP-1"], input_baselines={}, facts_used=[], decisions_used=[],
                structured_content={}, trace_links=[], validation_report=None,
                coverage_report=None, provenance={"run_id": "run-1"},
                content_hash="0" * 64,
            )
```

- [ ] **Step 2: Run the tests and verify they fail because the V2 contracts do not exist**

Run: `python -m unittest tests.delivery.test_contracts -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.delivery'`.

- [ ] **Step 3: Implement the contract kernel**

Use string enums and explicit Pydantic models. The central shapes must expose these exact fields:

```python
class ArtifactStatus(StrEnum):
    UNVERIFIED_DRAFT = "unverified_draft"
    DRAFT = "draft"
    VALIDATING = "validating"
    REVISION_REQUIRED = "revision_required"
    BLOCKED = "blocked"
    APPROVED = "approved"
    STALE = "stale"
    SUPERSEDED = "superseded"


class ArtifactEnvelope(BaseModel):
    artifact_id: str
    project_id: str
    type: ArtifactType
    schema_version: str
    version: int = Field(ge=1)
    status: ArtifactStatus
    scope: list[str]
    input_baselines: dict[str, int]
    facts_used: list[str]
    decisions_used: list[str]
    structured_content: dict[str, Any]
    assumptions: list[AssumptionRecord] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    trace_links: list[TraceLink] = Field(default_factory=list)
    coverage_report: CoverageReport | None = None
    validation_report: ValidationReport | None = None
    provenance: dict[str, Any]
    content_hash: str


class StageResult(BaseModel):
    candidate_artifact: ArtifactEnvelope
    baseline_versions: dict[str, int]
    proposed_patch: dict[str, Any]
    validation_report: ValidationReport
    review_findings: list[ReviewFinding]
    coverage_report: CoverageReport
    assumptions: list[AssumptionRecord]
    open_questions: list[str]
    provenance: dict[str, Any]
```

Implement `ALLOWED_ARTIFACT_TRANSITIONS` and `can_transition(current, target)`. Reject an `APPROVED` envelope unless deterministic validation passed, coverage is complete, no blocking finding exists, and no business assumption is unresolved.

- [ ] **Step 4: Run contract tests**

Run: `python -m unittest tests.delivery.test_contracts -v`

Expected: all contract, ID, hash, and lifecycle tests PASS.

- [ ] **Step 5: Commit the kernel**

```bash
git add src/delivery tests/__init__.py tests/delivery
git commit -m "feat: add delivery v2 contracts"
```

### Task 2: Persist Project Truth, Immutable Artifacts, and RFIs

**Files:**
- Create: `src/models/business/delivery_project.py`
- Create: `src/models/business/artifact.py`
- Create: `src/models/business/rfi.py`
- Create: `src/repositories/delivery_repository.py`
- Create: `src/delivery/truth.py`
- Test: `tests/delivery/test_delivery_repository.py`
- Test: `tests/delivery/test_truth.py`

**Interfaces:**
- Consumes: Task 1 contracts and existing `BUSINESS_DB` auto-discovery in `src/models/base.py`.
- Produces: `DeliveryRepository.get_truth(project_id: str) -> ProjectTruth | None`, `DeliveryRepository.compare_and_swap_truth(project_id: str, expected_revision: int, truth: ProjectTruth) -> int`, `DeliveryRepository.next_artifact_version(project_id: str, artifact_type: ArtifactType, artifact_id: str) -> int`, `DeliveryRepository.save_artifact(artifact: ArtifactEnvelope) -> None`, `DeliveryRepository.get_artifact(project_id: str, artifact_id: str, version: int | None = None) -> ArtifactEnvelope | None`, `DeliveryRepository.mark_stale(project_id: str, artifact_ids: set[str], caused_by: str) -> int`, `DeliveryRepository.save_rfi(rfi: RFIRequest) -> None`, and `ProjectTruthService.apply(action: TruthAction, expected_revision: int) -> ProjectTruth`.

- [ ] **Step 1: Write isolated repository and truth-service tests**

Use `tempfile.TemporaryDirectory`, point the model tables at an isolated SQLite engine in test setup, and prove these cases:

```python
class DeliveryRepositoryTest(IsolatedAsyncioTestCase):
    async def test_approved_artifact_version_cannot_be_overwritten(self):
        await self.repository.save_artifact(self.approved_outline_v1)
        with self.assertRaises(ImmutableArtifactError):
            await self.repository.save_artifact(self.approved_outline_v1.model_copy(
                update={"structured_content": {"changed": True}}
            ))

    async def test_truth_compare_and_swap_rejects_stale_writer(self):
        await self.repository.compare_and_swap_truth("project-1", 0, self.truth)
        with self.assertRaises(RevisionConflictError):
            await self.repository.compare_and_swap_truth("project-1", 0, self.truth)
```

Also verify that approving version 2 marks only version 1 of the same artifact identity `SUPERSEDED`, while an upstream change marks traced downstream artifacts `STALE` without deleting them.

- [ ] **Step 2: Run persistence tests and verify the missing models fail**

Run: `python -m unittest tests.delivery.test_delivery_repository tests.delivery.test_truth -v`

Expected: FAIL because `DeliveryRepository` and the V2 tables are absent.

- [ ] **Step 3: Add aggregate truth and immutable artifact tables**

Create three new Piccolo tables without altering the existing `project` table:

```python
class DeliveryProject(Table, db=BUSINESS_DB):
    project_id = Varchar(length=36, primary_key=True)
    revision = Integer(default=0)
    truth_json = Text()
    workflow_json = Text()
    created_at = Timestamp()
    updated_at = Timestamp()


class Artifact(Table, db=BUSINESS_DB):
    id = Varchar(length=36, primary_key=True)
    project_id = Varchar(length=36)
    artifact_id = Varchar(length=80)
    artifact_type = Varchar(length=40)
    version = Integer()
    status = Varchar(length=32)
    content_hash = Varchar(length=64)
    envelope_json = Text()
    created_at = Timestamp()


class Rfi(Table, db=BUSINESS_DB):
    id = Varchar(length=80, primary_key=True)
    project_id = Varchar(length=36)
    status = Varchar(length=24)
    payload_json = Text()
    created_at = Timestamp()
    resolved_at = Timestamp(null=True)
```

The repository must perform canonical serialization, compare stored hashes before writes, and use an atomic revision predicate for truth updates. `ProjectTruthService` is the only public mutation interface and accepts typed actions such as `AddFact`, `RecordDecision`, `OpenQuestionAction`, `MoveCursor`, and `CreateChangeRequest`.

- [ ] **Step 4: Run persistence and truth tests**

Run: `python -m unittest tests.delivery.test_delivery_repository tests.delivery.test_truth -v`

Expected: all optimistic-lock, immutable-version, stale-impact, canonical-JSON, and truth-authorization tests PASS.

- [ ] **Step 5: Commit persistence**

```bash
git add src/models/business/delivery_project.py src/models/business/artifact.py src/models/business/rfi.py src/repositories/delivery_repository.py src/delivery/truth.py tests/delivery/test_delivery_repository.py tests/delivery/test_truth.py
git commit -m "feat: persist delivery project truth"
```

### Task 3: Define Structured Requirement Artifacts and Markdown Rendering

**Files:**
- Create: `src/delivery/requirements/__init__.py`
- Create: `src/delivery/requirements/contracts.py`
- Create: `src/delivery/requirements/render.py`
- Create: `tests/delivery/requirements/__init__.py`
- Test: `tests/delivery/requirements/test_contracts.py`
- Test: `tests/delivery/requirements/test_render.py`

**Interfaces:**
- Consumes: Task 1 trace IDs and artifact envelope.
- Produces: `RequirementStage`, `RequirementOutline`, `RequirementModule`, `ProductRequirementsDocument`, `render_outline(content: RequirementOutline) -> str`, `render_module(content: RequirementModule) -> str`, and `render_prd(content: ProductRequirementsDocument) -> str`.

- [ ] **Step 1: Write schema and deterministic-render tests**

```python
class RequirementContractTest(TestCase):
    def test_business_rule_requires_acceptance_criteria(self):
        with self.assertRaises(ValidationError):
            RequirementModule(
                id="CAP-ACCOUNT", name="账户管理", mission="管理账户生命周期",
                business_value="保证账户可用", actors=["ACTOR-USER"], preconditions=[],
                triggers=["用户提交注册"], scenarios=[],
                rules=[BusinessRule(id="BR-REGISTER", statement="用户名唯一", acceptance_ids=[])],
                states=[], interactions=[], boundaries=[], nfr_ids=[], out_of_scope=[],
            )

    def test_outline_markdown_contains_business_sections_only(self):
        markdown = render_outline(valid_outline())
        self.assertIn("## 业务能力地图", markdown)
        self.assertNotIn("HTTP", markdown)
        self.assertNotIn("数据库", markdown)
```

- [ ] **Step 2: Run schema tests and verify they fail**

Run: `python -m unittest tests.delivery.requirements.test_contracts tests.delivery.requirements.test_render -v`

Expected: FAIL because the requirement contract package is absent.

- [ ] **Step 3: Implement the three stable content schemas**

Use typed nested models instead of Markdown fields. Required top-level fields are:

```python
class RequirementOutline(BaseModel):
    background: str
    problem_statement: str
    goals: list[Goal]
    actors: list[Actor]
    external_systems: list[ExternalSystem]
    in_scope: list[ScopeItem]
    out_of_scope: list[ScopeItem]
    scenarios: list[ScenarioSummary]
    capabilities: list[Capability]
    glossary: list[GlossaryTerm]
    constraints: list[Constraint]
    assumptions: list[AssumptionRecord]
    open_questions: list[str]
    fact_sources: dict[str, list[str]]


class RequirementModule(BaseModel):
    id: str
    name: str
    mission: str
    business_value: str
    actors: list[str]
    preconditions: list[str]
    triggers: list[str]
    scenarios: list[Scenario]
    rules: list[BusinessRule]
    states: list[StateDefinition]
    permissions: list[PermissionRule]
    interactions: list[CapabilityInteraction]
    boundaries: list[BoundaryCondition]
    acceptance_criteria: list[AcceptanceCriterion]
    nfr_ids: list[str]
    out_of_scope: list[str]
    assumptions: list[AssumptionRecord]
    open_questions: list[str]


class ProductRequirementsDocument(BaseModel):
    goals: list[Goal]
    release_scope: ReleaseScope
    roles_and_permissions: list[PermissionRule]
    journeys: list[Journey]
    capability_relationships: list[CapabilityInteraction]
    global_rules: list[BusinessRule]
    global_states: list[StateDefinition]
    glossary: list[GlossaryTerm]
    priorities: list[PriorityItem]
    global_acceptance_criteria: list[AcceptanceCriterion]
    nfrs: list[NonFunctionalRequirement]
    governance_requirements: list[GovernanceRequirement]
    external_interactions: list[ExternalInteraction]
    success_metrics: list[SuccessMetric]
    decisions: list[str]
    risks: list[RiskRecord]
    assumptions: list[AssumptionRecord]
    open_questions: list[str]
    traceability: list[TraceLink]
```

Renderers must sort stable IDs, produce repeatable Markdown, label assumptions and questions explicitly, and never add information absent from the structured content.

- [ ] **Step 4: Run requirement contract tests**

Run: `python -m unittest tests.delivery.requirements.test_contracts tests.delivery.requirements.test_render -v`

Expected: all schema-invariant and snapshot-string tests PASS.

- [ ] **Step 5: Commit requirement contracts**

```bash
git add src/delivery/requirements tests/delivery/requirements
git commit -m "feat: define structured requirement artifacts"
```

### Task 4: Build the Golden Project and Deterministic Quality Gates

**Files:**
- Create: `tests/fixtures/golden/user_center/project.json`
- Create: `tests/fixtures/golden/user_center/expected_rules.json`
- Create: `tests/fixtures/golden/user_center/defects.json`
- Create: `src/delivery/quality.py`
- Create: `src/delivery/requirements/validators.py`
- Test: `tests/delivery/requirements/test_validators.py`

**Interfaces:**
- Consumes: Task 1 reports and findings; Task 3 structured requirement schemas.
- Produces: `validate_outline(artifact, truth)`, `validate_module(artifact, truth)`, `validate_prd(artifact, truth)`, `aggregate_quality(validation, findings, coverage)`, and `ApprovalDecision`.

- [ ] **Step 1: Encode the user-center regression facts and failing gate tests**

The golden fixture must explicitly encode:

```json
{
  "confirmed_facts": [
    {"id": "BR-AUTH-001", "statement": "用户名和密码完成登录"},
    {"id": "BR-AUTH-002", "statement": "不使用 Token 或会话管理"},
    {"id": "BR-AUTH-003", "statement": "不实现失败登录锁定"}
  ],
  "forbidden_unconfirmed": [
    "密码重置", "短信验证码", "邮件验证", "API Key 网关", "Nacos", "Apollo"
  ],
  "forbidden_stage_terms": [
    "CREATE TABLE", "HTTP POST", "Kubernetes", "K8s", "连接池"
  ]
}
```

Write tests proving the validator rejects: reintroduced locking, an invented password-reset capability, a page called a business capability, a rule without an `AC-*` link, a PRD containing DDL, and a candidate based on a stale baseline.

- [ ] **Step 2: Run validator tests and verify they fail**

Run: `python -m unittest tests.delivery.requirements.test_validators -v`

Expected: FAIL because validator functions do not exist.

- [ ] **Step 3: Implement deterministic gates and explicit evidence**

Each validator returns `ValidationReport(checks=list[ValidationCheck], passed=bool)`. Implement checks for:

- schema and prefix validity;
- relevant fact used or explicitly excluded with a reason;
- scope inclusion/exclusion conflicts;
- forbidden stage terms and technical structures;
- capability classification (reject names ending in “页面”, “公共模块”, “初始化模块”, or “微服务” unless a domain profile explicitly permits them);
- every `BR-*` linked to one or more `AC-*`;
- every cross-capability interaction has exactly one owner;
- no unresolved business assumption;
- exact `input_baselines` match;
- blocking reviewer findings are zero.

`aggregate_quality` must return one of `APPROVE`, `REVISE`, or `BLOCK`; it may not calculate a single opaque score.

- [ ] **Step 4: Run quality-gate tests**

Run: `python -m unittest tests.delivery.requirements.test_validators -v`

Expected: all golden-fixture, defect-injection, evidence, and gate-decision tests PASS.

- [ ] **Step 5: Commit the baseline and validators**

```bash
git add tests/fixtures/golden/user_center src/delivery/quality.py src/delivery/requirements/validators.py tests/delivery/requirements/test_validators.py
git commit -m "feat: add requirement quality gates"
```

### Task 5: Add Fact Intake, Intent Parsing, and Deterministic PM Policy

**Files:**
- Create: `src/delivery/control/__init__.py`
- Create: `src/delivery/intake.py`
- Create: `src/delivery/control/intent.py`
- Create: `src/delivery/control/policy.py`
- Create: `template/prompts/v2/fact_extractor.md.j2`
- Create: `template/prompts/v2/intent_parser.md.j2`
- Modify: `src/utils/prompt_utils.py`
- Create: `tests/delivery/control/__init__.py`
- Test: `tests/delivery/test_intake.py`
- Test: `tests/delivery/control/test_intent.py`
- Test: `tests/delivery/control/test_policy.py`

**Interfaces:**
- Consumes: Task 1 `IntentEnvelope`, `PMAction`, truth records, workflow cursor, and artifact manifests.
- Produces: `FactExtractor.extract(evidence: list[EvidenceDocument]) -> FactExtraction`, `FactIngestionService.ingest(project_id: str, extraction: FactExtraction, expected_revision: int) -> ProjectTruth`, `IntentParser.parse(messages: list[AnyMessage], context: IntentContext) -> IntentEnvelope`, `PMPolicy.decide(intent: IntentEnvelope, truth: ProjectTruth) -> PMAction`, `get_v2_fact_extractor_prompt() -> str`, and `get_v2_intent_prompt(context: IntentContext) -> str`.

- [ ] **Step 1: Write intent and policy matrix tests**

```python
class PMPolicyTest(TestCase):
    def test_only_generate_user_service_tests_preserves_exclusion_scope(self):
        intent = IntentEnvelope(
            intent_type=IntentType.GENERATE,
            target_stage="test_design",
            target_artifacts=["user-service-tests"],
            include_scope=["CAP-USER"],
            exclude_scope=["CAP-ORDER", "CAP-AUDIT"],
            referenced_versions={"prd": 3},
            requested_effect="generate",
            changes_baseline=False,
            confidence=0.99,
            resume_task="TASK-42",
        )
        action = PMPolicy().decide(intent, truth_with_cursor("TASK-42"))
        self.assertEqual(action.type, PMActionType.DISPATCH)
        self.assertEqual(action.allowed_scope, ["CAP-USER"])
        self.assertEqual(action.forbidden_scope, ["CAP-ORDER", "CAP-AUDIT"])

    def test_business_scope_change_escalates(self):
        action = PMPolicy().decide(scope_change_intent(), approved_truth())
        self.assertEqual(action.type, PMActionType.ESCALATE)
```

Cover ordinary questions, clarification replies, “继续”, “是否更新”, scope restriction, pause, resume, retry after technical failure, low-confidence intent, reversible engineering defaults, and business/cost/compliance decisions.

Add intake tests proving every extracted confirmed fact contains a source message/file ID and quoted evidence span, duplicates merge without losing evidence, explicit exclusions remain negative facts, and suggestions/examples remain proposals rather than confirmed requirements.

- [ ] **Step 2: Run intent tests and verify they fail**

Run: `python -m unittest tests.delivery.test_intake tests.delivery.control.test_intent tests.delivery.control.test_policy -v`

Expected: FAIL because the fact intake and PM control packages are absent.

- [ ] **Step 3: Implement a narrow parser adapter and pure policy**

`FactExtractor` must request exactly `FactExtraction`, preserve `EvidenceRef(source_type, source_id, quote)`, classify exclusions as confirmed negative facts, and classify examples or suggestions as proposals. `FactIngestionService` validates evidence and writes through `ProjectTruthService`; the extractor cannot persist directly.

Use these intake boundaries:

```python
class EvidenceDocument(BaseModel):
    source_type: Literal["message", "file", "approved_artifact"]
    source_id: str
    content: str


class FactExtraction(BaseModel):
    confirmed_facts: list[FactRecord]
    derived_conclusions: list[FactRecord]
    proposals: list[AssumptionRecord]
    contradictions: list[FactContradiction]
    open_questions: list[OpenQuestion]


class IntentContext(BaseModel):
    cursor: WorkflowCursor
    open_questions: list[OpenQuestion]
    artifact_versions: dict[str, int]
    in_scope: list[str]
    out_of_scope: list[str]
```

The intent LLM adapter must request exactly `IntentEnvelope` and receive only the latest user message, current cursor, open questions, artifact manifests, and relevant scope. The pure policy must use an explicit table:

```python
POLICY: dict[IntentType, Callable[[IntentEnvelope, ProjectTruth], PMAction]] = {
    IntentType.QUESTION: answer_without_baseline_change,
    IntentType.CLARIFICATION: apply_clarification,
    IntentType.CHANGE_REQUEST: create_change_or_escalate,
    IntentType.SCOPE_LIMIT: dispatch_with_scope_guard,
    IntentType.PAUSE: pause_cursor,
    IntentType.RESUME: resume_cursor,
    IntentType.RETRY: retry_current_task,
    IntentType.GENERATE: dispatch_generation,
}
```

Reject dispatch when confidence is below `0.80`, a referenced baseline is stale, or target scope is ambiguous. These return `ESCALATE` with a concrete decision question; they do not guess.

- [ ] **Step 4: Run PM control tests**

Run: `python -m unittest tests.delivery.test_intake tests.delivery.control.test_intent tests.delivery.control.test_policy -v`

Expected: all intent fixtures and deterministic policy cases PASS.

- [ ] **Step 5: Commit PM control logic**

```bash
git add src/delivery/intake.py src/delivery/control template/prompts/v2/fact_extractor.md.j2 template/prompts/v2/intent_parser.md.j2 src/utils/prompt_utils.py tests/delivery/test_intake.py tests/delivery/control
git commit -m "feat: add fact intake and pm control policy"
```

### Task 6: Implement Context Projection and the Bounded Requirement Stage Runner

**Files:**
- Create: `src/delivery/requirements/context.py`
- Create: `src/delivery/requirements/runner.py`
- Create: `src/graphs/v2/__init__.py`
- Create: `src/graphs/v2/state.py`
- Create: `src/graphs/v2/requirement/__init__.py`
- Create: `src/graphs/v2/requirement/graph.py`
- Create: `src/graphs/v2/requirement/nodes.py`
- Create: `src/graphs/v2/requirement/routes.py`
- Test: `tests/delivery/requirements/test_context.py`
- Test: `tests/delivery/requirements/test_runner.py`

**Interfaces:**
- Consumes: Tasks 1–5 contracts, repository, truth, PM scope guard, and validators.
- Produces: `build_context_projection(project_truth, action, stage) -> ContextProjection`, `RequirementStageRunner.run(request) -> StageResult`, and `create_requirement_v2_graph() -> CompiledStateGraph`.

- [ ] **Step 1: Write context isolation and bounded-loop tests**

```python
class RequirementRunnerTest(IsolatedAsyncioTestCase):
    async def test_author_never_receives_unrelated_chat_history(self):
        projection = build_context_projection(self.truth, self.action, RequirementStage.OUTLINE)
        self.assertNotIn("messages", projection.model_dump())
        self.assertEqual(projection.allowed_scope, ["CAP-USER"])

    async def test_runner_stops_after_two_revisions(self):
        runner = RequirementStageRunner(author=failing_author(), reviewers=[blocking_reviewer()], max_revisions=2)
        result = await runner.run(self.request)
        self.assertEqual(result.candidate_artifact.status, ArtifactStatus.BLOCKED)
        self.assertEqual(result.provenance["revision_attempts"], 2)
```

Also prove reviewer exceptions produce a failed finding rather than being silently skipped, a changed baseline invalidates the stage result, and an author cannot write outside `allowed_scope`.

- [ ] **Step 2: Run runner tests and verify they fail**

Run: `python -m unittest tests.delivery.requirements.test_context tests.delivery.requirements.test_runner -v`

Expected: FAIL because projection and runner modules do not exist.

- [ ] **Step 3: Implement the reusable stage skeleton**

The graph must follow this exact state progression:

```text
prepare_context -> author -> validate -> review -> aggregate
  -> revise -> validate
  -> finalize
```

Use `max_revisions=2`. `author` and `revise` return structured content only. `validate` is deterministic. Reviewers run independently and return `ReviewFinding` values with `code`, `severity`, `artifact_path`, `evidence`, and `suggested_correction`. `finalize` returns `StageResult`; it cannot persist or approve. Route functions inspect typed gate decisions, not free-form model text.

- [ ] **Step 4: Run stage-runner tests**

Run: `python -m unittest tests.delivery.requirements.test_context tests.delivery.requirements.test_runner -v`

Expected: all context minimization, scope, reviewer-failure, stale-baseline, and bounded-revision tests PASS.

- [ ] **Step 5: Commit the stage skeleton**

```bash
git add src/delivery/requirements/context.py src/delivery/requirements/runner.py src/graphs/v2 tests/delivery/requirements/test_context.py tests/delivery/requirements/test_runner.py
git commit -m "feat: add bounded requirement stage runner"
```

### Task 7: Deepen Outline, Requirement Module, and PRD Generation

**Files:**
- Create: `src/delivery/requirements/authors.py`
- Create: `src/delivery/requirements/reviewers.py`
- Create: `src/delivery/profiles.py`
- Create: `template/prompts/v2/requirement_author.md.j2`
- Create: `template/prompts/v2/completeness_reviewer.md.j2`
- Create: `template/prompts/v2/consistency_reviewer.md.j2`
- Create: `template/prompts/v2/scope_reviewer.md.j2`
- Create: `template/prompts/v2/testability_reviewer.md.j2`
- Create: `template/prompts/v2/traceability_reviewer.md.j2`
- Modify: `src/utils/prompt_utils.py`
- Test: `tests/delivery/requirements/test_authors.py`
- Test: `tests/delivery/requirements/test_reviewers.py`

**Interfaces:**
- Consumes: Task 3 schemas, Task 4 validators, and Task 6 `ContextProjection`/runner ports.
- Produces: `RequirementAuthor.generate(projection, stage)`, reviewer adapters implementing `review(artifact, projection) -> list[ReviewFinding]`, and `DomainProfileRegistry.get(name)`.

- [ ] **Step 1: Write prompt-contract and reviewer-evidence tests**

Use fake structured-output models to capture messages and return fixed Pydantic values. Verify:

- the old text `Demo 优先：速度 > 细节` is absent from every V2 prompt;
- outline instructions require measurable goals, actors, scope, end-to-end scenarios, capability map, glossary, constraints, assumptions, questions, and evidence;
- module instructions require normal/alternate/error scenarios, rules, states, permissions, boundaries, and Given/When/Then acceptance criteria;
- PRD instructions require cross-module journeys, global rules, release scope, NFRs, governance, metrics, and traceability;
- facts marked out of scope cannot appear as capabilities;
- reviewers return a path and evidence for every blocking finding.

- [ ] **Step 2: Run author/reviewer tests and verify they fail**

Run: `python -m unittest tests.delivery.requirements.test_authors tests.delivery.requirements.test_reviewers -v`

Expected: FAIL because V2 authors, profiles, and reviewer adapters are absent.

- [ ] **Step 3: Implement contract-bound authors and specialized reviewers**

Provide one author adapter parameterized by `RequirementStage`, plus separate reviewer adapters for completeness, consistency, scope, testability, and traceability. Bind each call to the exact Pydantic output schema with strict structured output. Prompts must state:

```text
Use only confirmed_facts, approved_decisions, derived_conclusions, and direct upstream artifacts.
Do not convert examples, suggestions, or common industry behavior into requirements.
If business behavior is missing, emit an assumption or open question; do not fill it silently.
Modify only allowed_scope and preserve forbidden_scope.
Return structured data only. Approval is not your responsibility.
```

Add a `generic_software` domain profile with terminology checks, capability-name rules, common risk prompts, and required review dimensions. Profile rules supplement but never override core gates.

- [ ] **Step 4: Run generation adapter tests**

Run: `python -m unittest tests.delivery.requirements.test_authors tests.delivery.requirements.test_reviewers -v`

Expected: all prompt-boundary, schema-output, reviewer-evidence, and profile tests PASS.

- [ ] **Step 5: Commit requirement generation**

```bash
git add src/delivery/requirements/authors.py src/delivery/requirements/reviewers.py src/delivery/profiles.py template/prompts/v2 src/utils/prompt_utils.py tests/delivery/requirements/test_authors.py tests/delivery/requirements/test_reviewers.py
git commit -m "feat: deepen v2 requirement generation"
```

### Task 8: Add PM Approval, Versioning, Change Impact, and RFI Handling

**Files:**
- Create: `src/delivery/control/service.py`
- Create: `src/delivery/rfi.py`
- Test: `tests/delivery/control/test_service.py`
- Test: `tests/delivery/test_rfi.py`

**Interfaces:**
- Consumes: repository, truth service, PM policy, stage runner, quality gate, and `StageResult`.
- Produces: `PMControlService.handle_message(command)`, `PMControlService.handle_stage_result(result)`, `RFIService.create(request)`, and `RFIService.resolve(rfi_id, truth)`.

- [ ] **Step 1: Write approval and RFI decision tests**

```python
class PMControlServiceTest(IsolatedAsyncioTestCase):
    async def test_stage_result_cannot_approve_after_baseline_changes(self):
        result = stage_result(baseline_versions={"outline": 1})
        await self.repository.save_artifact(approved_outline(version=2))
        decision = await self.service.handle_stage_result(result)
        self.assertEqual(decision.type, PMActionType.DISPATCH)
        self.assertEqual(decision.reason_code, "STALE_STAGE_RESULT")

    async def test_business_rfi_escalates_to_human(self):
        resolution = await self.rfi_service.resolve("RFI-1", truth_without_business_answer())
        self.assertEqual(resolution.type, RFIResolutionType.HUMAN_ESCALATION)
```

Cover approval, revision, blocked human decision, answer from baseline, PM reversible engineering decision, change request, out-of-scope rejection, pause/resume cursor restoration, and exact downstream invalidation through trace links.

- [ ] **Step 2: Run control-service tests and verify they fail**

Run: `python -m unittest tests.delivery.control.test_service tests.delivery.test_rfi -v`

Expected: FAIL because the orchestration services do not exist.

- [ ] **Step 3: Implement the only artifact-approval boundary**

`PMControlService.handle_stage_result` must:

1. reload current truth and artifact baselines;
2. reject mismatched versions;
3. recompute deterministic validation rather than trusting the author result;
4. aggregate reviewer findings and coverage;
5. persist `DRAFT`, `BLOCKED`, or `APPROVED` as a new immutable version;
6. advance `WorkflowCursor` only after `APPROVED` is durably stored;
7. mark only traced downstream artifacts stale after a change;
8. return a typed `PMAction` for graph routing.

`RFIService.resolve` must return exactly one of `ANSWER_FROM_BASELINE`, `PM_DECISION`, `CREATE_CHANGE_REQUEST`, `HUMAN_ESCALATION`, or `REJECT_OUT_OF_SCOPE`, record the evidence and resolution, and notify affected workflow tasks through stored IDs.

- [ ] **Step 4: Run PM service and RFI tests**

Run: `python -m unittest tests.delivery.control.test_service tests.delivery.test_rfi -v`

Expected: all approval-boundary, version-race, impact, cursor, and RFI classification tests PASS.

- [ ] **Step 5: Commit PM orchestration**

```bash
git add src/delivery/control/service.py src/delivery/rfi.py tests/delivery/control/test_service.py tests/delivery/test_rfi.py
git commit -m "feat: enforce pm approval and rfi handling"
```

### Task 9: Integrate V2 Behind a Safe Feature Flag and Add Read APIs

**Files:**
- Modify: `.env.example`
- Modify: `src/config.py`
- Modify: `src/graphs/state.py`
- Modify: `src/graphs/graph.py`
- Modify: `src/graphs/nodes.py`
- Modify: `src/graphs/routes.py`
- Create: `src/graphs/v2/nodes.py`
- Create: `src/graphs/v2/routes.py`
- Modify: `src/services/interface/project_document_interface_service.py`
- Modify: `src/routes/project_document.py`
- Modify: `src/schemas/project_document.py`
- Test: `tests/delivery/test_graph_integration.py`
- Test: `tests/delivery/test_document_api.py`

**Interfaces:**
- Consumes: Task 8 `PMControlService`, Task 6 V2 requirement graph, and existing `create_agent()`/document routes.
- Produces: `settings.delivery_v2_enabled`, V2 graph nodes/routes, `GET /api/v1/project/{project_id}/artifacts/{artifact_type}`, and optional `version` query selection.

- [ ] **Step 1: Write flag, route, and API compatibility tests**

Use patched node functions and a fake repository. Prove:

- flag false routes exactly through the existing `product_manager_node` and V1 subgraphs;
- flag true uses `intent_parser_v2_node -> pm_policy_v2_node -> requirement_v2_node`;
- V2 `ANSWER` and `PAUSE` end without dispatch;
- scope-limited dispatch reaches V2 with allowed/forbidden scope intact;
- existing `/requirement-outline`, `/requirement-modules`, and `/requirement-overall` methods retain their response types;
- the new artifact endpoint returns structured content, rendered Markdown, version, status, trace links, and quality reports.

- [ ] **Step 2: Run integration tests and verify they fail**

Run: `python -m unittest tests.delivery.test_graph_integration tests.delivery.test_document_api -v`

Expected: FAIL because the feature flag, V2 routing, and artifact endpoint are absent.

- [ ] **Step 3: Wire V2 additively**

Add to `Settings`:

```python
delivery_v2_enabled: bool = Field(default=False, description="Enable requirement delivery V2")
delivery_v2_max_revisions: int = Field(default=2, ge=0, le=5)
delivery_v2_intent_confidence_threshold: float = Field(default=0.80, ge=0, le=1)
```

Add matching values to `.env.example`. Extend graph state with serialized V2 action, cursor, and stage result fields; add new serializer enum entries. Route at the graph boundary based on the setting, leaving all V1 nodes untouched. New document reads use `DeliveryRepository`; legacy reads keep using current project columns until a later migration phase.

- [ ] **Step 4: Run integration and the full deterministic suite**

Run: `python -m unittest discover -s tests -p 'test_*.py' -v`

Expected: all V2 unit/integration tests PASS; V1 route assertions PASS with the flag disabled.

- [ ] **Step 5: Commit the feature-flagged integration**

```bash
git add .env.example src/config.py src/graphs src/services/interface/project_document_interface_service.py src/routes/project_document.py src/schemas/project_document.py tests/delivery/test_graph_integration.py tests/delivery/test_document_api.py
git commit -m "feat: integrate requirement delivery v2"
```

### Task 10: Add Reproducible Evaluation and Phase-1 Acceptance Evidence

**Files:**
- Create: `src/delivery/evaluation.py`
- Create: `scripts/evaluate_requirement_v2.py`
- Create: `tests/delivery/test_evaluation.py`
- Create: `tests/fixtures/golden/user_center/compliant/outline.json`
- Create: `tests/fixtures/golden/user_center/compliant/module_account.json`
- Create: `tests/fixtures/golden/user_center/compliant/prd.json`
- Create: `docs/evaluation/requirement-v2.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: golden fixtures, artifact repository, validators, reviewer findings, prompt/schema/profile versions, and persisted provenance.
- Produces: `EvaluationRunner.evaluate(project_fixture, artifacts) -> EvaluationReport` and CLI JSON/Markdown reports.

- [ ] **Step 1: Write metric and acceptance-report tests**

```python
class EvaluationTest(TestCase):
    def test_user_center_acceptance_metrics_are_explicit(self):
        report = EvaluationRunner().evaluate(load_user_center_fixture(), compliant_artifacts())
        self.assertEqual(report.fact_coverage, 1.0)
        self.assertEqual(report.traceability, 1.0)
        self.assertEqual(report.unsupported_business_content_count, 0)
        self.assertEqual(report.stage_boundary_violation_count, 0)
        self.assertEqual(report.blocking_contradiction_count, 0)
        self.assertTrue(report.passed)
```

Add defect-injection expectations for removed scenarios, changed rules, invented assumptions, technical leakage, contradiction, and stale baselines.

- [ ] **Step 2: Run evaluation tests and verify they fail**

Run: `python -m unittest tests.delivery.test_evaluation -v`

Expected: FAIL because the evaluation runner is absent.

- [ ] **Step 3: Implement reproducible reports and operator documentation**

The report must contain exact counts and evidence for fact coverage, unsupported content, omissions, contradictions, stage leakage, traceability, acceptance-test coverage, reviewer defect recall, intent accuracy, escalation accuracy, and stale-baseline detection. Record model parameters, prompt/profile/schema versions, input hashes, tool calls, retry count, token use, duration, cost when available, and approval evidence; mark unavailable runtime fields as JSON `null`, not fabricated values.

The CLI accepts:

```text
python scripts/evaluate_requirement_v2.py \
  --fixture tests/fixtures/golden/user_center/project.json \
  --artifact-dir data/evaluation/user_center \
  --output data/evaluation/report.json
```

`docs/evaluation/requirement-v2.md` must document the golden fixture, metrics, release gate, defect-injection procedure, and how to compare a candidate result with the accepted baseline. Update the README with the disabled-by-default V2 flag and evaluation command.

- [ ] **Step 4: Run all verification checks**

Run: `python -m unittest discover -s tests -p 'test_*.py' -v`

Expected: all tests PASS.

Run: `python scripts/evaluate_requirement_v2.py --fixture tests/fixtures/golden/user_center/project.json --artifact-dir tests/fixtures/golden/user_center/compliant --output /tmp/requirement-v2-report.json`

Expected: exit code 0 and a report with `passed: true`, `fact_coverage: 1.0`, `traceability: 1.0`, and zero unsupported-content/stage-boundary/blocking-contradiction counts.

Run: `git diff --check`

Expected: no whitespace errors.

- [ ] **Step 5: Commit evaluation and docs**

```bash
git add src/delivery/evaluation.py scripts/evaluate_requirement_v2.py tests/delivery/test_evaluation.py tests/fixtures/golden/user_center/compliant docs/evaluation/requirement-v2.md README.md
git commit -m "feat: add requirement v2 evaluation gate"
```

---

## Completion Gate

Do not declare Phase 1 complete until all of these are true:

- `python -m unittest discover -s tests -p 'test_*.py' -v` passes from a clean process.
- The user-center golden report passes all hard gates with evidence.
- V1 routing and legacy document endpoints still work with `DELIVERY_V2_ENABLED=false`.
- V2 never reintroduces Token/session management, failed-login locking, password reset, SMS/email verification, API-key gateways, Nacos, or Apollo unless those facts are explicitly confirmed in a new baseline.
- Outline capabilities are business capabilities, not pages or services.
- Every business rule in every module and the PRD maps to at least one verifiable acceptance criterion.
- Outline, modules, and PRD contain no DDL, HTTP contract, Kubernetes, connection-pool, or framework design.
- Intent regressions for “继续”, “只生成某模块”, and “是否更新” preserve cursor and scope correctly.
- Reviewer failures are visible and block approval; they are never silently skipped.
- A stale `StageResult` is rejected and rescheduled against the latest baseline.
- Every approved artifact can be reproduced from its recorded inputs, prompt/profile/schema versions, and provenance.
