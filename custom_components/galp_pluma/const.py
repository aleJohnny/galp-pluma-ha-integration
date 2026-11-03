"""Constantes da integração Galp Pluma."""

DOMAIN = "galp_pluma"

CONF_SCAN_INTERVAL = "scan_interval"  # em minutos

DEFAULT_SCAN_INTERVAL = 15
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 240

# A garrafa entra em deep sleep: depois de uma falha tenta-se de novo mais cedo
# antes de dar o sensor como indisponível.
RETRY_INTERVAL_MINUTES = 3
MAX_CONSECUTIVE_FAILURES = 5

NAME_PREFIX = "Pluma"


def is_pluma_name(name: str | None) -> bool:
    """O nome Bluetooth começa por "Pluma", sem distinguir maiúsculas."""
    return (name or "").upper().startswith(NAME_PREFIX.upper())
