"""Disable Chroma product telemetry without changing the shared PostHog installation."""
from chromadb.config import Settings
from chromadb.telemetry.product import ProductTelemetryClient, ProductTelemetryEvent
from overrides import override


class NoOpTelemetry(ProductTelemetryClient):
    """Avoid the obsolete PostHog capture call made even when Chroma telemetry is disabled."""

    @override
    def capture(self, event: ProductTelemetryEvent) -> None:
        """Discard product events; helpdesk queries should not produce analytics events."""


def chroma_settings() -> Settings:
    """Use the same telemetry configuration for indexing and querying."""
    return Settings(
        anonymized_telemetry=False,
        chroma_product_telemetry_impl="assistant.telemetry.NoOpTelemetry",
        chroma_telemetry_impl="assistant.telemetry.NoOpTelemetry",
    )
