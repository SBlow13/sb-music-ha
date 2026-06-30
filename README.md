# SB'Music — Home Assistant Custom Component

Contrôlez votre instance [SB'Music](https://github.com/SB-Music/SB-Music) depuis Home Assistant.

## Installation

1. Copiez le dossier `custom_components/sb_music` dans le dossier `custom_components` de votre instance Home Assistant
2. Redémarrez Home Assistant
3. Allez dans **Paramètres → Appareils et services → Ajouter une intégration**
4. Recherchez **SB'Music** et cliquez dessus
5. Renseignez :
   - **URL du serveur** (ex: `http://192.168.1.100:3000`)
   - **Email** de votre compte SB'Music
   - **Mot de passe**
6. Sélectionnez le périphérique à contrôler

## Fonctionnalités

- **Media Player** complet : play, pause, next, previous, stop
- **Volume** : contrôle du volume
- **Shuffle / Repeat** : activation/désactivation
- **Seek** : avance rapide / retour
- **État en direct** : affiche le titre, l'artiste, l'album, la pochette, la position, la durée
- **Mise à jour** : polling toutes les 10 secondes

## Dépannage

- **Cannot connect** : vérifiez que l'URL du serveur est accessible depuis Home Assistant
- **Invalid auth** : vérifiez votre email/mot de passe SB'Music
- **No devices** : ouvrez SB'Music dans un navigateur pour qu'un périphérique soit connecté
