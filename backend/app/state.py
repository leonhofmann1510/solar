"""
Application state container and dependency injection.

All shared state (MQTT client, WebSocket manager, topic map) lives here.
This replaces global variables with proper FastAPI dependency injection.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from fastapi import Request

if TYPE_CHECKING:
    from app.routers.ws import ConnectionManager
    from app.services.mqtt import MQTTClient


@dataclass
class TopicMapEntry:
    """A single entry in the MQTT topic map."""
    device_id: int
    capability_key: str
    data_type: str


@dataclass
class AppState:
    """Container for all shared application state."""
    mqtt_client: MQTTClient | None = None
    ws_manager: ConnectionManager | None = None
    topic_map: dict[str, TopicMapEntry] = field(default_factory=dict)


def get_app_state(request: Request) -> AppState:
    """FastAPI dependency to get the application state."""
    return request.app.state.app_state


def get_mqtt_client(request: Request) -> MQTTClient | None:
    """FastAPI dependency to get the MQTT client."""
    return request.app.state.app_state.mqtt_client


def get_ws_manager(request: Request) -> ConnectionManager | None:
    """FastAPI dependency to get the WebSocket manager."""
    return request.app.state.app_state.ws_manager
