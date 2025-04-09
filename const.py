from homeassistant.const import Platform

# Domain pour l'intégration
DOMAIN = "emaux_spv150"

# Adresse IP par défaut pour le composant
DEFAULT_HOST = "192.168.1.1"

# Plateformes prises en charge par l'intégration
PLATFORMS = (Platform.SENSOR, Platform.NUMBER)
