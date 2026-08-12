"""Orchestrates layers 1-4 into one call. Used by both app/ and cli.py."""
from compiler.assembly import assemble_persona
from compiler.layers import build_instance_delta, load_common_template
from compiler.models import AssembledPersona, InstanceInput
from config import get_settings
from storage.archetype_store import ArchetypeStore


async def build_persona(
    instance: InstanceInput, store: ArchetypeStore
) -> AssembledPersona:
    archetype = store.get(instance.archetype_id)
    common_template = load_common_template(get_settings().common_template_path)
    delta = await build_instance_delta(instance.description)
    return assemble_persona(common_template, archetype, delta, instance)
