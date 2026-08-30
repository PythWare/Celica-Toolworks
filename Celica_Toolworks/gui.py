import os, queue, threading
import tkinter as tk
from tkinter import filedialog, messagebox
from . import config
from . import packidx
from . import patch
from . import unpack

WIDTH = 900
HEIGHT = 520
BG_COLOR = "#120b08"
CARD = "#1d120c"
HEADER = "#2b160c"
HIGHLIGHT = "#bf98d9"
HIGHLIGHT_DK = "#a87fc4"
ACCENT = "#ff6a00"
ACCENT_DKR = "#ffd23c"
TEXT = "#ffe8b4"
MUTED = "#d7a86c"
FIELD = "#2b160c"
SOFT = "#4b2c1c"
LOG_BG = "#0b0604"
BTN_TEXT = "#120b08"
EDGE = "#6b3a18"
DANGER = "#7a2f14"
TITLE = "Celica Toolworks"
MAIN_BUTTONS = ["Tools"]
SUB_OPTIONS = {
    "Tools": ["Set Path", "Unpack", "Patch DLL", "Revert DLL"],
}

SUB_SUB_OPTIONS = {
    "Set Path": ["Browse", "Show", "Clear"],
    "Unpack": ["Start", "Cancel", "Remove Files"],
    "Patch DLL": ["Install Loader", "Status"],
    "Revert DLL": ["Remove Loader"],
}

PANEL_X = 480
PANEL_Y = 60
PANEL_WIDTH = 400
PANEL_HEIGHT = 430
LOG_LIMIT = 500

def shorten_path_smart(path):
    parts = os.fspath(path).split(os.sep)
    if len(parts) >= 2:
        return f"{os.sep}{parts[-2]}{os.sep}{parts[-1]}"
    return os.fspath(path)

class CelicaApp:
    def __init__(self):
        self.ui_state = {"main": None, "sub": None}
        self.unpack_state = {
            "visible": False,
            "summary": "Idle.",
            "progress": 0.0,
            "running": False,
            "total_files": 0,
            "done_files": 0,
            "error_count": 0,
            "logs": [],
            "thread": None,
            "update_queue": None,
            "cancel_event": None,
        }

        self.shown = {
            "info": None,
            "summary": None,
            "fill": -1,
            "cancel": None,
            "bar_width": 0,
        }

        self.panel_item = None
        self.main_btns = []
        self.sub_btns = []
        self.sub_sub_btns = []
        self.drag_data = {"x": 0, "y": 0}
        self.topmost = True
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.geometry(f"{WIDTH}x{HEIGHT}+300+200")
        self.root.wm_attributes("-transparentcolor", BG_COLOR)
        self.root.attributes("-topmost", True)

        self.canvas = tk.Canvas(
            self.root,
            width=WIDTH,
            height=HEIGHT,
            bg=BG_COLOR,
            highlightthickness=0,
        )
        self.canvas.pack()

        self.create_unpack_widgets()
        self.bind_events()
        self.redraw()

    def bind_events(self):
        self.canvas.bind("<Button-1>", self.on_left_click)

        self.root.bind("<Button-3>", self.start_drag)
        self.root.bind("<B3-Motion>", self.do_drag)
        self.root.bind(
            "<ButtonRelease-3>",
            lambda event: self.drag_data.update({"x": 0, "y": 0}),
        )
        self.root.bind("<Escape>", self.close_app)
        self.root.bind("<F1>", self.toggle_topmost)

    def create_unpack_widgets(self):
        panel = tk.Frame(self.root, bg=CARD, highlightthickness=0)

        header = tk.Frame(panel, bg=HEADER, height=30)
        header.pack(fill="x")

        title_var = tk.StringVar(value="Unpack")
        title_label = tk.Label(
            header,
            textvariable=title_var,
            bg=HEADER,
            fg=HIGHLIGHT,
            font=("Segoe UI", 11, "bold"),
        )
        title_label.pack(side="left", padx=8, pady=5)

        close_button = tk.Button(
            header,
            text="X",
            command=self.close_unpack_panel,
            bg=SOFT,
            fg=TEXT,
            relief="flat",
            width=3,
            font=("Segoe UI", 9, "bold"),
            activebackground=HIGHLIGHT,
            activeforeground=BTN_TEXT,
        )
        close_button.pack(side="right", padx=6, pady=5)

        info_var = tk.StringVar(value="No game path set.")
        summary_var = tk.StringVar(value=self.unpack_state["summary"])

        info_label = tk.Label(
            panel,
            textvariable=info_var,
            bg=CARD,
            fg=TEXT,
            anchor="w",
            justify="left",
            wraplength=PANEL_WIDTH - 40,
            font=("Segoe UI", 9, "bold"),
        )
        info_label.pack(fill="x", padx=8, pady=(6, 2))

        summary_label = tk.Label(
            panel,
            textvariable=summary_var,
            bg=CARD,
            fg=HIGHLIGHT,
            anchor="w",
            justify="left",
            wraplength=PANEL_WIDTH - 40,
            font=("Segoe UI", 9, "bold"),
        )
        summary_label.pack(fill="x", padx=8, pady=(2, 6))

        progress_canvas = tk.Canvas(
            panel,
            height=12,
            bg=FIELD,
            highlightthickness=0,
            relief="flat",
        )
        progress_canvas.pack(fill="x", padx=8, pady=(0, 6))
        progress_fill = progress_canvas.create_rectangle(
            0, 0, 0, 12, fill=HIGHLIGHT, outline=""
        )

        log_frame = tk.Frame(panel, bg=CARD)
        log_frame.pack(fill="both", expand=True, padx=8)

        log_scrollbar = tk.Scrollbar(
            log_frame,
            bg=SOFT,
            troughcolor=FIELD,
            activebackground=HIGHLIGHT,
            highlightthickness=0,
            bd=0,
            width=13,
        )
        log_scrollbar.pack(side="right", fill="y")

        log_text = tk.Text(
            log_frame,
            height=12,
            wrap="word",
            bg=LOG_BG,
            fg=TEXT,
            relief="flat",
            insertbackground=TEXT,
            font=("Consolas", 9),
            state="disabled",
            yscrollcommand=log_scrollbar.set,
        )
        log_text.pack(side="left", fill="both", expand=True)
        log_scrollbar.configure(command=log_text.yview)

        for widget in (log_text, log_frame, log_scrollbar):
            widget.bind("<MouseWheel>", self.on_log_wheel)

        button_row = tk.Frame(panel, bg=CARD)
        button_row.pack(fill="x", padx=8, pady=(6, 8))

        cancel_button = tk.Button(
            button_row,
            text="Cancel",
            command=self.cancel_unpack,
            bg=DANGER,
            fg=TEXT,
            relief="flat",
            width=9,
            font=("Segoe UI", 9, "bold"),
            activebackground=HIGHLIGHT,
            activeforeground=BTN_TEXT,
        )
        cancel_button.pack(side="right")

        self.unpack_widgets = {
            "panel": panel,
            "title_var": title_var,
            "info_var": info_var,
            "summary_var": summary_var,
            "progress_canvas": progress_canvas,
            "progress_fill": progress_fill,
            "log_text": log_text,
            "cancel_button": cancel_button,
        }

        self.refresh_unpack_widgets()

    def on_log_wheel(self, event):
        self.unpack_widgets["log_text"].yview_scroll(
            -1 if event.delta > 0 else 1, "units"
        )
        return "break"

    def append_log(self, message):
        if message is None:
            return

        text = str(message).rstrip("\n")
        if not text:
            return

        self.unpack_state["logs"].extend(text.splitlines())
        if len(self.unpack_state["logs"]) > LOG_LIMIT:
            del self.unpack_state["logs"][:-LOG_LIMIT]

        widget = self.unpack_widgets["log_text"]
        pinned = widget.yview()[1] >= 0.999

        widget.configure(state="normal")
        widget.insert("end", text + "\n")
        lines = int(widget.index("end-1c").split(".")[0])
        if lines > LOG_LIMIT:
            widget.delete("1.0", f"{lines - LOG_LIMIT}.0")
        widget.configure(state="disabled")

        if pinned:
            widget.see("end")

    def clear_log(self):
        self.unpack_state["logs"] = []
        widget = self.unpack_widgets["log_text"]
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.configure(state="disabled")

    def set_summary(self, text):
        self.unpack_state["summary"] = text
        self.unpack_widgets["summary_var"].set(text)

    def refresh_path_info(self):
        game_root = config.get_game_root()

        if game_root:
            archive_dir = packidx.archive_dir_for(game_root)
            lines = [
                os.path.basename(str(game_root)) or str(game_root),
                f"Game: {shorten_path_smart(game_root)}",
            ]
            if archive_dir:
                lines.append(f"Apks: {shorten_path_smart(archive_dir)}")
            else:
                lines.append("Apks: none found")
            info = "\n".join(lines)
        else:
            info = "No game path set. Use Set Path, Browse."

        if info != self.shown["info"]:
            self.shown["info"] = info
            self.unpack_widgets["info_var"].set(info)

    def refresh_progress(self):
        summary = self.unpack_state["summary"]
        if summary != self.shown["summary"]:
            self.shown["summary"] = summary
            self.unpack_widgets["summary_var"].set(summary)

        progress_canvas = self.unpack_widgets["progress_canvas"]
        width = self.shown["bar_width"]
        if width <= 1:
            progress_canvas.update_idletasks()
            width = max(progress_canvas.winfo_width(), 1)
            self.shown["bar_width"] = width

        fill = int(max(0.0, min(1.0, self.unpack_state["progress"])) * width)
        if fill != self.shown["fill"]:
            self.shown["fill"] = fill
            progress_canvas.coords(self.unpack_widgets["progress_fill"], 0, 0, fill, 12)

        cancel = "Cancel" if self.unpack_state["running"] else "Done"
        if cancel != self.shown["cancel"]:
            self.shown["cancel"] = cancel
            self.unpack_widgets["cancel_button"].configure(
                state="normal" if self.unpack_state["running"] else "disabled",
                text=cancel,
            )

    def refresh_unpack_widgets(self):
        self.refresh_path_info()
        self.refresh_progress()

    def require_game_root(self):
        game_root = config.get_game_root()
        if game_root is None:
            self.unpack_state["visible"] = True
            self.append_log("No game path set. Use Set Path, Browse.")
            self.redraw()
            return None
        return game_root

    def browse_game_path(self):
        selected = filedialog.askdirectory(
            title="Select the Sword Art Online Lost Song folder"
        )
        if not selected:
            return

        root = packidx.resolve_game_root(selected)
        archives = packidx.discover_archives(root)

        self.unpack_state["visible"] = True

        if not archives:
            self.append_log("No containers found there.")
            self.append_log("Pick the folder with SAOLS.exe or its data folder.")
            self.refresh_unpack_widgets()
            self.redraw()
            return

        if not config.set_game_root(root):
            self.append_log("Couldnt write the config file.")
            self.redraw()
            return

        self.append_log(f"Path set. {len(archives)} containers found.")
        self.refresh_unpack_widgets()
        self.redraw()

    def show_game_path(self):
        self.unpack_state["visible"] = True
        game_root = config.get_game_root()

        if game_root is None:
            self.append_log("No game path set.")
        else:
            for line in patch.status(game_root):
                self.append_log(line)

        self.refresh_unpack_widgets()
        self.redraw()

    def clear_game_path(self):
        config.clear_game_root()
        self.unpack_state["visible"] = True
        self.append_log("Game path cleared.")
        self.refresh_unpack_widgets()
        self.redraw()

    def start_unpack(self):
        if self.unpack_state["running"]:
            self.append_log("An unpack is already running.")
            return

        game_root = self.require_game_root()
        if game_root is None:
            return

        update_queue = queue.Queue()
        cancel_event = threading.Event()
        worker = threading.Thread(
            target=unpack.run_unpack,
            args=(game_root, update_queue, cancel_event),
            daemon=True,
        )

        self.unpack_state["progress"] = 0.0
        self.unpack_state["running"] = True
        self.unpack_state["total_files"] = 0
        self.unpack_state["done_files"] = 0
        self.unpack_state["error_count"] = 0
        self.unpack_state["thread"] = worker
        self.unpack_state["update_queue"] = update_queue
        self.unpack_state["cancel_event"] = cancel_event
        self.unpack_state["visible"] = True

        self.clear_log()
        self.append_log("Unpack started.")
        self.set_summary("Scanning containers")
        self.refresh_unpack_widgets()
        self.redraw()

        worker.start()
        self.root.after(80, self.poll_unpack_updates)

    def cancel_unpack(self):
        if not self.unpack_state["running"]:
            return

        event = self.unpack_state["cancel_event"]
        if event is not None:
            event.set()

        self.append_log("Cancel requested.")

    def poll_unpack_updates(self):
        update_queue = self.unpack_state["update_queue"]
        if update_queue is None:
            return

        finished = False

        while True:
            try:
                event = update_queue.get_nowait()
            except queue.Empty:
                break

            kind = event.get("type")

            if kind == "log":
                self.append_log(event.get("message", ""))
            elif kind == "state":
                self.set_summary(event.get("status", self.unpack_state["summary"]))
                self.unpack_state["progress"] = float(
                    event.get("progress", self.unpack_state["progress"])
                )
                self.unpack_state["running"] = bool(
                    event.get("running", self.unpack_state["running"])
                )
                self.unpack_state["total_files"] = int(
                    event.get("total_files", self.unpack_state["total_files"])
                )
                self.unpack_state["done_files"] = int(
                    event.get("done_files", self.unpack_state["done_files"])
                )
                self.unpack_state["error_count"] = int(
                    event.get("error_count", self.unpack_state["error_count"])
                )
            elif kind == "error":
                self.unpack_state["running"] = False
                self.append_log(event.get("message", "Unpack failed."))
            elif kind == "finished":
                finished = True

        self.refresh_progress()
        if finished:
            self.unpack_state["running"] = False
            self.unpack_state["thread"] = None
            self.unpack_state["update_queue"] = None
            self.unpack_state["cancel_event"] = None
            self.append_log(self.unpack_state["summary"])
            self.refresh_unpack_widgets()
            self.redraw()
            return

        self.root.after(80, self.poll_unpack_updates)

    def remove_extracted(self):
        if self.unpack_state["running"]:
            self.append_log("Wait for the unpack to finish first.")
            return

        game_root = self.require_game_root()
        if game_root is None:
            return

        targets = patch.extracted_dirs(game_root)
        self.unpack_state["visible"] = True

        if not targets:
            self.append_log("Nothing extracted to remove.")
            self.redraw()
            return

        confirm = messagebox.askyesno(
            TITLE,
            f"Delete {len(targets)} extracted folders from the game data folder?\n\n"
            "The containers and pack.idx arent affcted.",
        )
        if not confirm:
            return

        for line in patch.remove_extracted(game_root):
            self.append_log(line)
        self.set_summary("Idle.")
        self.unpack_state["progress"] = 0.0
        self.refresh_unpack_widgets()
        self.redraw()

    def run_patch_action(self, action):
        game_root = self.require_game_root()
        if game_root is None:
            return

        self.unpack_state["visible"] = True
        try:
            for line in action(game_root):
                self.append_log(line)
        except patch.PatchError as exc:
            self.append_log(str(exc))

        self.refresh_unpack_widgets()
        self.redraw()

    def close_unpack_panel(self):
        if self.unpack_state["running"]:
            confirm = messagebox.askyesno(
                TITLE, "Cancel the running unpack and hide the panel?"
            )
            if not confirm:
                return
            self.cancel_unpack()

        self.unpack_state["visible"] = False
        self.redraw()

    def hide_panels(self):
        if not self.unpack_state["running"]:
            self.unpack_state["visible"] = False

    def draw_title(self):
        self.canvas.create_text(
            WIDTH // 2,
            25,
            text=TITLE,
            fill=HIGHLIGHT,
            font=("Segoe UI", 15, "bold"),
            tags="chrome",
        )

    def draw_main(self):
        buttons = []
        for index, name in enumerate(MAIN_BUTTONS):
            x, y = 60, 120 + index * 100
            radius = 30
            selected = self.ui_state["main"] == name

            self.canvas.create_oval(
                x - radius,
                y - radius,
                x + radius,
                y + radius,
                fill=HIGHLIGHT if selected else SOFT,
                outline=EDGE,
                tags="chrome",
            )
            self.canvas.create_text(
                x,
                y,
                text=name[0],
                fill=BTN_TEXT if selected else TEXT,
                font=("Segoe UI", 13, "bold"),
                tags="chrome",
            )
            buttons.append((name, (x, y, radius)))
        return buttons

    def draw_strip(self):
        if not self.ui_state["main"]:
            return []

        items = SUB_OPTIONS[self.ui_state["main"]]
        buttons = []
        base_x, base_y = 140, 100

        self.canvas.create_rectangle(
            base_x - 10,
            base_y - 10,
            base_x + 190,
            base_y + len(items) * 60,
            fill=CARD,
            outline=EDGE,
            tags="chrome",
        )

        for index, text in enumerate(items):
            y = base_y + index * 60
            selected = self.ui_state["sub"] == text
            self.canvas.create_rectangle(
                base_x,
                y,
                base_x + 180,
                y + 50,
                fill=HIGHLIGHT if selected else FIELD,
                outline=EDGE,
                tags="chrome",
            )
            self.canvas.create_text(
                base_x + 90,
                y + 25,
                text=text,
                fill=BTN_TEXT if selected else TEXT,
                font=("Segoe UI", 10, "bold"),
                tags="chrome",
            )
            buttons.append((text, (base_x, y, base_x + 180, y + 50)))
        return buttons

    def draw_sub_strip(self):
        if not self.ui_state["sub"]:
            return []

        items = SUB_SUB_OPTIONS.get(self.ui_state["sub"], [])
        buttons = []
        base_x, base_y = 340, 100

        self.canvas.create_rectangle(
            base_x - 10,
            base_y - 10,
            base_x + 130,
            base_y + len(items) * 60,
            fill=CARD,
            outline=EDGE,
            tags="chrome",
        )

        for index, text in enumerate(items):
            y = base_y + index * 60
            self.canvas.create_rectangle(
                base_x, y, base_x + 120, y + 50, fill=SOFT, outline=EDGE,
                tags="chrome",
            )
            self.canvas.create_text(
                base_x + 60,
                y + 25,
                text=text,
                fill=TEXT,
                font=("Segoe UI", 9, "bold"),
                tags="chrome",
            )
            buttons.append((text, (base_x, y, base_x + 120, y + 50)))
        return buttons

    def draw_unpack_panel(self):
        if not self.unpack_state["visible"]:
            if self.panel_item is not None:
                self.canvas.itemconfigure(self.panel_item, state="hidden")
            return

        self.canvas.create_rectangle(
            PANEL_X,
            PANEL_Y,
            PANEL_X + PANEL_WIDTH,
            PANEL_Y + PANEL_HEIGHT,
            fill=CARD,
            outline="",
            tags="chrome",
        )
        self.canvas.create_rectangle(
            PANEL_X + 3,
            PANEL_Y + 3,
            PANEL_X + PANEL_WIDTH - 3,
            PANEL_Y + PANEL_HEIGHT - 3,
            outline=EDGE,
            tags="chrome",
        )

        if self.panel_item is None:
            self.panel_item = self.canvas.create_window(
                PANEL_X + 6,
                PANEL_Y + 6,
                anchor="nw",
                window=self.unpack_widgets["panel"],
                width=PANEL_WIDTH - 12,
                height=PANEL_HEIGHT - 12,
            )
        else:
            self.canvas.itemconfigure(self.panel_item, state="normal")

        self.canvas.tag_raise(self.panel_item)

    def on_left_click(self, event):
        x, y = event.x, event.y
        if y < 50:
            return

        for name, (cx, cy, radius) in self.main_btns:
            if self.point_in_circle(x, y, cx, cy, radius):
                if self.ui_state["main"] == name:
                    self.ui_state["main"] = None
                    self.ui_state["sub"] = None
                else:
                    self.ui_state["main"] = name
                    self.ui_state["sub"] = None
                self.hide_panels()
                self.redraw()
                return

        for name, rect in self.sub_btns:
            if self.point_in_rect(x, y, rect):
                self.ui_state["sub"] = None if self.ui_state["sub"] == name else name
                self.hide_panels()
                self.redraw()
                return

        for name, rect in self.sub_sub_btns:
            if self.point_in_rect(x, y, rect):
                self.hide_panels()
                self.dispatch(self.ui_state["sub"], name)
                return

    def dispatch(self, section, action):
        if section == "Set Path":
            if action == "Browse":
                self.browse_game_path()
            elif action == "Show":
                self.show_game_path()
            elif action == "Clear":
                self.clear_game_path()
            return

        if section == "Unpack":
            if action == "Start":
                self.start_unpack()
            elif action == "Cancel":
                self.cancel_unpack()
            elif action == "Remove Files":
                self.remove_extracted()
            return

        if section == "Patch DLL":
            if action == "Install Loader":
                self.run_patch_action(patch.install)
            elif action == "Status":
                self.show_game_path()
            return

        if section == "Revert DLL" and action == "Remove Loader":
            self.run_patch_action(patch.remove)

    @staticmethod
    def point_in_circle(px, py, cx, cy, radius):
        return (px - cx) ** 2 + (py - cy) ** 2 <= radius ** 2

    @staticmethod
    def point_in_rect(px, py, rect):
        x1, y1, x2, y2 = rect
        return x1 <= px <= x2 and y1 <= py <= y2

    def start_drag(self, event):
        self.drag_data["x"] = event.x_root
        self.drag_data["y"] = event.y_root

    def do_drag(self, event):
        dx = event.x_root - self.drag_data["x"]
        dy = event.y_root - self.drag_data["y"]

        self.root.geometry(f"+{self.root.winfo_x() + dx}+{self.root.winfo_y() + dy}")

        self.drag_data["x"] = event.x_root
        self.drag_data["y"] = event.y_root

    def close_app(self, _event=None):
        if self.unpack_state["running"]:
            self.cancel_unpack()
            thread = self.unpack_state["thread"]
            if thread is not None:
                thread.join(timeout=2.0)
        self.root.destroy()

    def toggle_topmost(self, _event=None):
        self.topmost = not self.topmost
        self.root.attributes("-topmost", self.topmost)

    def redraw(self):
        self.canvas.delete("chrome")
        self.draw_title()
        self.main_btns = self.draw_main()
        self.sub_btns = self.draw_strip()
        self.sub_sub_btns = self.draw_sub_strip()
        self.draw_unpack_panel()

    def run(self):
        self.root.mainloop()

def run_app():
    app = CelicaApp()
    app.run()
