# emaux_spv150 pour Home Assistant

[English](./README.md) | **Français**

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Release](https://img.shields.io/github/v/release/0jety0/emaux_spv150?color=blue)](https://github.com/0jety0/emaux_spv150/releases)
[![Installations HACS](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=installations&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.emaux_spv150.total)](https://analytics.home-assistant.io/custom_integrations)
[![CI](https://github.com/0jety0/emaux_spv150/actions/workflows/ci.yaml/badge.svg)](https://github.com/0jety0/emaux_spv150/actions/workflows/ci.yaml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Stars](https://img.shields.io/github/stars/0jety0/emaux_spv150?style=flat&logo=github)](https://github.com/0jety0/emaux_spv150/stargazers)
[![Licence : PolyForm NC](https://img.shields.io/badge/licence-PolyForm%20NC%201.0.0-orange.svg)](LICENSE)

Intégration personnalisée Home Assistant pour contrôler et surveiller la pompe de piscine à vitesse variable **Emaux SPV150**.

![image info](/img/main.jpeg)

## Fonctionnalités

### Supervision
- Puissance consommée (W) et débit (GPM) en temps réel
- Énergie cumulée (kWh) — compatible dashboard Énergie HA
- Temps de fonctionnement depuis le dernier démarrage

### Contrôle
- Vitesse courante (RPM) et preset de vitesse (1/2/3) modifiables depuis l'UI
- Throttle configurable entre changements de vitesse (défaut : 60 s) pour protéger la pompe
- Timeout de requête et intervalle de polling configurables, modifiables à chaud, pour ne pas surcharger le serveur CGI de la pompe
- Séquence de démarrage : attente automatique de la fin du priming (défaut : 120 s, conforme manuel SPV150 section 5) uniquement lors d'une mise sous tension physique (switch OFF→ON)

### Mode solaire — régulateur P avec bande morte
- Sélecteur de mode : `Off` / `Manuel` / `Solaire` — **persisté entre les redémarrages**
- Entité puissance réseau configurable (n'importe quelle entité HA, ex : `sensor.puissance_reseau`)
- **Régulateur proportionnel (P)** centré sur un setpoint configurable :
  - `error = |puissance_réseau - setpoint|`
  - `step = min(step_max, max(10 W, error))` — proportionnel au delta, plafonné
  - En-dessous de la borne inférieure de la bande morte → vitesse + step
  - Au-dessus de la borne supérieure → vitesse − step
  - Dans la bande morte → aucune action
- Régulation active immédiatement si la pompe tourne déjà lors du passage en mode solaire
- Protection données périmées : si la valeur réseau n'a pas changé depuis plus de 60 s, la régulation est suspendue
- Tous les paramètres (setpoint, bande morte, pas, mode, vitesses min/max) **persistés entre les redémarrages**

## Installation

### Via HACS (recommandé)

1. Assurez-vous que [HACS](https://hacs.xyz/) est installé.
2. Dans HACS, allez dans **Intégrations**.
3. Cliquez sur les trois points (⋮) > **Dépôts personnalisés**.
4. Ajoutez l'URL de ce dépôt et sélectionnez **Intégration**.
5. Installez `emaux_spv150` depuis HACS.
6. Redémarrez Home Assistant.

### Installation manuelle

1. Copiez le dossier `custom_components/emaux_spv150` dans `config/custom_components/` de votre instance HA.
2. Redémarrez Home Assistant.

## Configuration initiale

1. **Paramètres > Appareils & Services > Ajouter une intégration**
2. Recherchez `emaux_spv150`
3. Saisissez l'adresse IP de la pompe
4. (optionnel) Sélectionnez un switch externe pour couper le polling quand la pompe est hors tension

La pompe est testée (ping HTTP) avant validation. Il est impossible d'ajouter deux fois la même IP.

## Options configurables

Accessibles via **Paramètres > Appareils & Services > Emaux SPV150 > Configurer** :

| Paramètre | Description | Défaut |
|-----------|-------------|--------|
| Adresse IP | IP de la pompe | — |
| Switch externe | Entité pour couper le polling | — |
| Intervalle de polling | 5 à 60 secondes | 30 s |
| Timeout de requête | Timeout HTTP par requête pompe (1–30 s) | 5 s |
| Entité puissance réseau | Capteur HA pour le mode solaire | — |
| Setpoint (W) | Puissance réseau cible du régulateur P | 0 W |
| Borne inférieure bande morte (W) | En-dessous : accélérer | 0 W |
| Borne supérieure bande morte (W) | Au-dessus : ralentir | 100 W |
| Pas max montée (RPM) | Plafond du step proportionnel en montée | 300 RPM |
| Pas max descente (RPM) | Plafond du step proportionnel en descente | 30 RPM |
| Délai priming (s) | Attente après mise sous tension avant régulation solaire | 120 s |
| Intervalle changement de vitesse (s) | Throttle entre deux commandes SetSpeed (0 = désactivé) | 60 s |

## Entités créées

| Entité | Type | Description |
|--------|------|-------------|
| `sensor.power` | Sensor | Puissance consommée (W) |
| `sensor.flow_rate` | Sensor | Débit (GPM) |
| `sensor.energy` | Sensor | Énergie cumulée (kWh) |
| `sensor.uptime` | Sensor | Temps de fonctionnement (h) |
| `number.speed` | Number | Vitesse courante (RPM) — slider |
| `number.speed_preset` | Number | Preset de vitesse (1/2/3) — slider |
| `number.setpoint` | Number | Setpoint du régulateur (W) |
| `number.dead_band_lower` | Number | Borne inférieure bande morte (W) |
| `number.dead_band_upper` | Number | Borne supérieure bande morte (W) |
| `number.step_up` | Number | Pas max montée (RPM) |
| `number.step_down` | Number | Pas max descente (RPM) |
| `number.rpm_min_solar` | Number | Vitesse min en mode solaire (RPM) |
| `number.rpm_max_solar` | Number | Vitesse max en mode solaire (RPM) |
| `number.poll_interval` | Number | Intervalle de polling (s) |
| `number.request_timeout` | Number | Timeout de requête HTTP (s) |
| `switch.running` | Switch | Démarrer / arrêter la pompe |
| `select.control_mode` | Select | Off / Manuel / Solaire |

![image info](/img/page_web.jpeg)

## Développement

Outils : [uv](https://docs.astral.sh/uv/) (environnement & dépendances) et [ruff](https://docs.astral.sh/ruff/) (lint + format).

```bash
uv sync                 # venv + dépendances de dev (depuis uv.lock)
uv run ruff check .     # lint
uv run ruff format .    # format
uv run pytest -q        # tests
```

La CI (GitHub Actions) lance `ruff check`, `ruff format --check` et `pytest`, en plus de `hassfest` et de la validation HACS.

## Licence

[PolyForm Noncommercial 1.0.0](LICENSE) — usage personnel/non commercial. Tout usage commercial nécessite un accord séparé.
