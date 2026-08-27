#!/usr/bin/env python3
"""Display network info, optionally edit pibooth settings, then exit.

A fullscreen window shows the active WiFi SSID and IP address. The operator
can either touch the screen to continue (pibooth launches) or tap the
"Paramètres" button to edit a small subset of pibooth settings (directory,
footer texts, text color, Nextcloud album name) in place in pibooth.cfg.
"""

import re
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

CONFIG_PATH = Path.home() / ".config" / "pibooth" / "pibooth.cfg"

EDITABLE_FIELDS = [
    {"section": "GENERAL", "key": "directory", "label": "Dossier des photos", "type": "text"},
    {"section": "PICTURE", "key": "footer_text1", "label": "Texte pied 1", "type": "quoted"},
    {"section": "PICTURE", "key": "footer_text2", "label": "Texte pied 2", "type": "quoted"},
    {"section": "PICTURE", "key": "text_colors", "label": "Couleur des textes", "type": "color"},
    {"section": "NEXTCLOUD", "key": "album_name", "label": "Nom de l'album Nextcloud", "type": "text"},
]


def get_wifi_ssid() -> str:
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show", "--active"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            name, _, ctype = line.partition(":")
            if ctype == "802-11-wireless":
                return name
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return "Non connecté"


def get_ip_address() -> str:
    try:
        result = subprocess.run(
            ["hostname", "-I"], capture_output=True, text=True, timeout=5,
        )
        addresses = result.stdout.split()
        if addresses:
            return addresses[0]
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return "Adresse IP indisponible"


def parse_color(raw: str) -> tuple[int, int, int]:
    nums = re.findall(r"\d+", raw)
    if len(nums) >= 3:
        return tuple(int(n) for n in nums[:3])
    return (255, 255, 255)


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb


def _build_palette_image(width: int, height: int, value: float):
    """Generate a hue×saturation palette image at the given brightness (0..1)."""
    import colorsys
    from PIL import Image
    img = Image.new("RGB", (width, height))
    pixels = img.load()
    for x in range(width):
        h = x / max(1, width - 1)
        for y in range(height):
            s = 1.0 - (y / max(1, height - 1))
            r, g, b = colorsys.hsv_to_rgb(h, s, value)
            pixels[x, y] = (int(r * 255), int(g * 255), int(b * 255))
    return img


def pick_color_touch(parent: tk.Misc, initial: tuple[int, int, int]) -> tuple[int, int, int] | None:
    """Touch-friendly color picker with a HSV palette and a brightness slider."""
    from PIL import ImageTk

    dlg = tk.Toplevel(parent)
    dlg.title("Couleur")
    dlg.configure(bg="#1e1e1e")
    dlg.attributes("-fullscreen", True)
    dlg.transient(parent)
    dlg.grab_set()

    state = {"rgb": tuple(initial), "result": None, "value": 1.0,
             "palette_img": None, "tk_img": None}

    tk.Label(dlg, text="Choisir la couleur", font=("DejaVu Sans", 36, "bold"),
             fg="#9ad1ff", bg="#1e1e1e").pack(pady=(30, 15))

    top = tk.Frame(dlg, bg="#1e1e1e")
    top.pack(pady=(0, 15))

    preview = tk.Label(top, text="", bg=rgb_to_hex(state["rgb"]),
                       width=8, height=3, relief="solid", borderwidth=2)
    preview.pack(side="left", padx=20)

    value_label = tk.Label(top, text=f"RGB {state['rgb'][0]}, {state['rgb'][1]}, {state['rgb'][2]}",
                           font=("DejaVu Sans Mono", 26, "bold"),
                           fg="#ffffff", bg="#1e1e1e")
    value_label.pack(side="left", padx=20)

    PALETTE_W, PALETTE_H = 900, 360

    canvas = tk.Canvas(dlg, width=PALETTE_W, height=PALETTE_H,
                       bg="#1e1e1e", highlightthickness=0, cursor="cross")
    canvas.pack(pady=(0, 15))

    def refresh_preview():
        preview.configure(bg=rgb_to_hex(state["rgb"]))
        value_label.configure(text=f"RGB {state['rgb'][0]}, {state['rgb'][1]}, {state['rgb'][2]}")

    def repaint_palette():
        img = _build_palette_image(PALETTE_W, PALETTE_H, state["value"])
        state["palette_img"] = img
        state["tk_img"] = ImageTk.PhotoImage(img)
        canvas.delete("palette")
        canvas.create_image(0, 0, image=state["tk_img"], anchor="nw", tags="palette")

    def on_palette_tap(event):
        x = max(0, min(PALETTE_W - 1, event.x))
        y = max(0, min(PALETTE_H - 1, event.y))
        if state["palette_img"] is not None:
            state["rgb"] = state["palette_img"].getpixel((x, y))
            refresh_preview()

    canvas.bind("<Button-1>", on_palette_tap)
    canvas.bind("<B1-Motion>", on_palette_tap)

    bright_row = tk.Frame(dlg, bg="#1e1e1e")
    bright_row.pack(fill="x", padx=80, pady=(0, 10))
    tk.Label(bright_row, text="Luminosité", font=("DejaVu Sans", 24, "bold"),
             fg="#ffffff", bg="#1e1e1e", width=12, anchor="w").pack(side="left")

    def on_brightness(v):
        state["value"] = int(float(v)) / 100
        repaint_palette()

    tk.Scale(bright_row, from_=10, to=100, orient="horizontal",
             length=600, sliderlength=80, width=50, showvalue=False,
             bg="#1e1e1e", fg="#ffffff", troughcolor="#444444",
             highlightthickness=0, command=on_brightness).pack(side="left", fill="x", expand=True)

    btns = tk.Frame(dlg, bg="#1e1e1e")
    btns.pack(side="bottom", pady=30)

    def cancel():
        state["result"] = None
        dlg.destroy()

    def confirm():
        state["result"] = state["rgb"]
        dlg.destroy()

    tk.Button(btns, text="Annuler", font=("DejaVu Sans", 26),
              command=cancel, padx=40, pady=18, bg="#444444", fg="#ffffff",
              activebackground="#666666", activeforeground="#ffffff",
              borderwidth=0).pack(side="left", padx=20)
    tk.Button(btns, text="Valider", font=("DejaVu Sans", 26, "bold"),
              command=confirm, padx=40, pady=18, bg="#2d6cdf", fg="#ffffff",
              activebackground="#1f4fa8", activeforeground="#ffffff",
              borderwidth=0).pack(side="left", padx=20)

    repaint_palette()
    parent.wait_window(dlg)
    return state["result"]


class ConfigFile:
    """In-place editor preserving comments, blank lines, and unrelated values."""

    def __init__(self, path: Path):
        self.path = path
        self.lines = path.read_text(encoding="utf-8").splitlines()

    def _section_bounds(self, section: str) -> tuple[int, int]:
        header = f"[{section}]"
        start = next((i for i, l in enumerate(self.lines) if l.strip() == header), -1)
        if start == -1:
            raise KeyError(f"Section [{section}] introuvable")
        end = len(self.lines)
        for i in range(start + 1, len(self.lines)):
            if self.lines[i].lstrip().startswith("[") and self.lines[i].rstrip().endswith("]"):
                end = i
                break
        return start, end

    def get(self, section: str, key: str) -> str:
        start, end = self._section_bounds(section)
        pattern = re.compile(rf"^\s*{re.escape(key)}\s*=\s*(.*)$")
        for i in range(start + 1, end):
            m = pattern.match(self.lines[i])
            if m:
                return m.group(1)
        return ""

    def set(self, section: str, key: str, raw_value: str) -> None:
        start, end = self._section_bounds(section)
        pattern = re.compile(rf"^(\s*{re.escape(key)}\s*=\s*).*$")
        for i in range(start + 1, end):
            m = pattern.match(self.lines[i])
            if m:
                self.lines[i] = f"{m.group(1)}{raw_value}"
                return
        insert_at = end
        while insert_at > start + 1 and self.lines[insert_at - 1].strip() == "":
            insert_at -= 1
        self.lines.insert(insert_at, f"{key} = {raw_value}")

    def save(self) -> None:
        self.path.write_text("\n".join(self.lines) + "\n", encoding="utf-8")


def open_settings_window(parent: tk.Tk) -> None:
    try:
        cfg = ConfigFile(CONFIG_PATH)
    except (OSError, KeyError) as exc:
        messagebox.showerror("Erreur", f"Impossible de lire la configuration:\n{exc}")
        return

    win = tk.Toplevel(parent)
    win.title("Paramètres pibooth")
    win.configure(bg="#1e1e1e")
    win.attributes("-fullscreen", True)
    win.config(cursor="arrow")

    container = tk.Frame(win, bg="#1e1e1e", padx=40, pady=30)
    container.pack(expand=True, fill="both")

    tk.Label(
        container, text="Paramètres pibooth",
        font=("DejaVu Sans", 36, "bold"), fg="#9ad1ff", bg="#1e1e1e",
    ).pack(pady=(0, 25))

    entries: dict[str, dict] = {}

    for field in EDITABLE_FIELDS:
        row = tk.Frame(container, bg="#1e1e1e")
        row.pack(fill="x", pady=8)

        tk.Label(
            row, text=field["label"], font=("DejaVu Sans", 22),
            fg="#ffffff", bg="#1e1e1e", width=22, anchor="w",
        ).pack(side="left")

        raw = cfg.get(field["section"], field["key"])
        state = {"field": field, "raw": raw}

        if field["type"] == "color":
            rgb = parse_color(raw)
            state["rgb"] = rgb
            swatch = tk.Label(
                row, text=f"  RGB {rgb[0]}, {rgb[1]}, {rgb[2]}  ",
                font=("DejaVu Sans Mono", 22), bg=rgb_to_hex(rgb),
                fg="#000000" if sum(rgb) > 380 else "#ffffff",
                padx=20, pady=8,
            )
            swatch.pack(side="left", fill="x", expand=True, padx=(0, 10))
            state["widget"] = swatch

            def pick_color(s=state):
                new_rgb = pick_color_touch(win, s["rgb"])
                if new_rgb is not None:
                    s["rgb"] = new_rgb
                    s["widget"].configure(
                        text=f"  RGB {new_rgb[0]}, {new_rgb[1]}, {new_rgb[2]}  ",
                        bg=rgb_to_hex(new_rgb),
                        fg="#000000" if sum(new_rgb) > 380 else "#ffffff",
                    )

            tk.Button(
                row, text="Choisir…", font=("DejaVu Sans", 18),
                command=pick_color, padx=15, pady=6,
            ).pack(side="left")
        else:
            value = raw
            if field["type"] == "quoted":
                value = raw.strip()
                if len(value) >= 2 and value[0] == value[-1] == '"':
                    value = value[1:-1]
            entry = tk.Entry(row, font=("DejaVu Sans", 22), bg="#2e2e2e", fg="#ffffff",
                             insertbackground="#ffffff")
            entry.insert(0, value)
            entry.pack(side="left", fill="x", expand=True)
            state["widget"] = entry

        entries[f"{field['section']}.{field['key']}"] = state

    buttons = tk.Frame(container, bg="#1e1e1e")
    buttons.pack(pady=(40, 0))

    def save_and_close():
        try:
            for state in entries.values():
                field = state["field"]
                if field["type"] == "color":
                    r, g, b = state["rgb"]
                    cfg.set(field["section"], field["key"], f"({r}, {g}, {b})")
                elif field["type"] == "quoted":
                    text = state["widget"].get()
                    cfg.set(field["section"], field["key"], f'"{text}"')
                else:
                    cfg.set(field["section"], field["key"], state["widget"].get())
            cfg.save()
        except OSError as exc:
            messagebox.showerror("Erreur", f"Échec de l'enregistrement:\n{exc}", parent=win)
            return
        win.destroy()
        parent.destroy()

    def cancel():
        win.destroy()

    tk.Button(
        buttons, text="Annuler", font=("DejaVu Sans", 22),
        command=cancel, padx=30, pady=12,
    ).pack(side="left", padx=10)

    tk.Button(
        buttons, text="Enregistrer et lancer pibooth", font=("DejaVu Sans", 22, "bold"),
        command=save_and_close, padx=30, pady=12, bg="#2d6cdf", fg="#ffffff",
        activebackground="#1f4fa8", activeforeground="#ffffff",
    ).pack(side="left", padx=10)


def build_window(ssid: str, ip: str) -> tk.Tk:
    root = tk.Tk()
    root.title("Informations réseau")
    root.configure(bg="#1e1e1e")
    root.attributes("-fullscreen", True)
    root.config(cursor="arrow")

    info = tk.Frame(root, bg="#1e1e1e")
    info.pack(expand=True, fill="both", pady=(80, 0))

    def add_label(parent, text, font, fg, pady):
        tk.Label(parent, text=text, font=font, fg=fg, bg="#1e1e1e").pack(pady=pady)

    add_label(info, "Réseau Wi-Fi", ("DejaVu Sans", 48, "bold"), "#9ad1ff", (0, 10))
    add_label(info, ssid, ("DejaVu Sans", 72, "bold"), "#ffffff", (0, 50))
    add_label(info, "Adresse IP", ("DejaVu Sans", 48, "bold"), "#9ad1ff", (0, 10))
    add_label(info, ip, ("DejaVu Sans Mono", 72, "bold"), "#ffffff", (0, 50))

    def launch_pibooth():
        root.destroy()

    def open_settings():
        root.config(cursor="arrow")
        try:
            open_settings_window(root)
        except Exception as exc:
            messagebox.showerror("Erreur", str(exc), parent=root)

    action_bar = tk.Frame(root, bg="#1e1e1e")
    action_bar.pack(side="bottom", fill="x", pady=(0, 80))

    tk.Button(
        action_bar, text="Paramètres", font=("DejaVu Sans", 32, "bold"),
        bg="#444444", fg="#ffffff",
        activebackground="#666666", activeforeground="#ffffff",
        command=open_settings, padx=40, pady=20, borderwidth=0,
    ).pack(side="left", expand=True, fill="x", padx=(80, 20), ipady=15)

    tk.Button(
        action_bar, text="Continuer ▶", font=("DejaVu Sans", 32, "bold"),
        bg="#2d6cdf", fg="#ffffff",
        activebackground="#1f4fa8", activeforeground="#ffffff",
        command=launch_pibooth, padx=40, pady=20, borderwidth=0,
    ).pack(side="left", expand=True, fill="x", padx=(20, 80), ipady=15)

    root.bind("<Key>", lambda e: launch_pibooth())
    root.focus_force()
    return root


def main() -> None:
    ssid = get_wifi_ssid()
    ip = get_ip_address()
    window = build_window(ssid, ip)
    window.mainloop()


if __name__ == "__main__":
    main()
