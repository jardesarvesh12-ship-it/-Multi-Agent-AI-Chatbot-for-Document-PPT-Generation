# Multi-Agent AI Chatbot for Document & PPT Generation

An enterprise-grade multi-agent AI chatbot POC that understands user requests, analyzes uploaded documents and PPT templates, performs real-time web research, retrieves information from enterprise knowledge sources, and generates professional, editable documents and presentations.


---

## Architecture

```
┌─────────────────────────────────────────────────┐
│              React Frontend (Vite)               │
│   Chat · File Upload · Agent Trace · Versions    │
└─────────────────────┬───────────────────────────┘
                      │ REST API
┌─────────────────────▼───────────────────────────┐
│              FastAPI Backend                    │
│              (main.py)                          │
└─────────────────────┬───────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────-┐
│       Supervisor / Orchestrator (LangGraph)      │
│                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │  Doc     │ │  PPT     │ │  Web Research    │  │
│  │  Analyzer│ │  Analyzer│ │  (Tavily)        │  │
│  └──────────┘ └──────────┘ └──────────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │  RAG     │ │  Doc     │ │  PPT Generator   │  │
│  │  Agent   │ │ Generator│ │  (python-pptx)   │  │
│  └──────────┘ └──────────┘ └──────────────────┘  │
│  ┌──────────┐ ┌──────────────────────────────┐   │
│  │ Validator│ │  Conversational Editor       │   │
│  └──────────┘ └──────────────────────────────┘   │
└──────────────────────────────────────────────────┘
        │              │                │
  ┌─────▼─────┐ ┌──────▼──────┐ ┌──────▼──────┐
  │ ChromaDB  │ │ Groq LLM    │ │ Tavily API  │
  │ (local)   │ │ (free tier) │ │ (free tier) │
  └───────────┘ └─────────────┘ └─────────────┘
```

## Features

### Multi-Agent System (9 Specialized Agents)
| Agent | Role |
|---|---|
| **Supervisor/Orchestrator** | Plans workflow, routes to agents, aggregates results |
| **Document Analyzer** | Parses DOCX, PDF, images; extracts structure/style |
| **PPT Analyzer** | Parses PPTX; extracts layouts, themes, fonts |
| **Web Researcher** | Real-time web search via Tavily API |
| **RAG Agent** | Retrieves enterprise knowledge from ChromaDB |
| **Document Generator** | Creates editable DOCX with style transfer |
| **PPT Generator** | Creates editable PPTX with theme transfer |
| **Validator** | Quality checks generated artifacts |
| **Conversational Editor** | Modifies existing documents via natural language |

### Supported Capabilities
- ✅ Upload & analyze DOCX, PDF, PPTX, and images (with OCR)
- ✅ Extract tone, style, formatting, and structure from templates
- ✅ Real-time web research with Tavily Search API
- ✅ Enterprise RAG with ChromaDB vector database
- ✅ Generate editable DOCX documents with style transfer
- ✅ Generate editable PPTX presentations with theme transfer
- ✅ Conversational editing preserving formatting
- ✅ Full version history for all generated artifacts
- ✅ Source citations and traceability
- ✅ Agent execution trace for full transparency
- ✅ Modular FastAPI backend with REST endpoints

---

## Tech Stack

| Layer | Technology | Cost |
|---|---|---|
| LLM | Groq API (Llama 3.1 70B) | **Free** (14,400 tokens/min) |
| Orchestration | LangGraph | Open-source |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | **Free** (local) |
| Vector DB | ChromaDB | **Free** (local) |
| Web Search | Tavily API | **Free** (1,000 searches/mo) |
| OCR | Tesseract (pytesseract) | **Free** (local) |
| DOCX | python-docx | Open-source |
| PPTX | python-pptx | Open-source |
| PDF | PyMuPDF (fitz) | Open-source |
| Backend | FastAPI + Uvicorn | Open-source |
| Frontend | React 18 + Vite | Open-source |

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
cd "d:\PROJECTS\End To End PROJECTS\6.-"

# Create Python virtual environment
python -m venv venv
venv\Scripts\activate   # Windows


# Install Python dependencies
pip install -r requirements.txt


#  To run backend 
.\start_backend.bat


# Open a new terminal in the root of your project: 
# 1. Navigate to the frontend folder
cd frontend

# 2. Install Node.js dependencies
npm install

# 3. Go back to the root and start the frontend
cd ..

.\start_frontend.bat

```

### Step 2: Get API Keys (Free)

1. **Groq API Key** (free, instant):
   - Go to [console.groq.com](https://console.groq.com)
   - Sign up / log in → API Keys → Create new key

2. **Tavily API Key** (free, 1000 searches/mo):
   - Go to [app.tavily.com](https://app.tavily.com)
   - Sign up → Dashboard → Copy API key

### Step 3: Configure Environment

```bash
# Copy the example env file
copy .env.example .env    # Windows
# cp .env.example .env    # macOS/Linux

# Edit .env and paste your API keys:
# GROQ_API_KEY=gsk_xxxxxxxxxxxxx
# TAVILY_API_KEY=tvly-xxxxxxxxxxxxx
```

### Step 4: Generate Sample Templates

```bash
python scripts/generate_samples.py
```

This creates `sample_templates/Company_Proposal.docx` and `sample_templates/Company_Template.pptx` for testing.

### Step 5: Start the Backend

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at: `http://localhost:8000`
- Swagger docs: `http://localhost:8000/api/docs`

### Step 6: Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

The UI will be available at: `http://localhost:5173`

---

## Usage Guidelines

### Basic Workflow

1. **Upload Templates**: Drag & drop your DOCX/PPTX templates into the left panel
2. **Give Instructions**: Type your request in the chat panel, e.g.:
   - _"Research the latest Generative AI trends and create a proposal and 12-slide presentation using the same tone and style as the uploaded files."_
3. **Wait for Agents**: Watch the Agent Trace panel on the right to see each agent executing
4. **Download Files**: Generated DOCX/PPTX files appear in the right panel — click to download
5. **Edit Conversationally**: Follow up with edits like:
   - _"Add an executive summary"_
   - _"Make the presentation more concise"_
   - _"Add a competitive analysis section"_
   - _"Update the report using the latest web information"_

### Example Prompts

| Prompt | What Happens |
|---|---|
| "Research AI trends and write a professional proposal" | Web search → LLM generates styled DOCX |
| "Create a 12-slide presentation on cloud computing" | LLM generates themed PPTX with speaker notes |
| "Add an executive summary to the document" | Editor agent modifies existing DOCX |
| "Make the presentation more concise" | Editor agent trims slide content |
| "Research cybersecurity and update the proposal" | Fresh web search → edits existing DOCX |

### API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/chat` | POST | Send message to multi-agent orchestrator |
| `/api/upload` | POST | Upload template files |
| `/api/download/{filename}` | GET | Download generated file |
| `/api/versions/{artifact_id}` | GET | Get version history |
| `/api/artifacts` | GET | List all artifacts |
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
│   │   │   ├── DocumentViewer.jsx # Artifact downloads
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
├── .env                           # Environment variables (user created)
├── .env.example                   # Example environment variables
└── README.md
```

---

## License

This is a POC (Proof of Concept) project for educational and demonstration purposes.
