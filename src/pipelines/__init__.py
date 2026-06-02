"""Pipeline registry."""
from .base import Pipeline, PipelineRun, EXTRACTION_PROMPT
from .variant_a import VariantA
from .variant_b import VariantB
from .variant_c import VariantC
from .variant_d import VariantD
from .variant_e import VariantE
from .variant_f import VariantF

VARIANTS = {
    "A": VariantA,
    "B": VariantB,
    "C": VariantC,
    "D": VariantD,
    "E": VariantE,
    "F": VariantF,
}

__all__ = ["Pipeline", "PipelineRun", "EXTRACTION_PROMPT", "VARIANTS",
           "VariantA", "VariantB", "VariantC", "VariantD", "VariantE", "VariantF"]
