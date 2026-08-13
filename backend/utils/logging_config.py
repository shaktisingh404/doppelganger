"""One place to turn logging on for the whole app. Every module just does
`logging.getLogger(__name__)` (see providers/llm.py, tools/handoff.py,
scheduler/dispatcher.py) and relies on this having run once at startup.

Without it, those loggers fall back to Python's bare "handler of last
resort": technically visible but with no timestamp, level, or logger
name — which is how providers.llm's truncated-reply warning went
unnoticed in practice even though the logger.warning() call was firing.
"""
import logging

_configured = False


def configure(level: int = logging.INFO) -> None:
    global _configured
    if _configured:
        return
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    _configured = True
