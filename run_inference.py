import cv2
import time
from src.detection.detector import ObjectDetector
from src.detection.vehicle_detector import VehicleDetector
from src.detection.person_detector import PersonDetector

def main():
    print("Starting Object Detection Test")
    
    # Try downloading a test image using urllib if one is not present
    import urllib.request
    import os
    
    image_path = "test_image.jpg"
    if not os.path.exists(image_path):
        url = "https://ultralytics.com/images/zidane.jpg"
        print(f"Downloading test image from {url}...")
        urllib.request.urlretrieve(url, image_path)
    
    # Initialize the detector
    model_path = "yolov8n.pt"
    print(f"Loading model {model_path}...")
    
    try:
        # Load a general ObjectDetector and specific ones
        general_detector = ObjectDetector(model_path=model_path, confidence_threshold=0.5)
        person_detector = PersonDetector(model_path=model_path, confidence_threshold=0.5)
        
        image = cv2.imread(image_path)
        if image is None:
            print("Failed to read image")
            return
            
        # Warmup
        _ = general_detector.detect(image)
        
        # Measure Performance
        start_time = time.time()
        detections = general_detector.detect(image)
        end_time = time.time()
        
        print(f"\nModel used: {model_path}")
        print(f"Inference Time: {(end_time - start_time) * 1000:.2f} ms")
        
        print("\nGeneral Detections (All classes with conf > 0.5):")
        for d in detections:
            print(f"- {d.class_name} (conf: {d.confidence:.2f})")
            
        # Person only test
        person_detections = person_detector.detect(image)
        print("\nPerson Detections:")
        for d in person_detections:
            print(f"- {d.class_name} (conf: {d.confidence:.2f})")
            
    except Exception as e:
        print(f"Error during test: {e}")

if __name__ == "__main__":
    main()
