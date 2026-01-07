# AI File Organizer

An intelligent file organization assistant powered by local AI (Ollama) with a retro Windows 95-style GUI. Organize your files using natural language commands.

## Features

- AI-Powered Organization: Uses local Ollama models to understand natural language commands
- Smart File Sorting: Automatically categorizes files based on content, filename patterns, and user notes
- Retro UI: Windows 95-inspired interface
- Intelligent Indexing: Scans and analyzes files to build a searchable index
- File Notes: Add custom notes to files for better organization
- Category Management: Create and manage custom categories
- Optimized Performance: Token-optimized AI prompts for faster responses
- Sandboxed: Secure file operations with permission-based access control

## Requirements

- Python 3.12+
- Ollama installed and running locally
- At least one Ollama model (e.g., llama3.1:8b, llama3.2:3b)
- I used the qwen 2.5:14b- instruct but 14b was difficult to run and took forever even on my pc.
      Would recommend 7b just will require to give the ai more context

## Installation

1. Clone the repository:
```bash
git clone https://github.com/AayushPat/AI-file-sorter-.git
cd AI-file-sorter-
```

2. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install and start Ollama:
   - Download from https://ollama.ai/
   - Pull a model: `ollama pull llama3.1:8b`
   - Ensure Ollama is running on localhost:11434

## Usage

1. Run the application:
```bash
python app.py
```

2. On first launch, you'll be prompted to:
   - Select a root directory to organize
   - Choose an AI model from your installed Ollama models

3. Start organizing! Try commands like:
   - "create a folder named math"
   - "organize files into math"
   - "put all PDFs into documents"
   - "show me files related to calculus"

## How It Works

1. File Indexing: The app scans your selected directory and builds an index of all files
2. Content Analysis: Files are analyzed for keywords, course codes, and content summaries
3. AI Interpretation: Your natural language commands are interpreted by the local AI model
4. Smart Filtering: Files are pre-filtered and pre-grouped before being sent to the AI for efficiency
5. Action Execution: The AI generates file operations (move, create folder, etc.) which are executed safely

## Architecture

- `app.py` - Main GUI application
- `Interpreter.py` - Core AI interpreter with token optimization
- `file_indexing.py` - File scanning and indexing
- `contentAnalyzer.py` - Content analysis and summarization
- `tools.py` - File operation utilities
- `workers.py` - Background workers for AI processing
- `ui_builder.py` - UI component builders
- `memoryManagement.py` - Persistent storage for categories and notes

## Token Optimization

The application implements several optimization strategies to reduce AI token usage:

- Pre-filtering: Files are filtered locally using keyword matching before sending to AI
- Pre-grouping: Files are grouped by clear signals (extension, course code) and only ambiguous files are sent to AI
- Static/Dynamic Prompts: System instructions are cached and only dynamic content is sent each turn
- Micro-notes: File summaries are truncated to 120 characters
- Compressed Metadata: Only essential signals (filename, keywords, course code) are included
- Context Capping: AI context is limited to 4096 tokens for faster processing

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

