#!/usr/bin/env python3
"""
Image Converter
Turns DDS, TGA and BMP files (and anything Pillow can read) into normal PNG images,
with a live preview. Plain Python + Tkinter, no extra packages needed.
"""
import os
import queue
import sys
import threading
import traceback

import image_core
import ui_common as ui
from ui_common import (ERR, FG, FIELD, MUTED, OK, WARN, ImagePreview, PathRow, filedialog, fmt_size,
                       messagebox, open_folder, tk, ttk, unique_path)

APP_NAME = "Image Converter"
VERSION = "1.0"
EXTENSIONS = (".dds", ".tga", ".bmp", ".tif", ".tiff", ".webp", ".psd", ".ico")
HINT = "Add some images to begin."


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("%s v%s" % (APP_NAME, VERSION))
        self.minsize(820, 560)
        self.configure(bg=ui.BG)
        try:
            self.iconbitmap(ui.resource_path("icon.ico"))
        except Exception:
            pass
        self.cfg = ui.load_config()
        self.geometry(self.cfg.get("geometry", "980x680"))
        self.q = queue.Queue()
        self.busy = False
        self.files = []
        self.gen = 0
        self.preview_job = None
        self.log_visible = False
        self.out_dir = tk.StringVar(value=self.cfg.get("out", ""))
        self.open_when_done = tk.BooleanVar(value=self.cfg.get("open", False))

        ui.setup_theme(self)
        self.build_header()
        self.build_status_bar()
        self.build_body()
        self.bind("<Control-o>", lambda e: self.add_files())
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(60, self.poll)

    def build_header(self):
        head = ttk.Frame(self)
        head.pack(fill="x", padx=18, pady=(14, 8))
        ttk.Label(head, text=APP_NAME, style="Title.TLabel").pack(side="left")
        ttk.Label(head, text="  v%s" % VERSION, style="Sub.TLabel").pack(side="left", pady=(10, 0))
        ttk.Label(head, text="DDS  \u2022  TGA  \u2022  BMP  \u2192  PNG", style="Sub.TLabel").pack(
            side="right", pady=(10, 0))

    def build_status_bar(self):
        bar = ttk.Frame(self, style="Panel.TFrame")
        bar.pack(side="bottom", fill="x")
        self.status_lbl = tk.Label(bar, text="Ready.", bg=ui.PANEL, fg=MUTED, anchor="w",
                                   font=("Segoe UI", 9), padx=18, pady=7)
        self.status_lbl.pack(side="left", fill="x", expand=True)
        self.log_btn = ttk.Button(bar, text="Show log", style="Link.TButton", command=self.toggle_log)
        self.log_btn.pack(side="right", padx=(0, 12))

    def build_body(self):
        self.body = ttk.Frame(self)
        self.body.pack(fill="both", expand=True, padx=18, pady=(0, 10))

        bar = ttk.Frame(self.body)
        bar.pack(fill="x")
        ttk.Button(bar, text="Add images", command=self.add_files).pack(side="left")
        ttk.Button(bar, text="Add folder", command=self.add_folder).pack(side="left", padx=8)
        ttk.Button(bar, text="Remove selected", command=self.remove).pack(side="left")
        ttk.Button(bar, text="Clear", command=self.clear).pack(side="left", padx=8)

        act = ttk.Frame(self.body)
        act.pack(side="bottom", fill="x", pady=(10, 0))
        out = ttk.Frame(self.body)
        out.pack(side="bottom", fill="x", pady=(8, 0))
        out.columnconfigure(1, weight=1)
        open_btn = ttk.Button(out, text="Open folder", command=self.open_out)
        PathRow(out, 0, "Save to", self.out_dir, self.browse_out, open_btn)
        ttk.Label(out, text="Leave empty to put each PNG next to its original file.", style="Hint.TLabel").grid(
            row=1, column=1, sticky="w")

        panes = ttk.PanedWindow(self.body, orient="horizontal")
        panes.pack(fill="both", expand=True, pady=(10, 0))
        left = ttk.Frame(panes)
        self.tree = ttk.Treeview(left, columns=("file", "size", "status"), show="headings", selectmode="extended")
        self.tree.heading("file", text="File", anchor="w")
        self.tree.heading("size", text="Size", anchor="e")
        self.tree.heading("status", text="Status", anchor="w")
        self.tree.column("file", width=240, anchor="w")
        self.tree.column("size", width=70, anchor="e", stretch=False)
        self.tree.column("status", width=80, anchor="w", stretch=False)
        self.tree.tag_configure("ok", foreground=OK)
        self.tree.tag_configure("fail", foreground=ERR)
        vs = ttk.Scrollbar(left, command=self.tree.yview)
        self.tree.config(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.on_select())
        self.tree.bind("<Delete>", lambda e: self.remove())
        self.tree.bind("<Control-a>", lambda e: (self.tree.selection_set(self.tree.get_children()), "break")[1])
        self.empty_lbl = ttk.Label(left, text="Add images or a whole folder.\nEach one becomes a normal PNG.",
                                   style="Muted.TLabel", justify="center", background=FIELD)
        self.empty_lbl.place(relx=0.5, rely=0.45, anchor="center")
        panes.add(left, weight=2)

        self.preview = ImagePreview(panes, "Click an image to see it.", "Save as PNG\u2026", self.save_one)
        panes.add(self.preview, weight=3)

        self.btn_all = ttk.Button(act, text="Convert all to PNG", style="Accent.TButton",
                                  command=lambda: self.convert("all"))
        self.btn_all.pack(side="left")
        self.btn_sel = ttk.Button(act, text="Convert selected", command=lambda: self.convert("sel"))
        self.btn_sel.pack(side="left", padx=8)
        ttk.Checkbutton(act, text="Open folder when done", variable=self.open_when_done).pack(side="right")
        self.lbl = ttk.Label(act, text=HINT, style="Muted.TLabel")
        self.lbl.pack(side="left", padx=14)
        self.update_buttons()

        self.logf = ttk.Frame(self)
        top = ttk.Frame(self.logf)
        top.pack(fill="x", padx=18, pady=(4, 4))
        ttk.Label(top, text="Log", style="Muted.TLabel").pack(side="left")
        ttk.Button(top, text="Clear", style="Small.TButton", command=self.clear_log).pack(side="right")
        box = ttk.Frame(self.logf)
        box.pack(fill="both", expand=True, padx=18, pady=(0, 8))
        self.logbox = tk.Text(box, bg=FIELD, fg=FG, relief="flat", height=7, state="disabled", wrap="word",
                              font=("Consolas", 9), padx=8, pady=6, highlightthickness=0, borderwidth=0)
        sb = ttk.Scrollbar(box, command=self.logbox.yview)
        self.logbox.config(yscrollcommand=sb.set)
        self.logbox.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for tag, color in (("ok", OK), ("err", ERR), ("warn", WARN)):
            self.logbox.tag_config(tag, foreground=color)

    def post(self, fn):
        self.q.put(fn)

    def poll(self):
        try:
            while True:
                self.q.get_nowait()()
        except queue.Empty:
            pass
        except Exception:
            self.log(traceback.format_exc(), "err")
        self.after(60, self.poll)

    def status(self, text, color=MUTED):
        self.status_lbl.config(text=text, fg=color)

    def log(self, text, tag=None):
        self.logbox.config(state="normal")
        self.logbox.insert("end", text + "\n", tag or ())
        self.logbox.see("end")
        self.logbox.config(state="disabled")

    def clear_log(self):
        self.logbox.config(state="normal")
        self.logbox.delete("1.0", "end")
        self.logbox.config(state="disabled")

    def toggle_log(self):
        self.log_visible = not self.log_visible
        if self.log_visible:
            self.logf.pack(side="bottom", fill="x", before=self.body)
            self.log_btn.config(text="Hide log")
        else:
            self.logf.pack_forget()
            self.log_btn.config(text="Show log")

    def report_callback_exception(self, exc, val, tb):
        self.log("".join(traceback.format_exception(exc, val, tb)), "err")
        self.status("Something went wrong. Open the log for details.", ERR)
        if not self.log_visible:
            self.toggle_log()

    def add(self, paths):
        added = 0
        for p in paths:
            p = os.path.normpath(p)
            if p not in self.files and os.path.isfile(p):
                self.files.append(p)
                self.tree.insert("", "end", iid=p, values=(os.path.basename(p), fmt_size(os.path.getsize(p)), "Ready"))
                added += 1
        self.after_list_change()
        return added

    def after_list_change(self):
        if self.files:
            self.empty_lbl.place_forget()
            self.lbl.config(text="%d image(s) ready." % len(self.files))
        else:
            self.empty_lbl.place(relx=0.5, rely=0.45, anchor="center")
            self.lbl.config(text=HINT)
        self.update_buttons()

    def add_files(self):
        patterns = " ".join("*" + e for e in EXTENSIONS)
        self.add(filedialog.askopenfilenames(title="Pick images",
                                             filetypes=[("Images", patterns), ("All files", "*.*")]))

    def add_folder(self):
        d = filedialog.askdirectory(title="Pick a folder with images")
        if d:
            self.add_folder_path(d)

    def add_folder_path(self, d):
        found = []
        for base, _dirs, names in os.walk(d):
            found += [os.path.join(base, n) for n in sorted(names) if n.lower().endswith(EXTENSIONS)]
        n = self.add(found)
        self.status("Added %d image(s) from the folder." % n if n else "No supported images found in that folder.",
                    OK if n else WARN)

    def remove(self):
        for iid in self.tree.selection():
            self.tree.delete(iid)
            if iid in self.files:
                self.files.remove(iid)
        self.preview.clear()
        self.after_list_change()

    def clear(self):
        self.tree.delete(*self.tree.get_children())
        self.files = []
        self.preview.clear()
        self.after_list_change()

    def browse_out(self):
        p = filedialog.askdirectory(title="Select output folder")
        if p:
            self.out_dir.set(os.path.normpath(p))

    def open_out(self):
        d = self.out_dir.get().strip()
        if not d and self.files:
            d = os.path.dirname(self.files[0])
        if d and os.path.isdir(d):
            open_folder(d)
        else:
            messagebox.showinfo("Folder", "Nothing to open yet.")

    def update_buttons(self):
        idle = not self.busy
        self.btn_all.config(state="normal" if (self.files and idle) else "disabled")
        sel = len(self.tree.selection())
        self.btn_sel.config(text="Convert selected (%d)" % sel if sel else "Convert selected",
                            state="normal" if (sel and idle) else "disabled")

    def on_select(self):
        self.update_buttons()
        if self.preview_job:
            self.after_cancel(self.preview_job)
        self.preview_job = self.after(100, self.show_preview)

    def show_preview(self):
        self.preview_job = None
        sel = self.tree.selection()
        if not sel:
            self.preview.clear()
            return
        if len(sel) > 1:
            self.preview.message("%d files selected" % len(sel))
            return
        self.gen += 1
        gen, path, box = self.gen, sel[0], self.preview.box()
        self.preview.message("Loading\u2026")

        def work():
            try:
                with open(path, "rb") as f:
                    data = f.read()
                png, _info = image_core.preview_png(data, box, path)
                cap = "%s  |  %s" % (image_core.describe(data, path), fmt_size(len(data)))
                self.post(lambda: self.preview_done(gen, png, cap, None))
            except Exception as ex:
                self.post(lambda m=str(ex): self.preview_done(gen, None, "", m))

        threading.Thread(target=work, daemon=True).start()

    def preview_done(self, gen, png, caption, err):
        if gen != self.gen:
            return
        if err:
            self.preview.message("Cannot read this image:\n%s" % err, ERR)
        else:
            self.preview.show_png(png, caption)

    def save_one(self):
        sel = self.tree.selection()
        if len(sel) != 1:
            return
        base = os.path.splitext(os.path.basename(sel[0]))[0]
        dest = filedialog.asksaveasfilename(title="Save as PNG", defaultextension=".png",
                                            initialfile=base + ".png", filetypes=[("PNG image", "*.png")],
                                            initialdir=os.path.dirname(sel[0]))
        if not dest:
            return
        try:
            with open(sel[0], "rb") as f:
                png = image_core.to_png(f.read(), sel[0])
            with open(dest, "wb") as f:
                f.write(png)
            self.status("Saved %s" % dest, OK)
        except Exception as ex:
            messagebox.showerror("Cannot save", str(ex))

    def convert(self, scope):
        if self.busy:
            return
        files = list(self.tree.selection()) if scope == "sel" else list(self.files)
        if not files:
            return
        out = self.out_dir.get().strip()
        self.busy = True
        self.update_buttons()
        self.lbl.config(text="Converting\u2026")
        self.status("Converting %d image(s) \u2026" % len(files))

        def work():
            ok = bad = 0
            used = set()
            for f in files:
                outdir = out or os.path.dirname(os.path.abspath(f))
                try:
                    with open(f, "rb") as fh:
                        png = image_core.to_png(fh.read(), f)
                    os.makedirs(outdir, exist_ok=True)
                    dest = unique_path(os.path.join(outdir, os.path.splitext(os.path.basename(f))[0] + ".png"), used)
                    with open(dest, "wb") as fh:
                        fh.write(png)
                    ok += 1
                    self.post(lambda i=f: self.mark(i, "Done", "ok"))
                except Exception as ex:
                    bad += 1
                    self.post(lambda i=f, m=ex: self.mark(i, "Failed", "fail",
                                                         "FAILED  %s: %s" % (os.path.basename(i), m)))
            self.post(lambda: self.done(ok, bad, out or os.path.dirname(os.path.abspath(files[0]))))

        threading.Thread(target=work, daemon=True).start()

    def mark(self, iid, status, tag, log_line=None):
        if self.tree.exists(iid):
            vals = list(self.tree.item(iid, "values"))
            vals[2] = status
            self.tree.item(iid, values=vals, tags=(tag,))
        if log_line:
            self.log(log_line, "err")

    def done(self, ok, bad, folder):
        self.busy = False
        self.update_buttons()
        msg = "Done. %d image(s) saved as PNG" % ok + ("; %d failed (see log)." % bad if bad else ".")
        self.lbl.config(text=msg)
        self.status(msg, WARN if bad else OK)
        self.log(msg, "warn" if bad else "ok")
        if bad and not self.log_visible:
            self.toggle_log()
        if self.open_when_done.get() and ok and os.path.isdir(folder):
            open_folder(folder)

    def on_close(self):
        self.cfg.update({"out": self.out_dir.get(), "open": bool(self.open_when_done.get()),
                         "geometry": self.geometry()})
        ui.save_config(self.cfg)
        self.destroy()


def enable_dpi_awareness():
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


def main():
    enable_dpi_awareness()
    app = App()
    for a in sys.argv[1:]:
        if os.path.isdir(a):
            app.add_folder_path(a)
        elif os.path.isfile(a):
            app.add([a])
    app.mainloop()


if __name__ == "__main__":
    main()
