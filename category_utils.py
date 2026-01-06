"""
CATEGORY UTILITIES MODULE

Helper functions for managing categories (folders for file sorting).
These functions work with the memory manager and permissions store.
"""

from pathlib import Path
from PyQt6.QtWidgets import QListWidget, QListWidgetItem
from PyQt6.QtCore import Qt


def add_category(category_name: str, memory) -> bool:
    """Add a new category to memory.
    
    Args:
        category_name: Name of the category to add
        memory: MemoryManager instance
        
    Returns:
        True if category was added, False if it already exists
    """
    if not category_name or not category_name.strip():
        return False
    
    category = category_name.strip()
    
    # Add to memory
    if "categories" not in memory.data:
        memory.data["categories"] = {}
    
    # Add category (if it doesn't exist, create empty entry)
    if category not in memory.data["categories"]:
        memory.data["categories"][category] = ""
        memory.save()
        return True
    
    return False


def auto_add_directory_categories(perms, memory) -> None:
    """Automatically scan subdirectories of the root directory and add them as categories.
    
    Args:
        perms: PermissionsStore instance
        memory: MemoryManager instance
    """
    if "categories" not in memory.data:
        memory.data["categories"] = {}
    
    # Get the single root directory
    root_path = perms.allowed_root
    if not root_path or not root_path.exists() or not root_path.is_dir():
        return
    
    # Remove the root directory name itself from categories if it exists
    # (shouldn't be a category since it's the sorting directory)
    root_name = root_path.name
    if root_name in memory.data["categories"]:
        del memory.data["categories"][root_name]
        memory.save()
    
    # Remove categories that no longer exist in the current root directory
    categories_to_remove = []
    for cat_name, cat_path in list(memory.data["categories"].items()):
        # If the category path is within the root, check if it still exists
        try:
            cat_path_obj = Path(cat_path)
            if perms.is_allowed(cat_path_obj):
                # Check if it's a subdirectory of current root
                try:
                    cat_path_obj.relative_to(root_path)
                    # It's within root, check if it still exists
                    if not cat_path_obj.exists() or not cat_path_obj.is_dir():
                        categories_to_remove.append(cat_name)
                except ValueError:
                    # Not within current root, remove it
                    categories_to_remove.append(cat_name)
            else:
                # Not allowed anymore, remove it
                categories_to_remove.append(cat_name)
        except Exception:
            # Invalid path, remove it
            categories_to_remove.append(cat_name)
    
    for cat_name in categories_to_remove:
        del memory.data["categories"][cat_name]
    if categories_to_remove:
        memory.save()
    
    try:
        # Scan subdirectories of the root (NOT the root itself)
        for item in root_path.iterdir():
            if item.is_dir():
                # Use the subdirectory name as the category
                folder_name = item.name
                # Make sure we're not adding the root directory itself
                if folder_name and folder_name != root_name:
                    # Add or update the category (even if it exists, update the path)
                    memory.data["categories"][folder_name] = str(item)
                    memory.save()
    except (PermissionError, OSError):
        # Silently skip directories we can't access
        pass


def refresh_categories_list(categories_list: QListWidget, memory) -> None:
    """Refresh the categories list widget with current categories from memory.
    
    Args:
        categories_list: QListWidget to populate
        memory: MemoryManager instance
    """
    categories_list.clear()
    categories = memory.data.get("categories", {})
    for cat in sorted(categories.keys()):
        item = QListWidgetItem(cat)
        categories_list.addItem(item)


def remove_category(category_name: str, memory) -> bool:
    """Remove a category from memory.
    
    Args:
        category_name: Name of the category to remove
        memory: MemoryManager instance
        
    Returns:
        True if category was removed, False if it didn't exist
    """
    if "categories" not in memory.data:
        return False
    
    if category_name in memory.data["categories"]:
        del memory.data["categories"][category_name]
        memory.save()
        return True
    
    return False

