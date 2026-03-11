import logging

import paho.mqtt.client as mqtt

from app.config import settings

logger = logging.getLogger(__name__)


class MQTTClient:
    """Thin wrapper around paho-mqtt with auto-reconnect."""

    def __init__(self) -> None:
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if settings.mqtt_username:
            self._client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._connected = False

    def _on_connect(self, client: mqtt.Client, userdata: object, flags: mqtt.ConnectFlags, rc: mqtt.ReasonCode, properties: mqtt.Properties | None = None) -> None:
        if rc == 0:
            logger.info("MQTT connected to %s:%s", settings.mqtt_host, settings.mqtt_port)
            self._connected = True
        else:
            logger.error("MQTT connection failed: %s", rc)

    def _on_disconnect(self, client: mqtt.Client, userdata: object, flags: mqtt.DisconnectFlags, rc: mqtt.ReasonCode, properties: mqtt.Properties | None = None) -> None:
        logger.warning("MQTT disconnected (rc=%s), will reconnect", rc)
        self._connected = False

    def connect(self) -> None:
        try:
            self._client.connect(settings.mqtt_host, settings.mqtt_port)
            self._client.loop_start()
        except Exception:
            logger.exception("MQTT initial connection failed")

    def publish(self, topic: str, payload: str) -> None:
        if not self._connected:
            logger.warning("MQTT not connected, skipping publish to %s", topic)
            return
        self._client.publish(topic, payload)
        logger.info("MQTT published: %s → %s", topic, payload)

    def disconnect(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()
