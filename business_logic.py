"""
Business logic for background removal operations.
Separates core processing logic from UI components.
"""
import os
import gc
import time
import threading
import multiprocessing
from typing import Optional, List, Tuple, Callable, Dict, Any
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image, ImageOps
import rembg
from rembg import remove, new_session
import psutil

try:
    import piexif
except ImportError:
    piexif = None

from utils import ImageUtils, SystemUtils, FileUtils, PathUtils, ValidationUtils


class ProcessingSettings:
    """Container for processing settings"""
    
    def __init__(self):
        # Model settings
        self.model_name: str = "u2netp"
        self.available_models = {
            "u2netp": "Lightweight model - Fast processing, good for most images",
            "u2net": "Standard model - Balanced accuracy and speed",
            "u2net_human_seg": "Human segmentation - Best for people and portraits", 
            "isnet-general-use": "High quality model - Slowest but most accurate"
        }
        
        # Alpha matting settings
        self.alpha_matting: bool = False
        self.alpha_matting_foreground_threshold: int = 240
        self.alpha_matting_background_threshold: int = 10
        
        # Post-processing settings
        self.post_process: bool = False
        
        # Resize settings
        self.resize_enabled: bool = True
        self.resize_mode: str = "fraction"  # "pixels" or "fraction"
        self.max_image_size: int = 800
        self.resize_fraction: float = 0.5
        
        # Performance settings
        self.max_threads: int = min(4, multiprocessing.cpu_count())
        self.memory_limit_mb: int = 2048
        self.batch_delay_ms: int = 100
        
        # Output settings
        self.background_type: str = "Alpha Matte (W/B)"  # "Transparent", "White", "Black", "Alpha Matte (W/B)"
    
    def get_model_description(self, model_name: str) -> str:
        """Get description for a model"""
        return self.available_models.get(model_name, "No description available")
    
    def validate_settings(self) -> List[str]:
        """Validate current settings and return any errors"""
        errors = []
        
        if self.model_name not in self.available_models:
            errors.append(f"Invalid model: {self.model_name}")
        
        if not ValidationUtils.validate_threshold_value(self.alpha_matting_foreground_threshold):
            errors.append("Foreground threshold must be between 0 and 255")
            
        if not ValidationUtils.validate_threshold_value(self.alpha_matting_background_threshold):
            errors.append("Background threshold must be between 0 and 255")
        
        if self.max_threads < 1:
            errors.append("Thread count must be at least 1")
            
        if self.memory_limit_mb < 512:
            errors.append("Memory limit must be at least 512 MB")
            
        if self.resize_fraction <= 0 or self.resize_fraction > 1:
            errors.append("Resize fraction must be between 0 and 1")
            
        if self.max_image_size < 100:
            errors.append("Max image size must be at least 100 pixels")
        
        return errors


class SessionManager:
    """Manages AI model sessions for background removal"""
    
    def __init__(self, settings: ProcessingSettings):
        self.settings = settings
        self.session_pool: Dict[int, Any] = {}
        self.lock = threading.Lock()
    
    def _get_cpu_providers(self) -> List[Tuple[str, Dict[str, Any]]]:
        """Get CPU execution providers with thread configuration"""
        thread_count = min(self.settings.max_threads, multiprocessing.cpu_count())
        os.environ['OMP_NUM_THREADS'] = str(thread_count)
        os.environ['CUDA_VISIBLE_DEVICES'] = ''
        return [('CPUExecutionProvider', {'intra_op_num_threads': thread_count})]
    
    def get_session(self, thread_id: Optional[int] = None) -> Any:
        """Get or create a session for the current thread"""
        if thread_id is None:
            thread_id = threading.current_thread().ident
        
        with self.lock:
            if thread_id not in self.session_pool:
                providers = self._get_cpu_providers()
                try:
                    self.session_pool[thread_id] = new_session(
                        self.settings.model_name, 
                        providers=providers
                    )
                except Exception:
                    # Fallback to basic CPU provider
                    self.session_pool[thread_id] = new_session(
                        self.settings.model_name, 
                        providers=['CPUExecutionProvider']
                    )
        
        return self.session_pool[thread_id]
    
    def clear_sessions(self):
        """Clear all cached sessions"""
        with self.lock:
            self.session_pool.clear()
            gc.collect()
    
    def get_session_count(self) -> int:
        """Get number of cached sessions"""
        return len(self.session_pool)


class ImageProcessor:
    """Core image processing logic for background removal"""
    
    def __init__(self, settings: ProcessingSettings):
        self.settings = settings
        self.session_manager = SessionManager(settings)
        self.processing_times = deque(maxlen=10)
        self.should_stop = False
        self.processed_count = 0
    
    def stop_processing(self):
        """Signal to stop processing"""
        self.should_stop = True
    
    def reset_stats(self):
        """Reset processing statistics"""
        self.processing_times.clear()
        self.processed_count = 0
    
    def _prepare_image_for_processing(self, image: Image.Image) -> Image.Image:
        """Prepare image for processing (resize, convert mode, etc.)"""
        # Handle resizing if enabled
        if self.settings.resize_enabled:
            should_resize, new_size = ImageUtils.should_resize_image(
                image.size,
                self.settings.resize_mode,
                self.settings.max_image_size,
                self.settings.resize_fraction
            )
            
            if should_resize:
                image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        # Ensure RGB mode
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        return image
    
    def _handle_exif_orientation(self, image: Image.Image) -> Tuple[Image.Image, int]:
        """Handle EXIF orientation data"""
        original_orientation = 1  # Default normal orientation
        
        if piexif and hasattr(image, 'info') and 'exif' in image.info:
            try:
                exif_dict = piexif.load(image.info['exif'])
                if piexif.ImageIFD.Orientation in exif_dict['0th']:
                    original_orientation = exif_dict['0th'][piexif.ImageIFD.Orientation]
            except Exception:
                pass  # Ignore EXIF errors
        
        # Create upright version for processing
        upright_image = ImageOps.exif_transpose(image)
        return upright_image, original_orientation
    
    def _apply_orientation_to_output(self, image: Image.Image, orientation: int) -> Image.Image:
        """Apply original orientation to processed output"""
        if orientation == 1:
            return image
        elif orientation == 2:
            return image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        elif orientation == 3:
            return image.rotate(180)
        elif orientation == 4:
            return image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        elif orientation == 5:
            return image.rotate(270, expand=True).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        elif orientation == 6:
            return image.rotate(90, expand=True)
        elif orientation == 7:
            return image.rotate(270, expand=True).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        elif orientation == 8:
            return image.rotate(270, expand=True)
        else:
            return image
    
    def remove_background(self, image: Image.Image) -> Image.Image:
        """Remove background from image"""
        # Check memory usage
        current_memory = SystemUtils.get_system_info()['memory_mb']
        if SystemUtils.is_memory_usage_high(current_memory, self.settings.memory_limit_mb):
            self.session_manager.clear_sessions()
        
        start_time = time.time()
        
        try:
            session = self.session_manager.get_session()
            result = remove(
                image,
                session=session,
                alpha_matting=self.settings.alpha_matting,
                alpha_matting_foreground_threshold=self.settings.alpha_matting_foreground_threshold,
                alpha_matting_background_threshold=self.settings.alpha_matting_background_threshold,
                post_process=self.settings.post_process
            )
        except Exception:
            # Fallback: simple background removal without advanced options
            session = self.session_manager.get_session()
            result = remove(image, session=session)
        
        processing_time = time.time() - start_time
        self.processing_times.append(processing_time)
        
        return result
    
    def process_single_image(self, input_path: str, output_path: str) -> Tuple[bool, str]:
        """Process a single image file"""
        try:
            # Validate input
            is_valid, error_msg = ValidationUtils.validate_image_file(input_path)
            if not is_valid:
                return False, error_msg
            
            with Image.open(input_path) as img:
                # Handle EXIF orientation
                upright_img, original_orientation = self._handle_exif_orientation(img)
                
                # Prepare image for processing
                processed_img = self._prepare_image_for_processing(upright_img)
                
                # Remove background
                result_img = self.remove_background(processed_img)
                
                # Apply background type
                final_img = ImageUtils.apply_background_to_image(
                    result_img, 
                    self.settings.background_type
                )
                
                # Restore original orientation
                final_img = self._apply_orientation_to_output(final_img, original_orientation)
                
                # Save result
                final_img.save(output_path)
                
                self.processed_count += 1
                return True, "Success"
                
        except FileNotFoundError:
            return False, f"File not found: {os.path.basename(input_path)}"
        except PermissionError:
            return False, f"Permission denied: {os.path.basename(input_path)}"
        except OSError as e:
            return False, f"OS error: {str(e)}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"
    
    def generate_preview(self, input_path: str) -> Tuple[Optional[Image.Image], Optional[str]]:
        """Generate preview of background removal result"""
        try:
            with Image.open(input_path) as img:
                # Always use upright image for preview
                upright_img, _ = self._handle_exif_orientation(img)
                prepared_img = self._prepare_image_for_processing(upright_img)
                
                start_time = time.time()
                result_img = self.remove_background(prepared_img)
                processing_time = time.time() - start_time
                
                # Create composite with checkerboard background for transparency
                if result_img.mode == 'RGBA':
                    checkerboard = ImageUtils.create_checkerboard_pattern(result_img.size)
                    composite = Image.alpha_composite(checkerboard, result_img)
                else:
                    composite = result_img
                
                status = f"Preview: {result_img.size[0]}×{result_img.size[1]}px, {processing_time:.1f}s"
                return composite, status
                
        except Exception as e:
            return None, f"Error generating preview: {str(e)}"


class BatchProcessor:
    """Handles batch processing of multiple images"""
    
    def __init__(self, settings: ProcessingSettings):
        self.settings = settings
        self.image_processor = ImageProcessor(settings)
        self.should_stop = False
    
    def stop_processing(self):
        """Stop the batch processing"""
        self.should_stop = True
        self.image_processor.stop_processing()
    
    def process_batch(self, image_paths: List[str], output_paths: List[str], 
                     progress_callback: Optional[Callable[[int, int], None]] = None) -> Dict[str, Any]:
        """Process a batch of images"""
        if len(image_paths) != len(output_paths):
            raise ValueError("Input and output path lists must have same length")
        
        self.should_stop = False
        self.image_processor.reset_stats()
        results = {
            'successful': 0,
            'failed': 0,
            'errors': [],
            'processing_time': 0.0
        }
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=self.settings.max_threads) as executor:
            # Submit all tasks
            future_to_path = {
                executor.submit(self.image_processor.process_single_image, ip, op): ip 
                for ip, op in zip(image_paths, output_paths)
            }
            
            # Process results as they complete
            for i, future in enumerate(as_completed(future_to_path)):
                if self.should_stop:
                    # Cancel remaining futures
                    for remaining_future in future_to_path:
                        remaining_future.cancel()
                    break
                
                input_path = future_to_path[future]
                try:
                    success, message = future.result()
                    if success:
                        results['successful'] += 1
                    else:
                        results['failed'] += 1
                        results['errors'].append(f"{os.path.basename(input_path)}: {message}")
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append(f"{os.path.basename(input_path)}: {str(e)}")
                
                # Update progress
                if progress_callback:
                    progress_callback(i + 1, len(image_paths))
                
                # Add delay between operations if configured
                if self.settings.batch_delay_ms > 0:
                    time.sleep(self.settings.batch_delay_ms / 1000.0)
        
        results['processing_time'] = time.time() - start_time
        
        # Clean up sessions after batch processing
        self.image_processor.session_manager.clear_sessions()
        
        return results


class ProjectManager:
    """Manages project settings and file operations"""
    
    def __init__(self):
        self.processing_settings = ProcessingSettings()
        self.input_folder: str = ""
        self.output_location_mode: str = "inside"  # "inside", "sibling", "custom"
        self.custom_output_folder: str = ""
        self.output_subfolder_name: str = "masks"
        self.output_naming_mode: str = "append_suffix"  # "append_suffix", "original_filename"
        self.output_filename_suffix: str = "_mask"
        self.overwrite_files: bool = False
    
    def set_input_folder(self, folder_path: str) -> Tuple[bool, str]:
        """Set and validate input folder"""
        is_valid, message = ValidationUtils.validate_directory_path(folder_path)
        if is_valid:
            self.input_folder = folder_path
        return is_valid, message
    
    def get_image_files(self) -> List[str]:
        """Get list of image files in input folder"""
        if not self.input_folder:
            return []
        return FileUtils.scan_image_files(self.input_folder)
    
    def get_output_directory(self) -> Optional[str]:
        """Get output directory based on current settings"""
        return PathUtils.get_output_directory(
            self.input_folder,
            self.output_location_mode,
            self.output_subfolder_name,
            self.custom_output_folder
        )
    
    def get_output_filename(self, input_filename: str) -> str:
        """Get output filename for an input filename"""
        return PathUtils.get_output_filename(
            input_filename,
            self.output_naming_mode,
            self.output_filename_suffix
        )
    
    def get_output_path(self, input_filename: str) -> Optional[str]:
        """Get full output path for an input filename"""
        output_dir = self.get_output_directory()
        if not output_dir:
            return None
        
        output_filename = self.get_output_filename(input_filename)
        return os.path.join(output_dir, output_filename)
    
    def prepare_batch_processing(self) -> Tuple[List[str], List[str], List[str]]:
        """Prepare file lists for batch processing"""
        image_files = self.get_image_files()
        output_dir = self.get_output_directory()
        
        if not image_files or not output_dir:
            return [], [], []
        
        # Ensure output directory exists
        if not FileUtils.ensure_directory_exists(output_dir):
            return [], [], []
        
        input_paths = []
        output_paths = []
        skipped_files = []
        
        for filename in image_files:
            input_path = os.path.join(self.input_folder, filename)
            output_path = self.get_output_path(filename)
            
            if not output_path:
                continue
            
            # Check if we should skip existing files
            if not self.overwrite_files and os.path.exists(output_path):
                skipped_files.append(filename)
                continue
            
            input_paths.append(input_path)
            output_paths.append(output_path)
        
        return input_paths, output_paths, skipped_files
    
    def update_output_naming_defaults(self):
        """Update naming defaults based on background type"""
        bg_choice = self.processing_settings.background_type
        if bg_choice == "Alpha Matte (W/B)":
            self.output_subfolder_name = "masks"
            self.output_filename_suffix = "_mask"
        else:
            self.output_subfolder_name = "output"
            self.output_filename_suffix = "_nobg"
    
    def validate_project_settings(self) -> List[str]:
        """Validate all project settings"""
        errors = []
        
        # Validate processing settings
        errors.extend(self.processing_settings.validate_settings())
        
        # Validate input folder
        if self.input_folder:
            is_valid, message = ValidationUtils.validate_directory_path(self.input_folder)
            if not is_valid:
                errors.append(f"Input folder: {message}")
        else:
            errors.append("Input folder not set")
        
        # Validate custom output folder if using custom mode
        if self.output_location_mode == "custom":
            if not self.custom_output_folder:
                errors.append("Custom output folder not set")
            else:
                is_valid, message = ValidationUtils.validate_directory_path(self.custom_output_folder)
                if not is_valid:
                    errors.append(f"Custom output folder: {message}")
        
        return errors