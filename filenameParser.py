"""
Filename Parser - Extract structured information from filenames
Extracts keywords, dates, course codes, file types, and subject hints
"""
import re
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


def parse_filename(filename: str) -> Dict:
    """
    Parse a filename to extract structured information.
    
    Returns a dict with:
    - keywords: List of extracted keywords
    - course: Course code if found (e.g., "CS240")
    - type: File type indicator (e.g., "homework", "lecture", "notes")
    - date: Date if found in filename
    - subject_hints: List of subject/topic keywords
    """
    name_lower = filename.lower()
    name_no_ext = Path(filename).stem.lower()
    
    parsed = {
        "keywords": [],
        "course": None,
        "type": None,
        "date": None,
        "subject_hints": []
    }
    
    # Extract course codes (e.g., CS240, MATH101, ENG200)
    course_patterns = [
        r'\b([A-Z]{2,4}\d{3,4})\b',  # CS240, MATH101
        r'\b([A-Z]{2,4}-\d{3,4})\b',  # CS-240
        r'\b([A-Z]{2,4}\s+\d{3,4})\b',  # CS 240
    ]
    for pattern in course_patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            parsed["course"] = match.group(1).upper()
            parsed["keywords"].append(parsed["course"])
            break
    
    # Extract dates (various formats)
    date_patterns = [
        r'\b(\d{4}-\d{2}-\d{2})\b',  # 2024-02-15
        r'\b(\d{2}-\d{2}-\d{4})\b',  # 02-15-2024
        r'\b(\d{2}/\d{2}/\d{4})\b',  # 02/15/2024
        r'\b(\d{4}\.\d{2}\.\d{2})\b',  # 2024.02.15
        r'\b(\d{4}_\d{2}_\d{2})\b',  # 2024_02_15
        r'\b(\d{2}-\d{2}-\d{2})\b',  # 02-15-24
    ]
    for pattern in date_patterns:
        match = re.search(pattern, filename)
        if match:
            date_str = match.group(1)
            # Try to parse and normalize
            try:
                if '-' in date_str:
                    parts = date_str.split('-')
                    if len(parts[0]) == 4:  # YYYY-MM-DD
                        parsed["date"] = date_str
                    elif len(parts[2]) == 4:  # MM-DD-YYYY
                        parsed["date"] = f"{parts[2]}-{parts[0]}-{parts[1]}"
                    else:  # MM-DD-YY
                        year = "20" + parts[2] if len(parts[2]) == 2 else parts[2]
                        parsed["date"] = f"{year}-{parts[0]}-{parts[1]}"
                elif '/' in date_str:
                    parts = date_str.split('/')
                    if len(parts[2]) == 4:  # MM/DD/YYYY
                        parsed["date"] = f"{parts[2]}-{parts[0]}-{parts[1]}"
                elif '.' in date_str or '_' in date_str:
                    parsed["date"] = date_str.replace('.', '-').replace('_', '-')
                else:
                    parsed["date"] = date_str
                parsed["keywords"].append(parsed["date"])
            except:
                parsed["date"] = date_str
            break
    
    # Extract file type indicators
    type_keywords = {
        "homework": ["hw", "homework", "assignment", "assign", "problem", "problemset", "pset"],
        "lecture": ["lecture", "lect", "class", "notes", "note"],
        "exam": ["exam", "test", "quiz", "midterm", "final"],
        "project": ["project", "proj", "lab", "assignment"],
        "document": ["doc", "document", "paper", "essay", "report"],
        "presentation": ["presentation", "pres", "slides", "ppt"],
        "code": ["code", "program", "script", "src", "source"],
    }
    
    for file_type, keywords in type_keywords.items():
        for keyword in keywords:
            if keyword in name_lower:
                parsed["type"] = file_type
                parsed["keywords"].append(keyword)
                break
        if parsed["type"]:
            break
    
    # Extract subject/topic keywords
    subject_keywords = {
        "math": ["math", "mathematics", "calculus", "algebra", "geometry", "statistics", "stat", "linear", "differential", "integral"],
        "computer science": ["cs", "computer", "programming", "code", "algorithm", "data structure", "software", "python", "java", "javascript"],
        "science": ["science", "physics", "chemistry", "biology", "bio", "chem", "physics"],
        "engineering": ["engineering", "eng", "mechanical", "electrical", "civil"],
        "business": ["business", "finance", "accounting", "economics", "econ", "marketing"],
        "language": ["english", "spanish", "french", "language", "literature", "writing"],
        "history": ["history", "hist", "historical"],
        "art": ["art", "design", "drawing", "painting", "creative"],
    }
    
    for subject, keywords in subject_keywords.items():
        for keyword in keywords:
            if keyword in name_lower:
                if subject not in parsed["subject_hints"]:
                    parsed["subject_hints"].append(subject)
                if keyword not in parsed["keywords"]:
                    parsed["keywords"].append(keyword)
    
    # Extract additional keywords (numbers, common words)
    # Extract numbers that might be relevant (assignment numbers, versions, etc.)
    numbers = re.findall(r'\b\d+\b', filename)
    for num in numbers[:3]:  # Limit to first 3 numbers
        if num not in parsed["keywords"] and len(num) <= 4:  # Skip very long numbers
            parsed["keywords"].append(num)
    
    # Extract common meaningful words (2+ chars, not too common)
    common_words = {"the", "and", "or", "of", "in", "on", "at", "to", "for", "a", "an"}
    words = re.findall(r'\b[a-z]{3,}\b', name_lower)
    for word in words:
        if word not in common_words and word not in parsed["keywords"]:
            # Only add if it's not already a part of a longer keyword
            is_substring = any(word in kw or kw in word for kw in parsed["keywords"] if len(kw) > 3)
            if not is_substring:
                parsed["keywords"].append(word)
    
    # Remove duplicates and sort
    parsed["keywords"] = sorted(list(set(parsed["keywords"])))
    parsed["subject_hints"] = sorted(list(set(parsed["subject_hints"])))
    
    return parsed


def parse_file_info(file_info: Dict) -> Dict:
    """
    Parse filename from a file_info dict and add parsed data.
    
    Args:
        file_info: Dict with at least "name" key
        
    Returns:
        Updated file_info dict with "parsed" key added
    """
    filename = file_info.get("name", "")
    if not filename:
        return file_info
    
    parsed_data = parse_filename(filename)
    file_info["parsed"] = parsed_data
    return file_info

