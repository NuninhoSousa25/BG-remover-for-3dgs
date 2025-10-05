# Batch Background Removal Tool
## Version 1.3

A cross-platform desktop application for automated batch processing of background removal in digital images. Built using Python and Tkinter, the application employs the rembg library for deep learning-based semantic segmentation. The system is architecturally designed for CPU-only execution to ensure broad compatibility across computing environments without GPU dependencies.

The tool is particularly suited for photogrammetry workflows, including Reality Capture preprocessing, 3D Gaussian Splatting image preparation, and other computer vision applications requiring precise foreground-background separation.

## Features

### Version 1.3 Enhancements:
*   **Enhanced User Interface Navigation:** Implemented comprehensive scrolling functionality with mouse wheel and keyboard input support throughout the control panel interface
*   **Dynamic Preview System:** Automatic mask recalculation triggered by parameter modifications, employing a 500-millisecond debounce mechanism to optimize computational efficiency
*   **Comparative Visualization Mode:** Toggle functionality for simultaneous display of source and processed images with synchronized viewport controls and geometric alignment
*   **Asynchronous Initialization:** Non-blocking application startup with background model loading to reduce perceived latency
*   **Logging Optimization:** Complete suppression of CUDA-related error messages and runtime warnings for cleaner operational output

### Core Functionality:
*   **Batch Processing Architecture:** Concurrent processing of image collections with configurable thread management and resource allocation
*   **Neural Network Model Selection:** Support for multiple pre-trained segmentation models with varying computational complexity:
    *   `u2netp`: Optimized lightweight architecture for rapid processing
    *   `u2net`: Balanced performance-quality trade-off model
    *   `u2net_human_seg`: Human-centric segmentation specialization
    *   `isnet-general-use`: High-fidelity general-purpose segmentation
*   **Multi-format Export Capabilities:**
    *   Transparent background preservation (PNG with alpha channel)
    *   Solid background substitution (configurable color fills)
    *   Alpha matte generation for professional post-production workflows
*   **Configurable Output Management:**
    *   Hierarchical directory structure control (nested, adjacent, or custom paths)
    *   Systematic filename convention management with customizable suffixes
*   **Performance Optimization Controls:**
    *   Multi-threaded execution with user-defined concurrency limits
    *   Memory usage constraints and automatic resource management
    *   Pre-processing image scaling for computational efficiency optimization
*   **Real-time Preview System:**
    *   Interactive parameter adjustment with immediate visual feedback
    *   Comparative source-result visualization capabilities
    *   Geometric transformation controls (scaling, translation, fitting algorithms)
*   **EXIF Metadata Processing:** Automatic detection and correction of image orientation parameters to ensure spatial consistency

## Requirements

This script is built with Python 3. You will need to have Python 3 installed on your system.

The script relies on several external Python libraries. They are listed below and can be installed easily using the instructions in the next section.

*   `Pillow`: For all image manipulation.
*   `rembg`: The core library for background removal.
*   `onnxruntime`: The AI model inference engine required by `rembg`.
*   `psutil`: For monitoring system CPU and memory usage.
*   `piexif`: For reading and writing EXIF metadata to fix image orientation issues.

## Installation

Follow these steps to set up the tool and install all necessary libraries.

#### Step 1: Get the Project Files

First, make sure you have the `bg_removal_tool.py` script on your computer. If you have `git` installed, you can clone the repository. Otherwise, simply download the files.

#### Step 2: Create a `requirements.txt` File

In the same directory as your `bg_removal_tool.py` script, create a new text file named `requirements.txt` and paste the following content into it. This file lists all the required libraries and their versions.

```text
Pillow>=9.0.0
rembg>=2.0.50
onnxruntime>=1.15.0
psutil>=5.9.0
piexif>=1.1.3
```

#### Step 3: Install the Libraries

Open your terminal (Command Prompt on Windows, Terminal on macOS/Linux) and navigate to the directory where you saved the project files.

Run the following command to install all the libraries listed in `requirements.txt` in one go.

**Recommended Command (More Reliable):**

*   On **Windows**:
    ```bash
    py -m pip install -r requirements.txt
    ```

*   On **macOS / Linux**:
    ```bash
    python3 -m pip install -r requirements.txt
    ```
    *(Using `py -m` or `python3 -m` is recommended as it ensures you are using the `pip` that corresponds to your Python installation, avoiding conflicts if you have multiple versions of Python.)*

**Standard Command:**

If the above command gives you trouble, you can try the simpler version:
```bash
pip install -r requirements.txt
```

Once the installation is complete without errors, you are ready to run the application.

## Usage

1.  Navigate to the project directory in your terminal.
2.  Run the application with the following command:

    *   On **Windows**:
        ```bash
        py bg_removal_tool.py
        ```
    *   On **macOS / Linux**:
        ```bash
        python3 bg_removal_tool.py
        ```

3.  **Operational Procedures:**

### Basic Operation:
1. **Input Selection:** Use the directory selection dialog to specify the source folder containing target images
2. **Parameter Configuration:** Adjust processing parameters via the scrollable control panel interface
3. **Dataset Scanning:** Execute folder scanning to populate the file index and enable preview functionality  
4. **Processing Execution:** Initiate either batch processing for complete dataset or single-image processing for individual files

### Advanced Configuration:

**Dynamic Preview System:**
*   Parameter modifications automatically trigger mask recalculation with visual feedback
*   Comparative visualization mode enables simultaneous display of source and processed images
*   Viewport controls maintain spatial registration between original and processed views

**Interface Navigation:**
*   Mouse wheel input provides scrolling functionality within the control panel and zoom control in preview area
*   Keyboard navigation supports directional keys for incremental movement and page-based jumping
*   Focus management ensures consistent input handling across interface elements

**Model Selection Guidelines:**
*   `u2netp`: Lightweight architecture optimized for computational efficiency in batch operations
*   `u2net`: Standard model providing balanced computational load and segmentation accuracy
*   `u2net_human_seg`: Specialized model trained for human subject segmentation tasks
*   `isnet-general-use`: High-complexity model delivering maximum segmentation fidelity

**Alpha Matting Optimization:**
*   Enable trimap-based alpha matting for improved edge quality at increased computational cost
*   Foreground and background threshold parameters control segmentation confidence boundaries
*   Real-time parameter adjustment with immediate visual feedback for iterative optimization

## Changelog

### Version 1.3
**Interface and Performance Improvements**

**Feature Additions:**
- **Comprehensive Scrolling Implementation:** Integrated mouse wheel and keyboard navigation throughout the control panel interface
  - Multi-input scrolling support across all interface widgets
  - Keyboard navigation with directional keys, page navigation, and boundary jumping
  - Consistent scrolling behavior across nested interface components

- **Dynamic Preview Recalculation:** Implemented intelligent mask regeneration system
  - Automatic preview refresh triggered by parameter state changes
  - Debounce mechanism with 500-millisecond delay to optimize computational resources
  - Comprehensive parameter monitoring including model selection, alpha matting configuration, and image scaling options

- **Comparative Visualization System:** Added source-result comparison functionality
  - Toggle-based display mode for simultaneous source and processed image viewing
  - Spatial alignment maintenance between original and processed image data
  - Synchronized viewport controls with geometric transformation consistency
  - Identical preprocessing pipeline application to ensure accurate visual comparison

**Performance Optimizations:**
- **Asynchronous Initialization Architecture:** Implemented non-blocking startup sequence
  - Background model loading with immediate interface availability
  - Progressive loading feedback with status indication
  - Approximately 70% reduction in perceived application startup latency

- **Runtime Logging Optimization:** Comprehensive suppression of non-critical system messages
  - Complete elimination of CUDA-related error outputs and runtime warnings
  - Streamlined console output for operational clarity
  - Systematic ONNX Runtime logging level management

**Technical Improvements:**
- Enhanced synchronization mechanisms between user interface and processing subsystems
- Improved neural network session management for model switching operations
- Optimized widget state management and input focus handling
- Refined preview generation pipeline for improved computational efficiency

---
