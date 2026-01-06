"""
Content Analyzer - Analyze file content and store summaries, chunks, and keywords
Uses hybrid storage: summaries for large files, chunks for small files, keywords for all
"""
import re
from typing import Dict, Optional, List
import requests
from config import get_ai_model


def extract_keywords(text: str, max_keywords: int = 15) -> List[str]:
    """
    Extract keywords from text content.
    Uses simple frequency-based extraction with common word filtering.
    """
    if not text or len(text) < 10:
        return []
    
    # Convert to lowercase
    text_lower = text.lower()
    
    # Remove common stop words
    stop_words = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
        "by", "from", "as", "is", "was", "are", "were", "be", "been", "being", "have", "has",
        "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "must",
        "can", "this", "that", "these", "those", "i", "you", "he", "she", "it", "we", "they",
        "what", "which", "who", "when", "where", "why", "how", "all", "each", "every", "some",
        "any", "no", "other", "another", "such", "only", "just", "more", "most", "many", "much",
        "few", "little", "very", "too", "so", "also", "even", "still", "yet", "already",
    }
    
    # Extract words (3+ characters, alphanumeric)
    words = re.findall(r'\b[a-z0-9]{3,}\b', text_lower)
    
    # Count frequencies
    word_counts = {}
    for word in words:
        if word not in stop_words and len(word) >= 3:
            word_counts[word] = word_counts.get(word, 0) + 1
    
    # Sort by frequency and get top keywords
    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
    keywords = [word for word, count in sorted_words[:max_keywords]]
    
    return keywords


def generate_summary(content: str, ai_url: str = "http://localhost:11434/api/generate", 
                     model: Optional[str] = None) -> Optional[str]:
    """
    Generate an AI summary of the content using Ollama.
    Returns a 2-3 sentence summary.
    """
    if model is None:
        model = get_ai_model()
    if not content or len(content) < 50:
        return None
    
    # Truncate content if too long (keep first 5000 chars for summary)
    content_for_summary = content[:5000] if len(content) > 5000 else content
    
    prompt = f"""Summarize the following content in 2-3 sentences. Focus on the main topic, purpose, and key information:

{content_for_summary}

Summary:"""
    
    try:
        response = requests.post(
            ai_url,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 150,  # Limit summary length
                    "num_ctx": 4096  # Cap context size
                }
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            summary = result.get("response", "").strip()
            # Clean up summary (remove "Summary:" prefix if present)
            summary = re.sub(r'^Summary:\s*', '', summary, flags=re.IGNORECASE)
            return summary[:500] if summary else None  # Limit to 500 chars
    except Exception:
        # If AI summary fails, return None (will use keywords only)
        pass
    
    return None


def analyze_content(content_data: Dict, file_size: int = 0, 
                    ai_url: str = "http://localhost:11434/api/generate",
                    model: Optional[str] = None) -> Dict:
    """
    Analyze file content and return structured data with summary, keywords, and optionally chunks.
    
    Args:
        content_data: Dict with "content" key (text content) and "type" key (file type)
        file_size: Size of the file in bytes
        ai_url: URL for Ollama API
        model: Model name for Ollama
    
    Returns:
        Dict with:
        - summary: AI-generated summary (for large files) or None
        - keywords: List of extracted keywords
        - chunk: First 500-1000 chars (for small files only)
    """
    result = {
        "summary": None,
        "keywords": [],
        "chunk": None
    }
    
    content = content_data.get("content", "")
    content_type = content_data.get("type", "text")
    
    if not content:
        # For images, use metadata to generate keywords
        if content_type == "image" and "metadata" in content_data:
            metadata = content_data["metadata"]
            keywords = []
            if metadata.get("format"):
                keywords.append(metadata["format"].lower())
            if metadata.get("size"):
                keywords.append(f"{metadata['width']}x{metadata['height']}")
            result["keywords"] = keywords
        # For archives, use file list as keywords
        elif content_type == "archive" and "archive_contents" in content_data:
            contents = content_data["archive_contents"]
            # Extract file extensions and common names as keywords
            keywords = []
            for item in contents[:10]:
                if '.' in item:
                    ext = item.split('.')[-1].lower()
                    if ext not in keywords:
                        keywords.append(ext)
                # Add filename parts
                name_parts = item.split('/')[-1].split('_')
                for part in name_parts[:3]:
                    if len(part) > 2:
                        keywords.append(part.lower())
            result["keywords"] = list(set(keywords))[:15]
        return result
    
    # Extract keywords from content
    keywords = extract_keywords(content)
    result["keywords"] = keywords
    
    # Determine storage strategy based on file size
    size_threshold = 10 * 1024  # 10KB
    
    if file_size < size_threshold and len(content) < 10000:
        # Small file: store chunk
        chunk_length = min(1000, len(content))
        result["chunk"] = content[:chunk_length]
    else:
        # Large file: generate summary
        summary = generate_summary(content, ai_url, model)
        if summary:
            result["summary"] = summary
        # Also store a small chunk for context
        result["chunk"] = content[:500]
    
    return result


def analyze_file(file_info: Dict, content_data: Optional[Dict], 
                 ai_url: str = "http://localhost:11434/api/generate",
                 model: Optional[str] = None) -> Dict:
    """
    Analyze a file and add content analysis to file_info.
    
    Args:
        file_info: File info dict with at least "name", "full_path", "extension"
        content_data: Result from contentReader.read_file_content() or None
        ai_url: URL for Ollama API
        model: Model name for Ollama
    
    Returns:
        Updated file_info with "content" key added (if content_data provided)
    """
    if model is None:
        model = get_ai_model()
    if content_data is None:
        return file_info
    
    # Get file size
    try:
        from pathlib import Path
        file_path = Path(file_info.get("full_path", ""))
        if file_path.exists():
            file_size = file_path.stat().st_size
        else:
            file_size = 0
    except:
        file_size = 0
    
    # Analyze content
    analysis = analyze_content(content_data, file_size, ai_url, model)
    
    # Add to file_info
    file_info["content"] = analysis
    
    # If content_data has metadata or archive_contents, preserve it
    if "metadata" in content_data:
        file_info["content"]["metadata"] = content_data["metadata"]
    if "archive_contents" in content_data:
        file_info["content"]["archive_contents"] = content_data["archive_contents"]
    
    return file_info

