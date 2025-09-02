import os
import sys
from typing import Optional, Tuple, List

# Force CPU-only execution before importing any ML libraries
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['OMP_NUM_THREADS'] = str(min(4, os.cpu_count()))

# Clear any existing CUDA paths that might interfere
if 'CUDA_PATH' in os.environ:
    del os.environ['CUDA_PATH']
if 'CUDA_PATH_V12_1' in os.environ:
    del os.environ['CUDA_PATH_V12_1']
if 'CUDA_PATH_V11_8' in os.environ:
    del os.environ['CUDA_PATH_V11_8']

# Suppress ONNX Runtime logging to hide CUDA error messages
os.environ['ORT_LOGGING_LEVEL'] = '3'  # Only show fatal errors

import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from PIL import Image, ImageTk, ImageOps
import threading
import queue
import time
import multiprocessing

try:
    import piexif
except ImportError:
    piexif = None

# Import business logic and utilities
from business_logic import ProjectManager, BatchProcessor, ProcessingSettings
from utils import UIUtils, FileUtils, SystemUtils, ImageUtils, ValidationUtils, PerformanceUtils

# Constants
class Constants:
    # UI Dimensions
    WINDOW_WIDTH = 1200
    WINDOW_HEIGHT = 750
    LEFT_PANEL_WIDTH = 450
    PREVIEW_CANVAS_BG = "light gray"
    
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
                      background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                      font=("tahoma", "8", "normal"), wraplength=300)
        label.pack(ipadx=1)

    def hide_tooltip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()

# UI Component Base Classes
class UIComponent:
    """Base class for all UI components"""
    def __init__(self, parent, settings_manager):
        self.parent = parent
        self.settings_manager = settings_manager
        self.frame = None
        
    def create_frame(self) -> tk.Widget:
        """Create and return the main frame for this component"""
        raise NotImplementedError("Subclasses must implement create_frame()")
        
    def add_tooltip(self, widget, text: str):
        """Helper to add tooltip to a widget"""
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
        ttk.Entry(frame, textvariable=self.settings_manager.input_folder, width=30).grid(row=0, column=1, padx=5, pady=5)
        browse_btn = ttk.Button(frame, text="Browse...", command=self.browse_callback)
        browse_btn.grid(row=0, column=2)
        self.add_tooltip(browse_btn, "Select folder containing images. The folder will be automatically scanned for image files.")
        
        # Overwrite checkbox
        overwrite_cb = ttk.Checkbutton(frame, text="Overwrite existing files", 
                                     variable=self.settings_manager.overwrite_files)
        overwrite_cb.grid(row=1, column=0, columnspan=3, sticky=tk.W)
        self.add_tooltip(overwrite_cb, "If enabled, replaces existing output files. If disabled, skips files that already exist in the output folder.")
        
        self.frame = frame
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
        ttk.Radiobutton(frame, text="Subfolder inside Input", 
                       variable=self.settings_manager.output_location_mode, 
                       value="inside", command=self.update_controls_callback).grid(row=1, column=0, columnspan=3, sticky=tk.W)
        ttk.Radiobutton(frame, text="Subfolder next to Input", 
                       variable=self.settings_manager.output_location_mode, 
                       value="sibling", command=self.update_controls_callback).grid(row=2, column=0, columnspan=3, sticky=tk.W)
        ttk.Radiobutton(frame, text="Custom Folder", 
                       variable=self.settings_manager.output_location_mode, 
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
        ttk.Label(frame, text="Background Type:").grid(row=6, column=0, sticky=tk.W, pady=2)
        bg_combo = ttk.Combobox(frame, textvariable=self.settings_manager.output_background, 
                               values=["Transparent", "White", "Black", "Alpha Matte (W/B)"], 
                               state="readonly", width=18)
        bg_combo.grid(row=6, column=1, columnspan=2, sticky=tk.W, pady=2)
        self.add_tooltip(bg_combo, "Output background type:\n• Transparent: PNG with alpha channel\n• White/Black: Solid color background\n• Alpha Matte (W/B): Grayscale mask image")
        
        # Filename options
        ttk.Label(frame, text="Filename:").grid(row=7, column=0, sticky=tk.W, pady=(8,2))
        ttk.Radiobutton(frame, text="Append Suffix", 
                       variable=self.settings_manager.output_naming_mode, 
                       value="append_suffix", command=self.update_controls_callback).grid(row=8, column=0, columnspan=3, sticky=tk.W)
        ttk.Radiobutton(frame, text="Original Filename", 
                       variable=self.settings_manager.output_naming_mode, 
                       value="original_filename", command=self.update_controls_callback).grid(row=9, column=0, columnspan=3, sticky=tk.W)
        
        # Suffix entry
        ttk.Label(frame, text="Suffix:").grid(row=10, column=0, sticky=tk.W, padx=(20,0))
        self.suffix_entry = ttk.Entry(frame, textvariable=self.settings_manager.output_filename_suffix, width=20)
        self.suffix_entry.grid(row=10, column=1, columnspan=2, sticky=tk.W)
        
        self.frame = frame
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
        ttk.Label(frame, text="Model:").grid(row=0, column=0, sticky=tk.W)
        model_dropdown = ttk.Combobox(frame, textvariable=self.settings_manager.model_name, 
                                    values=list(self.settings_manager.models.keys()), width=20)
        model_dropdown.grid(row=0, column=1, sticky=tk.W)
        model_dropdown.bind('<<ComboboxSelected>>', self.on_model_selected)
        self.add_tooltip(model_dropdown, "Choose the AI model for background removal:\n• u2netp: Fast, lightweight (recommended)\n• u2net: More accurate but slower\n• u2net_human_seg: Best for people\n• isnet-general-use: Highest quality")
        
        # Model description
        self.model_description = ttk.Label(frame, text=self.settings_manager.get_model_description("u2netp"), wraplength=300)
        self.model_description.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # Setup trace callback for model changes via variable
        self.settings_manager.model_name.trace_add('write', self.update_model_description)
        
        self.frame = frame
        return frame
    
    def on_model_selected(self, event=None):
        """Handle model selection from dropdown"""
        self.update_model_description()
        self.model_change_callback()
    
    def update_model_description(self, *args):
        """Update model description when model changes"""
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
        
        # Alpha matting checkbox
        self.alpha_matting_cb = ttk.Checkbutton(frame, text="Use alpha matting", 
                                              variable=self.settings_manager.alpha_matting, 
                                              command=self.alpha_matting_update_callback)
        self.alpha_matting_cb.grid(row=0, column=0, columnspan=3, sticky=tk.W)
        self.add_tooltip(self.alpha_matting_cb, "Alpha matting creates smoother, more natural edges by analyzing pixel transparency. More accurate but slower processing.")
        
        # Post-processing checkbox
        post_process_cb = ttk.Checkbutton(frame, text="Enable post-processing (edge refinement)", 
                                        variable=self.settings_manager.post_process)
        post_process_cb.grid(row=1, column=0, columnspan=3, sticky=tk.W)
        self.add_tooltip(post_process_cb, "Post-processing applies additional edge smoothing and hole filling to clean up the mask. Can improve results on complex images.")
        
        # Alpha matting threshold controls
        self.fg_label_text = ttk.Label(frame, text="Foreground threshold:")
        self.fg_label_text.grid(row=2, column=0, sticky=tk.W, padx=(20,0))
        self.fg_slider = ttk.Scale(frame, from_=0, to=255, 
                                 variable=self.settings_manager.alpha_matting_foreground_threshold, 
                                 orient=tk.HORIZONTAL, length=130, command=self.update_fg_label)
        self.fg_slider.grid(row=2, column=1)
        self.add_tooltip(self.fg_slider, "Foreground threshold (240 = default): Higher values (240-255) include more pixels as foreground. Lower values (200-240) are more selective.")
        self.fg_label = ttk.Label(frame, text="240")
        self.fg_label.grid(row=2, column=2)
        
        self.bg_label_text = ttk.Label(frame, text="Background threshold:")
        self.bg_label_text.grid(row=3, column=0, sticky=tk.W, padx=(20,0))
        self.bg_slider = ttk.Scale(frame, from_=0, to=255, 
                                 variable=self.settings_manager.alpha_matting_background_threshold, 
                                 orient=tk.HORIZONTAL, length=130, command=self.update_bg_label)
        self.bg_slider.grid(row=3, column=1)
        self.add_tooltip(self.bg_slider, "Background threshold (10 = default): Lower values (0-10) exclude more pixels from background. Higher values (10-50) include more as background.")
        self.bg_label = ttk.Label(frame, text="10")
        self.bg_label.grid(row=3, column=2)
        
        # Setup trace callbacks for threshold changes
        self.settings_manager.alpha_matting_foreground_threshold.trace_add('write', self.settings_change_callback)
        self.settings_manager.alpha_matting_background_threshold.trace_add('write', self.settings_change_callback)
        
        self.frame = frame
        return frame
    
    def update_alpha_matting_controls(self):
        """Enable/disable alpha matting threshold controls based on checkbox"""
        enabled = self.settings_manager.alpha_matting.get()
        state = tk.NORMAL if enabled else tk.DISABLED
        
        # Update slider states
        self.fg_slider.config(state=state)
        self.bg_slider.config(state=state)
        
        # Update label colors
        color = "black" if enabled else "gray"
        self.fg_label_text.config(foreground=color)
        self.bg_label_text.config(foreground=color)
        self.fg_label.config(foreground=color)
        self.bg_label.config(foreground=color)
    
    def update_fg_label(self, value=None):
        """Update foreground threshold label"""
        self.fg_label.config(text=str(int(float(self.settings_manager.alpha_matting_foreground_threshold.get()))))
    
    def update_bg_label(self, value=None):
        """Update background threshold label"""
        self.bg_label.config(text=str(int(float(self.settings_manager.alpha_matting_background_threshold.get()))))

class CPUSettingsSection(UIComponent):
    """CPU settings UI component"""
    def __init__(self, parent, settings_manager, resize_update_callback):
        super().__init__(parent, settings_manager)
        self.resize_update_callback = resize_update_callback
        
    def create_frame(self) -> tk.Widget:
        """Create the CPU settings frame"""
        frame = ttk.LabelFrame(self.parent, text="CPU Settings", padding="10")
        frame.pack(fill=tk.X, pady=5, padx=5)
        
        # Thread count
        ttk.Label(frame, text="Max Threads:").grid(row=0, column=0, sticky=tk.W)
        self.thread_spinbox = ttk.Spinbox(frame, from_=Constants.MIN_THREADS, 
                                        to=multiprocessing.cpu_count(), 
                                        textvariable=self.settings_manager.max_threads, 
                                        width=5, state="readonly")
        self.thread_spinbox.grid(row=0, column=1, sticky=tk.W)
        self.add_tooltip(self.thread_spinbox, f"Number of CPU threads to use (1-{multiprocessing.cpu_count()}). More threads = faster processing but higher CPU usage.")
        
        # Memory limit
        ttk.Label(frame, text="Memory Limit (MB):").grid(row=1, column=0, sticky=tk.W)
        self.memory_spinbox = ttk.Spinbox(frame, from_=512, to=8192, increment=256,
                                        textvariable=self.settings_manager.memory_limit_mb, 
                                        width=8, state="readonly")
        self.memory_spinbox.grid(row=1, column=1, sticky=tk.W)
        self.add_tooltip(self.memory_spinbox, "Memory limit before clearing model cache. Lower values save RAM but may slow processing.")
        
        # Batch delay
        ttk.Label(frame, text="Batch Delay (ms):").grid(row=2, column=0, sticky=tk.W)
        self.delay_spinbox = ttk.Spinbox(frame, from_=0, to=1000, increment=50,
                                       textvariable=self.settings_manager.batch_delay_ms, 
                                       width=8, state="readonly")
        self.delay_spinbox.grid(row=2, column=1, sticky=tk.W)
        self.add_tooltip(self.delay_spinbox, "Delay between batch operations (ms). Higher values reduce CPU usage but slow processing.")
        
        # Resize checkbox
        self.resize_cb = ttk.Checkbutton(frame, text="Resize images for faster processing", 
                                       variable=self.settings_manager.resize_enabled, 
                                       command=self.resize_update_callback)
        self.resize_cb.grid(row=3, column=0, columnspan=2, sticky=tk.W)
        self.add_tooltip(self.resize_cb, "Resize large images before processing to improve speed. Smaller images = faster processing but lower quality.")
        
        # Resize mode
        resize_frame = ttk.Frame(frame)
        resize_frame.grid(row=4, column=0, columnspan=2, sticky=tk.W, padx=(20,0))
        ttk.Radiobutton(resize_frame, text="By pixels", 
                       variable=self.settings_manager.resize_mode, 
                       value="pixels", command=self.resize_update_callback).grid(row=0, column=0, sticky=tk.W)
        ttk.Radiobutton(resize_frame, text="By fraction", 
                       variable=self.settings_manager.resize_mode, 
                       value="fraction", command=self.resize_update_callback).grid(row=0, column=1, sticky=tk.W, padx=(10,0))
        
        # Size controls
        self.size_label = ttk.Label(resize_frame, text="Max size:")
        self.size_label.grid(row=1, column=0, sticky=tk.W)
        self.size_spinbox = ttk.Spinbox(resize_frame, from_=400, to=2000, increment=100,
                                      textvariable=self.settings_manager.max_image_size, 
                                      width=8, state="readonly")
        self.size_spinbox.grid(row=1, column=1, sticky=tk.W, padx=(5,0))
        
        self.fraction_label = ttk.Label(resize_frame, text="Fraction:")
        self.fraction_label.grid(row=2, column=0, sticky=tk.W)
        self.fraction_spinbox = ttk.Spinbox(resize_frame, from_=0.1, to=1.0, increment=0.1,
                                          textvariable=self.settings_manager.resize_fraction, 
                                          width=8, state="readonly")
        self.fraction_spinbox.grid(row=2, column=1, sticky=tk.W, padx=(5,0))
        
        self.frame = frame
        return frame
    
    def update_resize_controls(self):
        """Enable/disable resize controls based on settings"""
        resize_enabled = self.settings_manager.resize_enabled.get()
        resize_mode = self.settings_manager.resize_mode.get()
        
        if resize_enabled:
            if resize_mode == "pixels":
                self.size_spinbox.grid()
                self.size_label.grid()
                self.fraction_spinbox.grid_remove()
                self.fraction_label.grid_remove()
            else:
                self.size_spinbox.grid_remove()
                self.size_label.grid_remove()
                self.fraction_spinbox.grid()
                self.fraction_label.grid()
        else:
            self.size_spinbox.grid_remove()
            self.size_label.grid_remove()
            self.fraction_spinbox.grid_remove()
            self.fraction_label.grid_remove()

class ResourceMonitorSection(UIComponent):
    """Resource monitor UI component"""
    def __init__(self, parent, settings_manager):
        super().__init__(parent, settings_manager)
        
    def create_frame(self) -> tk.Widget:
        """Create the resource monitor frame"""
        frame = ttk.LabelFrame(self.parent, text="Resource Monitor", padding="10")
        frame.pack(fill=tk.X, pady=5, padx=5)
        
        # Resource variables
        self.cpu_var = tk.StringVar(value="CPU: 0.0%")
        self.memory_var = tk.StringVar(value="Memory: 0 MB")
        self.avg_time_var = tk.StringVar(value="Avg Time: 0.0s")
        
        # Resource labels
        ttk.Label(frame, textvariable=self.cpu_var).pack(anchor=tk.W)
        ttk.Label(frame, textvariable=self.memory_var).pack(anchor=tk.W)
        ttk.Label(frame, textvariable=self.avg_time_var).pack(anchor=tk.W)
        
        self.frame = frame
        return frame

class SettingsPanel:
    """Container for all settings sections with scrollable support"""
    def __init__(self, parent, settings_manager, callbacks):
        self.parent = parent
        self.settings_manager = settings_manager
        self.callbacks = callbacks
        self.scrollable_frame = None
        self.components = {}
        
    def create_scrollable_panel(self) -> tk.Widget:
        """Create the scrollable left panel container"""
        container = ttk.Frame(self.parent, width=Constants.LEFT_PANEL_WIDTH)
        container.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10), pady=0)
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
        
        def bind_mouse_wheel(widget):
            widget.bind("<MouseWheel>", on_mouse_wheel)
            for child in widget.winfo_children():
                bind_mouse_wheel(child)
        
        canvas.bind("<MouseWheel>", on_mouse_wheel)
        self.parent.after(Constants.MOUSE_WHEEL_BIND_DELAY_MS, 
                         lambda: bind_mouse_wheel(self.scrollable_frame))
        
        return self.scrollable_frame
    
    def create_all_sections(self):
        """Create all settings sections"""
        if not self.scrollable_frame:
            raise ValueError("Must create scrollable panel first")
            
        # Input settings
        self.components['input'] = InputSettingsSection(
            self.scrollable_frame, self.settings_manager, self.callbacks['browse_input'])
        self.components['input'].create_frame()
        
        # Export settings  
        self.components['export'] = ExportSettingsSection(
            self.scrollable_frame, self.settings_manager, 
            self.callbacks['browse_output'], self.callbacks['update_export_controls'])
        self.components['export'].create_frame()
        
        # Model settings
        self.components['model'] = ModelSettingsSection(
            self.scrollable_frame, self.settings_manager, self.callbacks['model_change'])
        self.components['model'].create_frame()
        
        # Processing options
        self.components['processing'] = ProcessingOptionsSection(
            self.scrollable_frame, self.settings_manager, 
            self.callbacks['settings_change'], self.callbacks['alpha_matting_update'])
        self.components['processing'].create_frame()
        
        # CPU settings
        self.components['cpu'] = CPUSettingsSection(
            self.scrollable_frame, self.settings_manager, self.callbacks['resize_update'])
        self.components['cpu'].create_frame()
        
        # Resource monitor
        self.components['resource'] = ResourceMonitorSection(
            self.scrollable_frame, self.settings_manager)
        self.components['resource'].create_frame()
        
        return self.components

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
        self._create_preview_section(container)
        # Create actions section
        self._create_actions_section(container)
        
        return container
    
    def _create_preview_section(self, parent):
        """Create the preview section with canvas and controls"""
        preview_frame = ttk.LabelFrame(parent, text="Preview", padding="10")
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
        
        # Bind canvas events
        self.widgets['preview_canvas'].bind("<MouseWheel>", self.callbacks['on_mouse_wheel'])
        self.widgets['preview_canvas'].bind("<Button-1>", self.callbacks['start_pan'])
        self.widgets['preview_canvas'].bind("<B1-Motion>", self.callbacks['do_pan'])
        
        # File list
        list_frame = ttk.Frame(preview_frame)
        list_frame.pack(fill=tk.X, pady=5)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        
        self.widgets['file_listbox'] = tk.Listbox(list_frame, height=6, yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.widgets['file_listbox'].yview)
        self.widgets['file_listbox'].pack(side=tk.LEFT, fill=tk.X, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.widgets['file_listbox'].bind('<<ListboxSelect>>', self.callbacks['preview_selected'])
        
        # Current file label and process button
        self.widgets['current_file_var'] = tk.StringVar(value="Current: None")
        self.widgets['current_file_label'] = ttk.Label(preview_frame, textvariable=self.widgets['current_file_var'], anchor=tk.W)
        self.widgets['current_file_label'].pack(fill=tk.X, pady=(5, 0))
        
        self.widgets['process_single_button'] = ttk.Button(preview_frame, text="Process Selected Image", 
                                                         command=self.callbacks['process_single_image'], state=tk.DISABLED)
        self.widgets['process_single_button'].pack(pady=5)
    
    def _create_actions_section(self, parent):
        """Create the actions section with buttons and progress"""
        actions_frame = ttk.LabelFrame(parent, text="Actions", padding="10")
        actions_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10,0))
        
        # Action buttons
        button_frame = ttk.Frame(actions_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.widgets['scan_button'] = ttk.Button(button_frame, text="Scan Folder", command=self.callbacks['scan_folder'])
        self.widgets['scan_button'].pack(side=tk.LEFT, padx=5)
        
        self.widgets['process_button'] = ttk.Button(button_frame, text="Process All", command=self.callbacks['start_processing'])
        self.widgets['process_button'].pack(side=tk.LEFT, padx=5)
        
        self.widgets['stop_button'] = ttk.Button(button_frame, text="Stop", command=self.callbacks['stop_processing'], state=tk.DISABLED)
        self.widgets['stop_button'].pack(side=tk.LEFT, padx=5)
        
        # Progress bar and status
        self.widgets['progress_var'] = tk.DoubleVar()
        self.widgets['progress'] = ttk.Progressbar(actions_frame, variable=self.widgets['progress_var'], maximum=100)
        self.widgets['progress'].pack(fill=tk.X, pady=5)
        
        self.widgets['status_var'] = tk.StringVar(value="Ready")
        self.widgets['status_label'] = ttk.Label(actions_frame, textvariable=self.widgets['status_var'])
        self.widgets['status_label'].pack(fill=tk.X, pady=5)

class SettingsManager:
    """UI wrapper for business logic settings"""
    def __init__(self):
        # Initialize business logic
        self.project_manager = ProjectManager()
        
        # UI Variables linked to business logic
        self.input_folder = tk.StringVar()
        self.overwrite_files = tk.BooleanVar(value=False)
        self.post_process = tk.BooleanVar(value=False)
        self.model_name = tk.StringVar(value="u2netp")
        self.alpha_matting = tk.BooleanVar(value=False)
        self.alpha_matting_foreground_threshold = tk.IntVar(value=Constants.DEFAULT_ALPHA_FG_THRESHOLD)
        self.alpha_matting_background_threshold = tk.IntVar(value=Constants.DEFAULT_ALPHA_BG_THRESHOLD)
        self.resize_enabled = tk.BooleanVar(value=True)
        self.resize_mode = tk.StringVar(value="fraction")
        self.max_image_size = tk.IntVar(value=Constants.DEFAULT_MAX_IMAGE_SIZE)
        self.resize_fraction = tk.DoubleVar(value=Constants.DEFAULT_RESIZE_FRACTION)
        self.max_threads = tk.IntVar(value=min(Constants.DEFAULT_MAX_THREADS, multiprocessing.cpu_count()))
        self.memory_limit_mb = tk.IntVar(value=Constants.DEFAULT_MEMORY_LIMIT_MB)
        self.batch_delay_ms = tk.IntVar(value=Constants.DEFAULT_BATCH_DELAY_MS)
        self.output_location_mode = tk.StringVar(value="inside")
        self.custom_output_folder = tk.StringVar(value="")
        self.output_subfolder_name = tk.StringVar(value="masks")
        self.output_background = tk.StringVar(value="Alpha Matte (W/B)")
        self.output_naming_mode = tk.StringVar(value="append_suffix")
        self.output_filename_suffix = tk.StringVar(value="_mask")
        
        # Setup variable traces to sync with business logic
        self._setup_variable_traces()
    
    def _setup_variable_traces(self):
        """Setup traces to sync UI variables with business logic"""
        self.input_folder.trace_add('write', self._sync_input_folder)
        self.overwrite_files.trace_add('write', self._sync_overwrite_files)
        self.model_name.trace_add('write', self._sync_model_settings)
        self.alpha_matting.trace_add('write', self._sync_processing_settings)
        self.alpha_matting_foreground_threshold.trace_add('write', self._sync_processing_settings)
        self.alpha_matting_background_threshold.trace_add('write', self._sync_processing_settings)
        self.post_process.trace_add('write', self._sync_processing_settings)
        self.resize_enabled.trace_add('write', self._sync_processing_settings)
        self.resize_mode.trace_add('write', self._sync_processing_settings)
        self.max_image_size.trace_add('write', self._sync_processing_settings)
        self.resize_fraction.trace_add('write', self._sync_processing_settings)
        self.max_threads.trace_add('write', self._sync_processing_settings)
        self.memory_limit_mb.trace_add('write', self._sync_processing_settings)
        self.batch_delay_ms.trace_add('write', self._sync_processing_settings)
        self.output_location_mode.trace_add('write', self._sync_output_settings)
        self.custom_output_folder.trace_add('write', self._sync_output_settings)
        self.output_subfolder_name.trace_add('write', self._sync_output_settings)
        self.output_background.trace_add('write', self._sync_output_settings)
        self.output_naming_mode.trace_add('write', self._sync_output_settings)
        self.output_filename_suffix.trace_add('write', self._sync_output_settings)
    
    def _sync_input_folder(self, *args):
        """Sync input folder with business logic"""
        self.project_manager.set_input_folder(self.input_folder.get())
    
    def _sync_overwrite_files(self, *args):
        """Sync overwrite setting"""
        self.project_manager.overwrite_files = self.overwrite_files.get()
    
    def _sync_model_settings(self, *args):
        """Sync model settings with business logic"""
        self.project_manager.processing_settings.model_name = self.model_name.get()
    
    def _sync_processing_settings(self, *args):
        """Sync processing settings with business logic"""
        settings = self.project_manager.processing_settings
        settings.alpha_matting = self.alpha_matting.get()
        settings.alpha_matting_foreground_threshold = self.alpha_matting_foreground_threshold.get()
        settings.alpha_matting_background_threshold = self.alpha_matting_background_threshold.get()
        settings.post_process = self.post_process.get()
        settings.resize_enabled = self.resize_enabled.get()
        settings.resize_mode = self.resize_mode.get()
        settings.max_image_size = self.max_image_size.get()
        settings.resize_fraction = self.resize_fraction.get()
        settings.max_threads = self.max_threads.get()
        settings.memory_limit_mb = self.memory_limit_mb.get()
        settings.batch_delay_ms = self.batch_delay_ms.get()
    
    def _sync_output_settings(self, *args):
        """Sync output settings with business logic"""
        self.project_manager.output_location_mode = self.output_location_mode.get()
        self.project_manager.custom_output_folder = self.custom_output_folder.get()
        self.project_manager.output_subfolder_name = self.output_subfolder_name.get()
        self.project_manager.processing_settings.background_type = self.output_background.get()
        self.project_manager.output_naming_mode = self.output_naming_mode.get()
        self.project_manager.output_filename_suffix = self.output_filename_suffix.get()
    
    @property
    def models(self):
        """Get available models"""
        return self.project_manager.processing_settings.available_models
    
    def get_model_description(self, model_name: str) -> str:
        """Get model description"""
        return self.project_manager.processing_settings.get_model_description(model_name)

class ImageProcessorAdapter:
    """Adapter to bridge UI and business logic for image processing"""
    def __init__(self, settings_manager):
        self.settings_manager = settings_manager
        self.batch_processor = None
        self.image_processor = None
        self._init_processors()
    
    def _init_processors(self):
        """Initialize processors with current settings"""
        project_manager = self.settings_manager.project_manager
        self.batch_processor = BatchProcessor(project_manager.processing_settings)
        self.image_processor = self.batch_processor.image_processor
    
    @property
    def should_stop(self):
        """Check if processing should stop"""
        return self.batch_processor.should_stop if self.batch_processor else False
    
    @should_stop.setter
    def should_stop(self, value):
        """Set stop flag"""
        if self.batch_processor:
            if value:
                self.batch_processor.stop_processing()
            else:
                self.batch_processor.should_stop = False
    
    @property
    def processed_count(self):
        """Get processed image count"""
        return self.image_processor.processed_count if self.image_processor else 0
    
    @processed_count.setter
    def processed_count(self, value):
        """Set processed count"""
        if self.image_processor:
            self.image_processor.processed_count = value
    
    @property
    def processing_times(self):
        """Get processing times list"""
        return self.image_processor.processing_times if self.image_processor else []
    
    def cleanup_sessions(self):
        """Clean up processing sessions"""
        if self.image_processor:
            self.image_processor.session_manager.clear_sessions()
    
    def process_single_image(self, input_path: str, output_path: str) -> bool:
        """Process a single image"""
        if piexif is None and '.jpg' in input_path.lower():
            UIUtils.show_warning_message("Missing Library", 
                "The 'piexif' library is not installed. EXIF orientation data in JPEGs cannot be read, which may cause rotation issues.")
        
        if not self.image_processor:
            return False
            
        success, message = self.image_processor.process_single_image(input_path, output_path)
        if not success:
            print(f"Processing failed: {message}")
        return success
    
    def process_batch_cpu(self, image_paths: List[str], output_paths: List[str], 
                         progress_callback=None):
        """Process batch of images"""
        if not self.batch_processor:
            return
            
        def progress_wrapper(processed, total):
            if progress_callback:
                progress_callback(processed, total)
        
        self.batch_processor.process_batch(image_paths, output_paths, progress_wrapper)
    
    def generate_preview(self, input_path: str) -> Tuple[Optional[ImageTk.PhotoImage], Optional[Image.Image], str]:
        """Generate preview of processed image"""
        if not self.image_processor:
            return None, None, "Processor not initialized"
            
        try:
            composite, status = self.image_processor.generate_preview(input_path)
            if composite:
                # Create thumbnail for UI display
                composite.thumbnail(Constants.PREVIEW_THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(composite)
                return photo, composite, status
            else:
                return None, None, status
        except Exception as e:
            return None, None, f"Error generating preview: {str(e)}"

class BackgroundRemovalApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Batch Background Removal Tool")
        self.root.geometry(f"{Constants.WINDOW_WIDTH}x{Constants.WINDOW_HEIGHT}")
        self.settings_manager = SettingsManager()
        self.image_processor = ImageProcessorAdapter(self.settings_manager)
        self.preview_queue = queue.Queue()
        self.files_to_process = []
        self.debounce_timer = None
        self.processing = False
        self.create_ui()
        self.root.after(Constants.PREVIEW_CHECK_INTERVAL_MS, self.check_preview_queue)
        self.root.after(Constants.RESOURCE_UPDATE_INTERVAL_MS, self.update_resource_monitor)
        self.update_export_controls()
        self.update_resize_controls()
        self.update_alpha_matting_controls()
    
    def add_tooltip(self, widget, text: str):
        """Add a tooltip to a widget"""
        ToolTip(widget, text)
        
    def create_ui(self):
        """Create the main user interface using modular components"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Setup callback dictionaries for the UI components
        settings_callbacks = {
            'browse_input': self.browse_input,
            'browse_output': self.browse_output,
            'update_export_controls': self.update_export_controls,
            'model_change': self.on_model_change,
            'settings_change': self.on_settings_change,
            'alpha_matting_update': self.update_alpha_matting_controls_wrapper,
            'resize_update': self.update_resize_controls_wrapper
        }
        
        preview_callbacks = {
            'update_zoom': self.update_zoom,
            'fit_to_window': self.fit_to_window,
            'zoom_actual_size': self.zoom_actual_size,
            'on_mouse_wheel': self.on_mouse_wheel,
            'start_pan': self.start_pan,
            'do_pan': self.do_pan,
            'preview_selected': self.preview_selected,
            'process_single_image': self.process_single_image_action,
            'scan_folder': self.scan_folder,
            'start_processing': self.start_processing,
            'stop_processing': self.stop_processing
        }
        
        # Create settings panel (left side)
        self.settings_panel = SettingsPanel(main_frame, self.settings_manager, settings_callbacks)
        self.settings_panel.create_scrollable_panel()
        self.settings_components = self.settings_panel.create_all_sections()
        
        # Create preview panel (right side) 
        self.preview_panel = PreviewPanel(main_frame, self.settings_manager, preview_callbacks)
        self.preview_panel.create_panel()
        
        # Store widget references for compatibility with existing methods
        self._setup_widget_references()
    
    def _setup_widget_references(self):
        """Setup widget references for compatibility with existing methods"""
        # Get widgets from the preview panel
        widgets = self.preview_panel.widgets
        
        # Map to the old attribute names for compatibility
        self.preview_canvas = widgets['preview_canvas']
        self.zoom_var = widgets['zoom_var']
        self.zoom_scale = widgets['zoom_scale']
        self.zoom_label = widgets['zoom_label']
        self.file_listbox = widgets['file_listbox']
        self.current_file_var = widgets['current_file_var']
        self.current_file_label = widgets['current_file_label']
        self.process_single_button = widgets['process_single_button']
        self.scan_button = widgets['scan_button']
        self.add_tooltip(self.scan_button, "Manually re-scan the input folder for images. Folder is automatically scanned when selected via Browse.")
        self.process_button = widgets['process_button']
        self.stop_button = widgets['stop_button']
        self.progress_var = widgets['progress_var']
        self.progress = widgets['progress']
        self.status_var = widgets['status_var']
        self.status_label = widgets['status_label']
        
        # Map export settings widgets for compatibility
        export_component = self.settings_components['export']
        self.custom_folder_entry = export_component.custom_folder_entry
        self.custom_folder_button = export_component.custom_folder_button
        self.subfolder_entry = export_component.subfolder_entry
        self.suffix_entry = export_component.suffix_entry
    
    def update_alpha_matting_controls_wrapper(self):
        """Wrapper to call both the component update and the settings change callback"""
        if 'processing' in self.settings_components:
            self.settings_components['processing'].update_alpha_matting_controls()
        self.on_settings_change()
    
    def update_resize_controls_wrapper(self):
        """Wrapper to call the CPU component's resize controls update"""
        if 'cpu' in self.settings_components:
            self.settings_components['cpu'].update_resize_controls()

        
    
    def update_export_naming_defaults(self, event=None):
        """Update naming defaults using business logic"""
        self.settings_manager.project_manager.update_output_naming_defaults()
        # Update UI variables to reflect changes
        self.settings_manager.output_subfolder_name.set(self.settings_manager.project_manager.output_subfolder_name)
        self.settings_manager.output_filename_suffix.set(self.settings_manager.project_manager.output_filename_suffix)

    def update_export_controls(self):
        loc_mode = self.settings_manager.output_location_mode.get()
        is_custom = loc_mode == "custom"
        self.custom_folder_entry.config(state=tk.NORMAL if is_custom else tk.DISABLED)
        self.custom_folder_button.config(state=tk.NORMAL if is_custom else tk.DISABLED)
        self.subfolder_entry.config(state=tk.DISABLED if is_custom else tk.NORMAL)
        name_mode = self.settings_manager.output_naming_mode.get()
        is_append = name_mode == "append_suffix"
        self.suffix_entry.config(state=tk.NORMAL if is_append else tk.DISABLED)
    
    def get_output_dir(self):
        """Get output directory using business logic"""
        output_dir = self.settings_manager.project_manager.get_output_directory()
        if not output_dir:
            UIUtils.show_error_message("Error", "A valid input folder and output settings must be configured.")
        return output_dir

    def get_output_filename(self, input_filename):
        """Get output filename using business logic"""
        return self.settings_manager.project_manager.get_output_path(input_filename)
    
    def browse_output(self):
        folder = filedialog.askdirectory(title="Select Custom Output Folder")
        if folder:
            self.settings_manager.custom_output_folder.set(folder)
            
    def process_single_image_action(self):
        """Process single selected image using business logic"""
        selection = self.file_listbox.curselection()
        if not selection: 
            return
            
        filename = self.files_to_process[selection[0]]
        input_path = os.path.join(self.settings_manager.input_folder.get(), filename)
        output_path = self.get_output_filename(filename)
        
        if not output_path:
            UIUtils.show_error_message("Error", "Could not determine output path")
            return
            
        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if not FileUtils.ensure_directory_exists(output_dir):
            UIUtils.show_error_message("Error", f"Could not create output directory: {output_dir}")
            return
            
        # Check if file exists and overwrite setting
        if not self.settings_manager.overwrite_files.get() and os.path.exists(output_path):
            UIUtils.show_info_message("Info", f"File already exists (overwrite is off):\n{os.path.basename(output_path)}")
            return
            
        self.processing = True
        self.process_single_button.config(state=tk.DISABLED)
        
        def process():
            success = self.image_processor.process_single_image(input_path, output_path)
            if success:
                self.root.after(0, lambda: UIUtils.show_info_message("Success", f"Image saved to:\n{output_path}"))
            else:
                self.root.after(0, lambda: UIUtils.show_error_message("Error", f"Failed to process {filename}."))
            self.root.after(0, self.single_process_complete)
            
        threading.Thread(target=process, daemon=True).start()
        
    def start_processing(self):
        """Start batch processing using business logic"""
        if not self.files_to_process:
            UIUtils.show_error_message("Error", "Please scan a folder with images first.")
            return
            
        # Use business logic to prepare batch processing
        input_paths, output_paths, skipped_files = self.settings_manager.project_manager.prepare_batch_processing()
        
        if not input_paths:
            if skipped_files:
                UIUtils.show_info_message("Info", f"No new files to process. {len(skipped_files)} files already exist and overwrite is disabled.")
            else:
                UIUtils.show_error_message("Error", "No files to process.")
            return
            
        # Show info about skipped files if any
        if skipped_files:
            UIUtils.show_info_message("Info", f"Processing {len(input_paths)} files. Skipping {len(skipped_files)} existing files.")
            
        self.processing = True
        self.image_processor.should_stop = False
        self.scan_button.config(state=tk.DISABLED)
        self.process_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        def process_thread():
            self.image_processor.process_batch_cpu(
                input_paths, output_paths,
                lambda p, t: self.root.after(0, self.update_progress, p, t)
            )
            if not self.image_processor.should_stop:
                processed_count = self.image_processor.processed_count
                self.root.after(0, lambda: UIUtils.show_info_message("Complete", f"Successfully processed {processed_count} images."))
            self.root.after(0, self.processing_complete)
            
        threading.Thread(target=process_thread, daemon=True).start()

    def update_progress(self, processed, total):
        progress = (processed / total) * 100
        self.progress_var.set(progress)
        self.status_var.set(f"Processing {processed}/{total}...")
        
    def single_process_complete(self):
        self.processing = False
        self.process_single_button.config(state=tk.NORMAL)
        self.status_var.set("Ready")

    def processing_complete(self):
        self.processing = False
        self.scan_button.config(state=tk.NORMAL)
        self.process_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.progress_var.set(0)
        self.status_var.set("Ready")
        self.image_processor.processed_count = 0

    def browse_input(self):
        folder = filedialog.askdirectory(title="Select Input Folder")
        if folder:
            self.settings_manager.input_folder.set(folder)
            # Auto-scan the folder after selection if it's valid
            self.root.after(100, self.scan_folder)
            
    def scan_folder(self):
        """Scan folder for images using business logic"""
        input_dir = self.settings_manager.input_folder.get()
        is_valid, message = ValidationUtils.validate_directory_path(input_dir)
        if not is_valid:
            UIUtils.show_error_message("Error", f"Invalid input folder: {message}")
            return
            
        self.files_to_process = FileUtils.scan_image_files(input_dir)
        self.file_listbox.delete(0, tk.END)
        
        for file in self.files_to_process:
            self.file_listbox.insert(tk.END, file)
            
        self.status_var.set(f"Found {len(self.files_to_process)} images")
        if self.files_to_process:
            self.file_listbox.selection_set(0)
            self.preview_selected()
            
    def preview_selected(self, event=None):
        if not self.files_to_process or self.processing:
            return
        selection = self.file_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        filename = self.files_to_process[index]
        input_path = os.path.join(self.settings_manager.input_folder.get(), filename)
        self.current_file_var.set(f"Current: {filename}")
        self.status_var.set(f"Generating preview for {filename}...")
        threading.Thread(target=self.generate_preview_thread, args=(input_path,), daemon=True).start()
        self.process_single_button.config(state=tk.NORMAL)
        
    def generate_preview_thread(self, input_path):
        photo, pil_image, status = self.image_processor.generate_preview(input_path)
        self.preview_queue.put((photo, pil_image, status, None))
        
    def check_preview_queue(self):
        try:
            photo, pil_image, status, _ = self.preview_queue.get_nowait()
            if photo:
                # Save current zoom and scroll position
                current_zoom = self.zoom_var.get()
                scroll_x = self.preview_canvas.canvasx(0)
                scroll_y = self.preview_canvas.canvasy(0)
                
                self.preview_canvas.delete("all")
                self.current_preview = photo
                self.current_pil_image = pil_image
                self.preview_canvas.create_image(0, 0, anchor=tk.NW, image=self.current_preview, tags="preview_image")
                self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all"))
                
                # Restore zoom and position instead of resetting
                if hasattr(self, 'current_pil_image') and self.current_pil_image and current_zoom > 0:
                    self.zoom_var.set(current_zoom)
                    self.apply_zoom()
                    # Restore scroll position after zoom is applied
                    self.root.after(10, lambda: self.restore_scroll_position(scroll_x, scroll_y))
                else:
                    self.zoom_var.set(1.0)
                    self.root.after(100, self.fit_to_window)
            self.status_var.set(status)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.check_preview_queue)
            
    def restore_scroll_position(self, scroll_x, scroll_y):
        """Restore the canvas scroll position"""
        try:
            # Get the current scroll region
            bbox = self.preview_canvas.bbox("all")
            if bbox:
                # Calculate the relative position
                canvas_width = self.preview_canvas.winfo_width()
                canvas_height = self.preview_canvas.winfo_height()
                
                # Restore scroll position
                self.preview_canvas.xview_moveto(scroll_x / max(bbox[2] - bbox[0], canvas_width))
                self.preview_canvas.yview_moveto(scroll_y / max(bbox[3] - bbox[1], canvas_height))
        except Exception:
            # If restoration fails, just continue - better than crashing
            pass
    
    def stop_processing(self):
        self.image_processor.should_stop = True
        self.status_var.set("Stopping...")
        
    def update_resize_controls(self):
        """Delegate to the wrapper method"""
        self.update_resize_controls_wrapper()

    def update_alpha_matting_controls(self):
        """Delegate to the processing component's alpha matting controls"""
        if 'processing' in self.settings_components:
            self.settings_components['processing'].update_alpha_matting_controls()

    def update_model_description(self, *args):
        # This is now handled by the model component itself via callbacks
        pass

    def update_threshold_labels(self, *args):
        # This is now handled by the processing component's threshold label updates
        if 'processing' in self.settings_components:
            processing_component = self.settings_components['processing']
            processing_component.fg_label.config(text=str(self.settings_manager.alpha_matting_foreground_threshold.get()))
            processing_component.bg_label.config(text=str(self.settings_manager.alpha_matting_background_threshold.get()))

    def on_settings_change(self, *args):
        """Called when foreground/background threshold settings change"""
        if self.debounce_timer is not None:
            self.root.after_cancel(self.debounce_timer)
        self.debounce_timer = self.root.after(Constants.DEBOUNCE_DELAY_MS, self.debounced_preview_refresh)

    def on_model_change(self, *args):
        """Called when model selection changes"""
        # Clear session cache to force new model loading
        self.image_processor.cleanup_sessions()
        if self.debounce_timer is not None:
            self.root.after_cancel(self.debounce_timer)
        self.debounce_timer = self.root.after(Constants.DEBOUNCE_DELAY_MS, self.debounced_preview_refresh)

    def debounced_preview_refresh(self):
        """Refresh preview after a delay to avoid rapid updates"""
        self.debounce_timer = None
        selection = self.file_listbox.curselection()
        if selection and not self.processing:
            self.preview_selected()

    def update_zoom(self, value=None):
        zoom = self.zoom_var.get()
        self.zoom_label.config(text=f"{int(zoom * 100)}%")
        if hasattr(self, 'current_pil_image') and self.current_pil_image:
            self.apply_zoom()

    def apply_zoom(self):
        if not hasattr(self, 'current_pil_image') or self.current_pil_image is None: return
        zoom = self.zoom_var.get()
        original_width, original_height = self.current_pil_image.width, self.current_pil_image.height
        new_width, new_height = int(original_width * zoom), int(original_height * zoom)
        if new_width < 1 or new_height < 1: return
        scaled_image = self.current_pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        self.zoomed_preview = ImageTk.PhotoImage(scaled_image)
        self.preview_canvas.delete("preview_image")
        self.preview_canvas.create_image(0, 0, anchor=tk.NW, image=self.zoomed_preview, tags="preview_image")
        self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all"))

    def fit_to_window(self):
        """Fit image to window using utility calculations"""
        if not hasattr(self, 'current_pil_image') or self.current_pil_image is None: 
            return
            
        canvas_width = self.preview_canvas.winfo_width()
        canvas_height = self.preview_canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1: 
            return
            
        image_size = (self.current_pil_image.width, self.current_pil_image.height)
        canvas_size = (canvas_width, canvas_height)
        zoom = UIUtils.calculate_zoom_to_fit(image_size, canvas_size)
        
        self.zoom_var.set(zoom)
        self.apply_zoom()

    def zoom_actual_size(self):
        self.zoom_var.set(1.0)
        self.apply_zoom()

    def on_mouse_wheel(self, event):
        zoom_factor = 1.1 if (event.delta > 0 or event.num == 4) else 0.9
        new_zoom = max(0.1, min(3.0, self.zoom_var.get() * zoom_factor))
        self.zoom_var.set(new_zoom)
        self.apply_zoom()

    def start_pan(self, event):
        self.preview_canvas.scan_mark(event.x, event.y)
        self.preview_canvas.config(cursor="fleur")

    def do_pan(self, event):
        self.preview_canvas.scan_dragto(event.x, event.y, gain=1)
        
    def update_resource_monitor(self):
        """Update resource monitor using utilities"""
        try:
            if 'resource' in self.settings_components:
                resource_component = self.settings_components['resource']
                system_info = SystemUtils.get_system_info()
                
                resource_component.cpu_var.set(f"CPU: {system_info['cpu_percent']:.1f}%")
                resource_component.memory_var.set(f"Memory: {system_info['memory_mb']:.0f} MB")
                
                processing_times = self.image_processor.processing_times
                if processing_times:
                    avg_time = PerformanceUtils.calculate_average_time(list(processing_times))
                    formatted_time = UIUtils.format_time_duration(avg_time)
                    resource_component.avg_time_var.set(f"Avg Time: {formatted_time}")
                    
        except Exception:
            pass
        self.root.after(Constants.RESOURCE_UPDATE_INTERVAL_MS, self.update_resource_monitor)
        
    def on_closing(self):
        self.stop_processing()
        self.image_processor.cleanup_sessions()
        self.root.destroy()

if __name__ == "__main__":
    if piexif is None:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Missing Library", "The 'piexif' library was not found. This is required to fix image orientation.\n\nPlease run 'pip install piexif' in your terminal and restart the application.")
    else:
        root = tk.Tk()
        app = BackgroundRemovalApp(root)
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
        root.mainloop()