import os
from PIL import Image, ImageOps
import piexif

def test_image_transformations(image_path):
    print(f"\nTesting: {os.path.basename(image_path)}")
    
    with Image.open(image_path) as img:
        print(f"Original size: {img.size}")
        
        # Check EXIF orientation
        if 'exif' in img.info:
            exif_dict = piexif.load(img.info['exif'])
            if piexif.ImageIFD.Orientation in exif_dict['0th']:
                orientation = exif_dict['0th'][piexif.ImageIFD.Orientation]
                print(f"EXIF orientation: {orientation}")
            else:
                print("No orientation tag")
        
        # Apply exif_transpose
        upright = ImageOps.exif_transpose(img)
        print(f"After exif_transpose size: {upright.size}")
        
        # Test different rotations
        rotated_90 = upright.rotate(90, expand=True)
        rotated_270 = upright.rotate(270, expand=True)
        
        print(f"After 90° rotation size: {rotated_90.size}")
        print(f"After 270° rotation size: {rotated_270.size}")
        
        # Save test images to see the actual transformations
        base_name = os.path.splitext(os.path.basename(image_path))[0]
        upright.save(f"test_{base_name}_upright.png")
        rotated_90.save(f"test_{base_name}_rot90.png")
        rotated_270.save(f"test_{base_name}_rot270.png")
        
        print(f"Saved test images: test_{base_name}_*.png")

# Test the problematic images
images = [
    r"C:\Users\nunom\Desktop\coding_with_ai\bg remover\bg removal\IMG_1831_original.jpeg",
    r"C:\Users\nunom\Desktop\coding_with_ai\bg remover\bg removal\IMG_1832.jpeg"
]

for img_path in images:
    try:
        test_image_transformations(img_path)
    except Exception as e:
        print(f"Error with {os.path.basename(img_path)}: {e}")