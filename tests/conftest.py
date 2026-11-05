"""Prepara o ambiente de testes.

O ``__init__.py`` da integração importa o Home Assistant. Para testar a lógica
própria (protocolo, cliente BLE, coordinator) sem o instalar, regista-se um
pacote ``galp_pluma`` que aponta para a pasta SEM executar o ``__init__.py`` e,
quando o bleak / Home Assistant não estão instalados, módulos mínimos de
substituição (stubs).

Isto valida a lógica da integração, mas NÃO valida a compatibilidade com a API
real do Home Assistant (config flow, sensores, registo de entidades).
"""

from __future__ import annotations

from importlib.util import find_spec
from pathlib import Path
import sys
import types
from typing import Generic, TypeVar

REAL_HA = find_spec("homeassistant") is not None
REAL_BLEAK = find_spec("bleak") is not None and find_spec("bleak_retry_connector") is not None


def _stub(name: str, **attrs: object) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__dict__.update(attrs)
    sys.modules[name] = module
    parent, _, child = name.rpartition(".")
    if parent and parent in sys.modules:
        setattr(sys.modules[parent], child, module)
    return module


if not REAL_BLEAK:

    class BleakError(Exception):
        pass

    class BLEDevice:
        def __init__(self, address: str, name: str | None = None) -> None:
            self.address = address
            self.name = name

    _stub("bleak")
    _stub("bleak.backends")
    _stub("bleak.backends.device", BLEDevice=BLEDevice)
    _stub("bleak.exc", BleakError=BleakError)
    _stub(
        "bleak_retry_connector",
        BleakClientWithServiceCache=object,
        establish_connection=None,  # os testes substituem-no
    )

if not REAL_HA:
    _T = TypeVar("_T")

    class UpdateFailed(Exception):
        pass

    class DataUpdateCoordinator(Generic[_T]):
        def __init__(self, hass, logger, *, config_entry=None, name=None, update_interval=None):
            self.hass = hass
            self.logger = logger
            self.config_entry = config_entry
            self.name = name
            self.update_interval = update_interval
            self.data = None

        def async_update_listeners(self):
            self.listeners_called = getattr(self, "listeners_called", 0) + 1

    def async_ble_device_from_address(hass, address, connectable=True):
        return getattr(hass, "device", None)

    _stub("homeassistant")
    _stub("homeassistant.components")
    _stub(
        "homeassistant.components.bluetooth",
        async_ble_device_from_address=async_ble_device_from_address,
    )
    _stub("homeassistant.helpers")
    _stub(
        "homeassistant.helpers.update_coordinator",
        DataUpdateCoordinator=DataUpdateCoordinator,
        UpdateFailed=UpdateFailed,
    )
    _stub("homeassistant.core", callback=lambda func: func)
    _stub("homeassistant.util")
    _stub("homeassistant.util.dt", utcnow=lambda: None)  # os testes substituem-no

_pkg_dir = Path(__file__).parent.parent / "custom_components" / "galp_pluma"
_pkg = types.ModuleType("galp_pluma")
_pkg.__path__ = [str(_pkg_dir)]
sys.modules["galp_pluma"] = _pkg
