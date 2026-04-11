"""PDF processing sub-package.

This module provides multiple PDF extraction engines:
- PDFProcessor: Standard processor using PyMuPDF and pypdf
- DoclingEngine: GPU-accelerated processor using Docling
  (supports Apple Silicon MPS, NVIDIA CUDA, and CPU fallback)
- MinerUEngine: MinerU engine (best LaTeX formula extraction, CDM 90.85)
- MarkerEngine: Marker engine (best overall accuracy 95.67, GPL-3.0)
"""

from .enhanced import (  # noqa: F401
    EnhancedPDFProcessor,
    ExtractedImage,
    ExtractedTable,
    ExtractedFormula,
)
from .math_formula import (  # noqa: F401
    FormulaReconstructor,
    DoclingFormulaEnricher,
    MathRegion,
    unicode_to_latex,
    has_math_unicode,
    protect_math_content,
)
from .processor import PDFProcessor  # noqa: F401
from .docling_engine import (  # noqa: F401
    DoclingEngine,
    DoclingConversionResult,
    DoclingTable,
    DoclingImage,
    DoclingFormula,
    DoclingCodeBlock,
)
from .mineru_engine import (  # noqa: F401
    MinerUEngine,
    MinerUConversionResult,
    MinerUTable,
    MinerUImage,
    MinerUFormula,
)
from .marker_engine import (  # noqa: F401
    MarkerEngine,
    MarkerConversionResult,
    MarkerTable,
    MarkerImage,
    MarkerFormula,
    MarkerCodeBlock,
)
from .llm_client import LLMClient, LLMResponse  # noqa: F401
from .llm_orchestrator import (  # noqa: F401
    LLMOrchestrator,
    OrchestrationResult,
    OrchestrationPlan,
    PDFCharacteristics,
    EngineTask,
    EngineResult,
)

__all__ = [
    "PDFProcessor",
    "EnhancedPDFProcessor",
    "ExtractedImage",
    "ExtractedTable",
    "ExtractedFormula",
    "FormulaReconstructor",
    "DoclingFormulaEnricher",
    "MathRegion",
    "unicode_to_latex",
    "has_math_unicode",
    "protect_math_content",
    "DoclingEngine",
    "DoclingConversionResult",
    "DoclingTable",
    "DoclingImage",
    "DoclingFormula",
    "DoclingCodeBlock",
    "MinerUEngine",
    "MinerUConversionResult",
    "MinerUTable",
    "MinerUImage",
    "MinerUFormula",
    "MarkerEngine",
    "MarkerConversionResult",
    "MarkerTable",
    "MarkerImage",
    "MarkerFormula",
    "MarkerCodeBlock",
    "LLMClient",
    "LLMResponse",
    "LLMOrchestrator",
    "OrchestrationResult",
    "OrchestrationPlan",
    "PDFCharacteristics",
    "EngineTask",
    "EngineResult",
]
