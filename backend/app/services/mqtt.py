import logging
from collections.abc import Callable

import paho.mqtt.client as mqtt

from app.config import settings

logger = logging.getLogger(__name__)


class MQTTClient:
    """Thin wrapper around paho-mqtt with auto-reconnect and subscribe support."""

    def __init__(self) -> None:
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if settings.mqtt_username:
            self._client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._connected = False
        self._subscriptions: list[str] = []
        self._message_callback: Callable[[str, str], None] | None = None

    def _on_connect(self, client: mqtt.Client, userdata: object, flags: mqtt.ConnectFlags, rc: mqtt.ReasonCode, properties: mqtt.Properties | None = None) -> None:
        if rc == 0:
            logger.info("MQTT connected to %s:%s", settings.mqtt_host, settings.mqtt_port)
            self._connected = True
            # Re-subscribe on reconnect
            for topic in self._subscriptions:
                self._client.subscribe(topic)
        else:
            logger.error("MQTT connection failed: %s", rc)

    def _on_disconnect(self, client: mqtt.Client, userdata: object, flags: mqtt.DisconnectFlags, rc: mqtt.ReasonCode, properties: mqtt.Properties | None = None) -> None:
        logger.warning("MQTT disconnected (rc=%s), will reconnect", rc)
        self._connected = False

    def _on_message(self, client: mqtt.Client, userdata: object, msg: mqtt.MQTTMessage) -> None:
        if self._message_callback:
            try:
                self._message_callback(msg.topic, msg.payload.decode("utf-8", errors="replace"))
            except Exception:
                logger.exception("Error in MQTT message callback for %s", msg.topic)

    def set_message_callback(self, callback: Callable[[str, str], None]) -> None:
        """Set a callback that receives (topic, payload_str) for every message."""
        self._message_callback = callback

    def connect(self) -> None:
        try:
            self._client.connect(settings.mqtt_host, settings.mqtt_port)
            self._client.loop_start()
        except Exception:
            logger.exception("MQTT initial connection failed")

    def subscribe(self, topic: str) -> None:
        if topic not in self._subscriptions:
            self._subscriptions.append(topic)
        if self._connected:
            self._client.subscribe(topic)
            logger.info("MQTT subscribed: %s", topic)

    def publish(self, topic: str, payload: str) -> None:
        if not self._connected:
            logger.warning("MQTT not connected, skipping publish to %s", topic)
            return
        self._client.publish(topic, payload)
        logger.info("MQTT published: %s → %s", topic, payload)

    def disconnect(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()
