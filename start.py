import sys
import os
import subprocess
import uuid
import threading
import traceback
import importlib
import inspect
import os as _os

# When running as a PyInstaller one-file bundle, PyInstaller extracts
# runtime data (including tcl/tk) into a temporary folder available at
# sys._MEIPASS. Tkinter needs TCL_LIBRARY/TK_LIBRARY to point to the
# extracted tcl/tk folders so it can find init.tcl.
if getattr(sys, "frozen", False):
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        # PyInstaller places Tcl/Tk data under these bundle folders.
        # Force the library paths so tkinter can always find init.tcl/tk.tcl.
        tcl_dir = os.path.join(meipass, "_tcl_data")
        tk_dir = os.path.join(meipass, "_tk_data")
        if os.path.isdir(tcl_dir):
            os.environ["TCL_LIBRARY"] = tcl_dir
        if os.path.isdir(tk_dir):
            os.environ["TK_LIBRARY"] = tk_dir
else:
    # Normal source runs use the Tcl/Tk installed with Python.
    base_prefix = getattr(sys, "base_prefix", sys.prefix)
    tcl_dir = os.path.join(base_prefix, "tcl", "tcl8.6")
    tk_dir = os.path.join(base_prefix, "tcl", "tk8.6")
    if os.path.isdir(tcl_dir):
        os.environ["TCL_LIBRARY"] = tcl_dir
    if os.path.isdir(tk_dir):
        os.environ["TK_LIBRARY"] = tk_dir

from tkinter import *
from tkinter import ttk

def _crash_log(msg):
    try:
        log_path = _os.path.join(
            _os.path.expanduser("~"),
            "Desktop",
            "CFIS_crash_log.txt"
        )
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(msg)
    except Exception:
        pass

def runtime_base_dir():
    if getattr(sys, "frozen", False):
        # When bundled as one-file exe, PyInstaller extracts to a temp dir
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def runtime_python_executable():
    base_dir = runtime_base_dir()
    candidates = [
        os.path.join(base_dir, ".venv", "Scripts", "python.exe"),
        os.path.join(os.path.dirname(base_dir), ".venv", "Scripts", "python.exe"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return sys.executable


def ensure_runtime_cwd():
    try:
        os.chdir(runtime_base_dir())
    except OSError:
        pass


def ensure_project_venv():
    """Relaunch with .venv interpreter when launched from a different Python."""
    # Disable automatic relaunch during local runs to avoid execv/path issues.
    # This function is intentionally a no-op when running under development.
    return


class ModuleLoadingOverlay:
    """Animated loading popup shown while a module process starts."""

    def __init__(self, parent, module_name, messages=None):
        self.parent = parent
        self.module_name = module_name
        self.start_ms = 0
        self.spinner_frames = ["|", "/", "-", "\\"]
        self.spinner_index = 0
        self._messages = messages if messages else [f"Loading {module_name}..."]
        self._msg_index = 0
        self._closed = False
        self._after_ids = set()

        self.top = Toplevel(parent)
        self.top.title("Loading")
        self.top.resizable(False, False)
        self.top.configure(bg="#050B1A")
        self.top.attributes("-topmost", True)
        self.top.transient(parent)
        self.top.grab_set()
        self.top.attributes("-alpha", 0.0)

        width = 420
        height = 210
        screen_w = parent.winfo_screenwidth()
        screen_h = parent.winfo_screenheight()
        pos_x = (screen_w - width) // 2
        pos_y = (screen_h - height) // 2
        self.top.geometry(f"{width}x{height}+{pos_x}+{pos_y}")

        container = Frame(
            self.top,
            bg="#0A152A",
            highlightthickness=1,
            highlightbackground="#1E3A8A",
        )
        container.place(x=12, y=12, width=396, height=186)

        Label(
            container,
            text="INITIALIZING SYSTEM",
            bg="#0A152A",
            fg="#27B1FF",
            font=("Segoe UI Semibold", 12),
        ).place(x=18, y=14)

        self.message_label = Label(
            container,
            text=self._messages[0] if self._messages else f"Loading {module_name}...",
            bg="#0A152A",
            fg="#E6F1FF",
            font=("Segoe UI", 11),
            anchor="w",
        )
        self.message_label.place(x=18, y=46)

        self.spinner_label = Label(
            container,
            text="|",
            bg="#0A152A",
            fg="#86A4D9",
            font=("Consolas", 14),
            anchor="w",
        )
        self.spinner_label.place(x=18, y=74)

        style = ttk.Style(self.top)
        style.theme_use("clam")
        style.configure(
            "Launch.Horizontal.TProgressbar",
            troughcolor="#071226",
            bordercolor="#1E3A8A",
            background="#27B1FF",
            lightcolor="#27B1FF",
            darkcolor="#1A6CB0",
        )

        self.progress = ttk.Progressbar(
            container,
            orient=HORIZONTAL,
            length=356,
            mode="indeterminate",
            style="Launch.Horizontal.TProgressbar",
        )
        self.progress.place(x=18, y=122)
        self.progress.start(10)

        self._fade_in()
        self._animate_spinner()
        self._animate_messages()

    def _schedule(self, delay_ms, callback):
        if self._closed:
            return None
        try:
            if not self.top.winfo_exists():
                return None
        except Exception:
            return None
        after_id = self.top.after(delay_ms, callback)
        self._after_ids.add(after_id)
        return after_id

    def _animate_messages(self):
        if self._closed:
            return
        try:
            if not self.top.winfo_exists():
                return
        except Exception:
            return
        # Advance to next message; stay on the last one once exhausted
        next_index = self._msg_index + 1
        if next_index < len(self._messages):
            self._msg_index = next_index
            self.message_label.configure(text=self._messages[self._msg_index])
            self._schedule(1200, self._animate_messages)

    def watch_process(self, process, ready_file, on_finished):
        self._poll(process, ready_file, on_finished, wait_ticks=0)

    def _poll(self, process, ready_file, on_finished, wait_ticks):
        if os.path.exists(ready_file):
            try:
                os.remove(ready_file)
            except OSError:
                pass
            self.close()
            on_finished()
            return

        if process.poll() is not None and wait_ticks > 10:
            self.close()
            on_finished()
            return

        self._schedule(120, lambda: self._poll(process, ready_file, on_finished, wait_ticks + 1))

    def _fade_in(self):
        if self._closed:
            return
        try:
            if not self.top.winfo_exists():
                return
        except Exception:
            return
        try:
            alpha = float(self.top.attributes("-alpha"))
        except Exception:
            return
        if alpha < 1.0:
            self.top.attributes("-alpha", min(alpha + 0.08, 1.0))
            self._schedule(16, self._fade_in)

    def _animate_spinner(self):
        if self._closed:
            return
        try:
            if not self.top.winfo_exists():
                return
        except Exception:
            return
        self.spinner_label.configure(text=self.spinner_frames[self.spinner_index])
        self.spinner_index = (self.spinner_index + 1) % len(self.spinner_frames)
        self._schedule(90, self._animate_spinner)

    def close(self):
        self._closed = True
        for after_id in list(self._after_ids):
            try:
                self.top.after_cancel(after_id)
            except Exception:
                pass
        self._after_ids.clear()
        try:
            self.progress.stop()
        except Exception:
            pass
        try:
            self.top.grab_release()
        except Exception:
            pass
        try:
            if self.top.winfo_exists():
                self.top.destroy()
        except Exception:
            try:
                self.top.destroy()
            except Exception:
                pass


def launch_script(script_name, current_window=None, module_name="Module", messages=None):
    base_dir = runtime_base_dir()
    abs_script = os.path.join(base_dir, script_name)

    if getattr(sys, "frozen", False):
        module_exe = os.path.join(base_dir, f"{os.path.splitext(script_name)[0]}.exe")
        launch_cmd = [module_exe]
    else:
        launch_cmd = [runtime_python_executable(), abs_script]

    if current_window is None:
        subprocess.Popen(launch_cmd)
        return

    token = uuid.uuid4().hex
    temp_dir = os.path.join(base_dir, "temp")
    os.makedirs(temp_dir, exist_ok=True)
    ready_file = os.path.join(temp_dir, f"launch_ready_{token}.flag")

    env = os.environ.copy()
    env["CFIS_READY_FILE"] = ready_file

    loader = ModuleLoadingOverlay(current_window, module_name, messages=messages)
    process = subprocess.Popen(launch_cmd, env=env)
    loader.watch_process(process, ready_file, on_finished=lambda: current_window.destroy())


def _launch_module_in_process(current_window, module_name, messages, import_class):
    if current_window is None:
        module_class = import_class()
        module_class()
        return

    overlay = ModuleLoadingOverlay(current_window, module_name, messages=messages)
    state = {"cls": None, "min_done": False, "err": None}

    def _try_open():
        if state["err"] is not None:
            overlay.close()
            return
        if state["cls"] is not None and state["min_done"]:
            try:
                # Withdraw the parent window before closing overlay to avoid
                # race conditions where destroying the overlay also destroys
                # Tk internals used by the parent.
                if current_window is not None:
                    try:
                        if current_window.winfo_exists():
                            current_window.withdraw()
                    except Exception:
                        pass
                state["cls"](parent=current_window)
            finally:
                try:
                    overlay.close()
                except Exception:
                    pass

    def _bg_import():
        try:
            state["cls"] = import_class()
        except Exception as exc:
            state["err"] = exc
        current_window.after(0, _try_open)

    current_window.after(900, lambda: (state.__setitem__("min_done", True), _try_open()))
    threading.Thread(target=_bg_import, daemon=True).start()


def register(current_window=None):
    if getattr(sys, "frozen", False):
        def import_class():
            def ctor(parent=None):
                try:
                    mod = importlib.import_module("registerGUI")
                    cls = getattr(mod, "RegisterDashboard", None)
                    if cls is None:
                        return None
                    try:
                        return cls(parent=parent)
                    except TypeError:
                        return cls()
                except Exception:
                    _crash_log(traceback.format_exc())
                    return None
            return ctor
        _launch_module_in_process(current_window, "Register", ["Loading registration module...", "Preparing database...", "Opening form..."], import_class)
    else:
        launch_script(
            "registerGUI.py",
            current_window=current_window,
            module_name="Register",
            messages=["Loading registration module...", "Preparing database...", "Opening form..."],
        )


def video_surveillance(current_window=None):
    if getattr(sys, "frozen", False):
        def import_class():
            def ctor(parent=None):
                try:
                    mod = importlib.import_module("surveillance")
                    cls = getattr(mod, "App", None)
                    if cls is None:
                        return None
                    try:
                        return cls(parent=parent)
                    except TypeError:
                        return cls()
                except Exception:
                    _crash_log(traceback.format_exc())
                    return None
            return ctor
        _launch_module_in_process(current_window, "Surveillance", ["Loading surveillance module...", "Connecting to camera...", "Starting feed..."], import_class)
    else:
        launch_script(
            "surveillance.py",
            current_window=current_window,
            module_name="Surveillance",
            messages=["Loading surveillance module...", "Connecting to camera...", "Starting feed..."],
        )


def detect_criminal(current_window=None):
    if getattr(sys, "frozen", False):
        def import_class():
            def ctor(parent=None):
                try:
                    mod = importlib.import_module("detect")
                    cls = getattr(mod, "PhotoMatchDashboard", None)
                    if cls is None:
                        return None
                    try:
                        return cls(parent=parent)
                    except TypeError:
                        return cls()
                except Exception:
                    _crash_log(traceback.format_exc())
                    return None
            return ctor
        _launch_module_in_process(current_window, "Photo Match", ["Loading photo match module...", "Preparing recognition engine...", "Opening scanner..."], import_class)
    else:
        launch_script(
            "detect.py",
            current_window=current_window,
            module_name="Photo Match",
            messages=["Loading photo match module...", "Preparing recognition engine...", "Opening scanner..."],
        )


def records_management(current_window=None):
    if getattr(sys, "frozen", False):
        def import_class():
            def ctor(parent=None):
                try:
                    mod = importlib.import_module("records")
                    cls = getattr(mod, "RecordsManager", None)
                    if cls is None:
                        return None
                    try:
                        return cls()
                    except TypeError:
                        try:
                            return cls(parent=parent)
                        except Exception:
                            return cls()
                except Exception:
                    _crash_log(traceback.format_exc())
                    return None
            return ctor
        _launch_module_in_process(current_window, "Records", ["Loading records module...", "Fetching profiles...", "Opening records manager..."], import_class)
    else:
        launch_script(
            "records.py",
            current_window=current_window,
            module_name="Records",
            messages=["Loading records module...", "Fetching profiles...", "Opening records manager..."],
        )


class StartupSplash:
    """Borderless splash screen shown once at system startup before the main dashboard."""

    _MESSAGES = [
        "Initializing system...",
        "Loading core modules...",
        "Preparing dashboard...",
    ]
    _SPINNER = ["|", "/", "-", "\\"]

    def __init__(self, on_done):
        self._on_done = on_done
        self._msg_idx = 0
        self._spin_idx = 0
        self._closed = False
        self._after_ids = set()
        self._progress = None

        self.root = Tk()
        self.root.overrideredirect(True)
        self.root.configure(bg="#040B1A")
        self.root.attributes("-alpha", 0.0)
        self.root.attributes("-topmost", True)

        W, H = 520, 280
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")

        self._build()
        self._fade_in()
        self._schedule(700, self._tick_msg)
        self._schedule(90, self._tick_spin)
        self._schedule(2600, self._finish)
        self.root.mainloop()

    def _schedule(self, delay_ms, callback):
        if self._closed or not self.root.winfo_exists():
            return None
        after_id = self.root.after(delay_ms, callback)
        self._after_ids.add(after_id)
        return after_id

    def _build(self):
        container = Frame(
            self.root, bg="#0A152A",
            highlightthickness=1, highlightbackground="#1E3A8A",
        )
        container.place(x=14, y=14, width=492, height=252)

        Label(
            container,
            text="SECURITY FACE\nDETECTION SYSTEM",
            bg="#0A152A",
            fg="#27B1FF",
            font=("Bahnschrift SemiBold", 21),
            justify=CENTER,
        ).place(relx=0.5, y=12, anchor="n")

        Label(
            container, text="Security Face Detection System",
            bg="#0A152A", fg="#86A4D9", font=("Segoe UI", 12),
        ).place(relx=0.5, y=86, anchor="n")

        self._msg_lbl = Label(
            container, text=self._MESSAGES[0],
            bg="#0A152A", fg="#E6F1FF", font=("Segoe UI", 10),
        )
        self._msg_lbl.place(relx=0.5, y=122, anchor="n")

        self._spin_lbl = Label(
            container, text="|", bg="#0A152A",
            fg="#86A4D9", font=("Consolas", 14),
        )
        self._spin_lbl.place(relx=0.5, y=150, anchor="n")

        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "Splash.Horizontal.TProgressbar",
            troughcolor="#071226", bordercolor="#1E3A8A",
            background="#27B1FF", lightcolor="#27B1FF", darkcolor="#1A6CB0",
        )
        self._progress = ttk.Progressbar(
            container, orient=HORIZONTAL, length=440,
            mode="indeterminate", style="Splash.Horizontal.TProgressbar",
        )
        self._progress.place(relx=0.5, y=197, anchor="n")
        self._progress.start(10)

    def _fade_in(self):
        if self._closed or not self.root.winfo_exists():
            return
        alpha = float(self.root.attributes("-alpha"))
        if alpha < 1.0:
            self.root.attributes("-alpha", min(alpha + 0.08, 1.0))
            self._schedule(16, self._fade_in)

    def _tick_msg(self):
        if self._closed or not self.root.winfo_exists():
            return
        next_idx = self._msg_idx + 1
        if next_idx < len(self._MESSAGES):
            self._msg_idx = next_idx
            self._msg_lbl.configure(text=self._MESSAGES[self._msg_idx])
        self._schedule(700, self._tick_msg)

    def _tick_spin(self):
        if self._closed or not self.root.winfo_exists():
            return
        self._spin_lbl.configure(text=self._SPINNER[self._spin_idx % len(self._SPINNER)])
        self._spin_idx += 1
        self._schedule(90, self._tick_spin)

    def _finish(self):
        self._closed = True
        for after_id in list(self._after_ids):
            try:
                self.root.after_cancel(after_id)
            except Exception:
                pass
        self._after_ids.clear()
        try:
            if self._progress is not None:
                self._progress.stop()
        except Exception:
            pass
        if self.root.winfo_exists():
            self._on_done(self.root)


class AnimatedDashboard:
    """Modernized Security Face Detection System dashboard with dark theme and startup/button animations."""

    def __init__(self, root=None):
        self._owns_root = root is None
        self.root = root if root is not None else Tk()
        for child in list(self.root.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass
        self.root.title("Security Face Detection System")
        self.root.geometry("800x500")
        self.root.minsize(800, 500)
        self.root.maxsize(800, 500)
        self.root.configure(bg="#050B1A")
        self.root.overrideredirect(False)
        self._center_window(800, 500)

        # Fade-in starts from transparent to make startup feel smoother.
        self.root.attributes("-alpha", 0.0)

        self.colors = {
            "bg_top": "#030814",
            "bg_bottom": "#0B1D3A",
            "nav": "#081224",
            "panel": "#0A152A",
            "panel_border": "#1E3A8A",
            "text": "#E6F1FF",
            "muted": "#86A4D9",
            "btn": "#0A2A5A",
            "btn_hover": "#0E4D9C",
            "btn_pressed": "#123C73",
            "accent": "#27B1FF",
        }

        self.bg_canvas = Canvas(self.root, highlightthickness=0, bd=0)
        self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.bg_canvas.bind("<Configure>", self._draw_background)

        self._build_header()
        self._build_content_panel()

        self._fade_in_window()
        self._slide_panel_up()

    def _build_header(self):
        self.header = Frame(self.root, bg=self.colors["nav"], height=62)
        self.header.place(x=0, y=0, relwidth=1)

        Label(
            self.header,
            text="SECURITY FACE DETECTION SYSTEM",
            bg=self.colors["nav"],
            fg=self.colors["accent"],
            font=("Segoe UI Semibold", 12),
        ).pack(side=LEFT, padx=18, pady=16)


        Label(
            self.header,
            text="SECURITY DASHBOARD",
            bg=self.colors["nav"],
            fg=self.colors["muted"],
            font=("Segoe UI", 10),
        ).pack(side=RIGHT, padx=18, pady=18)

    def _build_content_panel(self):
        self.panel = Frame(
            self.root,
            bg=self.colors["panel"],
            highlightthickness=1,
            highlightbackground=self.colors["panel_border"],
        )

        # Panel starts slightly lower and slides upward on startup.
        self.panel_target_y = 0.56
        self.panel_current_y = 0.70
        self.panel.place(relx=0.5, rely=self.panel_current_y, anchor=CENTER, width=560, height=380)

        Label(
            self.panel,
            text="Security Face Detection System",
            bg=self.colors["panel"],
            fg=self.colors["text"],
            font=("Bahnschrift SemiBold", 24),
        ).pack(pady=(22, 8))

        Label(
            self.panel,
            text="Intelligent recognition and surveillance command center",
            bg=self.colors["panel"],
            fg=self.colors["muted"],
            font=("Segoe UI", 11),
        ).pack(pady=(0, 12))

        self._create_action_button("Records Management", lambda: records_management(self.root)).pack(pady=5)
        self._create_action_button("Register", lambda: register(self.root)).pack(pady=5)
        self._create_action_button("Photo Match", lambda: detect_criminal(self.root)).pack(pady=5)
        self._create_action_button("Video Surveillance", lambda: video_surveillance(self.root)).pack(pady=5)

    def _create_action_button(self, text, command):
        button = Button(
            self.panel,
            text=text,
            command=command,
            width=30,
            height=1,
            relief=FLAT,
            bd=0,
            bg=self.colors["btn"],
            fg=self.colors["text"],
            activebackground=self.colors["btn_hover"],
            activeforeground=self.colors["text"],
            cursor="hand2",
            font=("Segoe UI Semibold", 11),
            padx=14,
            pady=6,
        )

        # Hover glow and slight scaling with font/padding changes.
        button.bind("<Enter>", lambda event, b=button: self._on_hover_in(b))
        button.bind("<Leave>", lambda event, b=button: self._on_hover_out(b))
        button.bind("<ButtonPress-1>", lambda event, b=button: self._on_press(b))
        button.bind("<ButtonRelease-1>", lambda event, b=button: self._on_release(b))
        return button

    def _on_hover_in(self, button):
        button.configure(
            bg=self.colors["btn_hover"],
            font=("Segoe UI Semibold", 12),
            padx=16,
            pady=7,
            highlightthickness=1,
            highlightbackground=self.colors["accent"],
        )

    def _on_hover_out(self, button):
        button.configure(
            bg=self.colors["btn"],
            font=("Segoe UI Semibold", 11),
            padx=14,
            pady=6,
            highlightthickness=0,
        )

    def _on_press(self, button):
        button.configure(bg=self.colors["btn_pressed"], font=("Segoe UI Semibold", 10), padx=12, pady=5)

    def _on_release(self, button):
        button.configure(bg=self.colors["btn_hover"], font=("Segoe UI Semibold", 12), padx=16, pady=7)

    def _fade_in_window(self):
        alpha = self.root.attributes("-alpha")
        if alpha < 1.0:
            self.root.attributes("-alpha", min(alpha + 0.05, 1.0))
            self.root.after(22, self._fade_in_window)

    def _slide_panel_up(self):
        if self.panel_current_y > self.panel_target_y:
            self.panel_current_y -= 0.015
            self.panel.place_configure(rely=self.panel_current_y)
            self.root.after(18, self._slide_panel_up)
        else:
            self.panel.place_configure(rely=self.panel_target_y)

    def _draw_background(self, event):
        self.bg_canvas.delete("all")
        width = max(event.width, 1)
        height = max(event.height, 1)

        # Gradient background to mimic a cyber-security interface.
        r1, g1, b1 = self._hex_to_rgb(self.colors["bg_top"])
        r2, g2, b2 = self._hex_to_rgb(self.colors["bg_bottom"])

        for y in range(height):
            ratio = y / height
            r = int(r1 + (r2 - r1) * ratio)
            g = int(g1 + (g2 - g1) * ratio)
            b = int(b1 + (b2 - b1) * ratio)
            color = f"#{r:02x}{g:02x}{b:02x}"
            self.bg_canvas.create_line(0, y, width, y, fill=color)

        # Subtle grid and scan lines for futuristic dashboard mood.
        for x in range(0, width, 40):
            self.bg_canvas.create_line(x, 62, x, height, fill="#0D2A52")
        for y in range(62, height, 34):
            self.bg_canvas.create_line(0, y, width, y, fill="#0A2344")

        self.bg_canvas.create_rectangle(0, 61, width, 62, fill="#1A4A8A", outline="")

    def _center_window(self, width, height):
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        pos_x = (screen_width - width) // 2
        pos_y = (screen_height - height) // 2
        self.root.geometry(f"{width}x{height}+{pos_x}+{pos_y}")

    @staticmethod
    def _hex_to_rgb(value):
        value = value.lstrip("#")
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))

    def run(self):
        if self._owns_root:
            self.root.mainloop()


if __name__ == "__main__":
    try:
        ensure_runtime_cwd()
        ensure_project_venv()
        StartupSplash(on_done=lambda root: AnimatedDashboard(root=root).run())
    except Exception:
        _crash_log(traceback.format_exc())