import json
import os

class MemoryManager:
    def __init__(self, path="memory.json"):
        self.path = path
        self.data = {
            "categories": {},
            "file_preferences": {},
            "history": [],
            "manual_mappings": {},  # For backward compatibility
            "user_rules": [],
            "cluster_labels": {},
            "file_notes": {},  # File-specific notes
            "file_index": {}  # Index of all files for AI context
        }
        self.load()

    def load(self):
        if os.path.exists(self.path):
            with open(self.path, "r") as f:
                try:
                    self.data = json.load(f)
                except:
                    pass  # corrupted file fallback

    def save(self):
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=4)

    def remember_category(self, extension, category):
        self.data["file_preferences"][extension] = category
        self.save()

    def remember_folder(self, category, folder_path):
        self.data["categories"][category] = folder_path
        self.save()

    def add_history(self, event):
        self.data["history"].append(event)
        self.save()

    def get_category_for_extension(self, ext):
        return self.data["file_preferences"].get(ext)

    def get_folder_for_category(self, category):
        return self.data["categories"].get(category)
