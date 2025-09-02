"""
Utility functions for the background removal tool.
Contains common operations and helper functions.
"""
import os
import tkinter as tk
from tkinter import messagebox
from typing import List, Tuple, Optional
from PIL import Image
import psutil
import time


class FileUtils:
    """Utilities for file operations"""
    
    VALID_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp')
    
    @staticmethod
    def is_valid_image_file(filename: str) -> bool:
        """Check if file has valid image extension"""
        return filename.lower().endswith(FileUtils.VALID_IMAGE_EXTENSIONS)
    
    @staticmethod
    def scan_image_files(directory: str) -> List[str]:
        """Scan directory for valid image files"""
        if not directory or not os.path.isdir(directory):
            return []
        
        image_files = []
        try:
            for file in sorted(os.listdir(directory)):
                if FileUtils.is_valid_image_file(file):
                    image_files.append(file)
        except (OSError, PermissionError):
            return []
        
        return image_files
    
    @staticmethod
    def ensure_directory_exists(directory_path: str) -> bool:
        """Ensure directory exists, create if needed"""
        try:
            os.makedirs(directory_path, exist_ok=True)
            return True
        except (OSError, PermissionError):
            return False
    
    @staticmethod
    def file_exists_and_readable(file_path: str) -> bool:
        """Check if file exists and is readable"""
        try:
            return os.path.isfile(file_path) and os.access(file_path, os.R_OK)
        except (OSError, PermissionError):
            return False


class PathUtils:
    """Utilities for path operations"""
    
    @staticmethod
    def get_output_directory(input_dir: str, location_mode: str, subfolder_name: str, custom_dir: str) -> Optional[str]:
        """Generate output directory path based on settings"""
        if not input_dir or not os.path.isdir(input_dir):
            return None
            
        if location_mode == "inside":
            return os.path.join(input_dir, subfolder_name)
        elif location_mode == "sibling":
            parent_dir = os.path.dirname(input_dir)
            return os.path.join(parent_dir, subfolder_name)
        elif location_mode == "custom":
            if not custom_dir or not os.path.isdir(custom_dir):
                return None
            return custom_dir
        
        return None
    
    @staticmethod
    def get_output_filename(input_filename: str, naming_mode: str, suffix: str) -> str:
        """Generate output filename based on settings"""
        base_name = os.path.splitext(input_filename)[0]
        
        if naming_mode == "original_filename":
            return f"{base_name}.png"
        else:  # append_suffix
            return f"{base_name}{suffix}.png"
    
    @staticmethod
    def get_safe_filename(filename: str) -> str:
        """Get a filename safe for the current OS"""
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        safe_name = filename
        for char in invalid_chars:
            safe_name = safe_name.replace(char, '_')
        return safe_name


class ImageUtils:
    """Utilities for image operations"""
    
    @staticmethod
    def get_image_info(image_path: str) -> Optional[Tuple[int, int, str]]:
        """Get basic image information (width, height, mode)"""
        try:
            with Image.open(image_path) as img:
                return img.width, img.height, img.mode
        except Exception:
            return None
    
    @staticmethod
    def should_resize_image(image_size: Tuple[int, int], resize_mode: str, 
                          max_size: int, fraction: float) -> Tuple[bool, Tuple[int, int]]:
        """Determine if image should be resized and calculate new size"""
        width, height = image_size
        
        if resize_mode == "pixels":
            if max(width, height) > max_size:
                # Calculate new size maintaining aspect ratio
                if width > height:
                    new_width = max_size
                    new_height = int(height * (max_size / width))
                else:
                    new_height = max_size
                    new_width = int(width * (max_size / height))
                return True, (new_width, new_height)
        
        elif resize_mode == "fraction":
            if fraction < 1.0:
                new_width = int(width * fraction)
                new_height = int(height * fraction)
                return True, (new_width, new_height)
        
        return False, image_size
    
    @staticmethod
    def create_checkerboard_pattern(size: Tuple[int, int], cell_size: int = 10) -> Image.Image:
        """Create a checkerboard pattern for transparency preview"""
        width, height = size
        result = Image.new('RGBA', size, (255, 255, 255, 255))
        
        for y in range(0, height, cell_size):
            for x in range(0, width, cell_size):
                if (x // cell_size + y // cell_size) % 2 == 0:
                    for dy in range(min(cell_size, height - y)):
                        for dx in range(min(cell_size, width - x)):
                            result.putpixel((x + dx, y + dy), (200, 200, 200, 255))
        
        return result
    
    @staticmethod
    def apply_background_to_image(image: Image.Image, background_type: str) -> Image.Image:
        """Apply specified background to RGBA image"""
        if image.mode != 'RGBA':
            return image
            
        if background_type in ["White", "Black"]:
            # Create solid background
            background = Image.new('RGB', image.size, background_type.lower())
            background.paste(image, (0, 0), image)
            return background
        elif background_type == "Alpha Matte (W/B)":
            # Convert alpha channel to grayscale
            return image.getchannel('A').convert('RGB')
        else:  # Transparent
            return image


class SystemUtils:
    """Utilities for system operations"""
    
    @staticmethod
    def get_system_info() -> dict:
        """Get current system resource information"""
        try:
            cpu_percent = psutil.cpu_percent(interval=None)
            memory_info = psutil.Process().memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            return {
                'cpu_percent': cpu_percent,
                'memory_mb': memory_mb,
                'available_threads': psutil.cpu_count()
            }
        except Exception:
            return {
                'cpu_percent': 0.0,
                'memory_mb': 0.0,
                'available_threads': 1
            }
    
    @staticmethod
    def is_memory_usage_high(current_mb: float, limit_mb: float) -> bool:
        """Check if memory usage exceeds limit"""
        return current_mb > limit_mb
    
    @staticmethod
    def get_optimal_thread_count(max_threads: int) -> int:
        """Get optimal thread count for system"""
        available = psutil.cpu_count() or 1
        return min(max_threads, available)


class ValidationUtils:
    """Utilities for input validation"""
    
    @staticmethod
    def validate_directory_path(path: str) -> Tuple[bool, str]:
        """Validate directory path"""
        if not path:
            return False, "Path cannot be empty"
        if not os.path.exists(path):
            return False, "Path does not exist"
        if not os.path.isdir(path):
            return False, "Path is not a directory"
        if not os.access(path, os.R_OK):
            return False, "Directory is not readable"
        return True, "Valid directory"
    
    @staticmethod
    def validate_image_file(file_path: str) -> Tuple[bool, str]:
        """Validate image file"""
        if not FileUtils.file_exists_and_readable(file_path):
            return False, "File does not exist or is not readable"
        
        if not FileUtils.is_valid_image_file(file_path):
            return False, "File is not a supported image format"
        
        # Try to open image
        try:
            with Image.open(file_path) as img:
                img.verify()
            return True, "Valid image file"
        except Exception as e:
            return False, f"Invalid image file: {str(e)}"
    
    @staticmethod
    def validate_threshold_value(value: int, min_val: int = 0, max_val: int = 255) -> bool:
        """Validate threshold value is within range"""
        return min_val <= value <= max_val


class UIUtils:
    """Utilities for UI operations"""
    
    @staticmethod
    def show_error_message(title: str, message: str):
        """Show error message dialog"""
        messagebox.showerror(title, message)
    
    @staticmethod
    def show_info_message(title: str, message: str):
        """Show info message dialog"""
        messagebox.showinfo(title, message)
    
    @staticmethod
    def show_warning_message(title: str, message: str):
        """Show warning message dialog"""
        messagebox.showwarning(title, message)
    
    @staticmethod
    def ask_yes_no(title: str, message: str) -> bool:
        """Ask yes/no question"""
        return messagebox.askyesno(title, message)
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
    
    @staticmethod
    def format_time_duration(seconds: float) -> str:
        """Format time duration in human readable format"""
        if seconds < 1:
            return f"{seconds*1000:.0f}ms"
        elif seconds < 60:
            return f"{seconds:.1f}s"
        else:
            minutes = int(seconds // 60)
            remaining_seconds = seconds % 60
            return f"{minutes}m {remaining_seconds:.1f}s"
    
    @staticmethod
    def calculate_zoom_to_fit(image_size: Tuple[int, int], canvas_size: Tuple[int, int], 
                            padding: int = 20) -> float:
        """Calculate zoom level to fit image in canvas"""
        img_width, img_height = image_size
        canvas_width, canvas_height = canvas_size
        
        if canvas_width <= padding or canvas_height <= padding:
            return 1.0
            
        available_width = canvas_width - padding
        available_height = canvas_height - padding
        
        zoom_x = available_width / img_width
        zoom_y = available_height / img_height
        
        return min(zoom_x, zoom_y, 1.0)  # Don't zoom beyond 100%


class PerformanceUtils:
    """Utilities for performance monitoring"""
    
    @staticmethod
    def time_function(func):
        """Decorator to time function execution"""
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            print(f"{func.__name__} took {end_time - start_time:.3f} seconds")
            return result
        return wrapper
    
    @staticmethod
    def calculate_average_time(times_list: List[float]) -> float:
        """Calculate average time from list of execution times"""
        if not times_list:
            return 0.0
        return sum(times_list) / len(times_list)
    
    @staticmethod
    def format_performance_stats(processing_times: List[float]) -> dict:
        """Format performance statistics"""
        if not processing_times:
            return {
                'count': 0,
                'avg_time': 0.0,
                'min_time': 0.0,
                'max_time': 0.0,
                'total_time': 0.0
            }
        
        return {
            'count': len(processing_times),
            'avg_time': sum(processing_times) / len(processing_times),
            'min_time': min(processing_times),
            'max_time': max(processing_times),
            'total_time': sum(processing_times)
        }


class WidgetUtils:
    """Utilities for common widget operations"""
    
    @staticmethod
    def create_labeled_entry(parent, text: str, textvariable, row: int, 
                           column: int = 0, width: int = 20, **kwargs):
        """Create a labeled entry widget with consistent layout"""
        import tkinter as tk
        from tkinter import ttk
        
        ttk.Label(parent, text=text).grid(row=row, column=column, sticky=tk.W, pady=2)
        entry = ttk.Entry(parent, textvariable=textvariable, width=width)
        entry.grid(row=row, column=column+1, padx=5, pady=2, **kwargs)
        return entry
    
    @staticmethod
    def create_labeled_button(parent, label_text: str, button_text: str, 
                            command, row: int, column: int = 0, **kwargs):
        """Create a labeled button with consistent layout"""
        import tkinter as tk
        from tkinter import ttk
        
        ttk.Label(parent, text=label_text).grid(row=row, column=column, sticky=tk.W, pady=2)
        button = ttk.Button(parent, text=button_text, command=command)
        button.grid(row=row, column=column+1, padx=5, pady=2, **kwargs)
        return button
    
    @staticmethod
    def create_checkbutton_with_tooltip(parent, text: str, variable, tooltip_text: str, 
                                      row: int, column: int = 0, **kwargs):
        """Create a checkbutton with tooltip"""
        import tkinter as tk
        from tkinter import ttk
        
        cb = ttk.Checkbutton(parent, text=text, variable=variable)
        cb.grid(row=row, column=column, sticky=tk.W, **kwargs)
        # Note: Tooltip will be added externally using add_tooltip method
        return cb, tooltip_text
    
    @staticmethod
    def create_slider_with_labels(parent, from_val: float, to_val: float, 
                                variable, row: int, column: int = 0):
        """Create a slider with value labels"""
        import tkinter as tk
        from tkinter import ttk
        
        slider = ttk.Scale(parent, from_=from_val, to=to_val, variable=variable, orient=tk.HORIZONTAL)
        slider.grid(row=row, column=column, columnspan=2, sticky=tk.W+tk.E, padx=5, pady=2)
        
        label = ttk.Label(parent, text=str(int(variable.get())))
        label.grid(row=row, column=column+2, sticky=tk.W, padx=5)
        
        return slider, label
    
    @staticmethod
    def set_widget_state(widget, enabled: bool):
        """Set widget state (enabled/disabled) safely"""
        import tkinter as tk
        try:
            widget.config(state=tk.NORMAL if enabled else tk.DISABLED)
        except Exception:
            pass
    
    @staticmethod
    def set_widget_color(widget, foreground: str = None, background: str = None):
        """Set widget colors safely"""
        try:
            config_dict = {}
            if foreground:
                config_dict['foreground'] = foreground
            if background:
                config_dict['background'] = background
            if config_dict:
                widget.config(**config_dict)
        except Exception:
            pass


class ThreadUtils:
    """Utilities for threading operations"""
    
    @staticmethod
    def run_in_background(target, args=None, daemon=True, name=None):
        """Run function in background thread"""
        import threading
        
        if args is None:
            args = ()
        
        thread = threading.Thread(target=target, args=args, daemon=daemon, name=name)
        thread.start()
        return thread
    
    @staticmethod
    def safe_queue_put(queue_obj, item, timeout: float = None):
        """Safely put item in queue with timeout"""
        import queue
        try:
            queue_obj.put(item, timeout=timeout)
            return True
        except queue.Full:
            return False
    
    @staticmethod
    def safe_queue_get(queue_obj, timeout: float = None):
        """Safely get item from queue with timeout"""
        import queue
        try:
            return queue_obj.get_nowait() if timeout is None else queue_obj.get(timeout=timeout)
        except queue.Empty:
            return None


class SettingsUtils:
    """Utilities for common settings operations"""
    
    @staticmethod
    def bind_variable_trace(variable, callback, trace_mode='write'):
        """Safely bind variable trace"""
        try:
            variable.trace_add(trace_mode, callback)
        except Exception:
            pass
    
    @staticmethod
    def get_variable_value(variable, default_value=None):
        """Safely get variable value with fallback"""
        try:
            return variable.get()
        except Exception:
            return default_value
    
    @staticmethod
    def set_variable_value(variable, value):
        """Safely set variable value"""
        try:
            variable.set(value)
            return True
        except Exception:
            return False
    
    @staticmethod
    def validate_numeric_range(value, min_val: float, max_val: float, default_val: float = None):
        """Validate numeric value is within range"""
        try:
            num_val = float(value)
            if min_val <= num_val <= max_val:
                return num_val
        except (ValueError, TypeError):
            pass
        
        return default_val if default_val is not None else min_val


class CanvasUtils:
    """Utilities for canvas operations"""
    
    @staticmethod
    def safe_canvas_delete(canvas, *tags):
        """Safely delete canvas items by tags"""
        try:
            for tag in tags:
                canvas.delete(tag)
        except Exception:
            pass
    
    @staticmethod
    def safe_canvas_create_image(canvas, x: int, y: int, image, anchor="nw", tags=None):
        """Safely create canvas image"""
        try:
            return canvas.create_image(x, y, anchor=anchor, image=image, tags=tags)
        except Exception:
            return None
    
    @staticmethod
    def safe_canvas_configure_scroll(canvas, bbox=None):
        """Safely configure canvas scroll region"""
        try:
            if bbox is None:
                bbox = canvas.bbox("all")
            if bbox:
                canvas.configure(scrollregion=bbox)
        except Exception:
            pass
    
    @staticmethod
    def get_canvas_scroll_position(canvas):
        """Get current canvas scroll position"""
        try:
            return {
                'scroll_x': canvas.canvasx(0),
                'scroll_y': canvas.canvasy(0)
            }
        except Exception:
            return {'scroll_x': 0, 'scroll_y': 0}
    
    @staticmethod
    def restore_canvas_scroll_position(canvas, scroll_x: float, scroll_y: float):
        """Restore canvas scroll position"""
        try:
            bbox = canvas.bbox("all")
            if bbox:
                canvas_width = canvas.winfo_width()
                canvas_height = canvas.winfo_height()
                
                canvas.xview_moveto(scroll_x / max(bbox[2] - bbox[0], canvas_width))
                canvas.yview_moveto(scroll_y / max(bbox[3] - bbox[1], canvas_height))
        except Exception:
            pass