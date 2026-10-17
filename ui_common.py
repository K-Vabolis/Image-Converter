"""Colors, theme, helpers and small widgets for Image Converter."""
import base64
import json
import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

BG = "#17171c"
PANEL = "#202027"
FIELD = "#2a2a33"
BORDER = "#363641"
FG = "#e8e8ee"
MUTED = "#9a9aa8"
ACCENT = "#7c6cf0"
ACCENT_HI = "#9184ff"
BTN = "#34343f"
BTN_HI = "#454552"
OK = "#4cd18a"
ERR = "#ff6b6b"
WARN = "#f5c451"

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".image_converter.json")


def resource_path(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def fmt_size(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return "%d B" % n if unit == "B" else "%.1f %s" % (n, unit)
        n /= 1024


def open_folder(path):
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # noqa
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as ex:
        messagebox.showerror("Cannot open folder", str(ex))


def unique_path(path, used):
    """Avoid overwriting files made earlier in the same batch."""
    base, ext = os.path.splitext(path)
    cand, n = path, 2
    while cand.lower() in used:
        cand = "%s_%d%s" % (base, n, ext)
        n += 1
    used.add(cand.lower())
    return cand


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


def setup_theme(root):
    scale = 1.0
    try:
        scale = max(1.0, root.winfo_fpixels("1i") / 96.0)
    except Exception:
        pass
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(".", background=BG, foreground=FG, fieldbackground=FIELD, bordercolor=BORDER,
                lightcolor=BORDER, darkcolor=BORDER, troughcolor=FIELD, focuscolor=BG,
                font=("Segoe UI", 10))
    s.configure("TFrame", background=BG)
    s.configure("Panel.TFrame", background=PANEL)
    s.configure("TLabel", background=BG, foreground=FG)
    s.configure("Muted.TLabel", foreground=MUTED)
    s.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
    s.configure("Sub.TLabel", foreground=MUTED, font=("Segoe UI", 9))
    s.configure("Hint.TLabel", foreground=MUTED, font=("Segoe UI", 9))
    s.configure("Heading.TLabel", foreground=FG, font=("Segoe UI", 10, "bold"))
    s.configure("TEntry", fieldbackground=FIELD, foreground=FG, insertcolor=FG, padding=6,
                bordercolor=BORDER)
    s.map("TEntry", bordercolor=[("focus", ACCENT)])
    s.configure("TCombobox", fieldbackground=FIELD, background=BTN, foreground=FG, arrowcolor=FG,
                padding=5, bordercolor=BORDER)
    s.map("TCombobox", fieldbackground=[("readonly", FIELD)], foreground=[("readonly", FG)],
          selectbackground=[("readonly", FIELD)], selectforeground=[("readonly", FG)])
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", FG)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)

    s.configure("TButton", background=BTN, foreground=FG, padding=(14, 7), borderwidth=0, relief="flat")
    s.map("TButton", background=[("disabled", "#2a2a31"), ("active", BTN_HI)],
          foreground=[("disabled", "#6b6b78")])
    s.configure("Accent.TButton", background=ACCENT, foreground="white", font=("Segoe UI", 10, "bold"))
    s.map("Accent.TButton", background=[("disabled", "#443e7a"), ("active", ACCENT_HI)],
          foreground=[("disabled", "#9b97c0")])
    s.configure("Danger.TButton", background="#6b2b33", foreground="white")
    s.map("Danger.TButton", background=[("disabled", "#3a2a2d"), ("active", "#8a3640")])
    s.configure("Small.TButton", padding=(10, 4), font=("Segoe UI", 9))
    s.configure("Link.TButton", background=BG, foreground=ACCENT_HI, padding=(6, 2), font=("Segoe UI", 9))
    s.map("Link.TButton", background=[("active", BG)], foreground=[("active", "white")])

    for w in ("TCheckbutton", "TRadiobutton"):
        s.configure(w, background=BG, foreground=FG, indicatorbackground=FIELD,
                    indicatorforeground=FG, bordercolor=BORDER, lightcolor=FIELD, darkcolor=FIELD)
        s.map(w, background=[("active", BG)],
              indicatorbackground=[("selected", ACCENT), ("!selected", FIELD)],
              indicatorforeground=[("selected", "white"), ("!selected", FIELD)])

    s.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(0, 0, 0, 0),
                bordercolor=BG, lightcolor=BG, darkcolor=BG)
    s.configure("TNotebook.Tab", background=PANEL, foreground=MUTED, padding=(22, 10),
                font=("Segoe UI", 10, "bold"), borderwidth=0, bordercolor=PANEL,
                lightcolor=PANEL, darkcolor=PANEL)
    s.map("TNotebook.Tab",
          background=[("selected", BG), ("active", BTN)],
          foreground=[("selected", FG)],
          bordercolor=[("selected", BG)],
          lightcolor=[("selected", ACCENT)],
          darkcolor=[("selected", BG)])

    s.configure("Treeview", background=FIELD, fieldbackground=FIELD, foreground=FG,
                rowheight=int(26 * scale), borderwidth=0)
    s.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "white")])
    s.configure("Treeview.Heading", background=PANEL, foreground=MUTED, relief="flat", padding=6,
                font=("Segoe UI", 9, "bold"))
    s.map("Treeview.Heading", background=[("active", PANEL)])

    s.configure("Vertical.TScrollbar", background=BTN, troughcolor=BG, arrowcolor=MUTED, borderwidth=0)
    s.configure("Horizontal.TScrollbar", background=BTN, troughcolor=BG, arrowcolor=MUTED, borderwidth=0)
    s.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=FIELD, borderwidth=0, thickness=10)
    s.configure("TPanedwindow", background=BG)
    s.configure("Sash", background=BG)


class PathRow:
    """Label + entry + Browse button (+ optional extra button) on one grid row."""

    def __init__(self, parent, row, label, var, browse, extra=None, label_width=13):
        ttk.Label(parent, text=label, style="Muted.TLabel", width=label_width).grid(
            row=row, column=0, sticky="w", pady=3)
        self.entry = ttk.Entry(parent, textvariable=var)
        self.entry.grid(row=row, column=1, sticky="ew", pady=3, padx=(0, 8))
        ttk.Button(parent, text="Browse…", command=browse).grid(row=row, column=2, pady=3)
        if extra is not None:
            extra.grid(row=row, column=3, padx=(8, 0), pady=3)


class ImagePreview(ttk.Frame):
    """Right-hand preview pane: an image or text, a caption and an optional action button."""

    def __init__(self, parent, empty_text, action_text=None, action_cmd=None):
        super().__init__(parent)
        self.empty_text = empty_text
        self.photo = None
        ttk.Label(self, text="Preview", style="Muted.TLabel").pack(anchor="w", pady=(0, 4))
        self.stage = tk.Frame(self, bg=FIELD, highlightthickness=0)
        self.stage.pack(fill="both", expand=True)
        self.image_lbl = tk.Label(self.stage, bg=FIELD, fg=MUTED, justify="center",
                                  font=("Segoe UI", 10), wraplength=300)
        self.image_lbl.place(relx=0.5, rely=0.5, anchor="center")
        self.text = tk.Text(self.stage, bg=FIELD, fg=FG, relief="flat", wrap="none", state="disabled",
                            font=("Consolas", 9), padx=8, pady=6, highlightthickness=0, borderwidth=0)
        self.tscroll = ttk.Scrollbar(self.stage, command=self.text.yview)
        self.text.config(yscrollcommand=self.tscroll.set)
        bottom = ttk.Frame(self)
        bottom.pack(fill="x", pady=(6, 0))
        self.caption = ttk.Label(bottom, text="", style="Hint.TLabel")
        self.caption.pack(side="left")
        self.action = None
        if action_text:
            self.action = ttk.Button(bottom, text=action_text, style="Small.TButton", command=action_cmd,
                                     state="disabled")
            self.action.pack(side="right")
        self.clear()

    def box(self):
        """Largest square the preview stage can show right now."""
        w, h = self.stage.winfo_width(), self.stage.winfo_height()
        if w < 60 or h < 60:
            return 300
        return max(120, min(w, h) - 12)

    def _show_label(self):
        self.text.place_forget()
        self.tscroll.place_forget()
        self.image_lbl.place(relx=0.5, rely=0.5, anchor="center")

    def clear(self, message=None):
        self.photo = None
        self._show_label()
        self.image_lbl.config(image="", text=message or self.empty_text, fg=MUTED)
        self.caption.config(text="")
        if self.action:
            self.action.config(state="disabled")

    def message(self, text, color=MUTED, caption=""):
        self.photo = None
        self._show_label()
        self.image_lbl.config(image="", text=text, fg=color)
        self.caption.config(text=caption)
        if self.action:
            self.action.config(state="disabled")

    def show_png(self, png_bytes, caption="", can_save=True):
        self.photo = tk.PhotoImage(data=base64.b64encode(png_bytes))
        self._show_label()
        self.image_lbl.config(image=self.photo, text="")
        self.caption.config(text=caption)
        if self.action:
            self.action.config(state="normal" if can_save else "disabled")

    def show_text(self, text, caption=""):
        self.photo = None
        self.image_lbl.place_forget()
        self.text.place(relx=0, rely=0, relwidth=1, relheight=1, width=-14)
        self.tscroll.place(relx=1, rely=0, relheight=1, anchor="ne")
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.text.config(state="disabled")
        self.caption.config(text=caption)
        if self.action:
            self.action.config(state="disabled")


class Hint(ttk.Label):
    def __init__(self, parent, text):
        super().__init__(parent, text=text, style="Hint.TLabel")


__all__ = [n for n in dir() if not n.startswith("_")] + ["filedialog", "messagebox", "ttk", "tk"]
