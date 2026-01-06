import os
import shutil
from pathlib import Path

def list_files(path, limit=None):
    try:
        items = os.listdir(path)
    except Exception as e:
        return {"error": str(e)}

    # Convert to absolute paths
    full_paths = [os.path.join(path, i) for i in items]

    # If AI only wants top N files
    if limit is not None:
        full_paths = full_paths[:limit]

    return {
        "count": len(full_paths),
        "message": f"Found {len(full_paths)} items.",
        "files": full_paths  # Always return the files list, not conditionally
    }


def move_file(src, dst):
    src = Path(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return {"status": f"Moved {src.name} → {dst}"}

def file_type(path):
    return {"type": Path(path).suffix}

def create_folder(path):
    """Create a folder at the given path. Returns success status and message."""
    try:
        # Convert to absolute path for consistent checking
        folder_path = Path(path).expanduser()
        # Get absolute path (works even if path doesn't exist yet)
        abs_path = folder_path.absolute()
        
        # Check if it already exists (as directory)
        if abs_path.exists():
            if abs_path.is_dir():
                return {"status": f"Folder already exists: {path}", "already_exists": True, "path": str(abs_path)}
            else:
                return {"error": f"Path exists but is not a directory: {path}"}
        
        # Create the folder (parents=True creates parent directories if needed)
        abs_path.mkdir(parents=True, exist_ok=False)
        
        # Verify it was actually created
        if abs_path.exists() and abs_path.is_dir():
            return {"status": f"Created folder: {path}", "path": str(abs_path)}
        else:
            return {"error": f"Folder creation failed: {path}"}
    except FileExistsError:
        # Handle race condition where folder was created between check and creation
        abs_path = Path(path).expanduser().absolute()
        if abs_path.exists() and abs_path.is_dir():
            return {"status": f"Folder already exists: {path}", "already_exists": True, "path": str(abs_path)}
        return {"error": f"Folder creation failed: {path}"}
    except PermissionError as e:
        return {"error": f"Permission denied: Cannot create folder at {path}"}
    except Exception as e:
        return {"error": f"Error creating folder: {str(e)}"}

def list_all_files(path):
    try:
        count = 0
        for root, dirs, files in os.walk(path):
            count += len(files)

        return {
            "count": count,
            "message": f"Scan complete. Found {count} files."
        }
    except PermissionError:
        return {"error": "Permission denied: Cannot access this directory"}
    except OSError as e:
        return {"error": f"Cannot access directory: {str(e)}"}


def read_file(path):
    path = Path(path)
    if not path.exists():
        return {"error": f"File not found: {path}"}

    # Only allow safe text formats
    allowed = [".txt", ".md", ".py", ".java", ".json", ".csv", ".log", ".xml", ".html"]
    if path.suffix.lower() not in allowed:
        return {"error": f"Cannot read file type: {path.suffix}"}

    try:
        return {"content": path.read_text(), "message": f"Read {path.name}"}
    except Exception as e:
        return {"error": f"Error reading file: {e}"}
