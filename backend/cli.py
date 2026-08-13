"""Terminal chat loop for building and testing a persona without the API."""
import asyncio

from compiler.models import BusinessInfo, InstanceInput
from compiler.pipeline import generate_system_prompt, instantiate_persona
from config import get_settings
from providers.llm import run_turn
from storage.archetype_store import FileArchetypeStore


async def main() -> None:
    store = FileArchetypeStore(get_settings().archetypes_dir)
    archetypes = store.list()

    print("Available archetypes:")
    for a in archetypes:
        print(f"  {a.id} - {a.display_name}")

    archetype_id = input("archetype id: ").strip()
    name = input("persona name: ").strip()
    language = input("language [English]: ").strip() or "English"
    tone = input("tone (optional): ").strip() or None
    description = input("free-text description: ").strip()

    business_info = None
    if input("add business details? [y/N]: ").strip().lower() == "y":
        business_info = BusinessInfo(
            name=input("business name: ").strip(),
            address=input("address (optional): ").strip() or None,
            phone=input("phone (optional): ").strip() or None,
            hours=input("hours (optional): ").strip() or None,
            services=[
                s.strip()
                for s in input("services (comma-separated, optional): ").split(",")
                if s.strip()
            ],
            notes=[
                n.strip()
                for n in input("other facts (comma-separated, optional): ").split(",")
                if n.strip()
            ],
        )

    instance = InstanceInput(
        archetype_id=archetype_id,
        name=name,
        language=language,
        tone=tone,
        description=description,
        business_info=business_info,
    )

    system_prompt = await generate_system_prompt(instance, store)
    print("\n--- Generated system prompt ---")
    print(system_prompt)
    print("--- end system prompt ---\n")

    first_message = input("first message (optional, blank = user speaks first): ").strip()
    persona = instantiate_persona(
        name=name, system_prompt=system_prompt, first_message=first_message, archetype_id=archetype_id
    )

    print(f"\nChatting as {persona.name}. Type 'quit' to exit.\n")
    history: list[dict[str, str]] = []
    if persona.first_message:
        print(f"{persona.name}> {persona.first_message}\n")
        history.append({"role": "assistant", "content": persona.first_message})
    while True:
        user_message = input("you> ").strip()
        if user_message.lower() in {"quit", "exit"}:
            break
        reply = await run_turn(persona.system_prompt, history, user_message)
        print(f"{persona.name}> {reply}\n")
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": reply})


if __name__ == "__main__":
    asyncio.run(main())
