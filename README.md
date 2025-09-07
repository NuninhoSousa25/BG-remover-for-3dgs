# BG-remover-for-3dgs

to do

realityscan exports images rotated 90º can we do the same?


---

# Batch Background Removal Tool

A desktop application for Windows, macOS, and Linux designed for batch processing images to remove their backgrounds. The tool is built with Python and Tkinter, leveraging the powerful `rembg` library for AI-powered background segmentation. It is optimized for CPU-only execution to ensure it runs on a wide variety of machines without requiring a dedicated GPU.

The tool is particularly suited for photogrammetry workflows, including Reality Capture preprocessing, 3D Gaussian Splatting image preparation, and other computer vision applications requiring precise foreground-background separation.



## Features
### Version 1.3 Enhancements:
*   **Enhanced User Interface Navigation:** Implemented comprehensive scrolling functionality with mouse wheel and keyboard input support throughout the control panel interface
*   **Dynamic Preview System:** Automatic mask recalculation triggered by parameter modifications, employing a 500-millisecond debounce mechanism to optimize computational efficiency
*   **Comparative Visualization Mode:** Toggle functionality for simultaneous display of source and processed images with synchronized viewport controls and geometric alignment
*   **Asynchronous Initialization:** Non-blocking application startup with background model loading to reduce perceived latency
*   **Logging Optimization:** Complete suppression of CUDA-related error messages and runtime warnings for cleaner operational output
### Core Functionality:

*   **Batch Processing:** Process entire folders of images in one go.
*   **AI Model Selection:** Choose from different models (`u2netp`, `u2net`, etc.) to balance speed and quality.
*   **Advanced Export Options:**
    *   Save images with a transparent background (PNG).
    *   Save images with a solid white or black background.
    *   Generate black and white **alpha masks** for professional workflows (e.g., for Reality Capture, After Effects).
*   **Flexible Output Control:**
    *   Specify output location: inside the source folder, next to the source folder, or in any custom directory.
    *   Customize subfolder names and filename suffixes (e.g., `image_mask.png`).
*   **Performance Tuning:**
    *   Adjust the number of CPU threads and set a memory limit to manage resource usage.
    *   Enable/disable pre-resizing to speed up processing on large images.
*   **Live Preview:** See a preview of the processed image with your current settings before running a full batch.
*   **EXIF Orientation Fix:** Automatically reads and corrects for image rotation metadata, ensuring masks align perfectly with source photos from phones and cameras.

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

3.  **Using the Tool:**
    *   Click "**Browse...**" to select your input folder containing the images.
    *   Adjust the **Export Settings**, **CPU Settings**, and **Model Settings** on the left as needed.
    *   Click the "**Scan Folder**" button. This will populate the file list on the right.
    *   Click on any file in the list to see a live preview based on your current settings.
    *   To process all images, click "**Process All**". To process only the selected image, click "**Process Selected Image**".

---
