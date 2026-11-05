"""Config flow: deteção automática por Bluetooth + escolha manual."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.device_registry import format_mac

from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    CONF_GAS_TYPE,
    GAS_ICONS,
    GAS_TYPES,
    DEFAULT_GAS_TYPE,
    is_pluma_name,
)


def _short_title(address: str) -> str:
    """Título curto sem expor o número de série que vem no nome Bluetooth."""
    return f"Pluma {address.replace(':', '')[-6:].upper()}"

def _gas_type_schema(default: str) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_GAS_TYPE, default=default): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=GAS_TYPES,
                    translation_key=CONF_GAS_TYPE,
                )
            )
        }
    )

class PlumaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configura garrafas Pluma."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Garrafa encontrada automaticamente."""
        await self.async_set_unique_id(format_mac(discovery_info.address))
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": _short_title(discovery_info.address)
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pede confirmação para adicionar a garrafa descoberta."""
        assert self._discovery_info is not None
        title = _short_title(self._discovery_info.address)
        if user_input is not None:
            return self.async_create_entry(
                title=title, data={CONF_ADDRESS: self._discovery_info.address}
            )
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": title},
        )

    async def async_step_gas_type(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Tipo de gás após confirmação da descoberta."""
        assert self._discovery_info is not None
        if user_input is not None:
            return self.async_create_entry(
                title=_short_title(self._discovery_info.address),
                data={
                    CONF_ADDRESS: self._discovery_info.address,
                    CONF_GAS_TYPE: user_input[CONF_GAS_TYPE],
                },
            )
        return self.async_show_form(
            step_id="gas_type",
            data_schema=_gas_type_schema(DEFAULT_GAS_TYPE),
            description_placeholders={
                "name": _short_title(self._discovery_info.address)
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Escolha manual entre as garrafas visíveis."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(format_mac(address), raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=_short_title(address),
                data={CONF_ADDRESS: address,
                      CONF_GAS_TYPE: user_input[CONF_GAS_TYPE],}
            )

        current_ids = self._async_current_ids()
        for info in async_discovered_service_info(self.hass, connectable=True):
            if format_mac(info.address) in current_ids:
                continue
            if is_pluma_name(info.name):
                self._discovered[info.address] = info

        if not self._discovered:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
                        {
                            # O nome Bluetooth completo ajuda a distinguir as
                            # garrafas (o número pode coincidir com o da garrafa).
                            address: f"{info.name} ({address})"
                            for address, info in self._discovered.items()
                        }
                    )
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: Any) -> OptionsFlow:
        """Opções (intervalo de leitura)."""
        return PlumaOptionsFlow()


class PlumaOptionsFlow(OptionsFlow):
    """Intervalo entre leituras."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        current = int(
            self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )

        current_gas = gas_type_from_entry(self.config_entry)
        
        if user_input is not None:
            minutes = int(user_input[CONF_SCAN_INTERVAL])
            if 0 < minutes < MIN_SCAN_INTERVAL:
                errors["base"] = "interval_too_short"
                current = minutes
            else:
                return self.async_create_entry(
                    data={
                        CONF_SCAN_INTERVAL: minutes,
                        CONF_GAS_TYPE: user_input[CONF_GAS_TYPE],
                    }
                )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): selector.NumberSelector(...),
                    vol.Required(CONF_GAS_TYPE, default=current_gas): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=GAS_TYPES, translation_key=CONF_GAS_TYPE
                        )
                    ),
                }
            ),
            errors=errors,
        )
