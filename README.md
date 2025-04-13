# emaux_spv150 pour Home Assistant

![downloads](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=utilisateurs%20HACS&suffix=%20installations&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.emaux_spv150.total)

Intégration personnalisée Home Assistant pour contrôler et surveiller la pompe de piscine Emaux SPV150.

![image info](/img/main.jpeg)

## Fonctionnalités

- 🔄 Lecture automatique de l’état de la pompe toutes les 5 secondes.
- 📊 Exposition de capteurs (vitesse actuelle de la pompe).
- 🎛️ Contrôle de la vitesse de la pompe via une entité `number`.
- 🔧 Configuration via l'interface graphique de Home Assistant (aucun YAML requis).

## Installation

### Via HACS

1. Assurez-vous que [HACS](https://hacs.xyz/) est installé et configuré.
2. Dans HACS, allez dans **Intégrations**.
3. Cliquez sur les trois points (⋮) en haut à droite > **Dépôts personnalisés**.
4. Ajoutez l’URL de ce dépôt GitHub et sélectionnez **Intégration** comme catégorie.
5. Recherchez `emaux_spv150` dans HACS et installez l'intégration.

### Installation manuelle

1. Téléchargez ce dépôt.
2. Copiez le dossier `emaux_spv150` dans `config/custom_components/` de votre instance Home Assistant.
3. Redémarrez Home Assistant.

## Configuration

1. Allez dans **Paramètres > Appareils & Services**.
2. Cliquez sur **Ajouter une intégration**.
3. Recherchez `emaux_spv150`.
4. Entrez l’adresse IP de la pompe.

## Entités exposées

- `sensor.emaux_spv150_current_speed` : Vitesse actuelle de la pompe (RPM).
- `number.emaux_spv150_speed` : Permet de définir la vitesse de la pompe (entre 800 et 3400 RPM, par pas de 10).

![image info](/img/page_web.jpeg)
