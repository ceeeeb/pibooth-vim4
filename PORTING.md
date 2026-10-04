# Portage de pibooth sur Khadas VIM4

Ce dépôt est la variante du fork `pibooth-ceeeeb` destinée à remplacer le
Raspberry Pi 4 par un Khadas VIM4 (Amlogic A311D2, Ubuntu 22.04).

## 1. GPIO

### Ce qui a changé

L'accès aux boutons et aux LED passait par `gpiozero`, qui ne fonctionne que
sur Raspberry Pi : sur toute autre carte, `pibooth` basculait silencieusement
sur un GPIO simulé et aucun bouton ne répondait.

Le paquet `pibooth.hardware` remplace cet accès direct :

- la carte est détectée au démarrage via `/proc/device-tree/model` ;
- le backend correspondant est chargé (`gpiozero` sur Pi, `/dev/gpiochipN` via
  `lgpio` sur VIM4, simulateur sinon) ;
- les numéros de broches de `pibooth.cfg` restent ceux du connecteur physique
  (numérotation BOARD), quelle que soit la carte.

Ajouter une nouvelle carte ne demande aucun code : il suffit d'une section dans
`pibooth/hardware/pinouts.ini`.

### Correspondance des broches

Le connecteur 40 broches du VIM4 n'a pas le même brochage que celui du Pi. Les
lignes GPIO proviennent de la
[documentation Khadas](https://docs.khadas.com/products/sbc/vim4/applications/gpio/40pin-header)
et ont été vérifiées sur le noyau constructeur 5.15 (Fenix 1.7.5).

| Option de `[CONTROLS]` | Broche Pi | Broche VIM4 | GPIO VIM4 |
|---|---|---|---|
| `picture_btn_pin`  | 11 | **22** | 501 |
| `picture_led_pin`  | 16 | 16 | 490 |
| `print_btn_pin`    | 32 | 32 | 448 |
| `print_led_pin`    | 15 | 15 | 491 |
| `startup_led_pin`  | 29 | 29 | 447 |
| `preview_led_pin`  | 31 | 31 | 449 |
| `flash_led_pin`    | 33 | 33 | 450 |
| `forget_btn_pin`   | 36 | 36 | 464 |
| `forget_led_pin`   | 37 | 37 | 465 |

Seul le bouton de capture change de broche : la broche 11 du VIM4 est une
alimentation (VDD1V8). Le modèle `install/files/pibooth.cfg.template` garde la
broche 11 du Pi, l'installeur la remplace par 22 sur VIM4.

Broches encore libres : 13 (GPIO 420), 23 (502), 25 (466), 26 (467),
30 (446), 35 (492), 39 (417).

### Attention au câblage

Le connecteur n'est **pas numéroté comme celui du Pi**. Le Pi alterne les
broches impaires et paires d'une rangée à l'autre ; le VIM4 numérote **par
rangée** : 1 à 20 sur la première, 21 à 40 sur la seconde, la broche 21 faisant
face à la broche 1. La broche 37 est donc la 17ᵉ de la seconde rangée, en face
de la 17. Repérer la broche 1 sur la sérigraphie et compter avant de brancher :
un fil placé « comme sur le Pi » tombe sur une autre broche, et la LED reste
éteinte alors que pibooth la commande.

Les broches d'alimentation ne sont **pas** au même endroit que sur le Pi :

| Broche | Raspberry Pi | Khadas VIM4 |
|---|---|---|
| 1 | 3V3 | **5V** |
| 4 | 5V | **USB HUB_D4P** |
| 6 | GND | **VCCMCU** |
| 20, 27 | GND, ID_SD | **3V3** |

Réutiliser le faisceau du Pi tel quel peut détruire la carte. Masses du VIM4 :
5, 9, 14, 17, 21, 24, 28, 34, 40. 3V3 : 20 et 27.

Les résistances de tirage internes ne sont pas garanties sur toutes les lignes
Amlogic : prévoir des **pull-up externes de 10 kΩ** sur les boutons. Le backend
émet un avertissement quand le noyau refuse le tirage interne.

Une sortie GPIO donne 3,3 V et quelques mA : assez pour une LED simple avec
une résistance série de 330 Ω à 1 kΩ, pas pour une lampe de bouton d'arcade en
5 V ou 12 V, qu'il faut commander par un transistor.

Le flash (`flash_led_pin`) commande un **module relais 1 voie** à optocoupleur
(relais SRD-05VDC, « high/low level trigger ») :

| Borne du module | Broche du VIM4 |
|---|---|
| DC+ | 2 (5V) |
| DC− | 34 ou 40 (GND) |
| IN | 33 |

La bobine du relais demande **5 V** : alimenté en 3,3 V, le module reçoit le
signal mais le relais ne colle pas. Le cavalier du module se place sur **H**,
pibooth activant le flash par un état haut (`flash_led_active_high = True`) ;
sur L, régler cette option à `False`. Le côté puissance du relais commute le
secteur : le câbler hors tension et l'isoler du reste du montage.

Enfin, certaines broches sont multiplexées (I2C, UART, I2S). Si une ligne
refuse d'être réservée, la reconfigurer en GPIO via un *device tree overlay*.

### Vérification sur la carte

```bash
pip install -e .[chardev]   # installe lgpio en plus
pibooth-gpio                # allume chaque LED, puis affiche les appuis
```

Le script lit les broches déclarées dans `pibooth.cfg`, signale celles qui ne
sont pas des GPIO sur la carte détectée, fait clignoter chaque LED deux
secondes puis surveille les boutons pendant vingt secondes.

Si une ligne n'est pas résolue, elle peut être déclarée directement sous la
forme `chip:offset` dans `pinouts.ini`.

## 2. Caméra

Le Pi utilise un module CSI Raspberry Pi (IMX708) piloté par le plugin
`pibooth_picamera2.py`, qui repose sur `picamera2` et `libcamera` : **rien de
tout cela n'existe sur VIM4**, et le module CSI du Pi n'y est pas compatible
électriquement. Il faut changer de capteur.

| Solution | Capteur | Qualité photo | Travail |
|---|---|---|---|
| **Reflex/hybride USB (gPhoto2)** | APS-C | très supérieure au module Pi | aucun, `GpCamera` est déjà supporté |
| Webcam USB UVC | 1/3" | inférieure au module Pi | aucun, `CvCamera` est déjà supporté |
| Khadas OS08A10 (69 $) | OV08A10, 8 MP, f/2.1, 160°, objectif M12 interchangeable | proche du module Pi si l'objectif est remplacé | backend V4L2/GStreamer à écrire |
| Khadas IMX415 (50 $) | Sony 1/2.8", 8,29 MP, f/2.4, 110°, autofocus | en dessous du module Pi en basse lumière | backend V4L2/GStreamer à écrire |
| **Arducam B0304 USB UVC (69 €)** | IMX708, le capteur du module Pi actuel, derrière un adaptateur CSI vers UVC, f/2.2, 66° H | identique à aujourd'hui, au tuning ISP et à l'ouverture près | aucun, `CvCamera` est déjà supporté |

Remarques :

- 8 MP suffisent largement : un tirage 10×15 à 300 dpi ne demande que 2,2 MP.
- l'absence d'autofocus n'est pas gênante, le plugin actuel verrouille déjà la
  mise au point sur l'hyperfocale ;
- l'angle de champ, lui, est un vrai problème : 160° (OS08A10) et 110°
  (IMX415) sont des optiques de vision robotique, très déformantes en portrait.
  Seul l'OS08A10 permet de monter un objectif M12 plus long ;
- le VIM4 existe en deux versions avec des ISP différents, et l'auto-détection
  des caméras n'arrive qu'à partir du firmware 1.7.5 ;
- les captures passent par `/dev/media0` avec GStreamer, `cv2.VideoCapture` ne
  suffit pas.

**Recommandation** : passer au boîtier photo USB via gPhoto2. C'est le seul
choix qui gagne en qualité, il ne demande aucun développement, et il rend le
photomaton indépendant de la carte.

### Peut-on rebrancher le module Pi sur le VIM4 ?

Pas en MIPI. Khadas ne publie pas le brochage de ses ports CSI, laisse les
demandes d'adaptateur FPC vers le 15 ou 22 broches du Pi sans réponse sur son
forum, et son CSI est en 3,3 V non standard. Surtout, le blocage est logiciel :
il faudrait un pilote IMX708 dans le noyau Amlogic, l'overlay correspondant et
les fichiers de calibration de l'ISP Amlogic pour ce capteur, qui n'existent
pas. Toute la qualité d'image du module Pi vient du tuning `imx708.json` de
libcamera, côté ISP Broadcom, et n'est pas transposable.

En USB, en revanche, oui : Arducam vend le même capteur derrière un adaptateur
CSI vers UVC, en kit tout fait. Modèle retenu : **Arducam B0304, 12MP IMX708
USB UVC Fixed-Focus Camera Module 3**, environ 69 €.

| | B0304 | Module Pi 3 actuel |
|---|---|---|
| Capteur | IMX708, 4608×2592, pixels 1,4 µm | identique |
| Champ | 75° D, 66° H, 41° V | 75° D, 66° H |
| Ouverture | f/2.2, focale 2,75 mm | f/1.8, focale 4,74 mm |
| Mise au point | fixe | autofocus, verrouillé sur l'hyperfocale par le plugin |
| Débits | 4608×2592 à 15 i/s, 1920×1080 et 1280×720 à 30 i/s | — |
| Flux | MJPG et YUV, contrôles UVC standards | picamera2 et libcamera |

Le cadrage sera donc identique à celui d'aujourd'hui, à un tiers de diaphragme
près en moins. Le capteur devient une webcam standard : `CvCamera` fonctionne
directement et le plugin `pibooth_picamera2.py`, spécifique au Pi, disparaît.

Points d'attention :

- la pleine définition n'est atteinte qu'en flux compressé. `CvCamera` négocie
  donc le format MJPG à l'initialisation, sans quoi le pilote retombe
  silencieusement sur une définition plus basse ;
- le module Pi officiel ne peut pas être recyclé sur un adaptateur acheté seul,
  son moteur d'autofocus n'y est pas piloté : prendre le kit complet ;
- le traitement d'image est celui de l'adaptateur, pas celui du Raspberry Pi :
  couleurs et bruit un cran en dessous ;
- les réglages d'exposition et de balance des blancs passent par les contrôles
  UVC (`v4l2-ctl`) au lieu de ceux de picamera2 ;
- `resolution = (4608,2592)` peut rester tel quel dans la configuration.

Ce kit est testable sur le Pi actuel avant même la migration : le brancher en
USB, basculer la configuration sur `CvCamera` et comparer le rendu.

## 3. Pistes pour tirer parti du VIM4

Par ordre d'intérêt pour le photomaton :

1. **NPU 3,2 TOPS** — porter le modèle de détourage du plugin
   `background_changer` (silueta) sur le NPU via le SDK Amlogic. C'est
   aujourd'hui l'étape la plus lente de la chaîne sur Pi 4.
2. **Entrée HDMI 4K60** — brancher la sortie HDMI propre d'un hybride pour
   obtenir un aperçu fluide sans latence *et* la capture, là où gPhoto2 impose
   un live view médiocre. Fonctionnalité absente de tous les Raspberry Pi.
3. **Encodeur H.264/H.265 matériel** (`amlvenc`) — proposer un GIF animé ou une
   courte vidéo des invités sans coût CPU.
4. **8 cœurs (4×A73 + 4×A53)** — composer la photo précédente pendant la prise
   suivante au lieu de faire attendre les invités.
5. **Wi-Fi 6 et eMMC** — envois Nextcloud/pCloud et écritures disque nettement
   plus rapides.
6. **Deux ports MIPI-CSI** — deuxième point de vue, ou capture large + portrait
   dans la même séquence.

## 4. Installation

`install/install.sh` détecte la carte et adapte ce qui en dépend :

| | Raspberry Pi | autre carte |
|---|---|---|
| Paquets APT | `python3-picamera2`, `python3-gpiozero`, `python3-libgpiod` | `python3-libgpiod` |
| Paquets Python | `pibooth-picamera2` | `lgpio` |
| Affichage | rotation et `gpu_mem` écrits dans le `config.txt` du firmware | à configurer à la main |

Les plugins GPIO externes sont portés dans `~/git/pibooth-extra-lights-vim4` et
`~/git/pibooth-forget-button` : ils demandent leurs boutons et leurs LED à
`app.board` au lieu de `gpiozero`, et fonctionnent donc sur les deux cartes.

`~/git/pibooth-background-changer` ne touche pas au GPIO, mais choisissait son
modèle de détourage d'après la seule famille Raspberry Pi : le VIM4 tombait dans
la branche « ordinateur de bureau ». Il reconnaît maintenant la carte et choisit
`u2net_human_seg` sur le VIM4. L'installateur ne l'installe plus : le choix du
modèle de mise en page, par glissement sur l'écran d'accueil, l'a remplacé.

Le reste des étapes (services, hotspot, portail captif, galerie, démarrage
automatique) ne dépend pas de la carte. Le sudoers du portail Wi-Fi est limité
à `nmcli device wifi connect`, la seule commande privilégiée qu'il exécute.

## 5. Reste à faire

- **rotation de l'écran** : `xrandr` et matrice de transformation libinput à la
  place de `display_hdmi_rotate`. Les commandes exactes dépendent du serveur
  d'affichage livré par Khadas, à déterminer sur la carte ;
- **publication** : `install.sh` installe depuis PyPI, les versions portées
  doivent y être publiées pour que l'installation fonctionne sur VIM4. Le fork
  des lumières est renommé `pibooth-extra-lights-vim4`, le nom amont étant déjà
  pris ; `pibooth-forget-button` garde le sien et passe en 1.1.0 ;
- vérifier les versions figées de `Pillow` et `pygame-menu` sur ARM64.
