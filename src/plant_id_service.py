import os
import time
import requests
from ultralytics import YOLO
from plant_id_service_standalone import StandalonePlantID

class PlantIdentifier:
    def __init__(self, models_dir="models", method="specialized", model_file="plant_yolov8s.pt"):
        self.models_dir = models_dir
        self.model_path = os.path.join(models_dir, model_file)
        self.method = method
        
        self.model = None
        self.standalone_service = None
        self.last_used = None
        
        # Load labels/prompts
        self.prompts = self._load_prompts()
        
        print(f"[PlantID] Initialized with method: {method}")
        
    def unload(self):
        """Unload model from memory to free VRAM."""
        if self.model:
            del self.model
            import gc
            gc.collect()
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            self.model = None
            print("[PlantID] Model unloaded (VRAM freed).")
            
        # Also clean up standalone service
        if self.standalone_service:
            self.standalone_service = None
            import gc
            gc.collect()
            print("[PlantID] Standalone service unloaded.")

    def check_idle(self, timeout=300):
        """Check if model has been idle for too long and unload if necessary."""
        if not self.model and not self.standalone_service:
            return

        if self.last_used and (time.time() - self.last_used > timeout):
            print(f"[PlantID] Model idle for {timeout}s. Unloading...")
            self.unload()

    def _load_prompts(self):
        """Load prompts or detection instructions."""
        import json
        try:
            with open(os.path.join("config", "plant_id_prompts.json"), "r") as f:
                return json.load(f)
        except Exception:
            return {
                "system_prompt": "You are a specialized plant classification system.",
                "response_template": "Detected: {class_name} ({confidence}% confidence)"
            }

    def _load_model(self):
        """Lazy load model based on configured method."""
        if self.method == "standalone":
            if self.standalone_service is not None:
                return
            print(f"[PlantID] Initializing Standalone ONNX Service: {self.model_path}")
            self.standalone_service = StandalonePlantID(model_path=self.model_path)
            return

        if self.model is not None:
            return
            
        if not os.path.exists(self.model_path):
            print(f"[PlantID] ERROR: Model file not found at {self.model_path}")
            return

        try:
            print(f"[PlantID] Loading YOLO model: {self.model_path}")
            self.model = YOLO(self.model_path)
            print("[PlantID] YOLO model loaded successfully.")
        except Exception as e:
            print(f"[PlantID] ERROR loading YOLO model: {e}")

    def identify(self, image_path):
        """Identify plant using configured method (YOLO or Standalone)."""
        self._load_model()
        
        if self.method == "standalone":
            if not self.standalone_service:
                return "Error: Standalone Plant ID service failed to initialize."
            result = self.standalone_service.identify(image_path)
            if isinstance(result, str): return result
            
            self.last_used = time.time()
            # Format standalone response
            name = result.get('result', 'Unknown')
            conf = result.get('confidence', 0)
            prov = result.get('provider', 'CPU')
            return f"Standalone ID: {name} ({conf*100:.1f}% confidence) via {prov}."

        if not self.model:
            return "Error: Plant ID model (YOLO) failed to load."
            
        try:
            # Perform inference
            results = self.model(image_path, verbose=False)
            
            if not results or len(results[0].boxes) == 0:
                return "No plants or leaves clearly identified in the center of the image."
            
            # Extract top detection
            top_box = results[0].boxes[0] # YOLOv8 results[0] is the first image
            class_id = int(top_box.cls[0])
            confidence = float(top_box.conf[0])
            class_name = results[0].names[class_id]
            
            self.last_used = time.time()
            
            # Format response
            res = f"Identified: {class_name.replace('_', ' ').title()} ({confidence*100:.1f}% confidence)."
            
            # If there are multiple detections, maybe list others briefly
            if len(results[0].boxes) > 1:
                other_classes = []
                for box in results[0].boxes[1:3]: # Next 2
                    cid = int(box.cls[0])
                    conf = float(box.conf[0])
                    cname = results[0].names[cid].replace('_', ' ').title()
                    if cname not in other_classes and cname != class_name.replace('_', ' ').title():
                        other_classes.append(f"{cname} ({conf*100:.0f}%)")
                if other_classes:
                    res += " Also detected: " + ", ".join(other_classes)
            
            
            # Unload to save VRAM for other agents
            self.unload()
            
            return res
            
        except Exception as e:
            print(f"[PlantID] YOLO Inference error: {e}")
            return f"Error during specialized identification: {str(e)}"
