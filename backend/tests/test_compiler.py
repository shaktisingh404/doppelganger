"""Smoke test for the layer-loading and assembly logic (no LLM calls, no
network). Run with: python -m tests.test_compiler  (run from backend/)
"""
from compiler.assembly import assemble_persona
from compiler.layers import load_common_template
from compiler.models import BusinessInfo, InstanceDelta, InstanceInput
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

persona = assemble_persona(common_template, archetype, delta, instance)

assert persona.archetype_id == "finance_advisor"
assert "Alex" in persona.system_prompt
assert "# Role & Responsibilities" in persona.system_prompt
assert "# Communication Style" in persona.system_prompt
assert "Adopt a friendly tone throughout the conversation." in persona.system_prompt
assert "# Archetype Guardrails" in persona.system_prompt
assert "# Specialization\nretirement planning" in persona.system_prompt
assert "employer 401k matching" in persona.system_prompt
assert "specific stock picks" in persona.system_prompt
assert common_template.splitlines()[0] in persona.system_prompt

# Optional fields must not leak an empty section when unset.
bare_delta = InstanceDelta()
bare_persona = assemble_persona(common_template, archetype, bare_delta, instance)
assert "# Specialization" not in bare_persona.system_prompt
assert "# Things to Avoid" not in bare_persona.system_prompt
assert "# Business Information" not in bare_persona.system_prompt

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
business_persona = assemble_persona(common_template, archetype, delta, business_instance)
assert "# Business Information" in business_persona.system_prompt
assert "Riverside Dental" in business_persona.system_prompt
assert "12 Elm St" in business_persona.system_prompt
assert "Mon-Fri 9am-5pm" in business_persona.system_prompt
assert "- cleanings" in business_persona.system_prompt
assert "closed on public holidays" in business_persona.system_prompt
assert "say you'll check and follow up" in business_persona.system_prompt

# No tone given -> no tone directive, but language directive still present.
no_tone_instance = instance.model_copy(update={"tone": None})
no_tone_persona = assemble_persona(common_template, archetype, delta, no_tone_instance)
assert "Respond in English." in no_tone_persona.system_prompt
assert "tone throughout the conversation" not in no_tone_persona.system_prompt

# Archetype-static content must form a byte-identical, cacheable prefix
# across every instance of the same archetype, regardless of instance name
# or delta. Instance-specific content must come after it.
other_instance = instance.model_copy(update={"name": "Jordan"})
other_persona = assemble_persona(common_template, archetype, delta, other_instance)
static_prefix_end = persona.system_prompt.index("# Persona:")
assert persona.system_prompt[:static_prefix_end] == other_persona.system_prompt[:static_prefix_end]
assert persona.system_prompt.index(archetype.persona_text) < persona.system_prompt.index(instance.name)
assert persona.system_prompt.index("# Archetype Guardrails") < persona.system_prompt.index("# Persona:")

print("ok")
