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
- Puissance consommée (W) et débit (affiché en L/min) en temps réel
- Énergie cumulée (kWh) — compatible dashboard Énergie HA
- Temps de fonctionnement depuis le dernier démarrage

### Contrôle
- Vitesse courante (RPM) et preset de vitesse (1/2/3) modifiables depuis l'UI
- Throttle configurable entre changements de vitesse (défaut : 60 s) pour protéger la pompe
- Timeout de requête et intervalle de polling configurables, modifiables à chaud, pour ne pas surcharger le serveur CGI de la pompe
- Séquence de démarrage : attente automatique de la fin du priming (défaut : 120 s, conforme manuel SPV150 section 5) uniquement lors d'une mise sous tension physique (switch OFF→ON)

### Mode solaire — régulateur P avec bande morte
- Sélecteur de mode : `Off` / `Manuel` / `Solaire` — **persisté entre les redémarrages**
- Capteur de puissance réseau (un capteur `power`, positif en soutirage, négatif en injection)
- **Régulateur proportionnel (P)** centré sur un setpoint configurable :
  - `error = |puissance_réseau - setpoint|`
  - `step = min(step_max, max(10 W, error))` — proportionnel au delta, plafonné
  - En-dessous de la borne inférieure de la bande morte → vitesse + step
  - Au-dessus de la borne supérieure → vitesse − step
  - Dans la bande morte → aucune action
- Régulation active immédiatement si la pompe tourne déjà lors du passage en mode solaire
- Protection données périmées : si le capteur réseau n'a rien remonté depuis plus de 60 s, la régulation est suspendue
- Tous les paramètres (setpoint, bande morte, pas, mode, vitesses min/max) **persistés entre les redémarrages**

## Installation

Nécessite Home Assistant 2026.10 ou plus récent.

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
4. (optionnel) Choisissez la prise ou le switch qui alimente la pompe, et le capteur de puissance réseau pour le mode solaire

La pompe est testée (ping HTTP) avant validation. Il est impossible d'ajouter deux fois la même IP.

## Options configurables

Accessibles via **Paramètres > Appareils & Services > Emaux SPV150 > Configurer** :

| Paramètre | Description | Défaut |
|-----------|-------------|--------|
| Adresse IP | IP de la pompe | — |
| Switch externe | Prise ou switch qui alimente la pompe : tant qu'il est éteint, la pompe n'est pas interrogée | — |
| Intervalle de polling | 5 à 60 secondes | 30 s |
| Timeout de requête | Timeout HTTP par requête pompe (1–30 s) | 5 s |
| Capteur puissance réseau | Capteur de puissance pour le mode solaire | — |
| Setpoint (W) | Puissance réseau cible du régulateur P | 0 W |
| Borne inférieure bande morte (W) | En-dessous : accélérer | 0 W |
| Borne supérieure bande morte (W) | Au-dessus : ralentir | 100 W |
| Pas max montée (RPM) | Plafond du step proportionnel en montée | 300 RPM |
| Pas max descente (RPM) | Plafond du step proportionnel en descente | 30 RPM |
| Délai priming (s) | Attente après mise sous tension avant régulation solaire | 120 s |
| Intervalle changement de vitesse (s) | Throttle entre deux commandes SetSpeed (0 = désactivé) | 60 s |

## Entités créées

Identifiants d'entité par défaut sur une nouvelle installation (ils suivent les noms de l'appareil et des entités) :

| Entité | Type | Description |
|--------|------|-------------|
| `sensor.emaux_spv150_power` | Sensor | Puissance consommée (W) |
| `sensor.emaux_spv150_flow_rate` | Sensor | Débit (affiché en L/min) |
| `sensor.emaux_spv150_energy` | Sensor | Énergie cumulée (kWh) |
| `sensor.emaux_spv150_uptime` | Sensor | Temps de fonctionnement (h) — diagnostic |
| `number.emaux_spv150_speed` | Number | Vitesse courante (RPM) — slider |
| `number.emaux_spv150_speed_preset` | Number | Preset de vitesse (1/2/3) — slider |
| `number.emaux_spv150_setpoint` | Number | Setpoint du régulateur (W) |
| `number.emaux_spv150_dead_band_lower_bound` | Number | Borne inférieure bande morte (W) |
| `number.emaux_spv150_dead_band_upper_bound` | Number | Borne supérieure bande morte (W) |
| `number.emaux_spv150_max_speed_increase_step` | Number | Pas max montée (RPM) |
| `number.emaux_spv150_max_speed_decrease_step` | Number | Pas max descente (RPM) |
| `number.emaux_spv150_min_speed_solar` | Number | Vitesse min en mode solaire (RPM) |
| `number.emaux_spv150_max_speed_solar` | Number | Vitesse max en mode solaire (RPM) |
| `number.emaux_spv150_polling_interval` | Number | Intervalle de polling (s) |
| `number.emaux_spv150_request_timeout` | Number | Timeout de requête HTTP (s) |
| `switch.emaux_spv150_running` | Switch | Démarrer / arrêter la pompe |
| `select.emaux_spv150_control_mode` | Select | Off / Manuel / Solaire |

![image info](/img/page_web.jpeg)

## Mise à jour des données

- La pompe est interrogée toutes les 30 s par défaut (5 à 60 s, modifiable à chaud) avec une seule requête HTTP.
- Après une commande (vitesse, preset, marche/arrêt), la pompe est relue une fois stabilisée (2 s).
- Un changement d'état du switch externe déclenche une lecture immédiate.
- Tant que le switch externe est éteint, la pompe n'est pas interrogée : ses valeurs sont indisponibles et aucune erreur n'est signalée.
- Juste après un redémarrage de Home Assistant, l'état du switch peut rester inconnu une à deux minutes : une pompe qui ne répond pas ne fait alors pas échouer la mise en place. Ensuite, une pompe qui ne répond pas est signalée indisponible, quel que soit l'état du switch.

## Appareils supportés

Pompes à vitesse variable Emaux SPV150 avec l'interface web Wi-Fi intégrée (serveur CGI local). Les autres modèles Emaux n'ont pas été testés.

## Limites connues

- L'interface web de la pompe n'a pas d'authentification et passe en HTTP simple : gardez-la sur un réseau local de confiance.
- Une seule pompe par instance Home Assistant : les identifiants uniques des entités ne sont pas encore préfixés par entrée.
- Le mode `Off` coupe seulement la régulation solaire ; il n'arrête pas la pompe (utilisez le switch marche/arrêt).
- L'énergie est calculée par l'intégration à partir de la puissance lue à chaque polling : c'est une estimation.
- L'attente de priming ne s'applique que quand le switch externe allume la pompe, pas après un redémarrage de Home Assistant.

## Dépannage

- **« Impossible de se connecter » à la configuration** : vérifiez l'adresse IP, que la pompe est alimentée et sur le même réseau. Si le switch externe choisi est éteint, le test est sauté.
- **Entités indisponibles** : la pompe est hors tension ou ne répond pas. Une erreur est journalisée quand elle cesse de répondre, une ligne quand elle répond à nouveau.
- **Changement de vitesse refusé** : un seul changement par intervalle de changement de vitesse (60 s par défaut, 0 désactive la limite).
- **Logs de débogage** : ajoutez dans `configuration.yaml`, puis redémarrez :

  ```yaml
  logger:
    logs:
      custom_components.emaux_spv150: debug
  ```

- **Diagnostics** : **Paramètres > Appareils & Services > Emaux SPV150 > ⋮ > Télécharger les diagnostics** (l'adresse de la pompe est retirée). Joignez le fichier à une issue.

## Désinstallation

1. **Paramètres > Appareils & Services > Emaux SPV150 > ⋮ > Supprimer**.
2. Dans HACS, ouvrez l'intégration et choisissez **Supprimer** (installation manuelle : supprimez `config/custom_components/emaux_spv150`).
3. Redémarrez Home Assistant.

## Développement

Outils : [mise](https://mise.jdx.dev/) (versions des outils et tâches), [uv](https://docs.astral.sh/uv/) (environnement & dépendances), [ruff](https://docs.astral.sh/ruff/) (lint + format) et [mypy](https://mypy.readthedocs.io/) en mode strict, comme le cœur de Home Assistant.

```bash
mise run install        # venv + dépendances de dev (depuis uv.lock)
mise run lint           # ruff check + ruff format --check
mise run typecheck      # mypy --strict
mise run test           # pytest
```

La CI (GitHub Actions) lance les mêmes lint, contrôle de types et tests, en plus de `hassfest` et de la validation HACS.

## Licence

[PolyForm Noncommercial 1.0.0](LICENSE) — usage personnel/non commercial. Tout usage commercial nécessite un accord séparé.
