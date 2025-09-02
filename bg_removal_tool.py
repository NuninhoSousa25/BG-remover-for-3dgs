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
            'process_single_image': self.process_single_image
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
        self.image_processor.refresh_processors()
        self.refresh_preview_debounced()
    
    def browse_output(self):
        folder = filedialog.askdirectory(title="Select Custom Output Folder")
        if folder:
            self.settings_manager.custom_output_folder.set(folder)
    
    def process_single_image(self):
        """Process the currently selected image"""
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
        
    def generate_preview_thread(self, input_path):
        photo, pil_image, status = self.image_processor.generate_preview(input_path)
        ThreadUtils.safe_queue_put(self.preview_queue, (photo, pil_image, status, None))
        
    def check_preview_queue(self):
        try:
            photo, pil_image, status, _ = ThreadUtils.safe_queue_get(self.preview_queue)
            if photo:
                # Save current zoom and scroll position
                current_zoom = SettingsUtils.get_variable_value(self.zoom_var, 1.0)
                scroll_pos = CanvasUtils.get_canvas_scroll_position(self.preview_canvas)
                
                CanvasUtils.safe_canvas_delete(self.preview_canvas, "all")
                self.current_preview = photo
                self.current_pil_image = pil_image
                CanvasUtils.safe_canvas_create_image(self.preview_canvas, 0, 0, 
                                                   self.current_preview, tags="preview_image")
                CanvasUtils.safe_canvas_configure_scroll(self.preview_canvas)
                
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
        selection = self.file_listbox.curselection()
        if selection and not self.processing:
            self.preview_selected()

    def update_zoom(self, value=None):
        zoom = SettingsUtils.get_variable_value(self.zoom_var, 1.0)
        self.zoom_label.config(text=f"{int(zoom * 100)}%")
        if hasattr(self, 'current_pil_image') and self.current_pil_image:
            self.apply_zoom()

    def apply_zoom(self):
        if not hasattr(self, 'current_pil_image') or self.current_pil_image is None: return
        zoom = SettingsUtils.get_variable_value(self.zoom_var, 1.0)
        original_width, original_height = self.current_pil_image.width, self.current_pil_image.height
        new_width, new_height = int(original_width * zoom), int(original_height * zoom)
        if new_width < 1 or new_height < 1: return
        scaled_image = self.current_pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        self.zoomed_preview = ImageTk.PhotoImage(scaled_image)
        CanvasUtils.safe_canvas_delete(self.preview_canvas, "preview_image")
        CanvasUtils.safe_canvas_create_image(self.preview_canvas, 0, 0, 
                                           self.zoomed_preview, tags="preview_image")
        CanvasUtils.safe_canvas_configure_scroll(self.preview_canvas)

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


def main():
    """Main application entry point"""
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