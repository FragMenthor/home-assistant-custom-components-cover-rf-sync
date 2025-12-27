
from __future__ import annotations
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import selector

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_OPEN_SENSOR,
    CONF_CLOSE_SENSOR,
    CONF_OPEN_DURATION,
    CONF_CLOSE_DURATION,
    CONF_SCRIPT_ENTITY_ID,
    CONF_TOLERANCE,
)

DEFAULT_NAME = "Portão"
DEFAULT_OPEN = 25
DEFAULT_CLOSE = 25
DEFAULT_TOL = 10.0  # %

def _tol_hint(tol: float | None) -> str:
    if tol is not None and tol > 25.0:
        return "⚠️ Atenção: tolerâncias acima de 25% não são recomendadas e podem levar a comportamentos inesperados."
    return "Indique a tolerância em percentagem (ex.: 10). Valores acima de 25% não são recomendados."

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            name = user_input.get(CONF_NAME) or DEFAULT_NAME
            open_dur = int(user_input.get(CONF_OPEN_DURATION) or DEFAULT_OPEN)
            close_dur = int(user_input.get(CONF_CLOSE_DURATION) or DEFAULT_CLOSE)
            tolerance = float(user_input.get(CONF_TOLERANCE) or DEFAULT_TOL)
            script_entity = user_input.get(CONF_SCRIPT_ENTITY_ID)
            open_sensor = user_input.get(CONF_OPEN_SENSOR)
            close_sensor = user_input.get(CONF_CLOSE_SENSOR)

            if tolerance > 25.0:
                await self._create_tolerance_warning(tolerance)

            data = {
                CONF_NAME: name,
                CONF_OPEN_DURATION: open_dur,
                CONF_CLOSE_DURATION: close_dur,
                CONF_TOLERANCE: tolerance,
                CONF_SCRIPT_ENTITY_ID: script_entity,
                CONF_OPEN_SENSOR: open_sensor,
                CONF_CLOSE_SENSOR: close_sensor,
            }
            return self.async_create_entry(title=name, data=data)

        desc_ph = {"tol_hint": _tol_hint(None)}

        schema = vol.Schema({
            vol.Optional(CONF_SCRIPT_ENTITY_ID): selector({"entity": {"domain": "script"}}),
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
            vol.Optional(CONF_OPEN_DURATION, default=DEFAULT_OPEN): selector({"number": {"min": 1, "max": 600, "mode": "box"}}),
            vol.Optional(CONF_CLOSE_DURATION, default=DEFAULT_CLOSE): selector({"number": {"min": 1, "max": 600, "mode": "box"}}),
            vol.Optional(CONF_TOLERANCE, default=DEFAULT_TOL): selector({"number": {"min": 0, "max": 50, "step": 0.5, "mode": "box"}}),
            vol.Optional(CONF_OPEN_SENSOR): selector({"entity": {"domain": "binary_sensor"}}),
            vol.Optional(CONF_CLOSE_SENSOR): selector({"entity": {"domain": "binary_sensor"}}),
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors, description_placeholders=desc_ph)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Garante botão 'Configurar' após criação (Options Flow)."""
        return OptionsFlow(config_entry)

    async def _create_tolerance_warning(self, tolerance: float):
        try:
            nid = f"{DOMAIN}_tolerance_warning"
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "Cover RF Sync — Aviso de tolerância",
                    "message": f"A tolerância configurada ({tolerance:.1f}%) é elevada (>25%). Isto pode causar efeitos indesejados na lógica de extremos e na apresentação do UI.",
                    "notification_id": nid,
                },
                blocking=False,
            )
        except Exception:
            pass

class OptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry):
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            tol = user_input.get(CONF_TOLERANCE)
            tolerance = float(
                tol if tol is not None
                else self._entry.options.get(CONF_TOLERANCE, self._entry.data.get(CONF_TOLERANCE, DEFAULT_TOL))
            )
            if tolerance > 25.0:
                cf = ConfigFlow()
                cf.hass = self.hass
                await cf._create_tolerance_warning(tolerance)

            options = {
                CONF_SCRIPT_ENTITY_ID: user_input.get(CONF_SCRIPT_ENTITY_ID, self._entry.options.get(CONF_SCRIPT_ENTITY_ID, self._entry.data.get(CONF_SCRIPT_ENTITY_ID))),
                CONF_OPEN_DURATION: int(user_input.get(CONF_OPEN_DURATION) or self._entry.options.get(CONF_OPEN_DURATION) or self._entry.data.get(CONF_OPEN_DURATION) or DEFAULT_OPEN),
                CONF_CLOSE_DURATION: int(user_input.get(CONF_CLOSE_DURATION) or self._entry.options.get(CONF_CLOSE_DURATION) or self._entry.data.get(CONF_CLOSE_DURATION) or DEFAULT_CLOSE),
                CONF_TOLERANCE: tolerance,
                CONF_OPEN_SENSOR: user_input.get(CONF_OPEN_SENSOR, self._entry.options.get(CONF_OPEN_SENSOR, self._entry.data.get(CONF_OPEN_SENSOR))),
                CONF_CLOSE_SENSOR: user_input.get(CONF_CLOSE_SENSOR, self._entry.options.get(CONF_CLOSE_SENSOR, self._entry.data.get(CONF_CLOSE_SENSOR))),
            }
            return self.async_create_entry(title="", data=options)

        cur = self._entry.options
        data = self._entry.data
        cur_tol = cur.get(CONF_TOLERANCE, data.get(CONF_TOLERANCE, DEFAULT_TOL))
        desc_ph = {"tol_hint": _tol_hint(cur_tol)}

        schema = vol.Schema({
            vol.Optional(CONF_SCRIPT_ENTITY_ID, default=cur.get(CONF_SCRIPT_ENTITY_ID, data.get(CONF_SCRIPT_ENTITY_ID))): selector({"entity": {"domain": "script"}}),
            vol.Optional(CONF_OPEN_DURATION,  default=cur.get(CONF_OPEN_DURATION,  data.get(CONF_OPEN_DURATION,  DEFAULT_OPEN))):  selector({"number": {"min": 1, "max": 600, "mode": "box"}}),
            vol.Optional(CONF_CLOSE_DURATION, default=cur.get(CONF_CLOSE_DURATION, data.get(CONF_CLOSE_DURATION, DEFAULT_CLOSE))): selector({"number": {"min": 1, "max": 600, "mode": "box"}}),
            vol.Optional(CONF_TOLERANCE, default=cur_tol): selector({"number": {"min": 0, "max": 50, "step": 0.5, "mode": "box"}}),
            vol.Optional(CONF_OPEN_SENSOR,  default=cur.get(CONF_OPEN_SENSOR,  data.get(CONF_OPEN_SENSOR))):  selector({"entity": {"domain": "binary_sensor"}}),
            vol.Optional(CONF_CLOSE_SENSOR, default=cur.get(CONF_CLOSE_SENSOR, data.get(CONF_CLOSE_SENSOR))): selector({"entity": {"domain": "binary_sensor"}}),
        })
        return self.async_show_form(step_id="init", data_schema=schema, description_placeholders=desc_ph)
