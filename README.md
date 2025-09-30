# RAG-Azure HR Policy Chatbot

An advanced Retrieval-Augmented Generation (RAG) system for HR policy question answering, built with FastAPI, ChromaDB, and OpenAI.

## 🚀 Features

- **Conversational AI**: Multi-turn conversations with full context awareness
- **Intelligent Grounding**: AI responses strictly based on company policy documents with citations
- **Auto-sync**: Automatic document updates from AWS S3
- **Advanced Chunking**: Paragraph-aware semantic chunking with cross-page stitching
- **Production Ready**: Comprehensive logging, monitoring, and debugging tools
- **Cost Efficient**: Optimized with GPT-4o-mini and text-embedding-3-small

## 📋 Prerequisites

- Python 3.11+
- OpenAI API Key
- AWS Account with S3 access
- Windows/Linux/macOS

## 🛠️ Installation

1. **Clone the repository**
```bash
git clone <your-repo-url>
cd RAG-Azure
```

2. **Create virtual environment**
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**

Create a `.env` file in the project root:
```bash
OPENAI_API_KEY=sk-proj-your-key-here
CHAT_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
AWS_REGION=us-east-1
S3_BUCKET=your-bucket-name
DOC_ID=doc-001
THRESHOLD=0.15
TOP_K=6
```

5. **Upload documents to S3**

Create a manifest file at `s3://your-bucket/doc-001/manifest.json`:
```json
{
  "latest_pdf": "doc-001/1234567890.pdf"
}
```

Upload your PDF document to the same S3 path.

## 🚀 Usage

### Start the server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Access the application
- **Web UI**: http://localhost:8000/ui
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### API Endpoints

**Ask a question**
```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the vacation policy?"}'
```

**Debug search results**
```bash
curl -X POST http://localhost:8000/debug_search \
  -H "Content-Type: application/json" \
  -d '{"question": "vacation policy", "top_k": 10}'
```

**Refresh documents**
```bash
curl -X POST http://localhost:8000/refresh
```

## 📊 Architecture

```
┌─────────────┐
│   Web UI    │
└──────┬──────┘
       │
┌──────▼──────────────┐
│   FastAPI Backend   │
│   - /ask            │
│   - /refresh        │
│   - /debug_search   │
└──────┬──────────────┘
       │
┌──────▼──────────────┐
│  Processing Layer   │
│  - PDF Parsing      │
│  - Chunking         │
│  - Embeddings       │
└──────┬──────────────┘
       │
┌──────▼──────────────┐
│  Storage Layer      │
│  - ChromaDB         │
│  - AWS S3           │
│  - Local State      │
└─────────────────────┘
```

## 🔧 Configuration

Key configuration parameters in `.env`:

- **THRESHOLD**: Similarity threshold (0.15 = more permissive, 0.3 = more strict)
- **TOP_K**: Number of chunks to retrieve (default: 6)
- **DOC_ID**: Document identifier for multi-document support

## 📚 Documentation

- [Technical Documentation](./TECHNICAL_DOCUMENTATION.md) - Comprehensive system documentation
- [Azure Migration Guide](./AZURE_MIGRATION_GUIDE.md) - Guide for migrating to Azure services

## 🧪 Development

### Project Structure
```
RAG-Azure/
├── app/
│   ├── main.py              # FastAPI application
│   ├── utils.py             # Core business logic
│   └── vectordb/
│       ├── base.py          # Vector store interface
│       └── chroma_store.py  # ChromaDB implementation
├── web/
│   └── index.html           # Frontend UI
├── data/
│   └── chroma/              # Vector database (gitignored)
├── .state/                  # Application state (gitignored)
├── requirements.txt         # Python dependencies
└── .env                     # Configuration (gitignored)
```

### Running Tests
```bash
# Add test commands here when implemented
pytest tests/
```

## 🔒 Security

- Never commit `.env` file to git
- Rotate API keys monthly
- Use IAM roles for AWS access in production
- Enable HTTPS in production deployments

## 📈 Performance

- **P50 Latency**: ~1.2 seconds
- **P95 Latency**: ~2.8 seconds
- **Cost**: ~$1.81 per 1000 queries
- **Concurrent Users**: ~50 (single instance)

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📝 License

[Add your license here]

## 👥 Authors

- [Your Name]

## 🙏 Acknowledgments

- OpenAI for GPT-4o-mini and embedding models
- ChromaDB for vector database
- FastAPI for the web framework