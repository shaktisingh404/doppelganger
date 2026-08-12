"""Layer 1 (common template) and Layer 3 (delta extraction)."""
from pathlib import Path

from compiler.models import InstanceDelta
from providers.llm import extract_delta


def load_common_template(path: str | Path) -> str:
    """Layer 1: static guardrails/format text, loaded once, never per-request."""
    return Path(path).read_text().strip()


async def build_instance_delta(description: str) -> InstanceDelta:
    """Layer 3: the one narrow LLM call in this pipeline that isn't pure
    composition — extraction into a fixed schema, not open-ended generation."""
    return await extract_delta(description)
