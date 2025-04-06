"""Constantes"""

from homeassistant.const import Platform

DOMAIN = "emaux_spv150"
DEFAULT_HOST = "192.168.1.71"
PLATFORMS: list[Platform] = [Platform.SENSOR]
