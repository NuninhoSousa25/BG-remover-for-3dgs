"""
Settings Management for the Background Removal Tool.
Handles UI variables and synchronization with business logic.
"""
import tkinter as tk
import multiprocessing
from business_logic import ProjectManager
from ui import Constants
from utils import SettingsUtils


class SettingsManager:
    """UI wrapper for business logic settings"""
    def __init__(self):
        # Initialize business logic
        self.project_manager = ProjectManager()
        
        # UI Variables linked to business logic
        self.input_folder = tk.StringVar()
        self.overwrite_files = tk.BooleanVar(value=False)
        self.post_processing = tk.BooleanVar(value=False)
        self.model_name = tk.StringVar(value="u2netp")
        self.alpha_matting = tk.BooleanVar(value=False)
        self.alpha_matting_foreground_threshold = tk.IntVar(value=Constants.DEFAULT_ALPHA_FG_THRESHOLD)
        self.alpha_matting_background_threshold = tk.IntVar(value=Constants.DEFAULT_ALPHA_BG_THRESHOLD)
        self.resize_enabled = tk.BooleanVar(value=True)
        self.resize_mode = tk.StringVar(value="fraction")
        self.max_image_size = tk.IntVar(value=Constants.DEFAULT_MAX_IMAGE_SIZE)
        self.resize_fraction = tk.DoubleVar(value=Constants.DEFAULT_RESIZE_FRACTION)
        self.num_threads = tk.IntVar(value=min(Constants.DEFAULT_MAX_THREADS, multiprocessing.cpu_count()))
        self.memory_limit_mb = tk.IntVar(value=Constants.DEFAULT_MEMORY_LIMIT_MB)
        self.batch_delay_ms = tk.IntVar(value=Constants.DEFAULT_BATCH_DELAY_MS)
        self.output_location_mode = tk.StringVar(value="inside")
        self.custom_output_folder = tk.StringVar(value="")
        self.output_subfolder_name = tk.StringVar(value="masks")
        self.background_type = tk.StringVar(value="Alpha Matte (W/B)")
        self.output_naming_mode = tk.StringVar(value="append_suffix")
        self.output_filename_suffix = tk.StringVar(value="_mask")
        
        # Setup variable traces to sync with business logic
        self._setup_variable_traces()
        
        # Perform initial sync to ensure business logic matches UI defaults
        self._initial_sync()
    
    def _setup_variable_traces(self):
        """Setup traces to sync UI variables with business logic"""
        SettingsUtils.bind_variable_trace(self.input_folder, self._sync_input_folder)
        SettingsUtils.bind_variable_trace(self.overwrite_files, self._sync_overwrite_files)
        SettingsUtils.bind_variable_trace(self.model_name, self._sync_model_settings)
        SettingsUtils.bind_variable_trace(self.alpha_matting, self._sync_processing_settings)
        SettingsUtils.bind_variable_trace(self.alpha_matting_foreground_threshold, self._sync_processing_settings)
        SettingsUtils.bind_variable_trace(self.alpha_matting_background_threshold, self._sync_processing_settings)
        SettingsUtils.bind_variable_trace(self.post_processing, self._sync_processing_settings)
        SettingsUtils.bind_variable_trace(self.resize_enabled, self._sync_processing_settings)
        SettingsUtils.bind_variable_trace(self.resize_mode, self._sync_processing_settings)
        SettingsUtils.bind_variable_trace(self.max_image_size, self._sync_processing_settings)
        SettingsUtils.bind_variable_trace(self.resize_fraction, self._sync_processing_settings)
        SettingsUtils.bind_variable_trace(self.num_threads, self._sync_processing_settings)
        SettingsUtils.bind_variable_trace(self.memory_limit_mb, self._sync_processing_settings)
        SettingsUtils.bind_variable_trace(self.batch_delay_ms, self._sync_processing_settings)
        SettingsUtils.bind_variable_trace(self.output_location_mode, self._sync_output_settings)
        SettingsUtils.bind_variable_trace(self.custom_output_folder, self._sync_output_settings)
        SettingsUtils.bind_variable_trace(self.output_subfolder_name, self._sync_output_settings)
        SettingsUtils.bind_variable_trace(self.background_type, self._sync_output_settings)
        SettingsUtils.bind_variable_trace(self.output_naming_mode, self._sync_output_settings)
        SettingsUtils.bind_variable_trace(self.output_filename_suffix, self._sync_output_settings)
    
    def _initial_sync(self):
        """Perform initial synchronization of UI defaults to business logic"""
        # Sync all settings to ensure business logic matches UI defaults
        self._sync_input_folder()
        self._sync_overwrite_files()
        self._sync_model_settings()
        self._sync_processing_settings()
        self._sync_output_settings()
    
    def _sync_input_folder(self, *args):
        """Sync input folder with business logic"""
        folder_path = SettingsUtils.get_variable_value(self.input_folder, "")
        if folder_path:
            self.project_manager.set_input_folder(folder_path)
    
    def _sync_overwrite_files(self, *args):
        """Sync overwrite setting"""
        overwrite = SettingsUtils.get_variable_value(self.overwrite_files, False)
        self.project_manager.overwrite_files = overwrite
    
    def _sync_model_settings(self, *args):
        """Sync model settings with business logic"""
        model_name = SettingsUtils.get_variable_value(self.model_name, "u2netp")
        self.project_manager.processing_settings.model_name = model_name
    
    def _sync_processing_settings(self, *args):
        """Sync processing settings with business logic"""
        settings = self.project_manager.processing_settings
        
        settings.alpha_matting = SettingsUtils.get_variable_value(self.alpha_matting, False)
        settings.alpha_matting_foreground_threshold = SettingsUtils.get_variable_value(
            self.alpha_matting_foreground_threshold, Constants.DEFAULT_ALPHA_FG_THRESHOLD)
        settings.alpha_matting_background_threshold = SettingsUtils.get_variable_value(
            self.alpha_matting_background_threshold, Constants.DEFAULT_ALPHA_BG_THRESHOLD)
        settings.post_process = SettingsUtils.get_variable_value(self.post_processing, False)
        settings.resize_enabled = SettingsUtils.get_variable_value(self.resize_enabled, True)
        settings.resize_mode = SettingsUtils.get_variable_value(self.resize_mode, "fraction")
        settings.max_image_size = SettingsUtils.get_variable_value(
            self.max_image_size, Constants.DEFAULT_MAX_IMAGE_SIZE)
        settings.resize_fraction = SettingsUtils.get_variable_value(
            self.resize_fraction, Constants.DEFAULT_RESIZE_FRACTION)
        settings.max_threads = SettingsUtils.get_variable_value(
            self.num_threads, Constants.DEFAULT_MAX_THREADS)
        settings.memory_limit_mb = SettingsUtils.get_variable_value(
            self.memory_limit_mb, Constants.DEFAULT_MEMORY_LIMIT_MB)
        settings.batch_delay_ms = SettingsUtils.get_variable_value(
            self.batch_delay_ms, Constants.DEFAULT_BATCH_DELAY_MS)
    
    def _sync_output_settings(self, *args):
        """Sync output settings with business logic"""
        self.project_manager.output_location_mode = SettingsUtils.get_variable_value(
            self.output_location_mode, "inside")
        self.project_manager.custom_output_folder = SettingsUtils.get_variable_value(
            self.custom_output_folder, "")
        self.project_manager.output_subfolder_name = SettingsUtils.get_variable_value(
            self.output_subfolder_name, "masks")
        self.project_manager.processing_settings.background_type = SettingsUtils.get_variable_value(
            self.background_type, "Alpha Matte (W/B)")
        self.project_manager.output_naming_mode = SettingsUtils.get_variable_value(
            self.output_naming_mode, "append_suffix")
        self.project_manager.output_filename_suffix = SettingsUtils.get_variable_value(
            self.output_filename_suffix, "_mask")
    
    @property
    def models(self):
        """Get available models"""
        return self.project_manager.processing_settings.available_models
    
    def get_model_description(self, model_name: str) -> str:
        """Get model description"""
        return self.project_manager.processing_settings.get_model_description(model_name)
    
    def get_processing_settings(self) -> 'ProcessingSettings':
        """Get processing settings for use by processors"""
        return self.project_manager.processing_settings
    
    def validate_settings(self) -> tuple[bool, list[str]]:
        """Validate current settings"""
        return self.project_manager.validate_settings()
    
    def get_image_files(self) -> list[str]:
        """Get list of image files in input folder"""
        return self.project_manager.get_image_files()
    
    def get_output_directory(self) -> str:
        """Get output directory path"""
        return self.project_manager.get_output_directory()
    
    def get_output_filename(self, input_filename: str) -> str:
        """Get output filename for given input filename"""
        return self.project_manager.get_output_filename(input_filename)