"""
WORKERS MODULE

Background thread workers that handle time-consuming operations off the main
UI thread. Includes AIWorker for AI processing and IndexingWorker for file
indexing and note generation.
"""

import os
import time
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from filenameParser import parse_file_info
from contentReader import read_file_content
from contentAnalyzer import analyze_file


# AIWorker runs the AI interpretation in a background thread so the UI doesn't freeze.
# It takes user input, sends it to the Interpreter, and emits the result back
# to the main thread when done.
class AIWorker(QThread):
    """Runs Interpreter logic off the main thread and emits a single dict
    shaped the way process_ai_reply() expects.
    """
    finished = pyqtSignal(dict)

    def __init__(self, interpreter, user_text: str, conversation_history=None):
        super().__init__()
        self.interpreter = interpreter
        self.user_text = user_text
        self.conversation_history = conversation_history or []
        self._is_cancelled = False

    def cancel(self):
        """Request cancellation of the thread"""
        self._is_cancelled = True
        self.requestInterruption()

    def run(self):
        try:
            if self.isInterruptionRequested():
                return
            result = self.interpreter.interpret(self.user_text, conversation_history=self.conversation_history)
            
            if self.isInterruptionRequested() or self._is_cancelled:
                return

            # Chat-only
            if isinstance(result, dict) and result.get("mode") == "chat":
                reply = result.get("reply", "").strip()
                if not reply:
                    reply = "I'm here, but I didn't get a response. Try again?"
                ai = {"action": "chat", "message": reply}
                self.finished.emit(ai)
                return

            # Command mode
            if isinstance(result, dict) and result.get("mode") == "command":
                conversation = (result.get("conversation") or "").strip()
                command = result.get("command") or {}
                ai = {
                    "action": command.get("action", "none"),
                    "args": command.get("args", {}) or {},
                    # show the conversational reply in chat; tool results will appear as SYSTEM messages
                    "message": conversation or command.get("message", "") or "Processing your request..."
                }
                # Debug: log what we're emitting
                print(f"[DEBUG] AIWorker emitting: action={ai['action']}, args={ai['args']}, message={ai['message'][:50]}")
                self.finished.emit(ai)
                return

            # Fallback if interpreter returns something unexpected
            self.finished.emit({"action": "chat", "message": f"Unexpected response format: {type(result)}"})

        except Exception as e:
            import traceback
            from config import get_ai_model
            current_model = get_ai_model()
            error_msg = f"Error: {str(e)}\n\nMake sure Ollama is running and the model '{current_model}' is installed."
            self.finished.emit({"action": "chat", "message": error_msg})


# IndexingWorker scans all files in the root directory and generates notes
# for them. Runs in the background on startup so the UI stays responsive.
# Shows progress updates as it processes files.
class IndexingWorker(QThread):
    """Background worker for indexing files and generating notes"""
    progress = pyqtSignal(int, int, str)  # current, total, filename
    finished = pyqtSignal()
    
    def __init__(self, perms, memory, skip_indexing=False):
        super().__init__()
        self.perms = perms
        self.memory = memory
        self.skip_indexing = skip_indexing  # If True, skip indexing and only generate notes
        self._is_cancelled = False
    
    def cancel(self):
        """Request cancellation"""
        self._is_cancelled = True
        self.requestInterruption()
    
    def run(self):
        """Run indexing and note generation"""
        try:
            if not self.perms.allowed_root or not self.perms.allowed_root.exists():
                self.finished.emit()
                return
            
            root_path = self.perms.allowed_root
            
            # Get content reading configuration
            content_config = self.memory.data.get("content_reading_config", {})
            if not content_config:
                content_config = {
                    "enabled": False,
                    "enabled_types": [],
                    "max_file_size": 5 * 1024 * 1024
                }
            
            # Get AI model info for content analysis
            from config import get_ai_model
            ai_url = "http://localhost:11434/api/generate"
            ai_model = get_ai_model()
            
            # Step 1: Index all files (skip if we already have valid index)
            if self.skip_indexing:
                # Use existing index
                file_index = self.memory.data.get("file_index", {})
                all_files = file_index.get("all_files", [])
                self.progress.emit(50, 100, "Using existing index...")
            else:
                # Index all files
                all_files = []
                
                # First pass: collect all files
                file_paths = []
                for root, dirs, files in os.walk(root_path):
                    if self.isInterruptionRequested() or self._is_cancelled:
                        return
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                    files = [f for f in files if not f.startswith('.')]
                    for file in files:
                        file_path = Path(root) / file
                        try:
                            relative_path = file_path.relative_to(root_path)
                            file_paths.append((file_path, relative_path))
                        except (ValueError, PermissionError):
                            continue
                
                total_files = len(file_paths)
                
                # Second pass: process files with progress updates
                # Phase 1: Indexing (0-50% of progress)
                for idx, (file_path, relative_path) in enumerate(file_paths):
                    if self.isInterruptionRequested() or self._is_cancelled:
                        return
                    
                    # Progress: 0-50% for indexing phase
                    progress_pct = int((idx / total_files) * 50) if total_files > 0 else 0
                    self.progress.emit(progress_pct, 100, f"Indexing: {file_path.name}")
                    
                    try:
                        file_info = {
                            "path": str(relative_path),
                            "name": file_path.name,
                            "full_path": str(file_path),
                            "extension": file_path.suffix.lower()
                        }
                        
                        # Parse filename (ALWAYS do this - it's fast and provides basic info)
                        try:
                            file_info = parse_file_info(file_info)
                        except Exception:
                            # If parsing fails, keep basic info - file is still indexed
                            pass
                        
                        # Try to read content if enabled (but don't fail if it doesn't work)
                        content_data = None
                        if content_config.get("enabled", False):
                            try:
                                content_data = read_file_content(
                                    file_path,
                                    file_info["extension"],
                                    content_config
                                )
                            except Exception:
                                # Content reading failed, but file is still indexed with filename info
                                content_data = None
                        
                        # Analyze content if we have it (skip if slow/optional)
                        if content_data:
                            try:
                                file_info = analyze_file(
                                    file_info,
                                    content_data,
                                    ai_url,
                                    ai_model
                                )
                            except Exception:
                                # Content analysis failed, but file is still indexed with filename info
                                pass
                        
                        # ALWAYS add file to index, even if content reading/analysis failed
                        all_files.append(file_info)
                    except (ValueError, PermissionError):
                        # Skip files we can't access, but continue with others
                        continue
                    except Exception:
                        # Log error but continue - don't let one bad file stop indexing
                        continue
                
                # Store file index
                if "file_index" not in self.memory.data:
                    self.memory.data["file_index"] = {}
                self.memory.data["file_index"]["all_files"] = all_files
                self.memory.data["file_index"]["last_scan"] = time.time()
                self.memory.data["file_index"]["root_path"] = str(root_path)
                self.memory.save()
            
            # Step 2: Generate notes for root-level files
            if self.isInterruptionRequested() or self._is_cancelled:
                return
            
            root_files = [f for f in all_files if "/" not in f.get("path", "") or f.get("path", "").count("/") == 0]
            existing_notes = self.memory.data.get("file_notes", {})
            if "file_notes" not in self.memory.data:
                self.memory.data["file_notes"] = {}
            
            files_to_note = [f for f in root_files if str(f.get("path", "")) not in existing_notes]
            total_notes = len(files_to_note)
            
            # Phase 2: Note generation (50-100% of progress)
            for idx, file_info in enumerate(files_to_note):
                if self.isInterruptionRequested() or self._is_cancelled:
                    return
                
                # Progress: 50-100% for note generation phase
                progress_pct = 50 + int((idx / total_notes) * 50) if total_notes > 0 else 50
                self.progress.emit(progress_pct, 100, f"Generating note: {file_info.get('name', '')}")
                
                try:
                    file_path_str = str(file_info.get("path", ""))
                    full_path = Path(root_path) / file_path_str
                    if not full_path.exists():
                        continue
                    
                    # Ensure parsed data exists
                    if "parsed" not in file_info:
                        file_info = parse_file_info(file_info)
                    
                    # Read content if enabled and not already done
                    if "content" not in file_info:
                        content_data = None
                        if content_config.get("enabled", False):
                            content_data = read_file_content(
                                full_path,
                                file_info.get("extension", ""),
                                content_config
                            )
                        if content_data:
                            file_info = analyze_file(
                                file_info,
                                content_data,
                                ai_url,
                                ai_model
                            )
                    
                    # Generate note
                    note_parts = []
                    
                    if file_info.get("parsed"):
                        parsed = file_info["parsed"]
                        if parsed.get("course"):
                            note_parts.append(f"Course: {parsed['course']}")
                        if parsed.get("type"):
                            note_parts.append(f"Type: {parsed['type']}")
                        if parsed.get("date"):
                            note_parts.append(f"Date: {parsed['date']}")
                        if parsed.get("subject_hints"):
                            subjects = ", ".join(parsed["subject_hints"][:2])
                            note_parts.append(f"Subjects: {subjects}")
                    
                    if file_info.get("content", {}).get("summary"):
                        summary = file_info["content"]["summary"]
                        if len(summary) > 80:
                            summary = summary[:77] + "..."
                        note_parts.append(summary)
                    elif file_info.get("content", {}).get("keywords"):
                        keywords = ", ".join(file_info["content"]["keywords"][:5])
                        note_parts.append(f"Keywords: {keywords}")
                    
                    if note_parts:
                        auto_note = " | ".join(note_parts)
                        self.memory.data["file_notes"][file_path_str] = auto_note
                except Exception:
                    continue
            
            # Save notes
            self.memory.save()
            self.finished.emit()
        except Exception:
            self.finished.emit()

