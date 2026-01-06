import os
import json
import re
import requests
import hashlib
from pathlib import Path
from config import get_ai_model


# LOAD / SAVE MEMORY
MEMORY_FILE = "memory.json"  # Same file used by MemoryManager

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {
            "manual_mappings": {},
            "user_rules": [],
            "cluster_labels": {}
        }
    with open(MEMORY_FILE, "r") as f:
        return json.load(f)

def save_memory(mem):
    with open(MEMORY_FILE, "w") as f:
        json.dump(mem, f, indent=4)


# SIMPLE SEMANTIC CLASSIFIER (you can expand later)


def guess_category(filename, memory):
    name = filename.lower()

    # --- 1) Your stored memory mappings ---
    for pattern, folder in memory["manual_mappings"].items():
        if pattern in name:
            return folder, 0.95

    # --- 2) Keyword-based classifier ---
    KEYWORDS = {
        "images": ["png", "jpg", "jpeg", "gif"],
        "screenshots": ["screenshot"],
        "pdfs": ["pdf"],
        "school": ["syllabus", "assignment", "lecture", "hw", "cs159", "cs240"],
        "code": ["py", "java", "js", "html", "css"],
        "minecraft": ["jar", "minecraft", "forge", "neoforge", "mod"],
        "zips": ["zip", "tar", "gz"],
        "videos": ["mp4", "mov"],
        "music": ["mp3", "wav", "m4a"]
    }

    for cat, keys in KEYWORDS.items():
        if any(k in name for k in keys):
            return cat, 0.85

    # --- 3) Completely unknown ---
    return "misc", 0.40


# MAIN INTERPRETER CLASS


class Interpreter:
    def __init__(self, ROOT, allowed_paths=None, ai_model=None):
        self.ROOT = ROOT
        self.memory = load_memory()
        self.ai_url = "http://localhost:11434/api/generate"
        self.ai_model = ai_model or get_ai_model()
        self.allowed_paths = allowed_paths or []
        # Cache static prompt (built once per session)
        self.static_prompt = None
        # Build and cache static prompt on init (after allowed_paths is set)
        self._build_static_prompt()

    # HELPER METHODS FOR TOKEN OPTIMIZATION
    
    def _extract_keywords(self, user_message):
        """Extract keywords, course codes, and subject names from user message."""
        keywords = []
        text_lower = user_message.lower()
        
        # Extract words (3+ characters, alphanumeric)
        words = re.findall(r'\b[a-z0-9]{3,}\b', text_lower)
        keywords.extend(words)
        
        # Extract course codes (patterns like "CS231", "MATH101")
        course_patterns = re.findall(r'\b([A-Z]{2,4}\d{3,4})\b', user_message)
        keywords.extend([c.lower() for c in course_patterns])
        
        # Extract common subject names
        subjects = ['math', 'calculus', 'algebra', 'geometry', 'physics', 'chemistry', 
                   'biology', 'history', 'english', 'literature', 'science', 'cs', 
                   'computer', 'programming', 'code', 'homework', 'hw', 'assignment',
                   'lecture', 'notes', 'exam', 'test', 'quiz', 'project']
        for subject in subjects:
            if subject in text_lower:
                keywords.append(subject)
        
        # Remove duplicates and return
        return list(set(keywords))
    
    def _get_file_id(self, file_info):
        """Generate a stable file ID for caching."""
        file_path = file_info.get('path', '') or file_info.get('full_path', '')
        if file_path:
            # Use hash of path for stable ID
            return hashlib.md5(file_path.encode()).hexdigest()[:8]
        # Fallback to name hash
        name = file_info.get('name', '')
        return hashlib.md5(name.encode()).hexdigest()[:8]
    
    def _prefilter_files(self, user_message, root_files):
        """Filter files locally using keyword matching before sending to AI."""
        if not root_files:
            return []
        
        keywords = self._extract_keywords(user_message)
        if not keywords:
            # No keywords, return all files (but limit to 150)
            return root_files[:150]
        
        candidates = []
        file_notes = self.memory.get("file_notes", {})
        
        for f in root_files:
            name_lower = f.get('name', '').lower()
            path_lower = f.get('path', '').lower()
            
            # Check filename
            if any(kw in name_lower for kw in keywords):
                candidates.append(f)
                continue
            
            # Check course code in parsed data
            parsed = f.get('parsed', {})
            course = parsed.get('course', '').lower()
            if course and any(kw in course for kw in keywords):
                candidates.append(f)
                continue
            
            # Check subject hints
            subject_hints = parsed.get('subject_hints', [])
            if any(kw in ' '.join(subject_hints).lower() for kw in keywords):
                candidates.append(f)
                continue
            
            # Check file notes
            file_path = f.get('path', '')
            note = file_notes.get(file_path, '').lower()
            if note and any(kw in note for kw in keywords):
                candidates.append(f)
                continue
        
        # Return top 50-150 candidates (or all if <50)
        if len(candidates) < 50:
            return candidates
        return candidates[:150]
    
    def _pre_group_files(self, root_files, categories):
        """Pre-group files by clear signals and auto-assign obvious matches."""
        auto_assigned = {}
        ambiguous = []
        
        if not categories:
            # No categories, all files are ambiguous
            return {}, root_files
        
        # Get category names
        category_names = [cat.lower() for cat in categories.keys() if cat]
        
        # Extension-based auto-assignment
        extension_map = {
            '.pdf': ['documents', 'pdfs', 'docs'],
            '.docx': ['documents', 'docs'],
            '.doc': ['documents', 'docs'],
            '.txt': ['documents', 'text'],
            '.py': ['code', 'projects', 'programming'],
            '.js': ['code', 'projects', 'programming'],
            '.java': ['code', 'projects', 'programming'],
            '.cpp': ['code', 'projects', 'programming'],
            '.c': ['code', 'projects', 'programming'],
            '.jpg': ['images', 'photos'],
            '.jpeg': ['images', 'photos'],
            '.png': ['images', 'photos'],
            '.gif': ['images', 'photos'],
            '.mp4': ['videos', 'video'],
            '.mov': ['videos', 'video'],
            '.mp3': ['music', 'audio'],
            '.wav': ['music', 'audio'],
        }
        
        for file_info in root_files:
            file_path = file_info.get('path', '')
            # Skip files already in category folders
            if '/' in file_path:
                continue
            
            assigned = False
            name_lower = file_info.get('name', '').lower()
            ext = file_info.get('extension', '').lower()
            
            # Check extension-based assignment
            if ext in extension_map:
                for possible_cat in extension_map[ext]:
                    for cat_name in category_names:
                        if possible_cat in cat_name or cat_name in possible_cat:
                            if cat_name not in auto_assigned:
                                auto_assigned[cat_name] = []
                            auto_assigned[cat_name].append(file_info)
                            assigned = True
                            break
                    if assigned:
                        break
            
            # Check course code matching
            if not assigned:
                parsed = file_info.get('parsed', {})
                course = parsed.get('course', '').lower()
                if course:
                    for cat_name in category_names:
                        if course in cat_name or cat_name in course:
                            if cat_name not in auto_assigned:
                                auto_assigned[cat_name] = []
                            auto_assigned[cat_name].append(file_info)
                            assigned = True
                            break
            
            # Check keyword matching in filename
            if not assigned:
                for cat_name in category_names:
                    # Check if category keyword appears in filename
                    cat_words = cat_name.split()
                    if any(word in name_lower for word in cat_words if len(word) > 2):
                        if cat_name not in auto_assigned:
                            auto_assigned[cat_name] = []
                        auto_assigned[cat_name].append(file_info)
                        assigned = True
                        break
            
            # If not assigned, it's ambiguous
            if not assigned:
                ambiguous.append(file_info)
        
        return auto_assigned, ambiguous
    
    def _build_file_context(self, user_message, intent):
        """Build file context based on intent, using pre-filtering and pre-grouping."""
        file_context = ""
        file_notes_text = ""
        
        if not self.memory or "file_index" not in self.memory:
            return file_context, file_notes_text
        
        all_files = self.memory["file_index"].get("all_files", [])
        if not all_files:
            return file_context, file_notes_text
        
        # Get root files (not in subdirectories) - files already categorized are in subdirs, so excluded
        root_files = [f for f in all_files if "/" not in f.get("path", "") or f.get("path", "").count("/") == 0]
        
        if not root_files:
            return file_context, file_notes_text
        
        # Get file notes
        file_notes = self.memory.get("file_notes", {})
        
        if intent == "read":
            # Only show specific file if mentioned
            keywords = self._extract_keywords(user_message)
            if keywords:
                matching_files = [f for f in root_files if any(kw in f.get('name', '').lower() for kw in keywords)]
                if matching_files:
                    file_info = matching_files[0]
                    file_id = self._get_file_id(file_info)
                    name = file_info.get('name', '')
                    note = file_notes.get(file_info.get('path', ''), '')
                    if note:
                        note = note[:120]  # Micro-note
                        file_context = f"\nFile: {name}\nFile ID: {file_id} | Note: {note}\n"
                    else:
                        file_context = f"\nFile: {name}\nFile ID: {file_id}\n"
        
        elif intent == "organize":
            # Check if user mentioned a specific category
            user_lower = user_message.lower()
            mentioned_category = None
            if self.memory and "categories" in self.memory:
                categories = self.memory.get("categories", {})
                for cat in categories.keys():
                    if cat and cat.lower() in user_lower:
                        mentioned_category = cat
                        break
            
            # Pre-group files
            categories = self.memory.get("categories", {})
            auto_assigned, ambiguous = self._pre_group_files(root_files, categories)
            
            # If specific category mentioned, show ALL files (not just ambiguous) so AI can match them
            if mentioned_category:
                file_context = f"\nFiles to organize into '{mentioned_category}' category ({len(root_files)} files in root):\n"
                for file_info in root_files[:100]:  # Show up to 100 files
                    name = file_info.get('name', '')
                    parsed = file_info.get('parsed', {})
                    
                    # Compressed format: filename | keyword | course_code
                    signals = [name]
                    if parsed.get('type'):
                        signals.append(parsed['type'])
                    if parsed.get('course'):
                        signals.append(parsed['course'])
                    
                    file_context += f"  - {' | '.join(signals[:3])}\n"
                
                if len(root_files) > 100:
                    file_context += f"  ... and {len(root_files) - 100} more files\n"
                
                # Include notes for files
                notes_lines = []
                for file_info in root_files[:100]:
                    file_path = file_info.get('path', '')
                    note = file_notes.get(file_path, '')
                    if note:
                        note = note[:120]  # Micro-note
                        file_id = self._get_file_id(file_info)
                        notes_lines.append(f"File ID: {file_id} | Note: {note}")
                
                if notes_lines:
                    file_notes_text = "\nFile notes:\n" + "\n".join(notes_lines[:100]) + "\n"
            else:
                # Show auto-assigned summary
                if auto_assigned:
                    file_context = "\nAuto-assigned files (no AI needed):\n"
                    for cat, files in auto_assigned.items():
                        file_context += f"  - {len(files)} files → {cat}\n"
                
                # Show ambiguous files (compressed format)
                if ambiguous:
                    if file_context:
                        file_context += "\n"
                    file_context += f"Ambiguous files to categorize ({len(ambiguous)} files):\n"
                    for file_info in ambiguous[:50]:  # Limit to 50
                        name = file_info.get('name', '')
                        parsed = file_info.get('parsed', {})
                        
                        # Compressed format: filename | keyword | course_code
                        signals = [name]
                        if parsed.get('type'):
                            signals.append(parsed['type'])
                        if parsed.get('course'):
                            signals.append(parsed['course'])
                        
                        file_context += f"  - {' | '.join(signals[:3])}\n"
                    
                    if len(ambiguous) > 50:
                        file_context += f"  ... and {len(ambiguous) - 50} more ambiguous files\n"
                    
                    # Include notes for ambiguous files only (micro-notes, max 120 chars)
                    notes_lines = []
                    for file_info in ambiguous[:50]:
                        file_path = file_info.get('path', '')
                        note = file_notes.get(file_path, '')
                        if note:
                            note = note[:120]  # Micro-note
                            file_id = self._get_file_id(file_info)
                            notes_lines.append(f"File ID: {file_id} | Note: {note}")
                    
                    if notes_lines:
                        file_notes_text = "\nFile notes:\n" + "\n".join(notes_lines[:50]) + "\n"  # Limit to 50 notes
        
        elif intent == "list":
            # Show filtered candidates (top 20-30)
            candidates = self._prefilter_files(user_message, root_files)
            if candidates:
                file_context = f"\nFiles ({len(candidates)} found):\n"
                for file_info in candidates[:30]:
                    name = file_info.get('name', '')
                    file_context += f"  - {name}\n"
                if len(candidates) > 30:
                    file_context += f"  ... and {len(candidates) - 30} more\n"
        
        elif intent == "scan_all":
            # Show file type summary only
            files_by_ext = {}
            for file_info in root_files:
                ext = file_info.get("extension", "no extension")
                files_by_ext[ext] = files_by_ext.get(ext, 0) + 1
            
            if files_by_ext:
                file_context = f"\nFile types in root ({len(root_files)} files):\n"
                for ext, count in sorted(files_by_ext.items(), key=lambda x: x[1], reverse=True)[:10]:
                    file_context += f"  - {ext or '(no extension)'}: {count} files\n"
        
        elif intent == "create":
            # For create folder/category, don't need file context
            # The AI just needs to create the folder
            pass
        
        # For chat intent, don't include file list unless user mentions files
        # (handled by prefilter_files returning empty if no keywords)
        
        return file_context, file_notes_text
    
    def _build_static_prompt(self):
        """Build and cache static system prompt (sent once per session)."""
        if self.static_prompt:
            return self.static_prompt
        
        allowed_paths_text = "\n".join([f"  - {path}" for path in self.allowed_paths]) if self.allowed_paths else f"  - {self.ROOT}/SortMe (default)"
        
        static = """File organization AI. Two outputs required:

CONVERSATION: <natural reply>
COMMAND: <JSON action>

Actions: list_files, read_file, list_all_files, move_file, create_folder, file_type, none

Examples:
User: "create a folder named math"
→ CONVERSATION: "Creating folder 'math'..."
→ COMMAND: {"action": "create_folder", "args": {"path": "math"}, "message": "Creating folder math"}

User: "put files into math" or "organize files into math" or "sort files into math"
→ CONVERSATION: "Organizing files into math category..."
→ COMMAND: [{"action": "move_file", "args": {"src": "calculus_hw1.pdf", "dst": "math/calculus_hw1.pdf"}, ...}, ...]

User: "organize my files"
→ CONVERSATION: "Organizing files into categories..."
→ COMMAND: [{"action": "move_file", "args": {"src": "file1.pdf", "dst": "Documents/file1.pdf"}, ...}, ...]

Rules:
- "create a category X" or "create category X" or "create folder X" → MUST use create_folder with path=X
- "put files into X" or "organize into X" or "sort into X" → MUST use move_file actions to move matching files
- BE PROACTIVE: When user asks to organize into a category, look at available files and move matching ones
- Match files by keywords in filename/notes (e.g., math: math, calculus, algebra, equation, problem, homework, geometry, trig)
- If filename contains category-related keywords, move it. Better to try than ask for clarification.
- DO NOT ask "what files?" or "which files?" - just look at the file list and match them
- If files are listed above, use move_file actions. Don't ask for more information.
- Only access: {ALLOWED_PATHS}
- Always output both CONVERSATION and COMMAND""".replace("{ALLOWED_PATHS}", allowed_paths_text)
        
        self.static_prompt = static
        return static
    
    def _build_dynamic_prompt(self, user_message, intent, conversation_history):
        """Build dynamic prompt (changes per request)."""
        # Build file context
        file_context, file_notes_text = self._build_file_context(user_message, intent)
        
        # Build categories (simplified)
        categories_text = ""
        if self.memory and "categories" in self.memory and self.memory["categories"]:
            categories = self.memory["categories"]
            valid_categories = [cat for cat, path in categories.items() if cat and path]
            if valid_categories:
                categories_text = f"\nCategories: {', '.join(sorted(valid_categories))}\n"
                # If user mentions a specific category, emphasize it
                user_lower = user_message.lower()
                mentioned_category = None
                for cat in valid_categories:
                    if cat.lower() in user_lower:
                        mentioned_category = cat
                        break
                
                if mentioned_category:
                    categories_text += f"\nIMPORTANT: User wants to organize files into '{mentioned_category}' category.\n"
                    # Provide keyword hints based on category
                    if mentioned_category.lower() == "math":
                        categories_text += f"Match files containing: math, calculus, algebra, geometry, equation, problem, homework, trig, derivative, integral, formula\n"
                    elif "doc" in mentioned_category.lower():
                        categories_text += f"Match files with extensions: .pdf, .doc, .docx, .txt, .rtf\n"
                    else:
                        categories_text += f"Match files by keywords related to '{mentioned_category}' in filename or notes.\n"
                    categories_text += "BE PROACTIVE: Look at the files listed above and move matching ones using move_file actions.\n"
                    categories_text += "If a file's name contains category-related keywords, move it. Don't ask for clarification - just do it.\n"
                    categories_text += "Output multiple move_file actions in an array.\n"
                else:
                    categories_text += "Match files to categories by name/keywords. Use move_file actions.\n"
        
        # Build conversation history (last 3 messages = 1 exchange)
        history_text = ""
        if conversation_history:
            recent_history = conversation_history[-3:]  # Last 3 messages
            history_lines = []
            for msg in recent_history:
                role = "User" if msg.get("role") == "user" else "Assistant"
                content = msg.get("content", "")
                if content:
                    history_lines.append(f"{role}: {content}")
            if history_lines:
                history_text = "\nRecent conversation:\n" + "\n".join(history_lines) + "\n"
        
        dynamic = f"""{history_text}{file_notes_text}{file_context}{categories_text}

User: {user_message}"""
        
        return dynamic

    # DECIDE INTENT

    def detect_intent(self, text):
        t = text.lower()

        if any(word in t for word in ["yo", "sup", "hey", "hi", "hello"]):
            return "chat"

        # Check for create folder/category intent first (before organize)
        if any(phrase in t for phrase in ["create a category", "create category", "make a category", "make category", 
                                          "create a folder", "create folder", "make a folder", "make folder"]):
            return "create"

        if "list" in t or "show" in t:
            return "list"

        if "name" in t or "give me" in t:
            return "name"

        if "read" in t or "open" in t:
            return "read"

        if "move" in t or "clean" in t or "organize" in t:
            return "organize"

        if "scan" in t or "everything" in t:
            return "scan_all"

        return "chat"

    # CALL LOCAL AI

    def call_local_ai(self, user_message, conversation_history=None):
        """Call the local Ollama AI model with optimized token usage."""
        conversation_history = conversation_history or []
        
        # Reload memory to get latest file index and other updates
        self.memory = load_memory()
        
        # Detect intent for context building
        intent = self.detect_intent(user_message)
        
        # Build prompts (static cached, dynamic per request)
        static_prompt = self._build_static_prompt()
        dynamic_prompt = self._build_dynamic_prompt(user_message, intent, conversation_history)
        
        # Combine static + dynamic
        full_prompt = static_prompt + "\n\n" + dynamic_prompt
        
        try:
            data = {
                "model": self.ai_model,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "num_ctx": 4096  # Cap context size to 4096 tokens
                }
            }
            response = requests.post(self.ai_url, json=data, timeout=30)
            response.raise_for_status()
            return response.json().get("response", "").strip()
        except requests.exceptions.ConnectionError:
            # Ollama not running
            return f"CONVERSATION:\nI can't connect to Ollama. Make sure it's running on localhost:11434\n\nCOMMAND:\n{{\"action\": \"none\", \"args\": {{}}, \"message\": \"AI unavailable\"}}"
        except requests.exceptions.Timeout:
            return f"CONVERSATION:\nThe AI request timed out. The model might be slow or not responding.\n\nCOMMAND:\n{{\"action\": \"none\", \"args\": {{}}, \"message\": \"AI timeout\"}}"
        except Exception as e:
            # Fallback to simple responses if AI is unavailable
            return f"CONVERSATION:\nSorry, I'm having trouble connecting to the AI model. Error: {str(e)}\n\nCOMMAND:\n{{\"action\": \"none\", \"args\": {{}}, \"message\": \"AI unavailable\"}}"

    # PARSE AI OUTPUT
    def parse_ai_output(self, raw_output):
        """
        Splits the AI output into two parts:
        - conversation text (str)
        - command JSON (dict)
        """
        if not isinstance(raw_output, str) or not raw_output.strip():
            return ("No response from AI", {"action": "none", "args": {}, "message": "Invalid output"})

        # Normalize line endings
        text = raw_output.replace("\r", "")

        # Split into two required sections
        if "CONVERSATION:" not in text or "COMMAND:" not in text:
            # Try to extract JSON if it's just JSON
            try:
                # Maybe the AI just returned JSON directly
                command_json = json.loads(text.strip())
                return ("Processing your request...", command_json)
            except:
                # Return the raw output as conversation, no command
                return (text[:200] + ("..." if len(text) > 200 else ""), {"action": "none", "args": {}, "message": "AI response format unexpected"})

        conv_part = text.split("CONVERSATION:", 1)[1]
        command_split = conv_part.split("COMMAND:", 1)

        conversation_text = command_split[0].strip()
        command_text = command_split[1].strip() if len(command_split) > 1 else ""

        # Attempt to parse JSON in COMMAND block
        if not command_text:
            return (conversation_text or "Processing...", {"action": "none", "args": {}, "message": "No command block found"})
        
        try:
            command_json = json.loads(command_text)
            # Handle array of actions
            if isinstance(command_json, list):
                return (conversation_text or "Processing...", {"actions": command_json, "message": f"Executing {len(command_json)} action(s)"})
        except json.JSONDecodeError as e:
            # Try to extract JSON from the text if it's embedded
            import re
            json_match = re.search(r'\{[^{}]*\}', command_text)
            if json_match:
                try:
                    command_json = json.loads(json_match.group())
                except:
                    command_json = {"action": "none", "args": {}, "message": f"JSON parse error: {str(e)}"}
            else:
                command_json = {"action": "none", "args": {}, "message": f"Could not parse JSON: {str(e)}"}

        return (conversation_text or "Processing...", command_json)

    # MAIN ENTRY: INTERPRET USER REQUEST
    
    def interpret(self, text, conversation_history=None):
        # Try to use AI for all requests (it's smart enough to handle chat vs commands)
        try:
            ai_response = self.call_local_ai(text, conversation_history=conversation_history or [])
            if not ai_response:
                raise ValueError("Empty response from AI")
            
            conversation, command = self.parse_ai_output(ai_response)
            
            # Determine mode based on action
            action = command.get("action", "none")
            if action == "none" or action == "chat":
                reply = conversation or command.get("message", "") or "I'm here!"
                return {
                    "mode": "chat",
                    "reply": reply
                }
            else:
                return {
                    "mode": "command",
                    "conversation": conversation or "Processing...",
                    "command": command
                }
        except Exception as e:
            # Fallback to simple keyword matching if AI fails
            error_msg = f"AI unavailable, using fallback. Error: {str(e)}"
        intent = self.detect_intent(text)

        if intent == "chat":
            return {
                "mode": "chat",
                    "reply": self.generate_chat_reply(text) + f" ({error_msg})"
            }

        return {
            "mode": "command",
                "conversation": self.generate_chat_reply(text) + f" ({error_msg})",
            "command": self.generate_command(text, intent)
        }


    # CHAT RESPONSE GENERATOR
    # (Purely conversational mind)

    def generate_chat_reply(self, user_text):
        user_text = user_text.lower()

        if "name" in user_text:
            return "Sure, let me take a look…"

        if "list" in user_text:
            return "Okay, scanning the folder now…"

        if "organize" in user_text:
            return "Alright, I’ll clean things up…"

        if "read" in user_text:
            return "Let me open that real quick…"

        return "Got you."

    # COMMAND GENERATOR
    # (Hidden mind → produces JSON)

    def generate_command(self, text, intent):
        DESKTOP = os.path.join(self.ROOT, "Desktop")

        # CREATE FOLDER/CATEGORY
        if intent == "create":
            # Extract folder name from text
            text_lower = text.lower()
            folder_name = None
            
            # Try to extract folder name from common patterns
            patterns = [
                r"create\s+(?:a\s+)?(?:category|folder)\s+(?:called|named|for)?\s+['\"]?(\w+)['\"]?",
                r"make\s+(?:a\s+)?(?:category|folder)\s+(?:called|named|for)?\s+['\"]?(\w+)['\"]?",
                r"create\s+['\"]?(\w+)['\"]?\s+(?:category|folder)",
                r"make\s+['\"]?(\w+)['\"]?\s+(?:category|folder)",
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    folder_name = match.group(1)
                    break
            
            # If no pattern matched, try to find a word after "category" or "folder"
            if not folder_name:
                words = text.split()
                for i, word in enumerate(words):
                    if word.lower() in ["category", "folder"] and i + 1 < len(words):
                        folder_name = words[i + 1].strip("'\".,!?")
                        break
            
            if folder_name:
                return {
                    "action": "create_folder",
                    "args": {"path": folder_name},
                    "message": f"Creating folder: {folder_name}"
                }
            else:
                return {
                    "action": "create_folder",
                    "args": {"path": ""},
                    "message": "Creating folder"
                }

        # LIST or NAME
        if intent in ["list", "name"]:
            return {
                "action": "list_files",
                "args": {"path": DESKTOP, "limit": 1},
                "message": "Listing files on desktop"
            }

        # READ FILE
        if intent == "read":
            return {
                "action": "read_file",
                "args": {"path": DESKTOP},
                "message": "Reading a file from desktop"
            }

        # ORGANIZE FILES
        if intent == "organize":
            # Example: just scan everything (you expand later)
            return {
                "action": "list_all_files",
                "args": {"path": self.ROOT},
                "message": "Scanning all your files"
            }

        # SCAN ALL
        if intent == "scan_all":
            return {
                "action": "list_all_files",
                "args": {"path": self.ROOT},
                "message": "Deep scan of home directory"
            }

        # DEFAULT
        return {
            "action": "none",
            "args": {},
            "message": "No file action required"
        }

