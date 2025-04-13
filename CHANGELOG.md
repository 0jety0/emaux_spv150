# Changelog

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
