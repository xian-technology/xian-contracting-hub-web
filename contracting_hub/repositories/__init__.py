"""Repository layer for persistence-oriented data access."""

from contracting_hub.repositories.auth import AuthRepository
from contracting_hub.repositories.contract_versions import ContractVersionRepository
from contracting_hub.repositories.contracts import (
    CONTRACT_SEARCH_INDEX_TABLE_NAME,
    PUBLIC_VISIBLE_STATUSES,
    ContractDetailRecord,
    ContractRelationTraversal,
    ContractRepository,
    ContractSearchResult,
)
from contracting_hub.repositories.deployments import (
    PUBLIC_DEPLOYABLE_STATUSES,
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
    "ContractRelationTraversal",
    "ContractRepository",
    "ContractSearchResult",
    "ContractVersionRepository",
    "DeveloperKPIRecord",
    "DeveloperKPIRepository",
    "DeploymentRepository",
    "PlaygroundTargetRepository",
    "PUBLIC_DEPLOYABLE_STATUSES",
    "PUBLISHED_KPI_CONTRACT_STATUSES",
    "PUBLIC_VISIBLE_STATUSES",
    "RatingRepository",
    "StarRepository",
]
