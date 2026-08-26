"""Registry mapping provider values to adapter instances."""

from app.errors.app_error import NotFoundError
from app.providers.base import ProviderAdapter


class ProviderRegistry:
    """Maps ``providers.value`` to a ``ProviderAdapter``.

    Populated at app startup for every provider whose configuration is
    present; looked up by the provider routes. An unknown or unconfigured
    provider reads as missing (404), not as a server error.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, ProviderAdapter] = {}

    def register(self, adapter: ProviderAdapter) -> None:
        """Register an adapter under its ``provider`` value.

        Raises NotFoundError when a *different* adapter is already
        registered for the same provider (programming error).
        """
        existing = self._adapters.get(adapter.provider)
        if existing is not None and existing is not adapter:
            raise NotFoundError(
                f"An adapter for provider {adapter.provider!r} is already registered."
            )
        self._adapters[adapter.provider] = adapter

    def get(self, provider: str) -> ProviderAdapter:
        """The adapter for a provider value.

        Raises NotFoundError when the provider is unknown or not configured
        on this instance.
        """
        adapter = self._adapters.get(provider)
        if adapter is None:
            raise NotFoundError(f"Provider {provider!r} is not available on this instance.")
        return adapter

    def available(self) -> list[str]:
        """Registered provider values, in registration order."""
        return list(self._adapters)
