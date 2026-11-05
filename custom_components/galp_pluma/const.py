"""Constantes da integração Galp Pluma."""

DOMAIN = "galp_pluma"

CONF_SCAN_INTERVAL = "scan_interval"  # em minutos; 0 = só leitura manual

DEFAULT_SCAN_INTERVAL = 15
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 43200  # 30 dias
MANUAL_ONLY = 0

# A garrafa entra em deep sleep: depois de uma falha tenta-se de novo mais cedo.
RETRY_INTERVAL_MINUTES = 3
MAX_CONSECUTIVE_FAILURES = 5

# Depois das tentativas rápidas, continua-se a tentar de hora a hora (ou no
# intervalo normal, se for mais curto), para que um intervalo de dias não adie
# uma leitura falhada por uma semana inteira.
GIVE_UP_RETRY_MINUTES = 60

# Uma leitura falhada não torna os sensores indisponíveis enquanto a última
# leitura boa for mais recente do que max(2 x intervalo, STALE_MIN_MINUTES).
STALE_MIN_MINUTES = 60

NAME_PREFIX = "Pluma"

# Escolher se o gás é propano (garrafa azul) ou butano (garrafa laranja)
CONF_GAS_TYPE = "gas_type"

GAS_TYPE_BUTANE = "butane"
GAS_TYPE_PROPANE = "propane"

GAS_TYPES = [GAS_TYPE_BUTANE, GAS_TYPE_PROPANE]
DEFAULT_GAS_TYPE = GAS_TYPE_PROPANE 

GAS_ICONS = {
    GAS_TYPE_BUTANE: "mdi:gas-cylinder",
    GAS_TYPE_PROPANE: "mdi:propane-tank",
}


def gas_type_from_entry(entry) -> str:
    """Opção > dados > omissão. Nunca entry.data[CONF_GAS_TYPE] directamente."""
    return entry.options.get(
        CONF_GAS_TYPE, entry.data.get(CONF_GAS_TYPE, DEFAULT_GAS_TYPE)
    )


def is_pluma_name(name: str | None) -> bool:
    """O nome Bluetooth começa por "Pluma", sem distinguir maiúsculas."""
    return (name or "").upper().startswith(NAME_PREFIX.upper())
