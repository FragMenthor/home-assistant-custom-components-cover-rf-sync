
DOMAIN = "cover_rf_sync"

# Config keys
CONF_NAME = "name"
CONF_OPEN_SENSOR = "open_sensor"
CONF_CLOSE_SENSOR = "close_sensor"
CONF_OPEN_DURATION = "open_duration"     # segundos para viagem completa a abrir
CONF_CLOSE_DURATION = "close_duration"   # segundos para viagem completa a fechar
CONF_SCRIPT_ENTITY_ID = "script_entity_id"
CONF_TOLERANCE = "tolerance_percent"     # percentagem (0..50)

# Attributes
ATTR_NEXT_ACTION = "next_action"         # "open" | "close" | "stop"
ATTR_SCRIPT_CONFIGURED = "script_configured_entity_id"
ATTR_SCRIPT_RUNNING = "script_running_entity_id"
ATTR_IS_MOVING = "is_moving"
ATTR_LAST_TRIGGER = "last_trigger"       # "user_open"|"user_close"|"sensor_open"|"sensor_close"|"service"|"stop"
