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
et ne sont valables que pour le noyau constructeur 5.4.

| Option de `[CONTROLS]` | Broche actuelle | GPIO VIM4 | État |
|---|---|---|---|
| `picture_btn_pin`  | 11 | — | **à déplacer** : la broche 11 du VIM4 est une alimentation VDD1V8 |
| `picture_led_pin`  | 16 | 490 | inchangé |
| `print_btn_pin`    | 32 | 448 | inchangé |
| `print_led_pin`    | 15 | 491 | inchangé |
| `startup_led_pin`  | 29 | 447 | inchangé |
| `preview_led_pin`  | 31 | 449 | inchangé |
| `flash_led_pin`    | 33 | 450 | inchangé |
| `forget_btn_pin`   | 36 | 464 | inchangé |
| `forget_led_pin`   | 37 | 465 | inchangé |

Broches libres pour le bouton de capture : **22** (GPIO 501), **30** (446),
**23** (502), **25** (466), **26** (467), **35** (492).

### Attention au câblage

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
| **Kit Arducam IMX708 USB UVC (50 $)** | le capteur du module Pi actuel, derrière un adaptateur CSI vers UVC | identique à aujourd'hui, au tuning ISP près | aucun, `CvCamera` est déjà supporté |

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

En USB, en revanche, oui : Arducam vend une carte convertissant le MIPI CSI en
UVC, et donc un
[kit IMX708 tout fait](https://blog.arducam.com/imx708-camera-or-webcam-combined/)
à 49,98 $ (59,98 $ en 102° grand angle), qui conserve la définition native de
4608×2592. Le capteur devient une webcam standard : `CvCamera` fonctionne
directement et le plugin `pibooth_picamera2.py`, spécifique au Pi, disparaît.

Limites :

- ces kits sont à mise au point fixe, ce qui convient puisque le plugin actuel
  verrouille déjà l'hyperfocale, mais le module Pi officiel ne peut pas être
  recyclé sur l'adaptateur : son moteur d'autofocus n'est pas piloté. Acheter
  le kit complet plutôt que la carte seule ;
- le traitement d'image est celui de l'adaptateur, pas celui du Raspberry Pi :
  couleurs et bruit un cran en dessous ;
- la pleine définition tombe à une dizaine d'images par seconde, sans
  conséquence pour un photomaton ;
- les réglages d'exposition et de balance des blancs passent par les contrôles
  UVC (`v4l2-ctl`) au lieu de ceux de picamera2.

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

## 4. Reste à faire

- adapter la rotation de l'écran et l'inversion du tactile (`xrandr` et matrice
  de transformation libinput, à la place de `/boot/config.txt`) ;
- adapter les services du portail Wi-Fi et de la galerie (`install/`) ;
- vérifier les versions figées de `Pillow` et `pygame-menu` sur ARM64 ;
- porter les plugins externes qui utilisent encore `gpiozero` directement.
