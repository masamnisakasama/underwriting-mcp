"""mock サービス（APP_MODE=mock）の組み立て（§22.2）。

AWS 実装を足す際は、ここでアダプタを差し替えるだけで service 本体は変えない。
"""
from __future__ import annotations

from pathlib import Path

from .adapters.fixture_analyzer import FixtureDocumentAnalyzer
from .adapters.aws.stores import DynamoJobStore, S3ObjectStore
from .adapters.aws.workflow import StepFunctionsWorkflowClient
from .adapters.local_workflow import LocalWorkflowClient
from .adapters.memory import InMemoryJobStore, InMemoryObjectStore
from .demo_seed import seed_demo_cases
from .service import UnderwritingService

_REPO_ROOT = Path(__file__).resolve().parents[1]


def build_mock_service(
    *,
    rulesets_dir: str | Path | None = None,
    samples_dir: str | Path | None = None,
    public_base_url: str = "https://underwriting-mcp.local",
    code_version: str | None = None,
    seed_demos: bool = True,
) -> UnderwritingService:
    rulesets_dir = Path(rulesets_dir or _REPO_ROOT / "rulesets")
    samples_dir = Path(samples_dir or _REPO_ROOT / "samples")

    object_store = InMemoryObjectStore()
    job_store = InMemoryJobStore()
    analyzer = FixtureDocumentAnalyzer(samples_dir)
    workflow = LocalWorkflowClient(object_store, job_store, analyzer, code_version=code_version)

    if seed_demos:
        seed_demo_cases(job_store, samples_dir)

    return UnderwritingService(
        object_store=object_store,
        job_store=job_store,
        workflow=workflow,
        rulesets_dir=rulesets_dir,
        public_base_url=public_base_url,
        demo_mode=True,
    )


def build_aws_service(
    *,
    rulesets_dir: str | Path | None = None,
    public_base_url: str = "https://underwriting-mcp.local",
) -> UnderwritingService:
    rulesets_dir = Path(rulesets_dir or _REPO_ROOT / "rulesets")
    object_store = S3ObjectStore()
    job_store = DynamoJobStore()
    workflow = StepFunctionsWorkflowClient(job_store)
    return UnderwritingService(
        object_store=object_store,
        job_store=job_store,
        workflow=workflow,
        rulesets_dir=rulesets_dir,
        public_base_url=public_base_url,
        demo_mode=False,
    )
