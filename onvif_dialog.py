"""
ONVIF Camera Selection Dialog for the Security Face Detection System surveillance module.
Provides UI for discovering and selecting ONVIF cameras.
"""

from tkinter import Toplevel, Frame, Button, Label, Entry, StringVar, Listbox, Scrollbar, Canvas
from tkinter import messagebox, simpledialog
import threading


class ONVIFCameraDialog:
    """Dialog for discovering and selecting ONVIF cameras."""
    
    def __init__(self, parent, onvif_manager):
        self.parent = parent
        self.onvif_manager = onvif_manager
        self.selected_device = None
        self.dialog = None
        self.device_listbox = None
        self.status_label = None
        self.discover_button = None
        self.add_manual_button = None
        self.connect_button = None

    def _center_dialog(self, dialog, width, height):
        self.parent.update_idletasks()
        parent_x = self.parent.winfo_rootx()
        parent_y = self.parent.winfo_rooty()
        parent_w = self.parent.winfo_width()
        parent_h = self.parent.winfo_height()
        pos_x = parent_x + max(0, (parent_w - width) // 2)
        pos_y = parent_y + max(0, (parent_h - height) // 2)
        dialog.geometry(f"{width}x{height}+{pos_x}+{pos_y}")
        
    def show(self):
        """Show the ONVIF camera selection dialog."""
        self.dialog = Toplevel(self.parent)
        self.dialog.title("Select ONVIF Camera")
        self._center_dialog(self.dialog, 500, 450)
        self.dialog.resizable(False, False)
        self.dialog.grab_set()
        
        # Center on parent
        self.dialog.transient(self.parent)
        self.dialog.lift()
        self.dialog.focus_force()
        
        # Header
        header_frame = Frame(self.dialog, bg="#081224", height=50)
        header_frame.pack(fill="x")
        
        Label(
            header_frame,
            text="ONVIF Camera Discovery",
            bg="#081224",
            fg="#2DB3FF",
            font=("Segoe UI", 12, "bold")
        ).pack(pady=10)
        
        # Device list with scrollbar
        list_frame = Frame(self.dialog)
        list_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        scrollbar = Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        
        self.device_listbox = Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            bg="#0B152A",
            fg="#E6F1FF",
            font=("Segoe UI", 10),
            height=12
        )
        self.device_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.device_listbox.yview)
        self.device_listbox.bind("<<ListboxSelect>>", self._on_device_select)
        
        # Status label
        self.status_label = Label(
            self.dialog,
            text="Ready",
            bg="#040B1A",
            fg="#89A8D8",
            font=("Segoe UI", 9)
        )
        self.status_label.pack(fill="x", padx=10, pady=5)
        
        # Buttons frame
        button_frame = Frame(self.dialog, bg="#040B1A")
        button_frame.pack(fill="x", padx=10, pady=10)
        
        self.discover_button = Button(
            button_frame,
            text="Auto Discover",
            command=self._start_discovery,
            bg="#2DB3FF",
            fg="#040B1A",
            font=("Segoe UI", 10, "bold"),
            padx=10,
            pady=5
        )
        self.discover_button.pack(side="left", padx=5)
        
        self.add_manual_button = Button(
            button_frame,
            text="Add Manually",
            command=self._add_manual,
            bg="#16335E",
            fg="#E6F1FF",
            font=("Segoe UI", 10),
            padx=10,
            pady=5
        )
        self.add_manual_button.pack(side="left", padx=5)
        
        self.connect_button = Button(
            button_frame,
            text="Connect",
            command=self._on_connect,
            bg="#25C851",
            fg="#000",
            font=("Segoe UI", 10, "bold"),
            padx=10,
            pady=5,
            state="disabled"
        )
        self.connect_button.pack(side="right", padx=5)
        
        cancel_button = Button(
            button_frame,
            text="Cancel",
            command=self._on_cancel,
            bg="#555",
            fg="#FFF",
            font=("Segoe UI", 10),
            padx=10,
            pady=5
        )
        cancel_button.pack(side="right", padx=5)
        
        self._refresh_device_list()
    
    def _refresh_device_list(self):
        """Refresh the device list display."""
        self.device_listbox.delete(0, "end")
        for device in self.onvif_manager.devices:
            display_text = device.to_string()
            if getattr(device, "is_manual", False):
                display_text += " [Saved]"
            if device.stream_uri:
                display_text += " ✓"
            self.device_listbox.insert("end", display_text)
    
    def _on_device_select(self, event=None):
        """Handle device selection in listbox."""
        selection = self.device_listbox.curselection()
        if selection:
            self.selected_device = self.onvif_manager.devices[selection[0]]
            self.connect_button.config(state="normal")
        else:
            self.selected_device = None
            self.connect_button.config(state="disabled")
    
    def _start_discovery(self):
        """Start automatic ONVIF discovery."""
        self.discover_button.config(state="disabled")
        self.add_manual_button.config(state="disabled")
        self.status_label.config(text="Discovering ONVIF devices on network...", fg="#FFA500")
        
        def on_discovery_complete(devices):
            def _apply_results():
                if not self.dialog or not self.dialog.winfo_exists():
                    return
                self._refresh_device_list()
                device_count = len(devices)
                if device_count == 0:
                    self.status_label.config(text="No ONVIF devices found", fg="#FF5252")
                else:
                    self.status_label.config(
                        text=f"Found {device_count} device(s)",
                        fg="#25C851"
                    )
                self.discover_button.config(state="normal")
                self.add_manual_button.config(state="normal")

            self.dialog.after(0, _apply_results)
        
        self.onvif_manager.discover_devices_background(on_discovery_complete)
    
    def _add_manual(self):
        """Add a device manually."""
        # Create manual entry dialog
        manual_dialog = Toplevel(self.dialog)
        manual_dialog.title("Add ONVIF Device Manually")
        self._center_dialog(manual_dialog, 430, 330)
        manual_dialog.resizable(False, False)
        manual_dialog.transient(self.dialog)
        manual_dialog.grab_set()
        manual_dialog.lift()
        manual_dialog.focus_force()

        form_frame = Frame(manual_dialog)
        form_frame.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        form_canvas = Canvas(form_frame, highlightthickness=0)
        form_scrollbar = Scrollbar(form_frame, orient="vertical", command=form_canvas.yview)
        form_canvas.configure(yscrollcommand=form_scrollbar.set)

        form_scrollbar.pack(side="right", fill="y")
        form_canvas.pack(side="left", fill="both", expand=True)

        form_inner = Frame(form_canvas)
        form_window_id = form_canvas.create_window((0, 0), window=form_inner, anchor="nw")

        def _sync_scroll_region(event=None):
            form_canvas.configure(scrollregion=form_canvas.bbox("all"))

        def _sync_inner_width(event):
            form_canvas.itemconfigure(form_window_id, width=event.width)

        form_inner.bind("<Configure>", _sync_scroll_region)
        form_canvas.bind("<Configure>", _sync_inner_width)
        
        # IP entry
        Label(form_inner, text="Device IP:", font=("Segoe UI", 10)).pack(anchor="w", padx=20, pady=(20, 5))
        ip_var = StringVar()
        Entry(form_inner, textvariable=ip_var, font=("Segoe UI", 10), width=30).pack(padx=20, pady=5)
        
        # Port entry
        Label(form_inner, text="Port (try 554 for RTSP-only cameras):", font=("Segoe UI", 10)).pack(anchor="w", padx=20, pady=(10, 5))
        port_var = StringVar(value="554")
        Entry(form_inner, textvariable=port_var, font=("Segoe UI", 10), width=30).pack(padx=20, pady=5)
        
        # Username entry
        Label(form_inner, text="Username (optional):", font=("Segoe UI", 10)).pack(anchor="w", padx=20, pady=(10, 5))
        username_var = StringVar()
        Entry(form_inner, textvariable=username_var, font=("Segoe UI", 10), width=30).pack(padx=20, pady=5)
        
        # Password entry
        Label(form_inner, text="Password (optional):", font=("Segoe UI", 10)).pack(anchor="w", padx=20, pady=(10, 5))
        password_var = StringVar()
        Entry(form_inner, textvariable=password_var, font=("Segoe UI", 10), width=30, show="*").pack(padx=20, pady=5)

        # Stream URI entry
        Label(form_inner, text="RTSP Stream URI (optional):", font=("Segoe UI", 10)).pack(anchor="w", padx=20, pady=(10, 5))
        stream_uri_var = StringVar()
        Entry(form_inner, textvariable=stream_uri_var, font=("Segoe UI", 10), width=30).pack(padx=20, pady=5)
        
        def on_add():
            ip = ip_var.get().strip()
            if not ip:
                messagebox.showerror("Error", "Please enter an IP address")
                return
            
            try:
                port = int(port_var.get()) if port_var.get() else 8080
            except ValueError:
                messagebox.showerror("Error", "Invalid port number")
                return
            
            # Show progress
            manual_dialog.title("Adding device...")
            manual_dialog.update()
            
            username = username_var.get().strip()
            password = password_var.get().strip()
            stream_uri = stream_uri_var.get().strip()
            
            def add_in_thread():
                device = self.onvif_manager.add_device_manual(ip, port, username, password, stream_uri)
                manual_dialog.after(0, lambda: _on_add_complete(device))
            
            def _on_add_complete(device):
                if device:
                    self._refresh_device_list()
                    if stream_uri:
                        messagebox.showinfo("Saved", f"Device saved with stream URI: {device.to_string()}")
                    elif device.stream_uri:
                        messagebox.showinfo("Success", f"Device added: {device.to_string()}")
                    else:
                        messagebox.showinfo(
                            "Saved",
                            f"Device added: {device.to_string()}\nThe app will try common V380 RTSP paths when you connect.",
                        )
                    manual_dialog.destroy()
                else:
                    messagebox.showerror("Error", f"Failed to connect to {ip}:{port}\nMake sure the device is reachable and has ONVIF enabled")
                    manual_dialog.title("Add ONVIF Device Manually")
            
            threading.Thread(target=add_in_thread, daemon=True).start()
        
        button_frame = Frame(form_inner)
        button_frame.pack(fill="x", padx=20, pady=20)
        
        Button(
            button_frame,
            text="Add",
            command=on_add,
            bg="#2DB3FF",
            fg="#040B1A",
            font=("Segoe UI", 10, "bold"),
            padx=20,
            pady=5
        ).pack(side="left", padx=5)
        
        Button(
            button_frame,
            text="Cancel",
            command=manual_dialog.destroy,
            bg="#555",
            fg="#FFF",
            font=("Segoe UI", 10),
            padx=20,
            pady=5
        ).pack(side="right", padx=5)

        _sync_scroll_region()
    
    def _on_connect(self):
        """Connect to selected device."""
        if not self.selected_device:
            messagebox.showwarning("Warning", "Please select a device")
            return
        
        self.dialog.destroy()
    
    def _on_cancel(self):
        """Cancel and close dialog."""
        self.selected_device = None
        self.dialog.destroy()
    
    def get_selected_device_object(self):
        """Get the selected ONVIF device object."""
        return self.selected_device

    def get_selected_device(self):
        """Get selected device stream URI (compatibility helper)."""
        if self.selected_device:
            # Ensure we have the stream URI
            stream_uri = self.onvif_manager.get_device_stream(self.selected_device)
            return stream_uri or self.selected_device.stream_uri
        return None
