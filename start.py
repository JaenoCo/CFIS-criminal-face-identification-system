from tkinter import *
from tkinter import ttk
import sys
import os
import shutil
import subprocess
import uuid
import threading



def runtime_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def bundle_base_dir():
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", runtime_base_dir())
    return runtime_base_dir()


def ensure_runtime_assets():
    runtime_dir = runtime_base_dir()
    os.makedirs(os.path.join(runtime_dir, "temp"), exist_ok=True)

    if not getattr(sys, "frozen", False):
        return

    source_dir = bundle_base_dir()

    for filename in ("person.db", "haarcascade_frontalface_default.xml"):
        source_path = os.path.join(source_dir, filename)
        target_path = os.path.join(runtime_dir, filename)
        if os.path.exists(source_path) and not os.path.exists(target_path):
            try:
                shutil.copy2(source_path, target_path)
            except OSError:
                pass

    source_images = os.path.join(source_dir, "images")
    target_images = os.path.join(runtime_dir, "images")
    if os.path.isdir(source_images) and not os.path.exists(target_images):
        try:
            shutil.copytree(source_images, target_images)
        except OSError:
            pass


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
    runtime_python = runtime_python_executable()

    current = os.path.normcase(os.path.abspath(sys.executable))
    expected = os.path.normcase(os.path.abspath(runtime_python))
    already_bootstrapped = os.environ.get("CFIS_VENV_BOOTSTRAPPED") == "1"

    if current != expected and not already_bootstrapped:
        env = os.environ.copy()
        env["CFIS_VENV_BOOTSTRAPPED"] = "1"
        os.execv(runtime_python, [runtime_python, os.path.abspath(__file__)])


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
        if self._closed or not self.top.winfo_exists():
            return None
        after_id = self.top.after(delay_ms, callback)
        self._after_ids.add(after_id)
        return after_id

    def _animate_messages(self):
        if self._closed or not self.top.winfo_exists():
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
        if self._closed or not self.top.winfo_exists():
            return
        try:
            alpha = float(self.top.attributes("-alpha"))
        except Exception:
            return
        if alpha < 1.0:
            self.top.attributes("-alpha", min(alpha + 0.08, 1.0))
            self._schedule(16, self._fade_in)

    def _animate_spinner(self):
        if self._closed or not self.top.winfo_exists():
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
        if self.top.winfo_exists():
            self.top.destroy()


def launch_script(script_name, current_window=None, module_name="Module", messages=None):
    base_dir = runtime_base_dir()
    abs_script = os.path.join(base_dir, script_name)
    script_stem = os.path.splitext(script_name)[0]

    def _import_module_class(mod_name):
        import importlib

        module = importlib.import_module(mod_name)
        for cls_name in ("RegisterDashboard", "PhotoMatchDashboard", "App"):
            if hasattr(module, cls_name):
                return getattr(module, cls_name)
        raise ImportError(f"No dashboard class found in {mod_name}")

    # Keep button launches inside the current process so the main dashboard
    # stays consistent instead of closing and spawning a fresh instance.
    if current_window is not None:
        try:
            if not getattr(sys, "frozen", False):
                if script_stem == "registerGUI" and REGISTER_MODULE_CLASS:
                    _launch_module_in_process(current_window, module_name, messages, lambda: REGISTER_MODULE_CLASS)
                    return
                if script_stem == "detect" and DETECT_MODULE_CLASS:
                    _launch_module_in_process(current_window, module_name, messages, lambda: DETECT_MODULE_CLASS)
                    return
                if script_stem == "surveillance" and SURV_MODULE_CLASS:
                    _launch_module_in_process(current_window, module_name, messages, lambda: SURV_MODULE_CLASS)
                    return

            module_class = _import_module_class(script_stem)
            _launch_module_in_process(current_window, module_name, messages, lambda: module_class)
        except Exception:
            pass
        return

    # When frozen we prefer to launch companion module EXEs if they exist.
    # If they don't exist (single-file bundle), import and run the
    # module in-process so the UI opens as a child window.
    if getattr(sys, "frozen", False):
        module_exe = os.path.join(base_dir, f"{script_stem}.exe")
        if os.path.exists(module_exe):
            subprocess.Popen([module_exe])
            return

        try:
            module_class = _import_module_class(script_stem)
            module_class()
        except Exception:
            pass
        return

    subprocess.Popen([runtime_python_executable(), abs_script])


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
            state["cls"](parent=current_window)
            overlay.close()
            current_window.withdraw()

    def _bg_import():
        try:
            state["cls"] = import_class()
        except Exception as exc:
            state["err"] = exc
        current_window.after(0, _try_open)

    current_window.after(900, lambda: (state.__setitem__("min_done", True), _try_open()))
    threading.Thread(target=_bg_import, daemon=True).start()


# Pre-import lightweight references for development (non-frozen) runs only.
# Avoid importing heavy compiled extensions (dlib, cv2, etc.) when running
# as a frozen bundle since those binaries may not be present in the main
# single-file executable and will cause startup crashes.
REGISTER_MODULE_CLASS = None
DETECT_MODULE_CLASS = None
SURV_MODULE_CLASS = None
if not getattr(sys, "frozen", False):
    try:
        import registerGUI as _rg
        REGISTER_MODULE_CLASS = getattr(_rg, "RegisterDashboard", None)
    except Exception:
        REGISTER_MODULE_CLASS = None

    try:
        import detect as _dt
        DETECT_MODULE_CLASS = getattr(_dt, "PhotoMatchDashboard", None)
    except Exception:
        DETECT_MODULE_CLASS = None

    try:
        import surveillance as _sv
        SURV_MODULE_CLASS = getattr(_sv, "App", None)
    except Exception:
        SURV_MODULE_CLASS = None


def register(current_window=None):
    launch_script(
        "registerGUI.py",
        current_window=current_window,
        module_name="Register",
        messages=["Loading registration module...", "Preparing database...", "Opening form..."],
    )


def video_surveillance(current_window=None):
    launch_script(
        "surveillance.py",
        current_window=current_window,
        module_name="Surveillance",
        messages=["Loading surveillance module...", "Connecting to camera...", "Starting feed..."],
    )


def detect_person(current_window=None):
    launch_script(
        "detect.py",
        current_window=current_window,
        module_name="Photo Match",
        messages=["Loading photo match module...", "Preparing recognition engine...", "Opening scanner..."],
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
            self.root.destroy()
        self._on_done()


class AnimatedDashboard:
    """Modernized Security Face Detection System dashboard with dark theme and startup/button animations."""

    def __init__(self):
        self.root = Tk()
        self.root.title("Security Face Detection System")
        self.root.geometry("800x500")
        self.root.minsize(800, 500)
        self.root.maxsize(800, 500)
        self.root.configure(bg="#050B1A")
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
        self.panel.place(relx=0.5, rely=self.panel_current_y, anchor=CENTER, width=560, height=320)

        Label(
            self.panel,
            text="Security Face Detection System",
            bg=self.colors["panel"],
            fg=self.colors["text"],
            font=("Bahnschrift SemiBold", 24),
        ).pack(pady=(28, 10))

        Label(
            self.panel,
            text="Intelligent recognition and surveillance command center",
            bg=self.colors["panel"],
            fg=self.colors["muted"],
            font=("Segoe UI", 11),
        ).pack(pady=(0, 18))

        self._create_action_button("Register Person", lambda: register(self.root)).pack(pady=7)
        self._create_action_button("Photo Match", lambda: detect_person(self.root)).pack(pady=7)
        self._create_action_button("Video Surveillance", lambda: video_surveillance(self.root)).pack(pady=7)

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
            font=("Segoe UI Semibold", 12),
            padx=16,
            pady=8,
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
            font=("Segoe UI Semibold", 13),
            padx=18,
            pady=9,
            highlightthickness=1,
            highlightbackground=self.colors["accent"],
        )

    def _on_hover_out(self, button):
        button.configure(
            bg=self.colors["btn"],
            font=("Segoe UI Semibold", 12),
            padx=16,
            pady=8,
            highlightthickness=0,
        )

    def _on_press(self, button):
        button.configure(bg=self.colors["btn_pressed"], font=("Segoe UI Semibold", 11), padx=14, pady=7)

    def _on_release(self, button):
        button.configure(bg=self.colors["btn_hover"], font=("Segoe UI Semibold", 13), padx=18, pady=9)

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
        self.root.mainloop()


if __name__ == "__main__":
    ensure_runtime_cwd()
    ensure_runtime_assets()
    # When packaged by PyInstaller the app is already running from the
    # bundled runtime; avoid re-execing the interpreter which expects
    # a source `start.py` file on disk (not available in the onefile bundle).
    if not getattr(sys, "frozen", False):
        ensure_project_venv()
    StartupSplash(on_done=lambda: AnimatedDashboard().run())
