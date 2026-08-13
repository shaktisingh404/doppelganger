"""Orchestrates layers 1-4 into one call, plus the separate identity step.
Used by both app/ and cli.py.
"""
import uuid

from compiler.assembly import assemble_persona
from compiler.layers import build_instance_delta, load_common_template
from compiler.models import AssembledPersona, InstanceDelta, InstanceInput
from config import get_settings
from storage.archetype_store import ArchetypeStore


async def generate_system_prompt(instance: InstanceInput, store: ArchetypeStore) -> str:
    """The "Generate" step: free text in, a full system_prompt string out.
    Doesn't create or store anything — the caller may hand-edit the result
    before ever calling instantiate_persona with it.

    An empty description has nothing to extract, so the LLM call is
    skipped rather than spent on a guaranteed-empty InstanceDelta — this
    also makes it cheap enough to call the instant an archetype is picked,
    to preview the *full* prompt (common template + guardrails included),
    not just the archetype's own short blurb.
    """
    archetype = store.get(instance.archetype_id)
    common_template = load_common_template(get_settings().common_template_path)
    delta = await build_instance_delta(instance.description) if instance.description.strip() else InstanceDelta()
    return assemble_persona(common_template, archetype, delta, instance)


def instantiate_persona(
    name: str,
    system_prompt: str,
    first_message: str = "",
    archetype_id: str | None = None,
    tool_instance_ids: list[str] | None = None,
) -> AssembledPersona:
    """The "Create" step: whatever system_prompt/first_message the caller
    hands in — generated verbatim, hand-edited, or typed from scratch —
    becomes a real, identified, chattable persona."""
    return AssembledPersona(
        persona_id=str(uuid.uuid4()),
        archetype_id=archetype_id,
        name=name,
        first_message=first_message,
        system_prompt=system_prompt,
        tool_instance_ids=tool_instance_ids or [],
    )
