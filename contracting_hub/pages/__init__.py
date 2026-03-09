"""Application page modules."""

from contracting_hub.pages.browse import ROUTE as BROWSE_ROUTE
from contracting_hub.pages.browse import index as browse_index
from contracting_hub.pages.contract_detail import ROUTE as CONTRACT_DETAIL_ROUTE
from contracting_hub.pages.contract_detail import index as contract_detail_index
from contracting_hub.pages.home import ROUTE as HOME_ROUTE
from contracting_hub.pages.home import index

__all__ = [
    "BROWSE_ROUTE",
    "CONTRACT_DETAIL_ROUTE",
    "HOME_ROUTE",
    "browse_index",
    "contract_detail_index",
    "index",
]
