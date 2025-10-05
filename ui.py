"""
UI Components for the Background Removal Tool.
Contains all user interface classes and components.
"""
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from PIL import Image, ImageTk
import multiprocessing
from typing import Optional, Tuple, List

# Import utilities
from utils import (UIUtils, FileUtils, SystemUtils, ImageUtils, ValidationUtils, 
                   PerformanceUtils, WidgetUtils, ThreadUtils, SettingsUtils, CanvasUtils)

# Constants
class Constants:
    # UI Colors - Simple Black & White Theme
    BG_COLOR = "#ffffff"           # White background
    FG_COLOR = "#000000"           # Black text
    ACCENT_COLOR = "#333333"       # Dark gray for borders/accents
    BUTTON_BG = "#f0f0f0"          # Light gray for buttons
    BUTTON_FG = "#000000"          # Black button text
    ENTRY_BG = "#ffffff"           # White entry background
    ENTRY_FG = "#000000"           # Black entry text
    
    # UI Dimensions
    WINDOW_WIDTH = 1200
    WINDOW_HEIGHT = 750
    LEFT_PANEL_WIDTH = 450
    PREVIEW_CANVAS_BG = "#f5f5f5"
    
    # Timing
    DEBOUNCE_DELAY_MS = 500
    PREVIEW_CHECK_INTERVAL_MS = 100
    RESOURCE_UPDATE_INTERVAL_MS = 1000
    MOUSE_WHEEL_BIND_DELAY_MS = 100
    
    # Processing Defaults
    DEFAULT_ALPHA_FG_THRESHOLD = 240
    DEFAULT_ALPHA_BG_THRESHOLD = 10
    DEFAULT_MAX_IMAGE_SIZE = 800
    DEFAULT_RESIZE_FRACTION = 0.5
    DEFAULT_MEMORY_LIMIT_MB = 2048
    DEFAULT_BATCH_DELAY_MS = 100
    
    # File Extensions
    VALID_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp')
    
    # Zoom Settings
    MIN_ZOOM = 0.1
    MAX_ZOOM = 3.0
    DEFAULT_ZOOM = 1.0
    ZOOM_FACTOR = 1.1
    MOUSE_WHEEL_DELTA_DIVISOR = 120
    
    # Thumbnail Size
    PREVIEW_THUMBNAIL_SIZE = (800, 800)
    CHECKERBOARD_CELL_SIZE = 10
    
    # Threading
    DEFAULT_MAX_THREADS = 4
    MIN_THREADS = 1


class ToolTip:
    """Create a tooltip for a given widget"""
    def __init__(self, widget, text='widget info'):
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.tipwindow = None

    def enter(self, event=None):
        self.show_tooltip()

    def leave(self, event=None):
        self.hide_tooltip()

    def show_tooltip(self):
        if self.tipwindow or not self.text:
            return
        x, y, cx, cy = self.widget.bbox("insert") if hasattr(self.widget, 'bbox') else (0, 0, 0, 0)
        x = x + self.widget.winfo_rootx() + 25
        y = y + cy + self.widget.winfo_rooty() + 25
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                        background=Constants.BG_COLOR, foreground=Constants.FG_COLOR,
                        relief=tk.SOLID, borderwidth=1,
                        font=("Segoe UI", "9", "normal"))
        label.pack(ipadx=1)

    def hide_tooltip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()


class UIComponent:
    """Base class for UI components"""
    def __init__(self, parent, settings_manager):
        self.parent = parent
        self.settings_manager = settings_manager

    def create_frame(self) -> tk.Widget:
        """Create and return the UI frame - to be implemented by subclasses"""
        raise NotImplementedError

    def add_tooltip(self, widget, text: str):
        """Add a tooltip to a widget"""
        ToolTip(widget, text)


class InputSettingsSection(UIComponent):
    """Input settings UI component"""
    def __init__(self, parent, settings_manager, browse_callback):
        super().__init__(parent, settings_manager)
        self.browse_callback = browse_callback

    def create_frame(self) -> tk.Widget:
        """Create the input settings frame"""
        frame = ttk.LabelFrame(self.parent, text="Input Settings", padding="10")
        frame.pack(fill=tk.X, pady=5, padx=5)

        # Input folder selection
        ttk.Label(frame, text="Input Folder:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.input_entry = ttk.Entry(frame, textvariable=self.settings_manager.input_folder, width=30)
        self.input_entry.grid(row=0, column=1, padx=5, pady=5)
        browse_btn = ttk.Button(frame, text="Browse...", command=self.browse_callback)
        browse_btn.grid(row=0, column=2)
        self.add_tooltip(browse_btn, "Select folder containing images. The folder will be automatically scanned for image files.")

        # Overwrite checkbox
        overwrite_cb = ttk.Checkbutton(frame, text="Overwrite existing files",
                                     variable=self.settings_manager.overwrite_files)
        overwrite_cb.grid(row=1, column=0, columnspan=3, sticky=tk.W)
        self.add_tooltip(overwrite_cb, "If enabled, replaces existing output files. If disabled, skips files that already exist in the output folder.")

        return frame


class ExportSettingsSection(UIComponent):
    """Export settings UI component"""
    def __init__(self, parent, settings_manager, browse_output_callback, update_controls_callback):
        super().__init__(parent, settings_manager)
        self.browse_output_callback = browse_output_callback
        self.update_controls_callback = update_controls_callback

    def create_frame(self) -> tk.Widget:
        """Create the export settings frame"""
        frame = ttk.LabelFrame(self.parent, text="Export Settings", padding="10")
        frame.pack(fill=tk.X, pady=5, padx=5)
        
        # Location options
        ttk.Label(frame, text="Location:").grid(row=0, column=0, sticky=tk.W, pady=2)
        
        ttk.Radiobutton(frame, text="Subfolder inside Input", variable=self.settings_manager.output_location_mode,
                       value="inside", command=self.update_controls_callback).grid(row=1, column=0, columnspan=3, sticky=tk.W)
        
        ttk.Radiobutton(frame, text="Subfolder next to Input", variable=self.settings_manager.output_location_mode,
                       value="sibling", command=self.update_controls_callback).grid(row=2, column=0, columnspan=3, sticky=tk.W)
        
        ttk.Radiobutton(frame, text="Custom Folder", variable=self.settings_manager.output_location_mode,
                       value="custom", command=self.update_controls_callback).grid(row=3, column=0, columnspan=3, sticky=tk.W)
        
        # Custom folder controls
        self.custom_folder_entry = ttk.Entry(frame, textvariable=self.settings_manager.custom_output_folder, width=25)
        self.custom_folder_entry.grid(row=4, column=0, columnspan=2, sticky=tk.W, padx=(20, 5), pady=2)
        self.custom_folder_button = ttk.Button(frame, text="Browse...", command=self.browse_output_callback, width=8)
        self.custom_folder_button.grid(row=4, column=2, sticky=tk.W, pady=2)
        
        # Subfolder name
        ttk.Label(frame, text="Subfolder Name:").grid(row=5, column=0, sticky=tk.W, pady=(8,2))
        self.subfolder_entry = ttk.Entry(frame, textvariable=self.settings_manager.output_subfolder_name, width=20)
        self.subfolder_entry.grid(row=5, column=1, columnspan=2, sticky=tk.W, pady=(8,2))
        
        # Background type
        ttk.Label(frame, text="Background:").grid(row=6, column=0, sticky=tk.W, pady=2)
        bg_combo = ttk.Combobox(frame, textvariable=self.settings_manager.background_type, width=18,
                               values=["Transparent", "White", "Black", "Alpha Matte (W/B)"])
        bg_combo.grid(row=6, column=1, columnspan=2, sticky=tk.W, pady=2)
        self.add_tooltip(bg_combo, "Output background type:\n• Transparent: PNG with alpha channel\n• White/Black: Solid color background\n• Alpha Matte (W/B): Grayscale mask image")
        
        # Naming options
        ttk.Label(frame, text="Filename:").grid(row=7, column=0, sticky=tk.W, pady=(8,2))
        
        ttk.Radiobutton(frame, text="Add suffix", variable=self.settings_manager.output_naming_mode,
                       value="append_suffix", command=self.update_controls_callback).grid(row=8, column=0, columnspan=3, sticky=tk.W)
        
        ttk.Radiobutton(frame, text="Keep original", variable=self.settings_manager.output_naming_mode,
                       value="original_filename", command=self.update_controls_callback).grid(row=9, column=0, columnspan=3, sticky=tk.W)
        
        # Suffix entry
        ttk.Label(frame, text="Suffix:").grid(row=10, column=0, sticky=tk.W)
        self.suffix_entry = ttk.Entry(frame, textvariable=self.settings_manager.output_filename_suffix, width=20)
        self.suffix_entry.grid(row=10, column=1, columnspan=2, sticky=tk.W)
        
        return frame


class ModelSettingsSection(UIComponent):
    """Model settings UI component"""
    def __init__(self, parent, settings_manager, model_change_callback):
        super().__init__(parent, settings_manager)
        self.model_change_callback = model_change_callback

    def create_frame(self) -> tk.Widget:
        """Create the model settings frame"""
        frame = ttk.LabelFrame(self.parent, text="Model Settings", padding="10")
        frame.pack(fill=tk.X, pady=5, padx=5)
        
        # Model selection
        ttk.Label(frame, text="Model:").grid(row=0, column=0, sticky=tk.W, pady=5)
        model_dropdown = ttk.Combobox(frame, textvariable=self.settings_manager.model_name, width=25,
                                    values=["u2netp", "u2net", "u2net_human_seg", "isnet-general-use"])
        model_dropdown.grid(row=0, column=1, sticky=tk.W, pady=5)
        model_dropdown.bind("<<ComboboxSelected>>", self.on_model_selected)
        self.add_tooltip(model_dropdown, "Choose the AI model for background removal:\n• u2netp: Fast, lightweight (recommended)\n• u2net: More accurate but slower\n• u2net_human_seg: Best for people\n• isnet-general-use: Highest quality")
        
        # Model description
        self.model_description = ttk.Label(frame, text="", foreground="gray", wraplength=300)
        self.model_description.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=5)
        self.update_model_description()
        
        return frame
    
    def on_model_selected(self, event=None):
        """Handle model selection change"""
        self.update_model_description()
        if self.model_change_callback:
            self.model_change_callback()

    def update_model_description(self, *args):
        """Update model description based on selection"""
        model = self.settings_manager.model_name.get()
        self.model_description.config(text=self.settings_manager.get_model_description(model))


class ProcessingOptionsSection(UIComponent):
    """Processing options UI component"""
    def __init__(self, parent, settings_manager, settings_change_callback, alpha_matting_update_callback):
        super().__init__(parent, settings_manager)
        self.settings_change_callback = settings_change_callback
        self.alpha_matting_update_callback = alpha_matting_update_callback

    def create_frame(self) -> tk.Widget:
        """Create the processing options frame"""
        frame = ttk.LabelFrame(self.parent, text="Processing Options", padding="10")
        frame.pack(fill=tk.X, pady=5, padx=5)
        
        # Alpha matting
        self.alpha_matting_cb = ttk.Checkbutton(frame, text="Alpha Matting (Better Edges)", 
                                               variable=self.settings_manager.alpha_matting,
                                               command=self.alpha_matting_update_callback)
        self.alpha_matting_cb.grid(row=0, column=0, columnspan=3, sticky=tk.W)
        self.add_tooltip(self.alpha_matting_cb, "Alpha matting creates smoother, more natural edges by analyzing pixel transparency. More accurate but slower processing.")
        
        # Post-processing
        post_process_cb = ttk.Checkbutton(frame, text="Post-processing", 
                                        variable=self.settings_manager.post_processing,
                                        command=self.settings_change_callback)
        post_process_cb.grid(row=1, column=0, columnspan=3, sticky=tk.W)
        self.add_tooltip(post_process_cb, "Post-processing applies additional edge smoothing and hole filling to clean up the mask. Can improve results on complex images.")
        
        # Alpha matting thresholds
        ttk.Label(frame, text="Alpha Matting Thresholds:", font=("TkDefaultFont", 9, "bold")).grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(10,2))
        
        # Foreground threshold
        self.fg_label_text = ttk.Label(frame, text="Foreground:")
        self.fg_label_text.grid(row=3, column=0, sticky=tk.W, pady=2)
        self.fg_slider = ttk.Scale(frame, from_=0, to=255, variable=self.settings_manager.alpha_matting_foreground_threshold, orient=tk.HORIZONTAL, command=self.update_fg_label_and_preview)
        self.fg_slider.grid(row=3, column=1, sticky=tk.W+tk.E, padx=5, pady=2)
        self.fg_label = ttk.Label(frame, text=str(int(self.settings_manager.alpha_matting_foreground_threshold.get())))
        self.fg_label.grid(row=3, column=2, sticky=tk.W, padx=5)
        self.add_tooltip(self.fg_slider, "Foreground threshold (240 = default): Higher values (240-255) include more pixels as foreground. Lower values (200-240) are more selective.")
        
        # Background threshold
        self.bg_label_text = ttk.Label(frame, text="Background:")
        self.bg_label_text.grid(row=4, column=0, sticky=tk.W, pady=2)
        self.bg_slider = ttk.Scale(frame, from_=0, to=255, variable=self.settings_manager.alpha_matting_background_threshold, orient=tk.HORIZONTAL, command=self.update_bg_label_and_preview)
        self.bg_slider.grid(row=4, column=1, sticky=tk.W+tk.E, padx=5, pady=2)
        self.bg_label = ttk.Label(frame, text=str(int(self.settings_manager.alpha_matting_background_threshold.get())))
        self.bg_label.grid(row=4, column=2, sticky=tk.W, padx=5)
        self.add_tooltip(self.bg_slider, "Background threshold (10 = default): Lower values (0-10) exclude more pixels from background. Higher values (10-50) include more as background.")
        
        self.frame = frame
        return frame
    
    def update_alpha_matting_controls(self):
        """Enable/disable alpha matting threshold controls based on checkbox"""
        enabled = SettingsUtils.get_variable_value(self.settings_manager.alpha_matting, False)
        
        # Update slider states
        WidgetUtils.set_widget_state(self.fg_slider, enabled)
        WidgetUtils.set_widget_state(self.bg_slider, enabled)
        
        # Update label colors
        color = "black" if enabled else "gray"
        WidgetUtils.set_widget_color(self.fg_label_text, foreground=color)
        WidgetUtils.set_widget_color(self.bg_label_text, foreground=color)
        WidgetUtils.set_widget_color(self.fg_label, foreground=color)
        WidgetUtils.set_widget_color(self.bg_label, foreground=color)
    
    def update_fg_label(self, value=None):
        """Update foreground threshold label"""
        threshold_val = SettingsUtils.get_variable_value(
            self.settings_manager.alpha_matting_foreground_threshold, 240)
        self.fg_label.config(text=str(int(float(threshold_val))))
    
    def update_bg_label(self, value=None):
        """Update background threshold label"""
        threshold_val = SettingsUtils.get_variable_value(
            self.settings_manager.alpha_matting_background_threshold, 10)
        self.bg_label.config(text=str(int(float(threshold_val))))
    
    def update_fg_label_and_preview(self, value=None):
        """Update foreground label and trigger preview refresh"""
        self.update_fg_label(value)
        if self.settings_change_callback:
            self.settings_change_callback()
    
    def update_bg_label_and_preview(self, value=None):
        """Update background label and trigger preview refresh"""
        self.update_bg_label(value)
        self.settings_change_callback()


class CPUSettingsSection(UIComponent):
    """CPU settings UI component"""
    def __init__(self, parent, settings_manager, resize_update_callback, settings_change_callback=None):
        super().__init__(parent, settings_manager)
        self.resize_update_callback = resize_update_callback
        self.settings_change_callback = settings_change_callback

    def create_frame(self) -> tk.Widget:
        """Create the CPU settings frame"""
        frame = ttk.LabelFrame(self.parent, text="Performance Settings", padding="10")
        frame.pack(fill=tk.X, pady=5, padx=5)
        
        # CPU Threads
        ttk.Label(frame, text="CPU Threads:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.thread_spinbox = ttk.Spinbox(frame, from_=Constants.MIN_THREADS, to=multiprocessing.cpu_count(),
                                         textvariable=self.settings_manager.num_threads, width=10)
        self.thread_spinbox.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Label(frame, text=f"(1-{multiprocessing.cpu_count()})").grid(row=0, column=2, sticky=tk.W, pady=2)
        self.add_tooltip(self.thread_spinbox, f"Number of CPU threads to use (1-{multiprocessing.cpu_count()}). More threads = faster processing but higher CPU usage.")
        
        # Memory Limit
        ttk.Label(frame, text="Memory Limit (MB):").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.memory_spinbox = ttk.Spinbox(frame, from_=512, to=8192, increment=256,
                                         textvariable=self.settings_manager.memory_limit_mb, width=10)
        self.memory_spinbox.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Label(frame, text="(512-8192)").grid(row=1, column=2, sticky=tk.W, pady=2)
        self.add_tooltip(self.memory_spinbox, "Memory limit before clearing model cache. Lower values save RAM but may slow processing.")
        
        # Batch Delay
        ttk.Label(frame, text="Batch Delay (ms):").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.delay_spinbox = ttk.Spinbox(frame, from_=0, to=1000, increment=50,
                                        textvariable=self.settings_manager.batch_delay_ms, width=10)
        self.delay_spinbox.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Label(frame, text="(0-1000)").grid(row=2, column=2, sticky=tk.W, pady=2)
        self.add_tooltip(self.delay_spinbox, "Delay between batch operations (ms). Higher values reduce CPU usage but slow processing.")
        
        # Pre-resize option
        self.resize_cb = ttk.Checkbutton(frame, text="Pre-resize large images", 
                                        variable=self.settings_manager.resize_enabled,
                                        command=self.resize_update_and_preview_callback)
        self.resize_cb.grid(row=3, column=0, columnspan=2, sticky=tk.W)
        self.add_tooltip(self.resize_cb, "Resize large images before processing to improve speed. Smaller images = faster processing but lower quality.")
        
        # Resize settings
        resize_frame = ttk.Frame(frame)
        resize_frame.grid(row=4, column=0, columnspan=2, sticky=tk.W, padx=(20,0))
        
        # Resize mode selection
        ttk.Label(resize_frame, text="Resize Mode:").grid(row=0, column=0, sticky=tk.W, pady=2)
        resize_mode_combo = ttk.Combobox(resize_frame, textvariable=self.settings_manager.resize_mode, width=10,
                                        values=["pixels", "fraction"])
        resize_mode_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        resize_mode_combo.bind("<<ComboboxSelected>>", self.resize_update_and_preview_callback)
        
        # Max size (pixels mode)
        ttk.Label(resize_frame, text="Max Size:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.max_size_spinbox = ttk.Spinbox(resize_frame, from_=200, to=2000, increment=50,
                                           textvariable=self.settings_manager.max_image_size, width=10,
                                           command=self._on_resize_value_change)
        self.max_size_spinbox.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        # Resize fraction (fraction mode)
        ttk.Label(resize_frame, text="Resize Fraction:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.fraction_spinbox = ttk.Spinbox(resize_frame, from_=0.1, to=1.0, increment=0.1,
                                           textvariable=self.settings_manager.resize_fraction, width=10,
                                           command=self._on_resize_value_change)
        self.fraction_spinbox.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        
        self.resize_frame = resize_frame
        return frame
    
    def update_resize_controls(self):
        """Update resize controls based on settings"""
        resize_enabled = SettingsUtils.get_variable_value(self.settings_manager.resize_enabled, False)
        resize_mode = SettingsUtils.get_variable_value(self.settings_manager.resize_mode, "pixels")
        
        # Enable/disable resize controls
        for widget in self.resize_frame.winfo_children():
            WidgetUtils.set_widget_state(widget, resize_enabled)
        
        # Show/hide relevant controls based on mode
        if resize_enabled:
            pixels_mode = resize_mode == "pixels"
            WidgetUtils.set_widget_state(self.max_size_spinbox, pixels_mode)
            WidgetUtils.set_widget_state(self.fraction_spinbox, not pixels_mode)
    
    def resize_update_and_preview_callback(self, event=None):
        """Update resize controls and trigger preview refresh"""
        self.resize_update_callback()
        # Also trigger preview refresh since resize affects processing
        if hasattr(self, 'settings_change_callback') and callable(self.settings_change_callback):
            self.settings_change_callback()
    
    def _on_resize_value_change(self):
        """Called when resize values (max size, fraction) change"""
        # Trigger preview refresh since resize values affect processing
        if hasattr(self, 'settings_change_callback') and callable(self.settings_change_callback):
            self.settings_change_callback()


class ResourceMonitorSection(UIComponent):
    """Resource monitor UI component"""
    def __init__(self, parent, settings_manager):
        super().__init__(parent, settings_manager)

    def create_frame(self) -> tk.Widget:
        """Create the resource monitor frame"""
        frame = ttk.LabelFrame(self.parent, text="System Monitor", padding="10")
        frame.pack(fill=tk.X, pady=5, padx=5)
        
        # CPU Usage
        ttk.Label(frame, text="CPU Usage:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.cpu_label = ttk.Label(frame, text="0%")
        self.cpu_label.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        # Memory Usage
        ttk.Label(frame, text="Memory Usage:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.memory_label = ttk.Label(frame, text="0 MB")
        self.memory_label.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        return frame


class SettingsPanel:
    """Container for all settings sections with scrollable support"""
    def __init__(self, parent, settings_manager, callbacks):
        self.parent = parent
        self.settings_manager = settings_manager
        self.callbacks = callbacks
        self.scrollable_frame = None

    def create_scrollable_panel(self) -> tk.Widget:
        """Create the scrollable left panel container"""
        container = ttk.Frame(self.parent, width=Constants.LEFT_PANEL_WIDTH)
        container.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        container.pack_propagate(False)
        
        canvas = tk.Canvas(container)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind("<Configure>", 
                                 lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Enable mouse wheel scrolling
        def on_mouse_wheel(event):
            canvas.yview_scroll(int(-1*(event.delta/Constants.MOUSE_WHEEL_DELTA_DIVISOR)), "units")

        def on_key_scroll(event):
            """Handle keyboard scrolling"""
            if event.keysym == 'Up':
                canvas.yview_scroll(-1, "units")
            elif event.keysym == 'Down':
                canvas.yview_scroll(1, "units")
            elif event.keysym == 'Page_Up':
                canvas.yview_scroll(-5, "units")
            elif event.keysym == 'Page_Down':
                canvas.yview_scroll(5, "units")
            elif event.keysym == 'Home':
                canvas.yview_moveto(0)
            elif event.keysym == 'End':
                canvas.yview_moveto(1)

        def bind_scroll_events_recursive(widget):
            """Recursively bind scroll events to all child widgets"""
            widget.bind("<MouseWheel>", on_mouse_wheel)
            widget.bind("<Key-Up>", on_key_scroll)
            widget.bind("<Key-Down>", on_key_scroll)
            widget.bind("<Key-Page_Up>", on_key_scroll)
            widget.bind("<Key-Page_Down>", on_key_scroll)
            widget.bind("<Key-Home>", on_key_scroll)
            widget.bind("<Key-End>", on_key_scroll)
            for child in widget.winfo_children():
                bind_scroll_events_recursive(child)

        # Bind to canvas and container
        canvas.bind("<MouseWheel>", on_mouse_wheel)
        container.bind("<MouseWheel>", on_mouse_wheel)
        
        # Enable focus for keyboard scrolling
        canvas.focus_set()
        container.focus_set()
        
        # Bind to all child widgets after they're created
        def delayed_bind():
            bind_scroll_events_recursive(self.scrollable_frame)
            bind_scroll_events_recursive(container)
        
        self.parent.after(Constants.MOUSE_WHEEL_BIND_DELAY_MS, delayed_bind)
        
        # Store references for later use
        self.canvas = canvas
        self.container = container
        self.bind_scroll_events_recursive = bind_scroll_events_recursive

        return self.scrollable_frame

    def create_all_sections(self) -> dict:
        """Create all settings sections and return them as a dict"""
        if not self.scrollable_frame:
            raise ValueError("Must create scrollable panel first")
        
        sections = {}
        
        sections['input'] = InputSettingsSection(
            self.scrollable_frame, self.settings_manager, self.callbacks['browse_input'])
        sections['input'].create_frame()
        
        sections['export'] = ExportSettingsSection(
            self.scrollable_frame, self.settings_manager, 
            self.callbacks['browse_output'], self.callbacks['update_controls'])
        sections['export'].create_frame()
        
        sections['model'] = ModelSettingsSection(
            self.scrollable_frame, self.settings_manager, self.callbacks['model_change'])
        sections['model'].create_frame()
        
        sections['processing'] = ProcessingOptionsSection(
            self.scrollable_frame, self.settings_manager, 
            self.callbacks['settings_change'], self.callbacks['alpha_matting_update'])
        sections['processing'].create_frame()
        
        sections['cpu'] = CPUSettingsSection(
            self.scrollable_frame, self.settings_manager, self.callbacks['resize_update'], 
            self.callbacks.get('settings_change'))
        sections['cpu'].create_frame()
        
        sections['monitor'] = ResourceMonitorSection(
            self.scrollable_frame, self.settings_manager)
        sections['monitor'].create_frame()
        
        # Bind mouse wheel to all newly created widgets
        self.refresh_mouse_wheel_bindings()
        
        return sections
    
    def refresh_mouse_wheel_bindings(self):
        """Refresh scroll bindings for all widgets in the scrollable frame"""
        if hasattr(self, 'bind_scroll_events_recursive') and hasattr(self, 'scrollable_frame'):
            self.bind_scroll_events_recursive(self.scrollable_frame)
            if hasattr(self, 'container'):
                self.bind_scroll_events_recursive(self.container)


class PreviewPanel:
    """Container for preview, zoom controls, file list, and action buttons"""
    def __init__(self, parent, settings_manager, callbacks):
        self.parent = parent
        self.settings_manager = settings_manager
        self.callbacks = callbacks
        self.widgets = {}

    def create_panel(self) -> tk.Widget:
        """Create the preview panel container"""
        container = ttk.Frame(self.parent)
        container.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, pady=0)
        
        # Create preview section
        self.create_preview_section(container)
        
        # Create file list section
        self.create_file_list_section(container)
        
        # Create action buttons
        self.create_action_buttons(container)
        
        return container

    def create_preview_section(self, parent):
        """Create the preview section with canvas and controls"""
        preview_frame = ttk.LabelFrame(parent, text="Preview", padding="5")
        preview_frame.pack(fill=tk.BOTH, expand=True)

        # Canvas with scrollbars
        canvas_frame = ttk.Frame(preview_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.widgets['preview_canvas'] = tk.Canvas(canvas_frame, bg=Constants.PREVIEW_CANVAS_BG)
        v_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.widgets['preview_canvas'].yview)
        h_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.widgets['preview_canvas'].xview)

        self.widgets['preview_canvas'].configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.widgets['preview_canvas'].pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Zoom controls
        zoom_frame = ttk.Frame(preview_frame)
        zoom_frame.pack(fill=tk.X, pady=5)
        ttk.Label(zoom_frame, text="Zoom:").pack(side=tk.LEFT, padx=5)

        self.widgets['zoom_var'] = tk.DoubleVar(value=Constants.DEFAULT_ZOOM)
        self.widgets['zoom_scale'] = ttk.Scale(zoom_frame, from_=Constants.MIN_ZOOM, to=Constants.MAX_ZOOM, 
                                             variable=self.widgets['zoom_var'], orient=tk.HORIZONTAL, 
                                             length=200, command=self.callbacks['update_zoom'])
        self.widgets['zoom_scale'].pack(side=tk.LEFT, padx=5)

        self.widgets['zoom_label'] = ttk.Label(zoom_frame, text="100%")
        self.widgets['zoom_label'].pack(side=tk.LEFT, padx=5)

        ttk.Button(zoom_frame, text="Fit", command=self.callbacks['fit_to_window'], width=8).pack(side=tk.LEFT, padx=5)
        ttk.Button(zoom_frame, text="1:1", command=self.callbacks['zoom_actual_size'], width=8).pack(side=tk.LEFT, padx=5)
        
        # Original image toggle
        self.widgets['show_original_var'] = tk.BooleanVar(value=False)
        original_toggle = ttk.Checkbutton(zoom_frame, text="Show Original", 
                                        variable=self.widgets['show_original_var'],
                                        command=self.callbacks['toggle_original'])
        original_toggle.pack(side=tk.LEFT, padx=5)

        # Bind canvas events
        self.widgets['preview_canvas'].bind("<MouseWheel>", self.callbacks['on_mouse_wheel'])
        self.widgets['preview_canvas'].bind("<Button-1>", self.callbacks['start_pan'])
        self.widgets['preview_canvas'].bind("<B1-Motion>", self.callbacks['do_pan'])

    def create_file_list_section(self, parent):
        """Create the file list section"""
        list_frame = ttk.LabelFrame(parent, text="Image Files", padding="5")
        list_frame.pack(fill=tk.X, pady=5)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)

        self.widgets['file_listbox'] = tk.Listbox(list_frame, height=6, yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.widgets['file_listbox'].yview)
        self.widgets['file_listbox'].pack(side=tk.LEFT, fill=tk.X, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.widgets['file_listbox'].bind("<<ListboxSelect>>", self.callbacks['file_selected'])

        # Current file label
        self.widgets['current_file_var'] = tk.StringVar(value="Current: None")
        self.widgets['current_file_label'] = ttk.Label(list_frame, textvariable=self.widgets['current_file_var'])
        # Note: This label is packed elsewhere

    def create_action_buttons(self, parent):
        """Create action buttons"""
        actions_frame = ttk.Frame(parent)
        actions_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10,0))
        
        # Current file display
        self.widgets['current_file_label'] = ttk.Label(actions_frame, textvariable=self.widgets['current_file_var'])
        self.widgets['current_file_label'].pack(pady=(0, 5))
        
        # Process single image button
        self.widgets['process_single_button'] = ttk.Button(actions_frame, text="Process Selected Image", 
                                                         command=self.callbacks['process_single_image'], state=tk.DISABLED)
        self.widgets['process_single_button'].pack(pady=(0, 10))
        
        # Action buttons
        button_frame = ttk.Frame(actions_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.widgets['scan_button'] = ttk.Button(button_frame, text="Scan Folder", command=self.callbacks['scan_folder'])
        self.widgets['scan_button'].pack(side=tk.LEFT, padx=5)
        
        self.widgets['process_button'] = ttk.Button(button_frame, text="Process All", command=self.callbacks['start_processing'])
        self.widgets['process_button'].pack(side=tk.LEFT, padx=5)
        
        self.widgets['stop_button'] = ttk.Button(button_frame, text="Stop", command=self.callbacks['stop_processing'], state=tk.DISABLED)
        self.widgets['stop_button'].pack(side=tk.LEFT, padx=5)
        
        # Progress bar
        self.widgets['progress_var'] = tk.DoubleVar()
        self.widgets['progress'] = ttk.Progressbar(actions_frame, variable=self.widgets['progress_var'], maximum=100)
        self.widgets['progress'].pack(fill=tk.X, pady=(0, 5))
        
        # Status label
        self.widgets['status_var'] = tk.StringVar(value="Ready")
        self.widgets['status_label'] = ttk.Label(actions_frame, textvariable=self.widgets['status_var'])
        self.widgets['status_label'].pack()