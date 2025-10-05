"""
Main application file for the Background Removal Tool.
Contains the main application controller class.
"""
import os
import sys
from typing import Optional, Tuple, List

# Force CPU-only execution before importing any ML libraries
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['OMP_NUM_THREADS'] = str(min(4, os.cpu_count()))

# Comprehensive CUDA suppression
os.environ['CUDA_DEVICE_ORDER'] = 'PCI_BUS_ID'
os.environ['CUDA_DEVICE_MAX_CONNECTIONS'] = '1'

# Clear any existing CUDA paths that might interfere
cuda_vars = [k for k in os.environ.keys() if 'CUDA' in k]
for var in cuda_vars:
    if var != 'CUDA_VISIBLE_DEVICES':  # Keep our empty setting
        del os.environ[var]

# Suppress ONNX Runtime logging completely
os.environ['ORT_LOGGING_LEVEL'] = '4'  # No logging at all
os.environ['ONNXRUNTIME_LOG_SEVERITY_LEVEL'] = '4'

# Disable ONNX Runtime GPU providers completely
os.environ['ORT_DISABLE_TRT'] = '1'
os.environ['ORT_DISABLE_CUDA'] = '1'

import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from PIL import Image, ImageTk, ImageOps
import threading
import queue
import time
import multiprocessing

# Try to import tkinterdnd2 for drag and drop support
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DRAG_DROP_AVAILABLE = True
except ImportError:
    DRAG_DROP_AVAILABLE = False
    TkinterDnD = None

try:
    import piexif
except ImportError:
    piexif = None

# Import from our modules
from ui import Constants, SettingsPanel, PreviewPanel, ToolTip
from settings import SettingsManager
from processor import ImageProcessorAdapter
from business_logic import ProjectManager, BatchProcessor, ProcessingSettings
from utils import (UIUtils, FileUtils, SystemUtils, ImageUtils, ValidationUtils, 
                   PerformanceUtils, WidgetUtils, ThreadUtils, SettingsUtils, CanvasUtils)


class BackgroundRemovalApp:
    """Main application controller"""
    def __init__(self, root):
        self.root = root
        self.root.title("Batch Background Removal Tool - Loading...")
        self.root.geometry(f"{Constants.WINDOW_WIDTH}x{Constants.WINDOW_HEIGHT}")
        
        # Apply simple black & white theme
        self.root.configure(bg=Constants.BG_COLOR)
        
        # Configure ttk style for clean black & white theme
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Configure ttk styles
        self.style.configure('TLabel', background=Constants.BG_COLOR, foreground=Constants.FG_COLOR)
        self.style.configure('TFrame', background=Constants.BG_COLOR)
        self.style.configure('TLabelFrame', background=Constants.BG_COLOR, foreground=Constants.FG_COLOR)
        self.style.configure('TButton', background=Constants.BUTTON_BG, foreground=Constants.BUTTON_FG)
        self.style.configure('TEntry', fieldbackground=Constants.ENTRY_BG, foreground=Constants.ENTRY_FG)
        self.style.configure('TCombobox', fieldbackground=Constants.ENTRY_BG, foreground=Constants.ENTRY_FG)
        self.style.configure('TProgressbar', background=Constants.ACCENT_COLOR)
        
        # Initialize basic components first
        self.preview_queue = queue.Queue()
        self.files_to_process = []
        self.debounce_timer = None
        self.processing = False
        self.image_processor = None  # Lazy load this
        
        # Create UI immediately for responsive feel
        self.settings_manager = SettingsManager()
        self.create_ui()
        
        # Show loading status
        self.status_var.set("Loading AI model... (this may take a moment)")
        
        # Initialize heavy components in background
        self.root.after(50, self.lazy_init_processor)
        
        # Start UI update loops
        self.root.after(Constants.PREVIEW_CHECK_INTERVAL_MS, self.check_preview_queue)
        self.root.after(Constants.RESOURCE_UPDATE_INTERVAL_MS, self.update_resource_monitor)
        self.update_export_controls()
        self.update_resize_controls()
        self.update_alpha_matting_controls()
    
    def lazy_init_processor(self):
        """Initialize the image processor in background after UI is shown"""
        def init_in_thread():
            try:
                # This is the slow part - loading the AI model
                self.image_processor = ImageProcessorAdapter(self.settings_manager)
                
                # Update UI on main thread
                self.root.after(0, self.on_processor_ready)
            except Exception as e:
                self.root.after(0, lambda: self.on_processor_error(str(e)))
        
        # Run in background thread to keep UI responsive
        ThreadUtils.run_in_background(init_in_thread, name="processor-init")
    
    def on_processor_ready(self):
        """Called when processor is ready"""
        self.root.title("Batch Background Removal Tool")
        self.status_var.set("Ready - Select input folder to begin")
        
        # Enable buttons that require processor
        WidgetUtils.set_widget_state(self.scan_button, True)
        WidgetUtils.set_widget_state(self.process_button, True)
    
    def on_processor_error(self, error_msg):
        """Called when processor initialization fails"""
        self.root.title("Batch Background Removal Tool - Error")
        self.status_var.set(f"Error loading AI model: {error_msg}")
        UIUtils.show_error_message("Initialization Error", 
            f"Failed to load AI model: {error_msg}")

    def add_tooltip(self, widget, text: str):
        """Add a tooltip to a widget"""
        ToolTip(widget, text)
        
    def create_ui(self):
        """Create the main user interface using modular components"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Define callbacks for UI components
        settings_callbacks = {
            'browse_input': self.browse_input,
            'browse_output': self.browse_output,
            'update_controls': self.update_export_controls,
            'model_change': self.on_model_change,
            'settings_change': self.refresh_preview_debounced,
            'alpha_matting_update': self.update_alpha_matting_controls,
            'resize_update': self.update_resize_controls
        }

        preview_callbacks = {
            'update_zoom': self.update_zoom,
            'fit_to_window': self.fit_to_window,
            'zoom_actual_size': self.zoom_actual_size,
            'on_mouse_wheel': self.on_mouse_wheel,
            'start_pan': self.start_pan,
            'do_pan': self.do_pan,
            'file_selected': self.on_file_selected,
            'scan_folder': self.scan_folder,
            'start_processing': self.start_processing,
            'stop_processing': self.stop_processing,
            'process_single_image': self.process_single_image,
            'toggle_original': self.toggle_original_view
        }

        # Create settings panel (left side)
        self.settings_panel = SettingsPanel(main_frame, self.settings_manager, settings_callbacks)
        self.settings_panel.create_scrollable_panel()
        self.settings_components = self.settings_panel.create_all_sections()

        # Create preview panel (right side) 
        self.preview_panel = PreviewPanel(main_frame, self.settings_manager, preview_callbacks)
        self.preview_panel.create_panel()

        # Setup widget references for easy access
        self._setup_widget_references()

        # Setup keyboard shortcuts
        self._setup_keyboard_shortcuts()

        # Setup drag and drop
        self._setup_drag_and_drop()

    def _setup_widget_references(self):
        """Setup references to commonly used widgets"""
        # Get widgets from the settings components
        export_component = self.settings_components['export']
        cpu_component = self.settings_components['cpu']
        monitor_component = self.settings_components['monitor']
        
        # Settings widget references
        self.custom_folder_entry = export_component.custom_folder_entry
        self.custom_folder_button = export_component.custom_folder_button
        self.subfolder_entry = export_component.subfolder_entry
        self.suffix_entry = export_component.suffix_entry

        # Get widgets from the preview panel
        widgets = self.preview_panel.widgets

        # Preview widget references
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

        # Resource monitor references
        self.cpu_label = monitor_component.cpu_label
        self.memory_label = monitor_component.memory_label

        # Initialize current preview variables
        self.current_preview = None
        self.current_pil_image = None
        self.zoomed_preview = None
        self.current_original_image = None
        
        # Original image toggle reference
        self.show_original_var = widgets['show_original_var']

    def update_resize_controls_wrapper(self):
        """Wrapper to call the CPU component's resize update method"""
        if 'cpu' in self.settings_components:
            self.settings_components['cpu'].update_resize_controls()

    def sync_settings_to_ui(self):
        """Sync settings from business logic to UI variables"""
        # Sync project manager settings to UI
        pm = self.settings_manager.project_manager
        self.settings_manager.input_folder.set(pm.input_folder)
        self.settings_manager.output_location_mode.set(pm.output_location_mode)
        self.settings_manager.custom_output_folder.set(pm.custom_output_folder)
        self.settings_manager.output_subfolder_name.set(pm.output_subfolder_name)
        self.settings_manager.output_naming_mode.set(pm.output_naming_mode)
        self.settings_manager.output_filename_suffix.set(pm.output_filename_suffix)

    def update_export_controls(self):
        loc_mode = SettingsUtils.get_variable_value(self.settings_manager.output_location_mode, "inside")
        is_custom = loc_mode == "custom"
        WidgetUtils.set_widget_state(self.custom_folder_entry, is_custom)
        WidgetUtils.set_widget_state(self.custom_folder_button, is_custom)
        WidgetUtils.set_widget_state(self.subfolder_entry, not is_custom)
        name_mode = SettingsUtils.get_variable_value(self.settings_manager.output_naming_mode, "append_suffix")
        is_append = name_mode == "append_suffix"
        WidgetUtils.set_widget_state(self.suffix_entry, is_append)
    
    def get_output_dir(self):
        """Get output directory using business logic"""
        output_dir = self.settings_manager.project_manager.get_output_directory()
        if not output_dir:
            UIUtils.show_error_message("Error", "A valid input folder and output settings must be configured.")
            return None
        return output_dir
    
    def on_model_change(self):
        """Handle model change - refresh processors and preview"""
        if self.image_processor:
            # Sync the new model name to business logic before refreshing
            self._sync_ui_settings_to_processor()
            self.image_processor.refresh_processors()
            self.refresh_preview_debounced()
        else:
            self.status_var.set("Please wait for AI model to finish loading...")
    
    def browse_output(self):
        folder = filedialog.askdirectory(title="Select Custom Output Folder")
        if folder:
            self.settings_manager.custom_output_folder.set(folder)
    
    def process_single_image(self):
        """Process the currently selected image"""
        if not self.image_processor:
            UIUtils.show_error_message("Error", "Please wait for the AI model to finish loading.")
            return
            
        selection = self.file_listbox.curselection()
        if not selection:
            UIUtils.show_error_message("Error", "Please select an image to process.")
            return
            
        filename = self.files_to_process[selection[0]]
        input_path = os.path.join(self.settings_manager.input_folder.get(), filename)
        
        # Get output directory
        output_dir = self.get_output_dir()
        if not output_dir:
            return
            
        # Ensure output directory exists
        if not FileUtils.ensure_directory_exists(output_dir):
            UIUtils.show_error_message("Error", f"Could not create output directory: {output_dir}")
            return
            
        # Generate output filename
        output_filename = self.settings_manager.get_output_filename(filename)
        output_path = os.path.join(output_dir, output_filename)
        
        # Process the image
        WidgetUtils.set_widget_state(self.process_single_button, False)
        self.status_var.set(f"Processing {filename}...")
        
        def process_thread():
            success = self.image_processor.process_single_image(input_path, output_path)
            status = f"✓ Processed: {filename}" if success else f"✗ Failed: {filename}"
            self.root.after(0, lambda: self.status_var.set(status))
            self.root.after(0, lambda: WidgetUtils.set_widget_state(self.process_single_button, True))
        
        ThreadUtils.run_in_background(process_thread, name=f"process-{filename}")
    
    def start_processing(self):
        """Start batch processing"""
        if not self.image_processor:
            UIUtils.show_error_message("Error", "Please wait for the AI model to finish loading.")
            return
            
        if not self.files_to_process:
            UIUtils.show_error_message("Error", "Please scan a folder with images first.")
            return
        
        output_dir = self.get_output_dir()
        if not output_dir:
            return
        
        if not FileUtils.ensure_directory_exists(output_dir):
            UIUtils.show_error_message("Error", f"Could not create output directory: {output_dir}")
            return
        
        # Prepare file paths
        input_paths = []
        output_paths = []
        
        for filename in self.files_to_process:
            input_path = os.path.join(self.settings_manager.input_folder.get(), filename)
            output_filename = self.settings_manager.get_output_filename(filename)
            output_path = os.path.join(output_dir, output_filename)
            
            input_paths.append(input_path)
            output_paths.append(output_path)
        
        # Update UI state
        self.processing = True
        WidgetUtils.set_widget_state(self.scan_button, False)
        WidgetUtils.set_widget_state(self.process_button, False)
        WidgetUtils.set_widget_state(self.stop_button, True)
        self.progress_var.set(0)
        self.status_var.set("Starting batch processing...")
        self.image_processor.processed_count = 0
        
        # Start processing in background thread
        def process_batch():
            try:
                self.image_processor.process_batch_cpu(input_paths, output_paths, self.update_progress)
            except Exception as e:
                self.root.after(0, lambda: UIUtils.show_error_message("Processing Error", f"An error occurred during processing: {str(e)}"))
            finally:
                self.root.after(0, self.finish_processing)
        
        ThreadUtils.run_in_background(process_batch, name="batch-processing")
    
    def update_progress(self, processed: int, total: int):
        """Update progress bar and status"""
        progress_percent = (processed / total) * 100 if total > 0 else 0
        self.root.after(0, lambda: self.progress_var.set(progress_percent))
        self.root.after(0, lambda: self.status_var.set(f"Processing: {processed}/{total} images ({progress_percent:.1f}%)"))
    
    def finish_processing(self):
        """Finish processing and restore UI state"""
        self.processing = False
        WidgetUtils.set_widget_state(self.scan_button, True)
        WidgetUtils.set_widget_state(self.process_button, True)
        WidgetUtils.set_widget_state(self.stop_button, False)
        
        processed_count = self.image_processor.processed_count
        total_count = len(self.files_to_process)
        
        if self.image_processor.should_stop:
            self.status_var.set(f"Processing stopped. Completed: {processed_count}/{total_count}")
        else:
            self.status_var.set(f"Processing completed! Processed: {processed_count}/{total_count}")
        
        # Reset stop flag
        self.image_processor.should_stop = False
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
        """Generate preview for selected image"""
        selection = self.file_listbox.curselection()
        if not selection or self.processing:
            return
            
        index = selection[0]
        filename = self.files_to_process[index]
        input_path = os.path.join(self.settings_manager.input_folder.get(), filename)
        self.current_file_var.set(f"Current: {filename}")
        self.status_var.set(f"Generating preview for {filename}...")
        ThreadUtils.run_in_background(self.generate_preview_thread, args=(input_path,), 
                                    name=f"preview-{filename}")
        WidgetUtils.set_widget_state(self.process_single_button, True)
    
    def toggle_original_view(self):
        """Toggle between original and processed image view"""
        if hasattr(self, 'current_original_image') and self.current_original_image:
            self.update_preview_display()
        else:
            # If we don't have original cached, refresh the preview
            self.refresh_preview_now()
        
    def generate_preview_thread(self, input_path):
        # Generate processed image
        photo, pil_image, status = self.image_processor.generate_preview(input_path) if self.image_processor else (None, None, "Model loading...")
        
        # Load original image with same transforms as processed image
        try:
            original_pil = self._prepare_original_image_for_display(input_path)
            if original_pil:
                original_photo = ImageTk.PhotoImage(original_pil.copy())
            else:
                original_photo = None
        except Exception:
            original_pil = None
            original_photo = None
            
        ThreadUtils.safe_queue_put(self.preview_queue, (photo, pil_image, status, (original_photo, original_pil)))
    
    def _prepare_original_image_for_display(self, input_path: str) -> Optional[Image.Image]:
        """Prepare original image with same transforms as processed image for accurate comparison"""
        if not self.image_processor or not self.image_processor.image_processor:
            return None
            
        try:
            with Image.open(input_path) as img:
                # Apply the exact same transforms as the processing pipeline
                processor = self.image_processor.image_processor
                
                # Step 1: Handle EXIF orientation (same as processing)
                upright_img, _ = processor._handle_exif_orientation(img)
                
                # Step 2: Apply resize settings (same as processing)
                prepared_img = processor._prepare_image_for_processing(upright_img.copy())
                
                return prepared_img
                
        except Exception as e:
            print(f"Error preparing original image: {e}")
            return None
        
    def check_preview_queue(self):
        try:
            photo, pil_image, status, original_data = ThreadUtils.safe_queue_get(self.preview_queue)
            
            # Store original image data if available
            if original_data:
                original_photo, original_pil = original_data
                self.current_original_photo = original_photo
                self.current_original_image = original_pil
            
            if photo:
                # Save current zoom and scroll position
                current_zoom = SettingsUtils.get_variable_value(self.zoom_var, 1.0)
                scroll_pos = CanvasUtils.get_canvas_scroll_position(self.preview_canvas)
                
                # Store processed image
                self.current_preview = photo
                self.current_pil_image = pil_image
                
                # Update display based on toggle state
                self.update_preview_display()
                
                # Restore zoom and position instead of resetting
                if hasattr(self, 'current_pil_image') and self.current_pil_image and current_zoom > 0:
                    SettingsUtils.set_variable_value(self.zoom_var, current_zoom)
                    self.apply_zoom()
                    # Restore scroll position after zoom is applied
                    self.root.after(10, lambda: CanvasUtils.restore_canvas_scroll_position(
                        self.preview_canvas, scroll_pos['scroll_x'], scroll_pos['scroll_y']))
                else:
                    SettingsUtils.set_variable_value(self.zoom_var, 1.0)
                    self.root.after(100, self.fit_to_window)
            SettingsUtils.set_variable_value(self.status_var, status)
        except Exception:
            pass
        finally:
            self.root.after(100, self.check_preview_queue)
            
    def update_preview_display(self):
        """Update the preview display based on original/processed toggle"""
        show_original = SettingsUtils.get_variable_value(self.show_original_var, False)
        
        if show_original and hasattr(self, 'current_original_photo') and self.current_original_photo:
            # Show original image
            CanvasUtils.safe_canvas_delete(self.preview_canvas, "all")
            CanvasUtils.safe_canvas_create_image(self.preview_canvas, 0, 0, 
                                               self.current_original_photo, tags="preview_image")
            # Update current image reference for zoom operations
            self.current_display_image = self.current_original_image
        elif hasattr(self, 'current_preview') and self.current_preview:
            # Show processed image
            CanvasUtils.safe_canvas_delete(self.preview_canvas, "all")
            CanvasUtils.safe_canvas_create_image(self.preview_canvas, 0, 0, 
                                               self.current_preview, tags="preview_image")
            # Update current image reference for zoom operations
            self.current_display_image = self.current_pil_image
        
        CanvasUtils.safe_canvas_configure_scroll(self.preview_canvas)
            
    def stop_processing(self):
        self.image_processor.should_stop = True
        self.status_var.set("Stopping...")
        
    def update_resize_controls(self):
        """Delegate to the wrapper method"""
        self.update_resize_controls_wrapper()

    def update_alpha_matting_controls(self):
        """Delegate to the processing component's alpha matting controls and refresh preview"""
        if 'processing' in self.settings_components:
            self.settings_components['processing'].update_alpha_matting_controls()
        # Alpha matting toggle affects processing, so refresh preview
        self.refresh_preview_debounced()

    def on_file_selected(self, event):
        """Handle file selection in listbox"""
        if not self.processing:
            self.preview_selected()

    def refresh_preview_debounced(self):
        """Refresh preview after a delay to avoid rapid updates"""
        if self.debounce_timer:
            self.root.after_cancel(self.debounce_timer)
        self.debounce_timer = self.root.after(Constants.DEBOUNCE_DELAY_MS, self.refresh_preview_now)

    def refresh_preview_now(self):
        """Refresh preview after a delay to avoid rapid updates"""
        self.debounce_timer = None
        # Force sync UI settings to business logic before refresh
        self._sync_ui_settings_to_processor()
        selection = self.file_listbox.curselection()
        # Check if we have a selection OR if there's already a preview loaded
        has_current_image = (hasattr(self, 'current_pil_image') and self.current_pil_image is not None)
        
        if (selection or has_current_image) and not self.processing:
            # If no selection but we have a current image, refresh that
            if not selection and has_current_image:
                # Find the current image in the file list and refresh it
                current_file = self.current_file_var.get().replace("Current: ", "")
                if current_file != "None" and current_file in self.files_to_process:
                    index = self.files_to_process.index(current_file)
                    self.file_listbox.selection_set(index)
            self.preview_selected()
    
    def _sync_ui_settings_to_processor(self):
        """Sync UI settings to the image processor's business logic"""
        if not self.image_processor or not self.image_processor.image_processor:
            return
            
        try:
            # Get the processing settings object
            processor = self.image_processor.image_processor
            settings = processor.settings
            
            # Sync processing settings from UI
            settings.alpha_matting = SettingsUtils.get_variable_value(self.settings_manager.alpha_matting, False)
            settings.alpha_matting_foreground_threshold = int(SettingsUtils.get_variable_value(
                self.settings_manager.alpha_matting_foreground_threshold, 240))
            settings.alpha_matting_background_threshold = int(SettingsUtils.get_variable_value(
                self.settings_manager.alpha_matting_background_threshold, 10))
            settings.post_process = SettingsUtils.get_variable_value(self.settings_manager.post_processing, False)
            
            # Sync resize settings
            settings.resize_enabled = SettingsUtils.get_variable_value(self.settings_manager.resize_enabled, True)
            settings.resize_mode = SettingsUtils.get_variable_value(self.settings_manager.resize_mode, "fraction")
            settings.max_image_size = int(SettingsUtils.get_variable_value(self.settings_manager.max_image_size, 800))
            settings.resize_fraction = float(SettingsUtils.get_variable_value(self.settings_manager.resize_fraction, 0.5))
            
            # Sync model settings and check if model changed
            current_model = settings.model_name
            new_model = SettingsUtils.get_variable_value(self.settings_manager.model_name, "u2netp")
            model_changed = current_model != new_model
            settings.model_name = new_model
            
            # If model changed, clear sessions to force new model loading
            if model_changed:
                processor.session_manager.clear_sessions()
            
            # Force refresh of the processor to pick up new settings
            self.image_processor.refresh_processors()
            
        except Exception as e:
            # Silent error handling - settings sync failed but app continues
            pass

    def update_zoom(self, value=None):
        zoom = SettingsUtils.get_variable_value(self.zoom_var, 1.0)
        self.zoom_label.config(text=f"{int(zoom * 100)}%")
        if hasattr(self, 'current_pil_image') and self.current_pil_image:
            self.apply_zoom()

    def apply_zoom(self):
        # Determine which image to zoom based on toggle state
        show_original = SettingsUtils.get_variable_value(self.show_original_var, False)
        current_image = None
        
        if show_original and hasattr(self, 'current_original_image') and self.current_original_image:
            current_image = self.current_original_image
        elif hasattr(self, 'current_pil_image') and self.current_pil_image:
            current_image = self.current_pil_image
            
        if current_image is None: 
            return
            
        zoom = SettingsUtils.get_variable_value(self.zoom_var, 1.0)
        original_width, original_height = current_image.width, current_image.height
        new_width, new_height = int(original_width * zoom), int(original_height * zoom)
        if new_width < 1 or new_height < 1: return
        scaled_image = current_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        self.zoomed_preview = ImageTk.PhotoImage(scaled_image)
        CanvasUtils.safe_canvas_delete(self.preview_canvas, "preview_image")
        CanvasUtils.safe_canvas_create_image(self.preview_canvas, 0, 0, 
                                           self.zoomed_preview, tags="preview_image")
        CanvasUtils.safe_canvas_configure_scroll(self.preview_canvas)

    def fit_to_window(self):
        """Fit image to window using utility calculations"""
        # Determine which image to fit based on toggle state
        show_original = SettingsUtils.get_variable_value(self.show_original_var, False)
        current_image = None
        
        if show_original and hasattr(self, 'current_original_image') and self.current_original_image:
            current_image = self.current_original_image
        elif hasattr(self, 'current_pil_image') and self.current_pil_image:
            current_image = self.current_pil_image
            
        if current_image is None:
            return
            
        canvas_width = self.preview_canvas.winfo_width()
        canvas_height = self.preview_canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1: 
            return
            
        image_size = (current_image.width, current_image.height)
        canvas_size = (canvas_width, canvas_height)
        zoom = UIUtils.calculate_zoom_to_fit(image_size, canvas_size)
        
        SettingsUtils.set_variable_value(self.zoom_var, zoom)
        self.apply_zoom()

    def zoom_actual_size(self):
        SettingsUtils.set_variable_value(self.zoom_var, 1.0)
        self.apply_zoom()

    def on_mouse_wheel(self, event):
        zoom_factor = 1.1 if (event.delta > 0 or event.num == 4) else 0.9
        current_zoom = SettingsUtils.get_variable_value(self.zoom_var, 1.0)
        new_zoom = max(0.1, min(3.0, current_zoom * zoom_factor))
        SettingsUtils.set_variable_value(self.zoom_var, new_zoom)
        self.apply_zoom()

    def start_pan(self, event):
        self.preview_canvas.scan_mark(event.x, event.y)
        self.preview_canvas.config(cursor="fleur")

    def do_pan(self, event):
        self.preview_canvas.scan_dragto(event.x, event.y, gain=1)

    def update_resource_monitor(self):
        """Update CPU and memory usage display"""
        try:
            system_info = SystemUtils.get_system_info()
            cpu_text = f"{system_info['cpu_percent']:.1f}%"
            memory_text = f"{system_info['memory_mb']:.0f} MB"
            
            self.cpu_label.config(text=cpu_text)
            self.memory_label.config(text=memory_text)
        except Exception:
            # Fallback display if system info fails
            self.cpu_label.config(text="N/A")
            self.memory_label.config(text="N/A")
        finally:
            self.root.after(Constants.RESOURCE_UPDATE_INTERVAL_MS, self.update_resource_monitor)

    def _setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts for common actions"""
        self.root.bind('<Left>', self.navigate_previous_image)
        self.root.bind('<Right>', self.navigate_next_image)
        self.root.bind('t', self.toggle_original_shortcut)
        self.root.bind('T', self.toggle_original_shortcut)

    def navigate_previous_image(self, event=None):
        """Navigate to previous image in list"""
        if not self.files_to_process or self.processing:
            return

        selection = self.file_listbox.curselection()
        if selection:
            current_index = selection[0]
            if current_index > 0:
                self.file_listbox.selection_clear(0, tk.END)
                self.file_listbox.selection_set(current_index - 1)
                self.file_listbox.see(current_index - 1)
                self.preview_selected()

    def navigate_next_image(self, event=None):
        """Navigate to next image in list"""
        if not self.files_to_process or self.processing:
            return

        selection = self.file_listbox.curselection()
        if selection:
            current_index = selection[0]
            if current_index < len(self.files_to_process) - 1:
                self.file_listbox.selection_clear(0, tk.END)
                self.file_listbox.selection_set(current_index + 1)
                self.file_listbox.see(current_index + 1)
                self.preview_selected()

    def toggle_original_shortcut(self, event=None):
        """Toggle original view via keyboard shortcut"""
        current_value = SettingsUtils.get_variable_value(self.show_original_var, False)
        SettingsUtils.set_variable_value(self.show_original_var, not current_value)
        self.toggle_original_view()

    def _setup_drag_and_drop(self):
        """Setup drag and drop for images and folders"""
        if not DRAG_DROP_AVAILABLE:
            # Silently skip if drag and drop is not available
            return

        # Enable drag and drop for preview canvas (single images)
        self.preview_canvas.drop_target_register(DND_FILES)
        self.preview_canvas.dnd_bind('<<Drop>>', self.on_drop_image)
        self.preview_canvas.dnd_bind('<<DragEnter>>', self.on_drag_enter_canvas)
        self.preview_canvas.dnd_bind('<<DragLeave>>', self.on_drag_leave_canvas)

        # Enable drag and drop for input folder entry (folders and images)
        # We need to access the input settings component
        if 'input' in self.settings_components:
            input_entry = self.settings_components['input'].input_entry
            input_entry.drop_target_register(DND_FILES)
            input_entry.dnd_bind('<<Drop>>', self.on_drop_folder)
            input_entry.dnd_bind('<<DragEnter>>', self.on_drag_enter_entry)
            input_entry.dnd_bind('<<DragLeave>>', self.on_drag_leave_entry)

    def on_drag_enter_canvas(self, event):
        """Visual feedback when dragging over canvas"""
        self.preview_canvas.config(bg="#e8f4f8")
        return event.action

    def on_drag_leave_canvas(self, event):
        """Remove visual feedback when leaving canvas"""
        self.preview_canvas.config(bg=Constants.PREVIEW_CANVAS_BG)
        return event.action

    def on_drag_enter_entry(self, event):
        """Visual feedback when dragging over input entry"""
        if 'input' in self.settings_components:
            self.settings_components['input'].input_entry.config(bg="#e8f4f8")
        return event.action

    def on_drag_leave_entry(self, event):
        """Remove visual feedback when leaving input entry"""
        if 'input' in self.settings_components:
            self.settings_components['input'].input_entry.config(bg=Constants.ENTRY_BG)
        return event.action

    def on_drop_image(self, event):
        """Handle dropping image file(s) onto preview canvas"""
        self.preview_canvas.config(bg=Constants.PREVIEW_CANVAS_BG)

        if not self.image_processor:
            self.status_var.set("Please wait for AI model to finish loading...")
            return event.action

        # Parse dropped files
        files = self._parse_drop_data(event.data)
        if not files:
            return event.action

        # Filter for image files
        image_files = [f for f in files if os.path.isfile(f) and FileUtils.is_valid_image_file(os.path.basename(f))]

        if not image_files:
            self.status_var.set("No valid image files dropped")
            return event.action

        # Use the first image file
        dropped_image = image_files[0]

        # Get the folder and filename
        folder = os.path.dirname(dropped_image)
        filename = os.path.basename(dropped_image)

        # Set input folder if different
        if folder != self.settings_manager.input_folder.get():
            self.settings_manager.input_folder.set(folder)
            self.scan_folder()

        # Select the dropped file in listbox if it exists in the list
        if filename in self.files_to_process:
            index = self.files_to_process.index(filename)
            self.file_listbox.selection_clear(0, tk.END)
            self.file_listbox.selection_set(index)
            self.file_listbox.see(index)
            self.preview_selected()

        return event.action

    def on_drop_folder(self, event):
        """Handle dropping folder or images onto input entry"""
        if 'input' in self.settings_components:
            self.settings_components['input'].input_entry.config(bg=Constants.ENTRY_BG)

        # Parse dropped files/folders
        files = self._parse_drop_data(event.data)
        if not files:
            return event.action

        # Check if any of the dropped items is a directory
        for item in files:
            if os.path.isdir(item):
                # It's a folder - set as input folder
                self.settings_manager.input_folder.set(item)
                self.root.after(100, self.scan_folder)
                return event.action

        # No folder dropped, check if images were dropped
        image_files = [f for f in files if os.path.isfile(f) and FileUtils.is_valid_image_file(os.path.basename(f))]
        if image_files:
            # Use the parent folder of the first image
            folder = os.path.dirname(image_files[0])
            self.settings_manager.input_folder.set(folder)
            self.root.after(100, self.scan_folder)

        return event.action

    def _parse_drop_data(self, data):
        """Parse drag and drop data into list of file paths"""
        if not data:
            return []

        # Handle different formats of dropped data
        if isinstance(data, (list, tuple)):
            return [str(item).strip('{}') for item in data]

        # String format - could be space-separated or newline-separated
        data_str = str(data).strip()

        # Try to parse as brace-enclosed paths
        import re
        matches = re.findall(r'\{([^}]+)\}', data_str)
        if matches:
            return matches

        # Try space-separated (for single path without braces)
        if ' ' not in data_str or os.path.exists(data_str):
            return [data_str]

        # Fallback to splitting by space
        return [item.strip('{}') for item in data_str.split()]


def main():
    """Main application entry point"""
    # Use TkinterDnD if available for drag and drop support
    if DRAG_DROP_AVAILABLE and TkinterDnD:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    app = BackgroundRemovalApp(root)
    
    # Handle window close event
    def on_closing():
        if app.processing:
            if messagebox.askokcancel("Quit", "Processing is in progress. Stop and quit?"):
                app.image_processor.should_stop = True
                root.after(1000, root.destroy)  # Give time for processing to stop
        else:
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()