"""Repository layer for persistence-oriented data access."""

from contracting_hub.repositories.auth import AuthRepository
from contracting_hub.repositories.contract_versions import ContractVersionRepository
from contracting_hub.repositories.contracts import (
    CONTRACT_SEARCH_INDEX_TABLE_NAME,
    PUBLIC_HOME_PAGE_DEPLOYMENT_STATUSES,
    PUBLIC_VISIBLE_STATUSES,
    ContractDetailRecord,
    ContractHighlightRecord,
    ContractRelationTraversal,
    ContractRepository,
    ContractSearchResult,
)
from contracting_hub.repositories.deployments import (
    PUBLIC_DEPLOYABLE_STATUSES,
    DeploymentHistoryRecord,
    DeploymentRepository,
)
from contracting_hub.repositories.developer_kpis import (
    PUBLISHED_KPI_CONTRACT_STATUSES,
    DeveloperKPIRecord,
    DeveloperKPIRepository,
)
from contracting_hub.repositories.playground_targets import PlaygroundTargetRepository
from contracting_hub.repositories.ratings import RatingRepository
from contracting_hub.repositories.stars import StarRepository

__all__ = [
    "CONTRACT_SEARCH_INDEX_TABLE_NAME",
    "AuthRepository",
    "ContractDetailRecord",
    "ContractHighlightRecord",
    "ContractRelationTraversal",
    "ContractRepository",
    "ContractSearchResult",
    "ContractVersionRepository",
    "DeveloperKPIRecord",
    "DeveloperKPIRepository",
    "DeploymentHistoryRecord",
    "DeploymentRepository",
    "PlaygroundTargetRepository",
    "PUBLIC_HOME_PAGE_DEPLOYMENT_STATUSES",
    "PUBLIC_DEPLOYABLE_STATUSES",
    "PUBLISHED_KPI_CONTRACT_STATUSES",
    "PUBLIC_VISIBLE_STATUSES",
    "RatingRepository",
    "StarRepository",
]
