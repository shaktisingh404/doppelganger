"""Smoke test for the layer-loading and assembly logic (no LLM calls, no
network). Run with: python -m tests.test_compiler  (run from backend/)
"""
from pydantic import ValidationError

from compiler.assembly import assemble_persona
from compiler.layers import load_common_template
from compiler.models import (
    MAX_REFERENCE_FILE_CHARS,
    MAX_REFERENCE_FILES_TOTAL_CHARS,
    BusinessInfo,
    InstanceDelta,
    InstanceInput,
    ReferenceFile,
)
from compiler.pipeline import instantiate_persona
from storage.archetype_store import FileArchetypeStore

store = FileArchetypeStore("data/archetypes")
archetypes = store.list()
assert {a.id for a in archetypes} == {"finance_advisor", "receptionist"}

archetype = store.get("finance_advisor")
common_template = load_common_template("data/common_template.txt")
delta = InstanceDelta(
    specialization="retirement planning",
    key_talking_points=["employer 401k matching"],
    things_to_avoid=["specific stock picks"],
)
instance = InstanceInput(
    archetype_id="finance_advisor",
    name="Alex",
    language="English",
    tone="friendly",
    description="doesn't matter here, delta is precomputed above",
)

prompt = assemble_persona(common_template, archetype, delta, instance)

assert "Alex" in prompt
assert "# Role & Responsibilities" in prompt
assert "# Communication Style" in prompt
assert "Adopt a friendly tone throughout the conversation." in prompt
assert "# Archetype Guardrails" in prompt
assert "# Specialization\nretirement planning" in prompt
assert "employer 401k matching" in prompt
assert "specific stock picks" in prompt
assert common_template.splitlines()[0] in prompt

# Optional fields must not leak an empty section when unset.
bare_delta = InstanceDelta()
bare_prompt = assemble_persona(common_template, archetype, bare_delta, instance)
assert "# Specialization" not in bare_prompt
assert "# Things to Avoid" not in bare_prompt
assert "# Business Information" not in bare_prompt

# business_info is injected verbatim, not extracted, and stays out when unset.
business_instance = instance.model_copy(
    update={
        "business_info": BusinessInfo(
            name="Riverside Dental",
            address="12 Elm St",
            hours="Mon-Fri 9am-5pm",
            services=["cleanings", "checkups"],
            notes=["closed on public holidays"],
        )
    }
)
business_prompt = assemble_persona(common_template, archetype, delta, business_instance)
assert "# Business Information" in business_prompt
assert "Riverside Dental" in business_prompt
assert "12 Elm St" in business_prompt
assert "Mon-Fri 9am-5pm" in business_prompt
assert "- cleanings" in business_prompt
assert "closed on public holidays" in business_prompt
assert "say you'll check and follow up" in business_prompt

# No tone given -> no tone directive, but language directive still present.
no_tone_instance = instance.model_copy(update={"tone": None})
no_tone_prompt = assemble_persona(common_template, archetype, delta, no_tone_instance)
assert "Respond in English." in no_tone_prompt
assert "tone throughout the conversation" not in no_tone_prompt

# conversational_style, when given, rides in the same Communication Style
# section rather than starting a new one.
styled_instance = instance.model_copy(update={"conversational_style": "Keep replies to one sentence."})
styled_prompt = assemble_persona(common_template, archetype, delta, styled_instance)
style_section_start = styled_prompt.index("# Communication Style")
next_section_start = styled_prompt.index("# Specialization")
assert style_section_start < styled_prompt.index("Keep replies to one sentence.") < next_section_start

# reference_files are injected verbatim (like business_info), one section
# covering every attached file, and stay out entirely when unset.
files_instance = instance.model_copy(
    update={
        "reference_files": [
            ReferenceFile(filename="faq.md", content="Q: Refunds?\nA: Within 30 days."),
            ReferenceFile(filename="hours.txt", content="Open 9-5 Mon-Fri."),
        ]
    }
)
files_prompt = assemble_persona(common_template, archetype, delta, files_instance)
assert "# Reference Material" in files_prompt
assert "## faq.md" in files_prompt
assert "Within 30 days." in files_prompt
assert "## hours.txt" in files_prompt
assert "Open 9-5 Mon-Fri." in files_prompt
assert "# Reference Material" not in prompt  # unset on the base instance

# A single file over the per-file cap is rejected at the model boundary,
# not silently truncated or allowed to blow up the prompt.
try:
    ReferenceFile(filename="huge.txt", content="x" * (MAX_REFERENCE_FILE_CHARS + 1))
    assert False, "should reject a file over the per-file character limit"
except ValidationError:
    pass

# Several files individually under the cap can still collectively exceed
# the total budget, and that must be rejected too.
try:
    InstanceInput(
        archetype_id="finance_advisor",
        name="Alex",
        language="English",
        description="x",
        reference_files=[
            ReferenceFile(filename=f"f{i}.txt", content="x" * (MAX_REFERENCE_FILE_CHARS))
            for i in range(3)
        ],
    )
    assert False, "should reject files whose combined size exceeds the total limit"
except ValidationError:
    pass
assert 3 * MAX_REFERENCE_FILE_CHARS > MAX_REFERENCE_FILES_TOTAL_CHARS  # the test above is actually testing something

# Archetype-static content must form a byte-identical, cacheable prefix
# across every instance of the same archetype, regardless of instance name
# or delta. Instance-specific content must come after it.
other_instance = instance.model_copy(update={"name": "Jordan"})
other_prompt = assemble_persona(common_template, archetype, delta, other_instance)
static_prefix_end = prompt.index("# Persona:")
assert prompt[:static_prefix_end] == other_prompt[:static_prefix_end]
assert prompt.index(archetype.persona_text) < prompt.index(instance.name)
assert prompt.index("# Archetype Guardrails") < prompt.index("# Persona:")

print("ok")


# --- instantiate_persona: generation's output becoming a real persona ---

persona = instantiate_persona(
    name="Alex", system_prompt=prompt, first_message="Hi, this is Alex.", archetype_id="finance_advisor"
)
assert persona.name == "Alex"
assert persona.system_prompt == prompt
assert persona.first_message == "Hi, this is Alex."
assert persona.archetype_id == "finance_advisor"
assert persona.persona_id  # assigned, non-empty

# Two instantiations of the same text get different identities.
other = instantiate_persona(name="Alex", system_prompt=prompt)
assert other.persona_id != persona.persona_id
assert other.archetype_id is None
assert other.first_message == ""

print("instantiate_persona: ok")
