#!/usr/bin/env bash
#
# Installation complète du photobooth pibooth sur un Raspberry Pi neuf.
#
# Part d'une installation fraîche de Raspberry Pi OS Bookworm (64 bits, Desktop)
# et reconstruit l'intégralité du poste : application, plugins, services web,
# hotspot Wi-Fi invités, portail captif, affichage et démarrage automatique.
#
# Usage :
#   ./install.sh                 installation complète
#   ./install.sh --skip-network  tout sauf la configuration réseau
#   ./install.sh --only network  une seule étape (voir STEPS plus bas)
#
# Le script est idempotent : il peut être relancé sans dommage.

set -euo pipefail

# --- Configuration ---------------------------------------------------------
# Surchargeable par variable d'environnement : HOTSPOT_SSID=Fete ./install.sh

PIBOOTH_USER="${PIBOOTH_USER:-pi}"
PIBOOTH_HOME="${PIBOOTH_HOME:-/home/${PIBOOTH_USER}}"
VENV_DIR="${VENV_DIR:-${PIBOOTH_HOME}/pibooth/pibooth}"

HOTSPOT_SSID="${HOTSPOT_SSID:-Pibooth}"
HOTSPOT_PASSWORD="${HOTSPOT_PASSWORD:-}"
HOTSPOT_IFACE="${HOTSPOT_IFACE:-wlan1}"
HOTSPOT_CHANNEL="${HOTSPOT_CHANNEL:-11}"
HOTSPOT_ADDRESS="${HOTSPOT_ADDRESS:-10.42.0.1}"
CLIENT_IFACE="${CLIENT_IFACE:-wlan0}"
HOTSPOT_SHARE_INTERNET="${HOTSPOT_SHARE_INTERNET:-no}"

# Imprimante photo (Canon SELPHY) connectée au hotspot. Toutes les SELPHY se
# présentent au DHCP sous ce même nom : l'adresse fixe est réservée d'après lui,
# si bien que n'importe laquelle, interchangeable, la reçoit. Vide = aucune.
PRINTER_DHCP_NAME="${PRINTER_DHCP_NAME-SELPHY_DHCP_INSTANCE_0}"
PRINTER_ADDRESS="${PRINTER_ADDRESS:-10.42.0.50}"
PRINTER_QUEUE="${PRINTER_QUEUE:-Canon_SELPHY_CP1500}"

GALLERY_PORT="${GALLERY_PORT:-8081}"
WIFI_PORTAL_PORT="${WIFI_PORTAL_PORT:-8080}"
DISPLAY_ROTATE="${DISPLAY_ROTATE:-2}"
TIMEZONE="${TIMEZONE:-Europe/Paris}"
WIFI_COUNTRY="${WIFI_COUNTRY:-FR}"

# Renseignée par check_prerequisites : raspberry-pi, khadas-vim4 ou unknown.
BOARD="unknown"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FILES_DIR="${SCRIPT_DIR}/files"

STEPS=(packages system python scripts services network printer display autostart config)

# --- Sortie ----------------------------------------------------------------

readonly RED=$'\033[0;31m' GREEN=$'\033[0;32m' YELLOW=$'\033[0;33m'
readonly BLUE=$'\033[0;34m' BOLD=$'\033[1m' RESET=$'\033[0m'

step()  { printf '\n%s==> %s%s\n' "${BOLD}${BLUE}" "$*" "${RESET}"; }
info()  { printf '    %s\n' "$*"; }
ok()    { printf '    %s✓%s %s\n' "${GREEN}" "${RESET}" "$*"; }
warn()  { printf '    %s!%s %s\n' "${YELLOW}" "${RESET}" "$*"; }
fail()  { printf '\n%sÉchec :%s %s\n' "${RED}${BOLD}" "${RESET}" "$*" >&2; exit 1; }

# Installe un fichier depuis files/ avec propriétaire et droits explicites.
install_file() {
    local source="$1" target="$2" owner="$3" mode="$4"
    [[ -f "${FILES_DIR}/${source}" ]] || fail "fichier manquant : files/${source}"
    sudo install -D -o "${owner%%:*}" -g "${owner##*:}" -m "${mode}" \
        "${FILES_DIR}/${source}" "${target}"
    # Les fichiers de référence visent l'utilisateur pi du Raspberry Pi.
    sudo sed -i -e "s|/home/pi\b|${PIBOOTH_HOME}|g" -e "s|^User=pi$|User=${PIBOOTH_USER}|" "${target}"
    ok "${target}"
}

# --- Carte -----------------------------------------------------------------

# Seuls les paquets caméra et GPIO, et la configuration de l'affichage,
# dépendent de la carte. Voir PORTING.md pour le détail du portage.
detect_board() {
    local model=""
    [[ -f /proc/device-tree/model ]] && model="$(tr -d '\0' < /proc/device-tree/model)"
    case "${model}" in
        *"Raspberry Pi"*) echo "raspberry-pi" ;;
        *"Khadas VIM4"*)  echo "khadas-vim4" ;;
        *)                echo "unknown" ;;
    esac
}

# --- Vérifications ---------------------------------------------------------

check_prerequisites() {
    step "Vérifications préalables"

    [[ $EUID -ne 0 ]] || fail "à lancer en utilisateur normal (le script appelle sudo lui-même)"
    sudo -n true 2>/dev/null || sudo true || fail "sudo requis"

    id "${PIBOOTH_USER}" &>/dev/null || fail "utilisateur ${PIBOOTH_USER} inexistant"
    ok "utilisateur ${PIBOOTH_USER}"

    BOARD="$(detect_board)"
    if [[ -f /proc/device-tree/model ]]; then
        ok "$(tr -d '\0' < /proc/device-tree/model) → ${BOARD}"
    else
        warn "matériel sans device tree : GPIO et caméra seront indisponibles"
    fi
    if [[ "${BOARD}" == "unknown" ]]; then
        warn "carte non reconnue : le GPIO sera simulé, boutons et LED inertes"
    fi

    local codename
    codename="$(. /etc/os-release && echo "${VERSION_CODENAME:-inconnu}")"
    case "${codename}" in
        bookworm|jammy|noble) ok "distribution ${codename}" ;;
        *) warn "testé sur Bookworm et Jammy, détecté : ${codename}" ;;
    esac

    curl -fsS --head --max-time 10 -o /dev/null https://pypi.org/simple/pip/ \
        || fail "pas d'accès à PyPI — vérifier la connexion réseau"
    ok "accès réseau à PyPI"

    [[ -d "${FILES_DIR}" ]] || fail "répertoire files/ introuvable à côté du script"
}

# --- 1. Paquets système ----------------------------------------------------

step_packages() {
    step "Paquets système"

    # SDL2 : rendu pygame. gphoto2 : reflex USB. picamera2 : module caméra CSI.
    # CUPS : impression. nftables/NetworkManager : hotspot et portail captif.
    local packages=(
        git python3-venv python3-pip
        libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-mixer-2.0-0
        libsdl2-ttf-2.0-0 libsdl2-gfx-1.0-0
        libgphoto2-6 libgphoto2-dev libgphoto2-port12
        python3-numpy python3-opencv python3-flask
        cups libcups2-dev python3-cups
        # tkinter : fenêtre d'infos Wi-Fi affichée avant pibooth.
        python3-tk
        network-manager nftables dnsmasq-base
        ffmpeg fonts-liberation2 fonts-noto-color-emoji
        # Pillow 9.2.0, figé par pibooth, n'a pas de wheel pour Python 3.11+ :
        # pip le compile, et sans ces en-têtes il ne sait plus écrire de texte.
        libfreetype-dev libjpeg-dev zlib1g-dev libpng-dev
    )

    # picamera2 et gpiozero n'existent que sur Raspberry Pi OS. Ailleurs le GPIO
    # passe par le character device, et la caméra par l'USB.
    if [[ "${BOARD}" == "raspberry-pi" ]]; then
        packages+=(python3-picamera2 python3-gpiozero python3-libgpiod)
    else
        packages+=(python3-libgpiod)
    fi

    info "mise à jour de l'index APT…"
    sudo apt-get update -qq

    info "installation de ${#packages[@]} paquets (peut prendre plusieurs minutes)…"
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${packages[@]}"
    ok "paquets installés"

    [[ "${BOARD}" == "raspberry-pi" ]] || grant_gpio_access

    # lpadmin : gestion CUPS. gpio/spi/i2c : accès matériel sans root.
    local groups=(lpadmin gpio spi i2c input video render dialout plugdev)
    for group in "${groups[@]}"; do
        getent group "${group}" >/dev/null || continue
        sudo adduser "${PIBOOTH_USER}" "${group}" >/dev/null 2>&1 || true
    done
    ok "utilisateur ${PIBOOTH_USER} ajouté aux groupes matériels"
}

# Raspberry Pi OS livre déjà le groupe gpio et ses droits. Ailleurs, les
# /dev/gpiochipN appartiennent à root seul : sans cette règle, pibooth ne lit
# aucun bouton et n'allume aucune LED.
grant_gpio_access() {
    getent group gpio >/dev/null || sudo groupadd --system gpio
    install_file udev/99-pibooth-gpio.rules /etc/udev/rules.d/99-pibooth-gpio.rules root:root 644
    sudo udevadm control --reload-rules
    sudo udevadm trigger --subsystem-match=gpio
}

# --- 2. Réglages système -------------------------------------------------

step_system() {
    step "Réglages système"

    # Les dates des photos et le dossier du jour suivent le fuseau du système.
    sudo timedatectl set-timezone "${TIMEZONE}"
    ok "fuseau horaire : ${TIMEZONE}"

    [[ "${BOARD}" == "raspberry-pi" ]] && return 0

    shorten_disk_commit
    keep_journal
    configure_wifi_chip
    disable_camera_isp_server
}

# Les images Khadas n'écrivent sur l'eMMC que toutes les 10 minutes
# (commit=600) : une coupure de courant perdrait les dernières photos.
shorten_disk_commit() {
    if ! grep -E '\bcommit=[0-9]+' /etc/fstab | grep -qvE '\bcommit=5\b'; then
        ok "écriture sur disque toutes les 5 s"
        return 0
    fi
    sudo sed -i -E 's/\bcommit=[0-9]+/commit=5/' /etc/fstab
    sudo mount -o remount,commit=5 /
    ok "écriture sur disque toutes les 5 s au lieu de 10 min"
}

# Les images Khadas gardent le journal en mémoire seulement : après un blocage,
# plus rien n'explique ce qui s'est passé. 100 Mo suffisent à plusieurs semaines.
keep_journal() {
    sudo install -D -o root -g root -m 644 /dev/stdin /etc/systemd/journald.conf.d/50-pibooth-persistent.conf << CONF
[Journal]
Storage=persistent
SystemMaxUse=100M
CONF
    sudo systemctl restart systemd-journald
    ok "journal système conservé d'un démarrage à l'autre"
}

# Réglages de la puce Wi-Fi du VIM4, lus par son pilote bcmdhd au démarrage :
# - le pays, sans lequel il la règle pour la Chine (canaux et puissances d'un
#   autre pays, dont des canaux 5 GHz interdits ou manquants) ;
# - le 2,4 GHz seul : la puce porte le client et le hotspot sur un même canal,
#   et son itinérance ramènerait le client, donc le hotspot, en 5 GHz, hors de
#   portée de l'imprimante SELPHY qui ne capte que le 2,4 GHz.
# Le fichier appartient au paquet de la carte, qu'une mise à jour peut réécrire :
# relancer alors cette étape.
configure_wifi_chip() {
    local config=/lib/firmware/brcm/config_bcm43752a2_ag.txt
    [[ -f "${config}" ]] || return 0
    set_driver_option "${config}" ccode "${WIFI_COUNTRY}"
    set_driver_option "${config}" band b
    ok "puce Wi-Fi : pays ${WIFI_COUNTRY}, 2,4 GHz seulement (au prochain démarrage)"
}

set_driver_option() {
    local config="$1" key="$2" value="$3"
    if grep -q "^${key}=" "${config}"; then
        sudo sed -i "s/^${key}=.*/${key}=${value}/" "${config}"
    else
        echo "${key}=${value}" | sudo tee -a "${config}" >/dev/null
    fi
}

# Ce service ne sert qu'aux caméras MIPI, et échoue sans elles à chaque démarrage.
disable_camera_isp_server() {
    systemctl list-unit-files camera_isp_3a_server.service &>/dev/null || return 0
    sudo systemctl disable --now camera_isp_3a_server.service >/dev/null 2>&1 || true
    ok "service camera_isp_3a_server désactivé (caméra USB)"
}

# --- 3. Environnement Python ----------------------------------------------

step_python() {
    step "Environnement Python et application"

    # --system-site-packages : picamera2 et python3-opencv viennent d'APT,
    # ils ne s'installent pas correctement via pip sur Raspberry Pi OS.
    if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
        sudo -u "${PIBOOTH_USER}" python3 -m venv --system-site-packages "${VENV_DIR}"
        ok "venv créé : ${VENV_DIR}"
    else
        ok "venv déjà présent : ${VENV_DIR}"
    fi

    local pip="${VENV_DIR}/bin/pip"
    sudo -u "${PIBOOTH_USER}" "${pip}" install --quiet --upgrade pip setuptools wheel

    # Fork personnalisé publié sur PyPI, puis les plugins.
    local packages=(
        pibooth-ceeeeb
        pibooth-nextcloud
        pibooth-pcloud
        pibooth-gallery-qr
        pibooth-extra-lights-vim4
        pibooth-forget-button
        pibooth-template-chooser
        # pibooth n'imprime qu'avec pycups (APT, python3-cups) et pycups-notify.
        pycups-notify
    )

    # Le module caméra CSI du Pi n'a pas d'équivalent ailleurs : la caméra y est
    # branchée en USB et pilotée par OpenCV, et le GPIO a besoin de lgpio.
    if [[ "${BOARD}" == "raspberry-pi" ]]; then
        packages+=(pibooth-picamera2)
    else
        packages+=(lgpio)
    fi

    info "installation de pibooth et des ${#packages[@]} paquets Python…"
    sudo -u "${PIBOOTH_USER}" "${pip}" install --quiet --upgrade "${packages[@]}" \
        || fail "installation pip échouée"

    # pibooth-template-chooser intègre désormais pibooth-picture-template : les
    # deux déclarent [PICTURE] template et pibooth refuserait de démarrer.
    if "${pip}" show pibooth-picture-template &>/dev/null; then
        sudo -u "${PIBOOTH_USER}" "${pip}" uninstall --quiet --yes pibooth-picture-template
        ok "pibooth-picture-template retiré (intégré à pibooth-template-chooser)"
    fi

    ensure_fork_owns_pibooth "${pip}"

    for package in "${packages[@]}"; do
        local version
        version="$("${pip}" show "${package}" 2>/dev/null | awk '/^Version:/{print $2}')"
        [[ -n "${version}" ]] && ok "${package} ${version}" || warn "${package} absent"
    done
}

# pibooth-ceeeeb et le pibooth amont installent le même module : un plugin qui
# dépend encore de l'amont le fait installer par-dessus le fork. Désinstaller
# l'amont supprime aussi les fichiers partagés, d'où la réinstallation du fork.
ensure_fork_owns_pibooth() {
    local pip="$1" fork_version module_version
    fork_version="$("${pip}" show pibooth-ceeeeb 2>/dev/null | awk '/^Version:/{print $2}')"
    if "${pip}" show pibooth &>/dev/null; then
        warn "pibooth amont installé par un plugin : retiré au profit du fork"
        sudo -u "${PIBOOTH_USER}" "${pip}" uninstall --quiet --yes pibooth
        sudo -u "${PIBOOTH_USER}" "${pip}" install --quiet --force-reinstall --no-deps \
            "pibooth-ceeeeb==${fork_version}" || fail "réinstallation de pibooth-ceeeeb échouée"
    fi
    module_version="$(cd / && "${VENV_DIR}/bin/python" -c 'import pibooth; print(pibooth.__version__)' 2>/dev/null)"
    [[ "${module_version}" == "${fork_version}" ]] \
        || fail "le module pibooth (${module_version:-absent}) n'est pas celui du fork (${fork_version})"
    ok "module pibooth fourni par pibooth-ceeeeb ${fork_version}"
}

# --- 4. Scripts auxiliaires ------------------------------------------------

step_scripts() {
    step "Scripts auxiliaires"

    local owner="${PIBOOTH_USER}:${PIBOOTH_USER}"
    install_file gallery.py           "${PIBOOTH_HOME}/gallery.py"           "${owner}" 755
    install_file wifi-portal.py       "${PIBOOTH_HOME}/wifi-portal.py"       "${owner}" 755
    install_file captive-portal.py    "${PIBOOTH_HOME}/captive-portal.py"    "${owner}" 755
    install_file wifi-info-display.py "${PIBOOTH_HOME}/wifi-info-display.py" "${owner}" 755
    install_file start-pibooth.sh     "${PIBOOTH_HOME}/start-pibooth.sh"     "${owner}" 755

    # Le portail ne connecte que le Wi-Fi client. Un accès complet à nmcli
    # laisserait lire les mots de passe enregistrés avec 'connection show
    # --show-secrets' et supprimer n'importe quel profil.
    sudo tee /etc/sudoers.d/wifi-portal >/dev/null <<SUDOERS
Cmnd_Alias PIBOOTH_NMCLI = /usr/bin/nmcli device wifi connect *
${PIBOOTH_USER} ALL=(ALL) NOPASSWD: PIBOOTH_NMCLI
SUDOERS
    sudo chmod 440 /etc/sudoers.d/wifi-portal
    sudo visudo -cqf /etc/sudoers.d/wifi-portal || fail "sudoers wifi-portal invalide"
    ok "/etc/sudoers.d/wifi-portal"

    # Les adresses et ports diffèrent si la configuration a été surchargée.
    sudo sed -i \
        -e "s|^LISTEN_ADDRESS = .*|LISTEN_ADDRESS = \"${HOTSPOT_ADDRESS}\"|" \
        -e "s|^GALLERY_URL = .*|GALLERY_URL = \"http://${HOTSPOT_ADDRESS}:${GALLERY_PORT}/\"|" \
        "${PIBOOTH_HOME}/captive-portal.py"
    sudo sed -i "s|^CLIENT_IFACE = .*|CLIENT_IFACE = \"${CLIENT_IFACE}\"|" \
        "${PIBOOTH_HOME}/wifi-portal.py"
    ok "scripts adaptés à la configuration"
}

# --- 5. Services systemd ---------------------------------------------------

step_services() {
    step "Services systemd"

    install_file systemd/gallery.service        /etc/systemd/system/gallery.service        root:root 644
    install_file systemd/wifi-portal.service    /etc/systemd/system/wifi-portal.service    root:root 644
    install_file systemd/captive-portal.service /etc/systemd/system/captive-portal.service root:root 644

    sudo sed -i "s|^Environment=GALLERY_PORT=.*|Environment=GALLERY_PORT=${GALLERY_PORT}|" \
        /etc/systemd/system/gallery.service

    sudo systemctl daemon-reload

    # captive-portal écoute sur l'adresse du hotspot : l'étape réseau l'active.
    local services=(gallery wifi-portal)
    for service in "${services[@]}"; do
        sudo systemctl enable --now "${service}.service" >/dev/null 2>&1 || true
    done

    sleep 2
    for service in "${services[@]}"; do
        local state
        state="$(systemctl is-active "${service}.service" || true)"
        if [[ "${state}" == "active" ]]; then
            ok "${service} : ${state}"
        else
            warn "${service} : ${state}"
        fi
    done
}

# --- 6. Réseau : hotspot invités et portail captif -------------------------

step_network() {
    step "Configuration réseau"

    if [[ -z "${HOTSPOT_PASSWORD}" ]]; then
        warn "HOTSPOT_PASSWORD vide : hotspot non configuré"
        info "relancer avec : HOTSPOT_PASSWORD='motdepasse' ./install.sh --only network"
        disable_captive_portal
        return 0
    fi
    if (( ${#HOTSPOT_PASSWORD} < 8 )); then
        fail "HOTSPOT_PASSWORD doit faire au moins 8 caractères (contrainte WPA2)"
    fi

    # Sans épinglage, NetworkManager peut activer une connexion client sur
    # l'interface du hotspot et couper ce dernier.
    local pinned=0
    while IFS=: read -r name _; do
        [[ -n "${name}" ]] || continue
        sudo nmcli connection modify "${name}" connection.interface-name "${CLIENT_IFACE}" \
            2>/dev/null && ((pinned++)) || true
    done < <(nmcli -t -f NAME,TYPE connection show 2>/dev/null | grep ':802-11-wireless$')
    ok "${pinned} connexion(s) client épinglée(s) sur ${CLIENT_IFACE}"

    if [[ ! -d "/sys/class/net/${HOTSPOT_IFACE}" ]]; then
        warn "interface ${HOTSPOT_IFACE} absente : dongle USB non détecté"
        info "le hotspot exige une seconde radio (voir README, section matériel)"
        disable_captive_portal
        return 0
    fi

    if ! iw list 2>/dev/null | grep -q '\* AP$'; then
        warn "aucune radio n'annonce le mode AP — le hotspot risque de ne pas démarrer"
    fi

    sudo nmcli connection delete pibooth-ap >/dev/null 2>&1 || true
    sudo nmcli connection add type wifi ifname "${HOTSPOT_IFACE}" con-name pibooth-ap \
        autoconnect yes \
        ssid "${HOTSPOT_SSID}" \
        connection.interface-name "${HOTSPOT_IFACE}" \
        connection.autoconnect-priority 50 \
        802-11-wireless.mode ap \
        802-11-wireless.band bg \
        802-11-wireless.channel "${HOTSPOT_CHANNEL}" \
        wifi-sec.key-mgmt wpa-psk \
        wifi-sec.proto rsn \
        wifi-sec.pairwise ccmp \
        wifi-sec.group ccmp \
        wifi-sec.psk "${HOTSPOT_PASSWORD}" \
        ipv4.method shared \
        ipv4.addresses "${HOTSPOT_ADDRESS}/24" \
        ipv6.method ignore >/dev/null
    ok "connexion pibooth-ap créée (SSID ${HOTSPOT_SSID}, canal ${HOTSPOT_CHANNEL})"

    # Portail captif : tout domaine résout vers le Pi, toute requête HTTP est
    # redirigée vers la galerie. dnsmasq est celui que NetworkManager lance déjà.
    sudo install -D -o root -g root -m 644 /dev/stdin \
        /etc/NetworkManager/dnsmasq-shared.d/captive-portal.conf << CONF
# Resolve every domain to the Pi so guest connectivity checks land on our redirector.
address=/#/${HOTSPOT_ADDRESS}

# RFC 8910: advertise the portal URL directly in the DHCP lease, so recent
# clients open it without waiting for their connectivity probe to fail.
dhcp-option=114,http://${HOTSPOT_ADDRESS}/
CONF
    ok "/etc/NetworkManager/dnsmasq-shared.d/captive-portal.conf"

    reserve_printer_address

    if [[ "${HOTSPOT_SHARE_INTERNET}" == "no" ]]; then
        install_file network/50-pibooth-ap-local \
            /etc/NetworkManager/dispatcher.d/50-pibooth-ap-local root:root 755
        sudo sed -i "s|^INTERFACE_NAME=.*|INTERFACE_NAME=${HOTSPOT_IFACE}|" \
            /etc/NetworkManager/dispatcher.d/50-pibooth-ap-local 2>/dev/null || true
        ok "accès invités restreint au réseau local (pas d'internet partagé)"
    else
        sudo rm -f /etc/NetworkManager/dispatcher.d/50-pibooth-ap-local
        ok "accès internet partagé avec les invités (NAT)"
    fi

    sudo nmcli connection up pibooth-ap >/dev/null 2>&1 \
        && ok "hotspot actif sur ${HOTSPOT_ADDRESS}" \
        || warn "hotspot non démarré — vérifier 'journalctl -u NetworkManager'"

    sudo systemctl enable captive-portal.service >/dev/null 2>&1 || true
    sudo systemctl restart captive-portal.service 2>/dev/null || true
}

# Une adresse fixe pour l'imprimante : CUPS la joint par son adresse IP.
reserve_printer_address() {
    local conf=/etc/NetworkManager/dnsmasq-shared.d/pibooth-printer.conf
    if [[ -z "${PRINTER_DHCP_NAME}" ]]; then
        sudo rm -f "${conf}"
        return 0
    fi
    echo "dhcp-host=${PRINTER_DHCP_NAME},${PRINTER_ADDRESS}" \
        | sudo install -D -o root -g root -m 644 /dev/stdin "${conf}"
    ok "adresse ${PRINTER_ADDRESS} réservée aux imprimantes ${PRINTER_DHCP_NAME}"
}

# Sans hotspot, l'adresse du portail n'existe pas et le service redémarrerait
# en boucle.
disable_captive_portal() {
    sudo systemctl disable --now captive-portal.service >/dev/null 2>&1 || true
    info "portail captif désactivé tant que le hotspot n'est pas configuré"
}

# --- 7. Imprimante ----------------------------------------------------------

step_printer() {
    step "Imprimante"

    if [[ -z "${PRINTER_DHCP_NAME}" ]]; then
        warn "PRINTER_DHCP_NAME vide : aucune imprimante déclarée"
        return 0
    fi

    # La SELPHY ne répond pas à 'lpadmin -m everywhere' ; driverless, lui, lit
    # ses attributs et en tire un pilote IPP sans pilote constructeur.
    local uri="ipp://${PRINTER_ADDRESS}/ipp/print" ppd
    ppd="$(mktemp)"
    if ! timeout 30 driverless "${uri}" > "${ppd}" 2>/dev/null || [[ ! -s "${ppd}" ]]; then
        rm -f "${ppd}"
        warn "imprimante injoignable sur ${uri}"
        info "l'allumer (elle rejoint le hotspot et prend ${PRINTER_ADDRESS}), puis : ./install.sh --only printer"
        return 0
    fi
    sudo lpadmin -p "${PRINTER_QUEUE}" -E -v "${uri}" -P "${ppd}" 2>/dev/null
    rm -f "${ppd}"
    # Le sans-bord passe aussi par printer_options de pibooth.cfg : CUPS
    # n'envoie pas les marges nulles de ce format à l'imprimante.
    sudo lpadmin -p "${PRINTER_QUEUE}" -o PageSize=Postcard.Borderless
    sudo lpadmin -d "${PRINTER_QUEUE}"
    ok "imprimante ${PRINTER_QUEUE} déclarée sur ${uri}, par défaut"
}

# --- 8. Affichage ----------------------------------------------------------

step_display() {
    step "Affichage"

    if [[ "${BOARD}" == "raspberry-pi" ]]; then
        configure_firmware_display
    else
        install_light_desktop
        warn "rotation de l'écran à configurer à la main sur ${BOARD} (xrandr)"
    fi
}

# Les images serveur des autres cartes n'ont pas de session graphique, or
# pibooth démarre avec elle : LightDM ouvre une session Openbox automatiquement.
install_light_desktop() {
    if [[ -f /etc/X11/default-display-manager ]] \
        && [[ "$(cat /etc/X11/default-display-manager)" != */lightdm ]]; then
        ok "gestionnaire d'affichage déjà présent : $(cat /etc/X11/default-display-manager)"
        return 0
    fi

    local packages=(
        xserver-xorg-core xserver-xorg-input-libinput xserver-xorg-video-fbdev
        x11-xserver-utils xinit lightdm lightdm-gtk-greeter openbox python3-xdg
    )
    info "installation d'un bureau léger (Xorg, LightDM, Openbox)…"
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends "${packages[@]}"

    # python3-xdg permet à Openbox de lancer ~/.config/autostart/pibooth.desktop.
    sudo install -D -o root -g root -m 644 /dev/stdin /etc/lightdm/lightdm.conf.d/50-pibooth.conf << CONF
[Seat:*]
autologin-user=${PIBOOTH_USER}
autologin-session=openbox
user-session=openbox
CONF
    ok "session Openbox ouverte automatiquement pour ${PIBOOTH_USER}"
}

# Sur Raspberry Pi, la rotation et la mémoire vidéo se règlent dans le firmware.
configure_firmware_display() {
    local config_file=/boot/firmware/config.txt
    [[ -f "${config_file}" ]] || config_file=/boot/config.txt
    [[ -f "${config_file}" ]] || { warn "config.txt introuvable"; return 0; }

    # L'écran du photobooth est monté à l'envers : rotation par le firmware.
    if grep -q "^display_hdmi_rotate=" "${config_file}"; then
        sudo sed -i "s/^display_hdmi_rotate=.*/display_hdmi_rotate=${DISPLAY_ROTATE}/" "${config_file}"
    else
        echo "display_hdmi_rotate=${DISPLAY_ROTATE}" | sudo tee -a "${config_file}" >/dev/null
    fi
    ok "rotation écran : ${DISPLAY_ROTATE} (redémarrage requis)"

    # Mémoire GPU suffisante pour l'aperçu caméra plein écran.
    if ! grep -q "^gpu_mem=" "${config_file}"; then
        echo "gpu_mem=128" | sudo tee -a "${config_file}" >/dev/null
    fi
    ok "gpu_mem=128"
}

# --- 9. Démarrage automatique ---------------------------------------------

step_autostart() {
    step "Démarrage automatique"

    local autostart_dir="${PIBOOTH_HOME}/.config/autostart"
    sudo -u "${PIBOOTH_USER}" mkdir -p "${autostart_dir}"
    install_file autostart/pibooth.desktop "${autostart_dir}/pibooth.desktop" \
        "${PIBOOTH_USER}:${PIBOOTH_USER}" 644

    info "pibooth démarre avec la session graphique via start-pibooth.sh"
}

# --- 10. Configuration pibooth ---------------------------------------------

step_config() {
    step "Configuration pibooth"

    local config_dir="${PIBOOTH_HOME}/.config/pibooth"
    local config_file="${config_dir}/pibooth.cfg"

    sudo -u "${PIBOOTH_USER}" mkdir -p "${config_dir}"

    if [[ -f "${config_file}" ]]; then
        warn "configuration existante conservée : ${config_file}"
        info "modèle de référence : ${FILES_DIR}/pibooth.cfg.template"
    else
        install_file pibooth.cfg.template "${config_file}" \
            "${PIBOOTH_USER}:${PIBOOTH_USER}" 600
        warn "identifiants Nextcloud et pCloud à renseigner (champs A_RENSEIGNER)"
        info "éditer avec : nano ${config_file}"
    fi

    configure_touch_flip "${config_file}"
    configure_capture_button "${config_file}"

    local pictures_dir="${PIBOOTH_HOME}/Pictures/pibooth"
    sudo -u "${PIBOOTH_USER}" mkdir -p "${pictures_dir}"
    ok "répertoire photos : ${pictures_dir}"
}

# Le firmware du Raspberry Pi retourne l'affichage (display_hdmi_rotate=2) mais
# SDL lit le tactile en coordonnées brutes : pibooth doit le retourner aussi.
# Une valeur déjà présente est conservée, elle a pu être réglée à la main.
configure_touch_flip() {
    local config_file="$1"
    local touch_flip=False
    [[ "${BOARD}" == "raspberry-pi" && "${DISPLAY_ROTATE}" == "2" ]] && touch_flip=True

    if grep -q "^touch_flip" "${config_file}"; then
        ok "retournement tactile déjà réglé : $(grep "^touch_flip" "${config_file}")"
        return 0
    fi
    sudo sed -i "/^\[WINDOW\]/a touch_flip = ${touch_flip}" "${config_file}"
    ok "retournement tactile : touch_flip = ${touch_flip}"
}

# Le modèle reprend le câblage du Pi, où le bouton de capture est sur la broche
# 11. Sur le VIM4 cette broche est une alimentation (VDD1V8) : le bouton passe
# sur la broche 22. Une autre valeur, réglée à la main, est conservée.
configure_capture_button() {
    local config_file="$1"
    [[ "${BOARD}" == "khadas-vim4" ]] || return 0

    if grep -q "^picture_btn_pin = 11$" "${config_file}"; then
        sudo sed -i "s/^picture_btn_pin = 11$/picture_btn_pin = 22/" "${config_file}"
        ok "bouton de capture : broche 11 (alimentation sur VIM4) → 22"
    fi
}

# --- Résumé ----------------------------------------------------------------

print_summary() {
    local ip
    ip="$(hostname -I | awk '{print $1}')"

    cat << SUMMARY

${BOLD}${GREEN}Installation terminée.${RESET}

  Galerie locale      http://${ip}:${GALLERY_PORT}/
  Portail Wi-Fi       http://${ip}:${WIFI_PORTAL_PORT}/
  Hotspot invités     ${HOTSPOT_SSID} → http://${HOTSPOT_ADDRESS}:${GALLERY_PORT}/

${BOLD}À faire avant utilisation :${RESET}

  1. Renseigner les identifiants Nextcloud / pCloud :
       nano ${PIBOOTH_HOME}/.config/pibooth/pibooth.cfg
  2. Configurer l'imprimante si présente :
       ${VENV_DIR}/bin/pibooth-printcfg
  3. Redémarrer pour appliquer la rotation d'écran :
       sudo reboot

${BOLD}Vérification après redémarrage :${RESET}

       ${VENV_DIR}/bin/pibooth-diag
       systemctl status gallery wifi-portal captive-portal

SUMMARY
}

# --- Point d'entrée --------------------------------------------------------

main() {
    local only="" skip=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --only)        only="$2"; shift 2 ;;
            --skip-network) skip="network"; shift ;;
            --help|-h)
                sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'
                exit 0 ;;
            *) fail "option inconnue : $1 (voir --help)" ;;
        esac
    done

    check_prerequisites

    for step_name in "${STEPS[@]}"; do
        [[ -n "${only}" && "${only}" != "${step_name}" ]] && continue
        [[ "${skip}" == "${step_name}" ]] && { warn "étape ${step_name} ignorée"; continue; }
        "step_${step_name}"
    done

    [[ -z "${only}" ]] && print_summary
    return 0
}

main "$@"
