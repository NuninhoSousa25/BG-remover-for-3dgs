"""
Image Processing Logic for the Background Removal Tool.
Handles image processing operations and adapter logic.
"""
import os
from typing import Optional, Tuple, List
from PIL import Image, ImageTk
try:
    import piexif
except ImportError:
    piexif = None

# Import business logic and utilities
from business_logic import BatchProcessor
from utils import UIUtils
from ui import Constants


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
    
    def refresh_processors(self):
        """Refresh processors when settings change"""
        self._init_processors()
    
    def get_model_info(self) -> dict:
        """Get current model information"""
        if not self.image_processor:
            return {"name": "None", "loaded": False}
            
        return {
            "name": self.image_processor.current_model_name,
            "loaded": bool(self.image_processor.session_manager.current_session),
            "memory_usage": self.image_processor.session_manager.get_memory_usage()
        }
    
    def force_model_reload(self):
        """Force reload of the current model"""
        if self.image_processor:
            self.image_processor.session_manager.clear_sessions()
            self._init_processors()
    
    def get_processing_stats(self) -> dict:
        """Get processing performance statistics"""
        if not self.image_processor or not self.processing_times:
            return {
                "total_processed": 0,
                "average_time": 0.0,
                "min_time": 0.0,
                "max_time": 0.0
            }
        
        times = self.processing_times
        return {
            "total_processed": len(times),
            "average_time": sum(times) / len(times),
            "min_time": min(times),
            "max_time": max(times)
        }