from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    db_host: str = "db"
    db_port: int = 5432
    db_user: str = "solarflow"
    db_password: str = "changeme"
    db_name: str = "solar"

    # Modbus / inverter config
    inverters_config_path: str = "../inverters.yaml"
    poll_interval_seconds: int = 30

    # MQTT
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: str = ""
    mqtt_password: str = ""

    # Rules
    rules_file_path: str = "/app/rules/example_rules.yaml"

    # Tuya (QR login — no API key needed)
    tuya_region: str = "eu"

    @property
    def tuya_endpoint(self) -> str:
        endpoints = {
            "eu": "https://px1.tuyaeu.com",
            "us": "https://px1.tuyaus.com",
            "in": "https://px1.tuyain.com",
            "cn": "https://px1.tuyacn.com",
        }
        return endpoints.get(self.tuya_region, "https://px1.tuyaeu.com")

    # Smart Meter (Bitshake HTTP reader)
    smart_meter_enabled: bool = False
    smart_meter_ip: str = ""

    # Discovery
    zigbee2mqtt_bridge_topic: str = "zigbee2mqtt/bridge/devices"
    mdns_scan_timeout_seconds: int = 10

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    model_config = {"env_file": (".env", "../.env"), "env_file_encoding": "utf-8"}


settings = Settings()
