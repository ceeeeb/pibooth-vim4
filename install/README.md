# Réinstallation complète du photobooth

Reconstruit un poste pibooth depuis un Raspberry Pi neuf, sur lequel seul le
système d'exploitation est installé.

## Prérequis

### Système

Raspberry Pi OS **Bookworm 64 bits, édition Desktop** (l'édition Lite ne convient
pas : pibooth a besoin d'une session graphique). Au premier démarrage, activer SSH
et connecter le Pi au Wi-Fi.

### Matériel

| Élément | Nécessité | Remarque |
|---|---|---|
| Raspberry Pi 4 (2 Go minimum) | requis | |
| Caméra CSI ou reflex USB | requis | gPhoto2 pour un reflex |
| Écran tactile HDMI | requis | monté à l'envers, d'où la rotation |
| Boutons et LED GPIO | optionnel | numérotation BOARD |
| Imprimante CUPS | optionnel | Canon SELPHY testée |
| **Dongle Wi-Fi USB** | requis pour le hotspot | voir ci-dessous |

### Le dongle Wi-Fi : à lire avant d'acheter

Le hotspot invités exige une **seconde radio**. La puce interne du Pi sait faire
point d'accès et client simultanément, mais impose alors un canal unique partagé
avec la box, ce qui est instable.

Deux critères pour le dongle :

1. **Le mode AP doit être supporté.** Vérifier après branchement :
   `iw list | grep -A6 "Supported interface modes"` doit lister `* AP`.
2. **La consommation doit être modérée.** Les vieux chipsets (RT2573 par exemple)
   tirent jusqu'à 500 mA en émission. Le Pi 4 plafonne à ~1,2 A pour l'ensemble de
   ses ports USB : au démarrage, quand l'écran tactile et les autres périphériques
   s'initialisent en même temps, le limiteur déclenche et **le dongle disparaît
   jusqu'au prochain débranchement physique**. Aucun reset logiciel ne l'en sort,
   pas même une réinitialisation du contrôleur USB PCIe.

Chipsets recommandés : **RTL8188EUS** ou **MT7601U** — sobres, mode AP natif, et
802.11n. En cas de doute, ou pour garder un montage chargé, utiliser un **hub USB
alimenté** : c'est la seule solution robuste.

## Installation

```bash
git clone https://github.com/ceeeeb/pibooth.git
cd pibooth/install
HOTSPOT_SSID="Pibooth" HOTSPOT_PASSWORD="motdepasse" ./install.sh
```

Compter 15 à 30 minutes selon la connexion. Le script est **idempotent** : il peut
être relancé sans dommage.

### Options

```bash
./install.sh --skip-network        # tout sauf le réseau
./install.sh --only python         # une seule étape
./install.sh --help
```

Étapes disponibles pour `--only` : `packages`, `system`, `python`, `scripts`,
`services`, `network`, `display`, `autostart`, `config`.

### Variables de configuration

Toutes surchargeables par variable d'environnement.

| Variable | Défaut | Rôle |
|---|---|---|
| `HOTSPOT_SSID` | `Pibooth` | nom du réseau invités |
| `HOTSPOT_PASSWORD` | *(vide)* | WPA2, 8 caractères minimum. Vide = hotspot non configuré |
| `HOTSPOT_IFACE` | `wlan1` | interface du dongle |
| `HOTSPOT_CHANNEL` | `11` | canal 2,4 GHz |
| `HOTSPOT_ADDRESS` | `10.42.0.1` | adresse du Pi sur le hotspot |
| `HOTSPOT_SHARE_INTERNET` | `no` | `yes` partage la connexion avec les invités |
| `CLIENT_IFACE` | `wlan0` | radio interne, connexion à la box |
| `GALLERY_PORT` | `8081` | port de la galerie |
| `DISPLAY_ROTATE` | `2` | rotation écran (2 = 180°) |
| `TIMEZONE` | `Europe/Paris` | fuseau horaire, qui date les photos |
| `WIFI_COUNTRY` | `FR` | pays de la puce Wi-Fi du VIM4 (canaux et puissances autorisés) |

**Choisir un SSID qui n'existe pas déjà autour de vous.** Si le hotspot porte le
nom d'un réseau connu des téléphones mais avec un autre mot de passe, ceux-ci
retentent l'ancien et affichent « mot de passe incorrect » **sans jamais demander
le nouveau**. Il faut alors faire « oublier ce réseau » sur chaque appareil.

## Après l'installation

1. **Identifiants d'envoi** — le modèle de configuration contient des champs
   `A_RENSEIGNER` pour Nextcloud et pCloud :
   ```bash
   nano ~/.config/pibooth/pibooth.cfg
   ```
2. **Imprimante**, si présente :
   ```bash
   ~/pibooth/pibooth/bin/pibooth-printcfg
   ```
3. **Redémarrer** pour appliquer la rotation d'écran :
   ```bash
   sudo reboot
   ```

## Ce que le script installe

### Retournement du tactile

L'écran étant monté à l'envers, le firmware pivote l'affichage
(`display_hdmi_rotate=2`) mais **SDL lit le tactile en coordonnées brutes, non
pivotées**. Sans correction, chaque appui atterrit à l'opposé de la cible.

pibooth retourne le tactile quand l'option `touch_flip` de la section
`[WINDOW]` de `pibooth.cfg` vaut `True` (désactivée par défaut). Le script
l'active sur Raspberry Pi avec `DISPLAY_ROTATE=2`, et la laisse à `False` sur les
autres cartes, où l'affichage n'est pas pivoté par le firmware. Une valeur déjà
présente dans `pibooth.cfg` est conservée.

Si le tactile répond à l'opposé (par exemple sur une configuration antérieure à
cette option), ajouter l'option :

```bash
./install.sh --only config
```

ou régler `touch_flip = True` à la main dans `[WINDOW]`, ou dans le menu de
réglages (« Flip touchscreen »).

**Application** — un venv en `~/pibooth/pibooth` créé avec
`--system-site-packages`, indispensable car `picamera2` et `python3-opencv`
proviennent d'APT et ne s'installent pas correctement via pip sur Raspberry Pi OS.
Le fork `pibooth-ceeeeb` et ses plugins sont tirés de PyPI. Le fork et le
pibooth amont installent le même module `pibooth` : si un plugin tiers fait
installer l'amont, l'installateur le retire et réinstalle le fork.

**Mise en page** — les invités choisissent leur modèle sur l'écran d'accueil en
faisant glisser le doigt : la dernière photo y est réassemblée dans le modèle
choisi (plugin `pibooth-template-chooser`). Le plugin fournit neuf modèles pour
la carte SELPHY 10 × 15 — photomaton, Hollywood, anniversaire, art déco, quatre
mariages, carte postale vintage — chacun avec une page 1 photo et une page
4 photos, ainsi que leurs polices libres (licence OFL). Les noms et la date
restent `footer_text1` et `footer_text2` de `pibooth.cfg`. Pour retoucher les
modèles dans draw.io, voir le README du plugin. L'ancien plugin
`pibooth-picture-template`, désormais intégré, est désinstallé s'il est présent.

**Services web** — `gallery` (galerie de la session en cours, port 8081),
`wifi-portal` (ajout d'un réseau Wi-Fi depuis un téléphone, port 8080),
`captive-portal` (redirection HTTP, port 80), activé seulement avec le hotspot.

**Système** — fuseau horaire. Hors Raspberry Pi : écriture sur disque toutes les
5 s (les images Khadas attendent 10 min, une coupure perdrait les dernières
photos), journal système conservé d'un démarrage à l'autre, puce Wi-Fi du VIM4 réglée pour le pays (la Chine par défaut), et service
`camera_isp_3a_server` désactivé, inutile avec une caméra USB.

**Réseau** — un point d'accès `pibooth-ap` sur le dongle, pendant que la radio
interne reste cliente de la box. Toutes les connexions client sont épinglées sur
`wlan0` : sans cela, NetworkManager peut activer un profil client sur l'interface
du hotspot et le couper.

**Portail captif** — le dnsmasq que NetworkManager lance déjà résout tout domaine
vers le Pi, et un redirecteur HTTP renvoie vers la galerie. Les téléphones
détectent alors un portail et proposent d'ouvrir la page. L'option DHCP 114
(RFC 8910) annonce l'URL directement dans le bail.

Par défaut les invités **n'ont pas accès à internet** : une table nftables
prioritaire bloque le routage sortant du hotspot. Le dnsmasq n'écoute que sur
l'adresse du hotspot, donc le Pi conserve son propre DNS et ses envois vers
Nextcloud et pCloud.

### Cloisonnement du réseau invités

Le hotspot est ouvert à des inconnus : la même table nftables applique donc un
**refus par défaut** sur les paquets entrants du hotspot, et n'autorise que ce
dont un invité a besoin — DNS et DHCP (53, 67), portail captif (80), galerie
(8081), et `echo-request`.

Restent donc inaccessibles depuis le réseau invités :

| Service | Pourquoi il est fermé aux invités |
|---|---|
| Portail Wi-Fi (8080) | pilote `nmcli` en sudo : un invité pourrait supprimer les réseaux enregistrés ou faire basculer le Pi sur un réseau qu'il contrôle |
| SSH (22) | accès shell |

Ces deux services restent joignables normalement depuis le LAN opérateur — c'est
l'interface d'arrivée qui décide, pas le port.

Le portail valide par ailleurs les identifiants saisis avant de les passer à
`nmcli` : un SSID ou un mot de passe commençant par `-` serait interprété comme
une option par `nmcli`, qui **ne reconnaît pas le sentinelle `--`** (il le lit
comme un nom de profil littéral). Ces valeurs sont donc rejetées, de même que les
caractères de contrôle et les longueurs hors spécification (32 octets de SSID,
63 caractères de clé).

## Dépannage

| Symptôme | Cause probable | Action |
|---|---|---|
| `wlan1` absent après un reboot | surintensité USB au démarrage | débrancher/rebrancher le dongle ; voir la section matériel |
| « mot de passe incorrect » sur le hotspot | profil homonyme mémorisé sur le téléphone | « oublier ce réseau » sur l'appareil |
| La galerie ne s'ouvre pas seule | comportement normal d'Android | une notification apparaît, un tap suffit |
| Le hotspot tombe après un ajout de Wi-Fi | connexion non épinglée | `./install.sh --only network` |
| pibooth ne démarre pas | dépendance ou matériel | `~/pibooth/pibooth/bin/pibooth-diag` |
| Le tactile répond à l'opposé | retournement perdu après une mise à jour pip | `./install.sh --only display` |

Journaux utiles :

```bash
systemctl status gallery wifi-portal captive-portal
journalctl -u NetworkManager -f
sudo dmesg | grep -iE "over-current|rt2x00"
```

## Sauvegarde

Le script ne restaure **ni les photos ni les identifiants**. À sauvegarder
séparément avant de reconstruire un poste :

- `~/Pictures/pibooth/` — les photos des évènements
- `~/.config/pibooth/pibooth.cfg` — la configuration, identifiants compris
