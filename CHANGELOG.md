# Changelog

## [2.1.0] — 2026-06-06

### Nouvelles fonctionnalités

- **Timeout de requête configurable** : nouvelle entité `number` « Request timeout » (1–30 s, défaut 5 s), modifiable à chaud comme l'intervalle de polling. Le serveur CGI embarqué de la pompe étant lent/instable sur le LAN, le timeout passe de 2 s à 5 s par défaut pour réduire les faux `timed out`. Intervalle de polling et timeout sont tous deux ajustables depuis l'UI pour ne pas surcharger la pompe.

### Outils & projet

- **Migration vers `uv` + `ruff`** : `pyproject.toml` (PEP 621) remplace le `Pipfile` ; `ruff` (lint + format) remplace `black` + `isort` ; config `pytest` intégrée au `pyproject` (suppression de `pytest.ini`). `uv.lock` versionné. Outils de dev/CI uniquement — aucun impact sur le runtime HA.
- **CI GitHub Actions** : `ruff check` + `ruff format --check` + `pytest` (via `uv`), en plus de `hassfest` et de la validation HACS.
- **Licence** : [PolyForm Noncommercial 1.0.0](LICENSE) (usage personnel / non commercial).

### Corrections de bugs

- **`api.py` — JSON invalide** : `json.JSONDecodeError` est désormais capturé (réponse non-JSON, HTML d'erreur, corps vide) et renvoie `{}` au lieu de remonter une exception non gérée qui stoppait le polling.
- **`api.py` — injection d'URL** : la clé de commande est encodée (`urllib.parse.quote`) avant d'être insérée dans l'URL ; la valeur est forcée en `int`.
- **`api.py` — fuite d'information** : l'IP de la pompe n'apparaît plus dans les logs `ERROR` (déplacée en `DEBUG`).
- **`coordinator.py` — reload intempestif** : ajuster un paramètre `number` local (setpoint, bande morte, pas, RPM, intervalle) ne recharge plus toute l'intégration. Le `update_listener` ne recharge que sur changement de connexion (IP / switch / entité réseau). L'énergie cumulée et l'uptime ne sont plus remis à zéro à chaque réglage.
- **`coordinator.py` / `number.py` — invariants solaires** : `rpm_min_solar` ≤ `rpm_max_solar` **et** `dead_band_lower` ≤ `dead_band_upper` sont garantis ; les setters bornent automatiquement la valeur (avant, seul le config flow validait la bande morte).
- **`__init__.py` — listener de reload sans course** : la décision de recharger compare les réglages de connexion (IP / switch / entité réseau) au lieu d'un drapeau, supprimant une fenêtre de course ; un réglage modifié via le formulaire d'options s'applique désormais à chaud (sans reload).
- **`config_flow.py` — perte de `grid_power_entity`** : le formulaire d'options retombe sur `entry.data` (comme le switch), évitant d'effacer l'entité réseau lors d'une édition d'options.
- **`sensor.py`** : échec de restauration de l'énergie loggé (`warning`) au lieu d'être avalé silencieusement.
- **`RunningStatus`** : normalisé via `str()`, la détection marche que la pompe renvoie `"1"` ou `1`.
- **Options flow** : un `switch_entity`/`grid_power_entity` valant `None` ne casse plus le formulaire d'options.

### Améliorations techniques

- **DTO `PumpStatus`** (`models.py`) : les données pompe sont converties une seule fois en objet typé ; fin des `float(...)` / comparaisons de chaînes dispersés dans les entités.
- **`SolarRegulator` + `SolarControllerConfig`** (`solar.py`) : le régulateur P est extrait du coordinator en unité pure et testable (SRP).
- **`NumberEntityDescription` / `SensorEntityDescription`** : les entités `number` et `sensor` utilisent le pattern idiomatique HA (dataclass) ; les trois structures parallèles de `number.py` sont fusionnées en une seule source de vérité (DRY).
- **Constante `GRID_POWER_STALENESS_SECONDS`** : le seuil de péremption de l'entité réseau n'est plus un magic number.
- **`config_flow.py`** : validation du format IP / hostname (`invalid_host`) avant le test de connexion, sur les trois flux (initial, reconfigure, options).
- **`coordinator` typé** `DataUpdateCoordinator[PumpStatus]`.
- Suppression de `utils.py` (devenu inutile).
- **Tests** : 38 tests pytest (régulateur solaire, API + cas d'erreur, énergie/uptime, reconfigure, invariants RPM, normalisation `RunningStatus`). Le test orphelin `enable_maintenance` a été retiré.
- `Pipfile` : suppression de `re` (module stdlib, pas un paquet) et `pydantic` (inutilisé) ; dépendances de test explicites.

---

## [2.0.1] — 2026-05-02

### Bug fixes

- **Entities grayed out when pump is powered off**: when the external switch turns OFF, entities now become `unavailable` (grayed out) instead of showing zero values with an orange warning icon. A new `pump_switch_off` flag on the coordinator is checked in the `available` property of all entities.

---

## [2.0.0] — 2026-04-17

### Nouvelles fonctionnalités

#### Qualité & architecture (HA Quality Scale Bronze/Silver/Gold)
- **Appareil unique dans HA** : toutes les entités regroupées sous un seul appareil "Emaux SPV150"
- **Statistiques long terme** : `CurrentWatts` et `CurrentGPM` utilisent `SensorStateClass.MEASUREMENT`
- **Reconfiguration sans suppression** : bouton "Reconfigurer" pour changer IP/switch sans réinstaller
- **Options modifiables** : IP, switch, intervalle de polling et paramètres solaires via "Configurer"
- **Test de connexion** : la pompe est pingée avant de valider la configuration
- **Protection contre les doublons** : impossible d'ajouter deux fois la même IP
- **Classes d'appareil** : `SensorDeviceClass.POWER` sur Watts, `SensorDeviceClass.VOLUME_FLOW_RATE` sur GPM
- **Traductions** : `strings.json` + `translations/en.json`

#### Monitoring
- **Énergie cumulée** (`sensor.energy`) : kWh accumulés, `SensorStateClass.TOTAL_INCREASING`, compatible dashboard Énergie
- **Temps de fonctionnement** (`sensor.uptime`) : heures depuis le dernier démarrage
- **Intervalle de polling configurable** : 5 / 15 / 30 / 60 secondes (défaut : 30 s)

#### Contrôle de vitesse — protection et séquencement
- **Throttle configurable** (`speed_change_interval`) : intervalle minimum entre deux changements de vitesse (défaut : 60 s)
- **Priming au démarrage physique** : lors d'une mise sous tension via le switch externe (OFF→ON), attente de la fin du priming (défaut : 120 s) avant d'activer la régulation solaire. Dans tous les autres cas, la régulation s'applique immédiatement.

#### Mode solaire — régulateur P avec bande morte
- **Sélecteur de mode** (`select.control_mode`) : `Off` / `Manuel` / `Solaire` — **persisté entre les redémarrages**
- **Entité puissance réseau configurable** : accepte n'importe quelle entité HA
- **Régulateur proportionnel (P)** centré sur un setpoint configurable :
  - `error = |grid_power - setpoint|`
  - `step = min(step_max, max(10, int(error)))` — proportionnel au delta, plafonné
  - En-dessous de la borne inférieure → vitesse + step
  - Au-dessus de la borne supérieure → vitesse − step
  - Dans la bande morte → aucun changement
- **Protection données périmées** : si l'entité puissance réseau n'a pas changé depuis plus de 60 s, la régulation est suspendue
- **Persistance complète** : mode, setpoint, bande morte et pas survivent aux redémarrages
- **Paramètres ajustables depuis l'UI** (entités `number`, saisie directe) :
  - Setpoint (W) — défaut : 0 W
  - Borne inférieure bande morte (W) — défaut : 0 W
  - Borne supérieure bande morte (W) — défaut : 100 W
  - Pas max montée (RPM) — défaut : 300 RPM
  - Pas max descente (RPM) — défaut : 30 RPM
  - Vitesse min solaire (RPM) — défaut : 1400 RPM
  - Vitesse max solaire (RPM) — défaut : 3000 RPM

### Améliorations techniques
- `entry.runtime_data` remplace `hass.data[DOMAIN]`
- `PumpBaseEntity` : classe de base partagée (`DeviceInfo`, `available`, `has_entity_name`)
- `PARALLEL_UPDATES = 1` sur toutes les plateformes
- `UpdateFailed` quand la pompe ne répond plus (entités → `unavailable`, récupération automatique au poll suivant)
- `async_config_entry_first_refresh` au démarrage
- Options flow : les clés persistées (mode, paramètres solaires) sont préservées lors d'une mise à jour des options
- Timeout HTTP appliqué à chaque requête (session partagée HA)
- `ConfigEntryNotReady` dans `_async_setup` pour retry automatique si pompe offline au boot
- Énergie accumulée uniquement si `RunningStatus == 1`
- `NumberMode.BOX` sur tous les paramètres de saisie (pas de slider)
- `restore_energy()` méthode publique sur le coordinator

### Bugs corrigés
- `api.py` : timeout ignoré sur la session partagée HA → passé à chaque requête
- `coordinator.py` : `UpdateFailed` → `ConfigEntryNotReady` dans `_async_setup`
- `coordinator.py` : énergie accumulée avant le check `running` → corrigé
- `coordinator.py` : `switch_entity=""` falsy retombait sur `entry.data` → clé-existence check
- `coordinator.py` : réponse vide ne levait pas d'erreur → `UpdateFailed`
- `switch.py` : pas de refresh après `turn_on` / `turn_off`
- Options flow : sauvegarde écrasait le mode de contrôle persisté
- Priming : déclenchement parasite à chaque rechargement de configuration
- Imports absolus → imports relatifs
- Logs f-strings → format `%s`

---

## [1.0.0] — 2025-04-14

- Commit initial : surveillance et contrôle de la pompe Emaux SPV150
- Entités : `CurrentWatts`, `CurrentGPM` (sensors), `CurrentSpeed`, `SpeedSelected` (numbers), `RunningStatus` (switch)
- Polling toutes les 5 secondes via HTTP CGI
- Support d'une entité switch externe pour couper le polling
- Config flow UI
- Compatible HACS
