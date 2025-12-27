
from __future__ import annotations
import asyncio
import logging
from typing import Optional, Dict, Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.const import (
    STATE_OPENING,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_CLOSED,
)
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    DOMAIN,
    CONF_OPEN_SENSOR,
    CONF_CLOSE_SENSOR,
    CONF_OPEN_DURATION,
    CONF_CLOSE_DURATION,
    CONF_SCRIPT_ENTITY_ID,
    CONF_TOLERANCE,
    ATTR_NEXT_ACTION,
    ATTR_SCRIPT_CONFIGURED,
    ATTR_SCRIPT_RUNNING,
    ATTR_IS_MOVING,
    ATTR_LAST_TRIGGER,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_OPEN = 25
DEFAULT_CLOSE = 25
DEFAULT_TOL = 10.0  # %

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Adicionar a entidade de cover da integração."""
    entity = CoverRFSyncEntity(hass, entry)
    async_add_entities([entity])

    # Serviço por entidade: cover_rf_sync.activate_script
    async def _handle_activate_script(call):
        target_eid = call.data.get("entity_id")
        if not target_eid or target_eid != entity.entity_id:
            return
        await entity.async_activate_script()

    hass.services.async_register(DOMAIN, "activate_script", _handle_activate_script)

class CoverRFSyncEntity(CoverEntity):
    """Cover lógica que sincroniza com sensores/tempo e expõe próxima ação."""

    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry
        self._unique_id = f"{entry.entry_id}_cover"
        self._attr_unique_id = self._unique_id
        self._attr_name = entry.title or "Portão"

        data = entry.data
        options = entry.options or {}

        # Config
        self._open_duration: int = options.get(CONF_OPEN_DURATION) or data.get(CONF_OPEN_DURATION) or DEFAULT_OPEN
        self._close_duration: int = options.get(CONF_CLOSE_DURATION) or data.get(CONF_CLOSE_DURATION) or DEFAULT_CLOSE
        tol_opt = options.get(CONF_TOLERANCE, data.get(CONF_TOLERANCE, DEFAULT_TOL))
        try:
            self._tol: float = max(0.0, min(50.0, float(tol_opt)))
        except (ValueError, TypeError):
            self._tol = DEFAULT_TOL

        self._open_sensor: str | None = options.get(CONF_OPEN_SENSOR) or data.get(CONF_OPEN_SENSOR)
        self._close_sensor: str | None = options.get(CONF_CLOSE_SENSOR) or data.get(CONF_CLOSE_SENSOR)
        self._script_configured: str | None = options.get(CONF_SCRIPT_ENTITY_ID) or data.get(CONF_SCRIPT_ENTITY_ID)

        # Estado
        self._is_moving: bool = False
        self._position: float = 0.0  # 0 fechado, 100 aberto
        self._state: str = STATE_CLOSED
        self._next_action: str = "open"  # "open" | "close" | "stop"
        self._last_trigger: str | None = None
        self._script_running: str | None = None

        # Arranque pendente quando aguardamos sensor
        self._pending_start: Optional[Dict[str, Any]] = None  # {"direction": "...", "target": int|None}

        # Unsubs
        self._unsub_open = None
        self._unsub_close = None

    # Botões dinâmicos
    @property
    def supported_features(self) -> int:
        base = CoverEntityFeature.SET_POSITION
        if self._is_moving or self._next_action == "stop":
            return base | CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        if self._next_action == "open":
            return base | CoverEntityFeature.OPEN
        if self._next_action == "close":
            return base | CoverEntityFeature.CLOSE
        return base | CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    # Ciclo de vida
    async def async_added_to_hass(self):
        if self._open_sensor:
            self._unsub_open = async_track_state_change_event(
                self.hass, [self._open_sensor], self._handle_open_sensor
            )
        if self._close_sensor:
            self._unsub_close = async_track_state_change_event(
                self.hass, [self._close_sensor], self._handle_close_sensor
            )
        self._apply_next_action_from_position()
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self):
        if self._unsub_open:
            self._unsub_open(); self._unsub_open = None
        if self._unsub_close:
            self._unsub_close(); self._unsub_close = None

    # Ações do utilizador
    async def async_open_cover(self, **kwargs):
        self._last_trigger = "user_open"
        await self._start_movement("open", call_script=True)

    async def async_close_cover(self, **kwargs):
        self._last_trigger = "user_close"
        await self._start_movement("close", call_script=True)

    async def async_set_cover_position(self, **kwargs):
        target = int(kwargs.get("position", round(self._position)))
        direction = "open" if target > self._position else "close" if target < self._position else None
        if not direction:
            return
        self._last_trigger = f"user_set_position_{target}"
        await self._start_movement(direction, call_script=False, target_position=target)

    async def async_stop_cover(self, **kwargs):
        self._pending_start = None
        self._is_moving = False
        self._script_running = None

        tol = self._tol
        if self._position <= tol:
            self._state = STATE_CLOSED
            self._next_action = "open"
        elif self._position >= 100.0 - tol:
            self._state = STATE_OPEN
            self._next_action = "close"
        else:
            if self._state == STATE_OPENING:
                self._next_action = "close"
            elif self._state == STATE_CLOSING:
                self._next_action = "open"
            self._state = STATE_OPEN if self._position >= 50 else STATE_CLOSED

        self._last_trigger = "stop"
        self.async_write_ha_state()

    async def async_activate_script(self):
        """Serviço: chama o script configurado para esta cover."""
        if not self._script_configured:
            return
        await self.hass.services.async_call(
            "script", "turn_on", {"entity_id": self._script_configured}, blocking=False
        )
        self._script_running = self._script_configured
        self._last_trigger = "service"
        self.async_write_ha_state()

        # Sem sensor para a direção, arranca já; com sensor, aguarda
        if self._next_action == "open" and not self._open_sensor:
            await self._begin_movement("open", target_position=None)
        elif self._next_action == "close" and not self._close_sensor:
            await self._begin_movement("close", target_position=None)
        else:
            if self._next_action in ("open", "close"):
                self._pending_start = {"direction": self._next_action, "target": None}
                self.async_write_ha_state()

    # Sensores
    async def _handle_open_sensor(self, event):
        new_state = event.data.get("new_state")
        if not new_state:
            return
        if str(new_state.state).lower() in ("on", "true", "opening", "open"):
            self._last_trigger = "sensor_open"
            if self._pending_start and self._pending_start.get("direction") == "open":
                target = self._pending_start.get("target")
                self._pending_start = None
                await self._begin_movement("open", target)
                return
            await self._begin_movement("open", 100)

    async def _handle_close_sensor(self, event):
        new_state = event.data.get("new_state")
        if not new_state:
            return
        if str(new_state.state).lower() in ("on", "true", "closing", "closed"):
            self._last_trigger = "sensor_close"
            if self._pending_start and self._pending_start.get("direction") == "close":
                target = self._pending_start.get("target")
                self._pending_start = None
                await self._begin_movement("close", target)
                return
            await self._begin_movement("close", 0)

    # Núcleo de movimento
    async def _start_movement(self, direction: str, call_script: bool, target_position: int | None = None):
        if direction not in ("open", "close"):
            return

        # Se já em movimento e comando chamaria script -> STOP
        if self._is_moving and call_script:
            await self.async_stop_cover()
            return

        # Se há sensor para a direção e o comando chama script: aguardar sensor
        if call_script and ((direction == "open" and self._open_sensor) or (direction == "close" and self._close_sensor)):
            if self._script_configured:
                await self.hass.services.async_call(
                    "script", "turn_on", {"entity_id": self._script_configured}, blocking=False
                )
                self._script_running = self._script_configured
            self._pending_start = {"direction": direction, "target": target_position}
            self.async_write_ha_state()
            return

        # Caso contrário, arrancar já
        await self._begin_movement(direction, target_position)

    async def _begin_movement(self, direction: str, target_position: int | None):
        """Inicia efetivamente o movimento (simulação)."""
        self._is_moving = True
        self._state = STATE_OPENING if direction == "open" else STATE_CLOSING
        self._next_action = "stop"
        self.async_write_ha_state()

        full = max(1, int(self._open_duration if direction == "open" else self._close_duration))
        step = 0.5
        delta = 100.0 / (full / step)
        if direction == "close":
            delta = -delta

        target = target_position if target_position is not None else (100 if direction == "open" else 0)

        try:
            while self._is_moving:
                self._position = max(0.0, min(100.0, self._position + delta))
                if (direction == "open" and self._position >= target) or (direction == "close" and self._position <= target):
                    break
                self.async_write_ha_state()
                await asyncio.sleep(step)
        finally:
            self._is_moving = False
            self._script_running = None

            tol = self._tol
            if self._position <= tol:
                self._state = STATE_CLOSED
                self._next_action = "open"
            elif self._position >= 100.0 - tol:
                self._state = STATE_OPEN
                self._next_action = "close"
            else:
                self._state = STATE_OPEN if self._position >= 50 else STATE_CLOSED
                self._next_action = "close" if direction == "open" else "open"

            self.async_write_ha_state()

    # Helpers / getters
    @property
    def is_closed(self) -> bool | None:
        return self._state == STATE_CLOSED

    @property
    def current_cover_position(self) -> int | None:
        return int(round(self._position))

    @property
    def extra_state_attributes(self) -> dict:
        return {
            ATTR_IS_MOVING: self._is_moving,
            ATTR_NEXT_ACTION: self._next_action,
            ATTR_SCRIPT_CONFIGURED: self._script_configured,
            ATTR_SCRIPT_RUNNING: self._script_running,
            ATTR_LAST_TRIGGER: self._last_trigger,
        }

    def _apply_next_action_from_position(self):
        tol = self._tol
        if self._position <= tol:
            self._state = STATE_CLOSED
            self._next_action = "open"
        elif self._position >= 100.0 - tol:
            self._state = STATE_OPEN
            self._next_action = "close"
        else:
            self._state = STATE_OPEN if self._position >= 50 else STATE_CLOSED
            self._next_action = "close" if self._position >= 50 else "open"
