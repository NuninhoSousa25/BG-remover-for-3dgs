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