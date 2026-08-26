"""Third-party provider integrations (Strava first; Garmin, Polar, ... later).

The provider-agnostic core lives here (adapter contract, registry);
provider-specific code lives in ``app.providers.<name>`` subpackages.
"""

from app.providers.base import (
    ActivityIdPage,
    Provider,
    ProviderAdapter,
    ProviderCredentials,
    ProviderIdentity,
)
from app.providers.registry import ProviderRegistry

__all__ = [
    "ActivityIdPage",
    "Provider",
    "ProviderAdapter",
    "ProviderCredentials",
    "ProviderIdentity",
    "ProviderRegistry",
]
