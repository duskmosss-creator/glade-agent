import json
import os
import time

class UIDTracker:
    def __init__(self, filename="processed_uids.json"):
        self.filename = filename
        self.processed_uids = set()
        self.load()

    def load(self):
        """Load processed UIDs from JSON file."""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    data = json.load(f)
                    # Support both list and set (though JSON is list)
                    self.processed_uids = set(data.get("uids", []))
            except Exception as e:
                print(f"[UIDTracker] Error loading UIDs: {e}")
                self.processed_uids = set()
        else:
            self.processed_uids = set()

    def save(self):
        """Save processed UIDs to JSON file."""
        try:
            with open(self.filename, 'w') as f:
                json.dump({"uids": list(self.processed_uids), "updated": time.time()}, f)
        except Exception as e:
            print(f"[UIDTracker] Error saving UIDs: {e}")

    def is_processed(self, uid):
        """Check if a UID has already been processed."""
        # Convert to string to be safe
        return str(uid) in self.processed_uids

    def mark_processed(self, uid):
        """Mark a UID as processed and save immediately."""
        uid_str = str(uid)
        if uid_str not in self.processed_uids:
            self.processed_uids.add(uid_str)
            self.save()

    def mark_batch_processed(self, uids):
        """Mark a list of UIDs as processed efficiently."""
        if not uids: return
        
        updated = False
        for uid in uids:
            uid_str = str(uid)
            if uid_str not in self.processed_uids:
                self.processed_uids.add(uid_str)
                updated = True
        
        if updated:
            self.save()
