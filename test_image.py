from PIL import Image
import numpy as np
import face_recognition as fr
import cv2

# Create a simple test image
print("Creating simple synthetic image:")
test_img = np.zeros((100, 100, 3), dtype=np.uint8)
test_img[:, :] = [128, 128, 128]  # Gray image

print(f'Shape: {test_img.shape}, Dtype: {test_img.dtype}')
try:
    locations = fr.face_locations(test_img)
    print(f'Success! Synthetic image works. Faces: {len(locations)}')
except Exception as e:
    print(f'Synthetic Error: {e}')

# Now test if maybe we need to ensure order='C'
print("\nTesting with explicitly ordered array:")
img = Image.open('images/user.1.png')
img = img.convert('RGB')
img_array = np.array(img, order='C', dtype=np.uint8)
print(f'Shape: {img_array.shape}, Dtype: {img_array.dtype}')

try:
    locations2 = fr.face_locations(img_array)
    print(f'Success! Faces found: {len(locations2)}')
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
