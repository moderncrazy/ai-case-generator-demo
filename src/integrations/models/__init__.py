"""Model-gateway persistence under ``src/integrations/models``.

The ``model_profile`` table is owned by the integrations layer so that
Profile domain modules do not absorb model-gateway configuration.
"""

from src.integrations.models.profile_model import ModelProfile

__all__ = ["ModelProfile"]
