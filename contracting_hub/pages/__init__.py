"""Application page modules."""

from contracting_hub.pages.browse import ROUTE as BROWSE_ROUTE
from contracting_hub.pages.browse import index as browse_index
from contracting_hub.pages.contract_detail import ROUTE as CONTRACT_DETAIL_ROUTE
from contracting_hub.pages.contract_detail import index as contract_detail_index
from contracting_hub.pages.developer_profile import ROUTE as DEVELOPER_PROFILE_ROUTE
from contracting_hub.pages.developer_profile import index as developer_profile_index
from contracting_hub.pages.home import ROUTE as HOME_ROUTE
from contracting_hub.pages.home import index
from contracting_hub.pages.login import ROUTE as LOGIN_ROUTE
from contracting_hub.pages.login import index as login_index
from contracting_hub.pages.profile_settings import ROUTE as PROFILE_SETTINGS_ROUTE
from contracting_hub.pages.profile_settings import index as profile_settings_index
from contracting_hub.pages.register import ROUTE as REGISTER_ROUTE
from contracting_hub.pages.register import index as register_index

__all__ = [
    "BROWSE_ROUTE",
    "CONTRACT_DETAIL_ROUTE",
    "DEVELOPER_PROFILE_ROUTE",
    "HOME_ROUTE",
    "LOGIN_ROUTE",
    "PROFILE_SETTINGS_ROUTE",
    "REGISTER_ROUTE",
    "browse_index",
    "contract_detail_index",
    "developer_profile_index",
    "index",
    "login_index",
    "profile_settings_index",
    "register_index",
]
