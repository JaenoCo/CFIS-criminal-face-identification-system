import cv2
import numpy as np
import face_recognition as fr
import os

# Load images
images_folder = "images"
images = []
valid_extensions = ['.png', '.jpg', '.jpeg', '.bmp']
for filename in os.listdir(images_folder):
    if any(filename.lower().endswith(ext) for ext in valid_extensions):
        images.append(filename)

print(f"Found {len(images)} images:")
for img in images:
    print(f"  - {img}")

# Try to load and encode each image
encodings = []
known_face_names = []

for img in images:
    try:
        loaded_img = fr.load_image_file(os.path.join(images_folder, img))
        
        # Convert RGBA to RGB if necessary
        if len(loaded_img.shape) == 3 and loaded_img.shape[-1] == 4:
            loaded_img = loaded_img[:, :, :3]
        
        # Ensure the image is in the correct format (uint8)
        if loaded_img.dtype != np.uint8:
            loaded_img = (loaded_img * 255).astype(np.uint8)
        
        # Get face encodings
        face_encode = fr.face_encodings(loaded_img)
        if len(face_encode) > 0:
            encodings.append(face_encode[0])
            # Extract ID from filename
            face_id = (os.path.splitext(img)[0]).split('.')[1]
            known_face_names.append(face_id)
            print(f"  ✓ {img} -> ID: {face_id} (encoding successful)")
        else:
            print(f"  ✗ {img} -> No face detected!")
    except Exception as e:
        print(f"  ✗ {img} -> Error: {str(e)}")

print(f"\nSuccessfully encoded {len(encodings)} faces")
print(f"Known IDs: {known_face_names}")

# Test with webcam
print("\nTesting with webcam...")
print("Press 'q' to quit")

cam = cv2.VideoCapture(0)
if not cam.isOpened():
    print("Error: Cannot open webcam")
    exit()

frame_count = 0
while True:
    ret, frame = cam.read()
    if not ret:
        print("Failed to grab frame")
        break
    
    frame_count += 1
    
    # Process every 5th frame for speed
    if frame_count % 5 == 0 and len(encodings) > 0:
        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        rgb_small_frame = small_frame[:, :, ::-1]
        
        face_locations = fr.face_locations(rgb_small_frame)
        face_encodings = fr.face_encodings(rgb_small_frame, face_locations)
        
        if len(face_locations) > 0:
            print(f"Detected {len(face_locations)} face(s)")
        
        for face_encoding in face_encodings:
            matches = fr.compare_faces(encodings, face_encoding)
            face_distances = fr.face_distance(encodings, face_encoding)
            best_match_index = np.argmin(face_distances)
            
            if matches[best_match_index]:
                face_id = known_face_names[best_match_index]
                confidence = 1 - face_distances[best_match_index]
                print(f"  -> Match found! ID: {face_id}, Distance: {face_distances[best_match_index]:.3f}, Confidence: {confidence:.2%}")
    
    cv2.imshow('Webcam Test', frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cam.release()
cv2.destroyAllWindows()
