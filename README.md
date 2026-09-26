# Multi-Agent AI Chatbot for Document & PPT Generation

An enterprise-grade multi-agent AI chatbot Proof of Concept (POC) that understands user requests, analyzes uploaded documents and PPT templates, performs real-time web research, retrieves information from enterprise knowledge sources, and generates professional, editable documents and presentations.

---

## Architecture

```
## System Architecture

```text
                            ┌─────────────────┐
                            │      USER       │
                            └────────┬────────┘
                                     │
                                     ▼
                       ┌─────────────────────────┐
                       │    React Frontend       │
                       │  Chat • Upload • Edit   │
                       │  Trace • Versions       │
                       └────────────┬────────────┘
                                    │
                              REST API / HTTP
                                    │
                                    ▼
                       ┌─────────────────────────┐
                       │    FastAPI Backend      │
                       │     API Layer           │
                       └────────────┬────────────┘
                                    │
                                    ▼
                 ┌─────────────────────────────────────┐
                 │     LangGraph Supervisor             │
                 │   Orchestrator / Workflow Manager    │
                 └──────────────┬──────────────────────┘
                                │
             ┌──────────────────┼──────────────────┐
             │                  │                  │
             ▼                  ▼                  ▼
      ┌──────────────┐   ┌──────────────┐   ┌────────────────┐
      │    DOC       │   │     PPT      │   │      WEB       │
      │   ANALYZER   │   │   ANALYZER   │   │   RESEARCHER   │
      └──────┬───────┘   └──────┬───────┘   └───────┬────────┘
             │                  │                    │
             └──────────────────┼────────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │    RAG Agent    │
                       └────────┬────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │    ChromaDB     │
                       │  Vector Store   │
                       └────────┬────────┘
                                │
                                ▼
                  ┌─────────────────────────────┐
                  │     Content Generation      │
                  └──────────────┬──────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                    ▼                         ▼
             ┌──────────────┐         ┌──────────────┐
             │ DOCX Builder │         │ PPTX Builder │
             │ python-docx  │         │ python-pptx  │
             └──────┬───────┘         └──────┬───────┘
                    │                         │
                    └────────────┬────────────┘
                                 │
                                 ▼
                       ┌─────────────────┐
                       │    Validator    │
                       │ Quality Checks  │
                       └────────┬────────┘
                                │
                                ▼
                  ┌──────────────────────────┐
                  │  Conversational Editor   │
                  │   Natural Language Edit  │
                  └────────────┬─────────────┘
                               │
                               ▼
                       ┌─────────────────┐
                       │ Final Artifact  │
                       │ DOCX / PPTX     │
                       └────────┬────────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
                    ▼                       ▼
             ┌──────────────┐       ┌──────────────┐
             │   Version    │       │   Download   │
             │   History    │       │    Files     │
             └──────────────┘       └──────────────┘
```

## Features

### Multi-Agent System (9 Specialized Agents)
| Agent | Role |
|---|---|
| **Supervisor/Orchestrator** | Plans workflow, routes tasks to agents, aggregates results |
| **Document Analyzer** | Parses DOCX, PDF, images; extracts structure, font, and style |
| **PPT Analyzer** | Parses PPTX; extracts layouts, themes, slide masters, and fonts |
| **Web Researcher** | Performs real-time web search via Tavily API |
| **RAG Agent** | Retrieves enterprise knowledge from ChromaDB |
| **Document Generator** | Creates editable DOCX with style transfer |
| **PPT Generator** | Creates editable PPTX natively using imported templates |
| **Validator** | Quality checks generated artifacts |
| **Conversational Editor** | Modifies existing documents via natural language |

### Supported Capabilities
- ✅ **Upload & Analyze**: Supports DOCX, PDF, PPTX, and images (with built-in OCR).
- ✅ **Style Extraction**: Extracts tone, formatting, and structure from templates.
- ✅ **Web & RAG Integration**: Real-time web research and enterprise RAG with ChromaDB.
- ✅ **Editable DOCX Generation**: Full style transfer preserving branding.
- ✅ **Native PPTX Generation**: LLM-generated presentations natively adopt your uploaded Master Slides, Themes, Layouts, Fonts, Colors, Backgrounds, Text Styles, Shapes, Images, Tables, Charts, Element Positions, and Spacing.
- ✅ **Interactive UI Preview**: View and directly edit generated files via an inline Quick Edit AI input without leaving the document card.
- ✅ **In-App Editing & Export**: Conversational editing preserves formatting, triggering instant UI updates and seamless one-click downloads.
- ✅ **Image Insertion**: Modal UI to insert logos and images at specific targets.
- ✅ **Full Version History**: Navigate through past revisions of all generated artifacts.
- ✅ **Source Citations**: Traceability for all LLM facts and web research.
- ✅ **Agent Trace**: Full transparency into agent execution logs.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **LLM** | Groq API (Llama 3.1 70B) |
| **Orchestration** | LangGraph |
| **Embeddings** | sentence-transformers (all-MiniLM-L6-v2) |
| **Vector DB** | ChromaDB (local) |
| **Web Search** | Tavily API |
| **OCR** | Tesseract (pytesseract) |
| **File Builders** | python-docx, python-pptx, PyMuPDF (fitz) |
| **Backend** | FastAPI + Uvicorn |
| **Frontend** | React 18 + Vite |

---

## Setup Instructions

### Prerequisites
- **Python 3.10+**
- **Node.js 18+** and npm
- **Tesseract OCR** (optional, for scanned documents)
  - Windows: [Download installer](https://github.com/UB-Mannheim/tesseract/wiki)

### Step 1: Clone & Setup Environment

```bash
# Navigate to the project
cd "d:\PROJECTS\End To End PROJECTS\6.- Multi-Agent AI Chatbot for Document and PPT Generation"

# Create and activate Python virtual environment
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # macOS/Linux

# Install Python dependencies
pip install -r requirements.txt
```

### Step 2: Get API Keys (Free)
1. **Groq API Key**: Go to [console.groq.com](https://console.groq.com) → API Keys → Create new key
2. **Tavily API Key**: Go to [app.tavily.com](https://app.tavily.com) → Dashboard → Copy API key

### Step 3: Configure Environment
Copy the example `.env` file:
```bash
copy .env.example .env    # Windows
# cp .env.example .env    # macOS/Linux
```
Edit `.env` and paste your API keys:
```env
GROQ_API_KEY=gsk_xxxxxxxxxxxxx
TAVILY_API_KEY=tvly-xxxxxxxxxxxxx
```

### Step 4: Generate Sample Templates (Optional)
Run the script to generate local testing templates:
```bash
python scripts/generate_samples.py
```
This creates `sample_templates/Company_Proposal.docx` and `sample_templates/Company_Template.pptx`.

### Step 5: Start the Servers
You can use the provided batch scripts for convenience:
```bash
# Open terminal 1
.\start_backend.bat
# API available at: http://localhost:8000
# Swagger docs: http://localhost:8000/api/docs

# Open terminal 2
.\start_frontend.bat
# UI available at: http://localhost:5173
```





SET UP For python backend  
# Navigate to the project folder
cd "d:\PROJECTS\End To End PROJECTS\6.- Multi-Agent AI Chatbot for Document and PPT Generation"

# Create a virtual environment (so your global Python stays clean)
python -m venv venv

# Activate the virtual environment
.\venv\Scripts\activate

# Install all the required Python libraries
pip install -r requirements.txt

# Generate Sample Templates
python scripts/generate_samples.py

#  Start the Backend Server
.\start_backend.bat


Set Up and Start the React Frontend

# Navigate to the frontend folder
cd "d:\PROJECTS\End To End PROJECTS\6.- Multi-Agent AI Chatbot for Document and PPT Generation\frontend"

# Install Node.js dependencies and start the frontend UI
cd frontend

npm install

cd ..

# Start the frontend UI
npm run dev


#  just run root folder if you have that script configured
.\start_frontend.bat
---





## Usage Guidelines

### Basic Workflow

1. **Upload Templates**: Drag & drop your DOCX/PPTX templates into the left panel.
2. **Give Instructions**: Type your request in the central chat panel.
3. **Wait for Agents**: Watch the Agent Trace panel on the right to see each LangGraph agent executing in real time.
4. **Download Files**: Generated files appear in the right panel under the "Files" tab — click to download.
5. **Quick Edit AI**: Use the inline "Quick Edit via AI" text box directly on the file card to modify the document conversationally.
6. **Insert Images**: Click "Insert Image" on a DOCX card to dynamically inject logos or graphics into specific sections.

### Example Prompts

| Prompt | Agent Action |
|---|---|
| *"Research AI trends and write a professional proposal"* | Web Researcher → Document Generator |
| *"Create a 12-slide presentation on cloud computing"* | PPT Generator builds natively on uploaded template |
| *"Make the presentation more concise"* | Editor Agent trims slide content directly |
| *"Add an executive summary to the document"* | Editor Agent adds a styled section to the DOCX |
| *"Insert the company logo at the top cover"* | Triggers specialized Image Insertion flow |

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/chat` | POST | Send message to multi-agent orchestrator |
| `/api/upload` | POST | Upload template files |
| `/api/download/{filename}` | GET | Download generated file |
| `/api/versions/{artifact_id}` | GET | Get version history |
| `/api/artifacts` | GET | List all generated artifacts |
| `/api/knowledge` | GET | RAG knowledge base stats |
| `/health` | GET | System health check |

---

## Project Structure

```
├── backend/
│   ├── main.py                    # FastAPI application
│   ├── config.py                  # Pydantic settings
│   ├── agents/
│   │   ├── orchestrator.py        # LangGraph supervisor
│   │   ├── document_analyzer.py   # PDF/DOCX analysis
│   │   ├── ppt_analyzer.py        # PPTX analysis
│   │   ├── web_researcher.py      # Tavily web search
│   │   ├── rag_agent.py           # ChromaDB retrieval
│   │   ├── doc_generator.py       # DOCX generation
│   │   ├── ppt_generator.py       # PPTX generation
│   │   ├── validator.py           # Content validation
│   │   └── editor.py              # Conversational editor
│   ├── tools/
│   │   ├── ocr.py                 # Tesseract OCR
│   │   ├── pdf_parser.py          # PyMuPDF PDF parser
│   │   ├── docx_parser.py         # python-docx parser
│   │   ├── pptx_parser.py         # python-pptx parser
│   │   └── style_extractor.py     # Style extraction
│   ├── rag/
│   │   ├── embedder.py            # sentence-transformers
│   │   ├── vector_store.py        # ChromaDB interface
│   │   └── retriever.py           # RAG retrieval logic
│   ├── generators/
│   │   ├── docx_builder.py        # DOCX builder
│   │   └── pptx_builder.py        # PPTX builder
│   └── versioning/
│       └── version_manager.py     # Version tracking
├── frontend/
│   ├── src/
│   │   ├── App.jsx                # Main app layout
│   │   ├── components/
│   │   │   ├── ChatPanel.jsx      # Chat interface
│   │   │   ├── FileUploader.jsx   # Drag & drop upload
│   │   │   ├── AgentTracePanel.jsx# Agent execution trace
│   │   │   ├── DocumentViewer.jsx # Artifact downloads & Quick Edit
│   │   │   ├── InsertImageModal.jsx # Image upload modal
│   │   │   └── VersionHistory.jsx # Version browser
│   │   └── api/
│   │       └── client.js          # Axios API client
│   └── package.json
├── chroma_db/                     # Local ChromaDB vector database storage
├── generated/                     # Directory for generated artifacts and outputs
├── scripts/
│   └── generate_samples.py        # Sample template generator
├── sample_templates/              # Generated test template files
├── uploads/                       # Directory for user uploaded files
├── versions/                      # Artifact version history tracking
├── requirements.txt               # Python dependencies
├── start_backend.bat              # Batch script to start the FastAPI backend
├── start_frontend.bat             # Batch script to start the React frontend
├── .env                           # Environment variables
└── README.md
```

---

## License

This is a POC (Proof of Concept) project for educational and demonstration purposes.
