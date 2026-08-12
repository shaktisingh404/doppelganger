"""Layer 4: pure composition of layers 1-3 into a final system prompt.

No LLM calls here — just string/object concatenation.
"""
import uuid

from compiler.models import (
    ArchetypeSpec,
    AssembledPersona,
    BusinessInfo,
    InstanceDelta,
    InstanceInput,
)


def _business_info_section(info: BusinessInfo) -> str:
    lines = [f"Business name: {info.name}"]
    if info.address:
        lines.append(f"Address: {info.address}")
    if info.phone:
        lines.append(f"Phone: {info.phone}")
    if info.hours:
        lines.append(f"Hours: {info.hours}")
    if info.services:
        lines.append("Services offered:\n" + "\n".join(f"- {s}" for s in info.services))
    if info.notes:
        lines.append("Additional facts:\n" + "\n".join(f"- {n}" for n in info.notes))
    lines.append(
        "Only state the details listed above about this business; if asked "
        "something not covered here, say you'll check and follow up."
    )
    return "# Business Information\n" + "\n".join(lines)


def assemble_persona(
    common_template: str,
    archetype: ArchetypeSpec,
    delta: InstanceDelta,
    instance: InstanceInput,
) -> AssembledPersona:
    guardrails = "\n".join(f"- {g}" for g in archetype.guardrail_additions)
    talking_points = "\n".join(f"- {p}" for p in delta.key_talking_points)
    avoid = "\n".join(f"- {a}" for a in delta.things_to_avoid)

    style_lines = [f"Respond in {instance.language}."]
    if instance.tone:
        style_lines.append(f"Adopt a {instance.tone} tone throughout the conversation.")

    # Archetype-static content stays first and byte-identical across every
    # instance of this archetype, so it forms a stable, cacheable prefix.
    # Instance/delta content — which varies per call — always comes after.
    sections = [
        common_template,
        f"# Role & Responsibilities\n{archetype.persona_text}",
    ]
    if guardrails:
        sections.append(f"# Archetype Guardrails\n{guardrails}")
    sections.append(f"# Persona: {instance.name}")
    if instance.business_info:
        sections.append(_business_info_section(instance.business_info))
    sections.append("# Communication Style\n" + "\n".join(style_lines))
    if delta.specialization:
        sections.append(f"# Specialization\n{delta.specialization}")
    if delta.extra_constraint:
        sections.append(f"# Extra Constraints\n{delta.extra_constraint}")
    if talking_points:
        sections.append(f"# Key Talking Points\n{talking_points}")
    if avoid:
        sections.append(f"# Things to Avoid\n{avoid}")

    return AssembledPersona(
        persona_id=str(uuid.uuid4()),
        archetype_id=archetype.id,
        name=instance.name,
        system_prompt="\n\n".join(sections),
    )
