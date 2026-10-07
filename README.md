# Interview RAG

A small local RAG app for storing interview-preparation notes and asking grounded questions about them.

## Stack

- Python 3.12
- PostgreSQL + pgvector
- Ollama
  - `nomic-embed-text` for embeddings
  - `qwen2.5:7b` for answers
- Streamlit UI

## How it works

1. Add a structured Markdown note to `data/`.
2. Run the ingestion script.
3. The app embeds the note and stores it in PostgreSQL.
4. A user question is embedded with the same model.
5. pgvector finds related notes using cosine similarity.
6. If a match passes the similarity threshold, Qwen answers using only the retrieved context.
7. The UI shows the answer and its source note.

```text
data/*.md
  -> src/ingest_markdown.py
  -> Ollama embeddings
  -> PostgreSQL + pgvector
  -> Streamlit app
  -> retrieved context
  -> Qwen answer + sources
```

## Prerequisites

- Python 3.12+
- Docker
- Ollama running locally
- Models installed:

```bash
ollama pull nomic-embed-text
ollama pull qwen2.5:7b
```

## Setup

```bash
pyenv local 3.12.7

python -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install ollama "psycopg[binary]" python-dotenv streamlit
```

Create `.env`:

```env
DATABASE_URL=postgresql://rag:rag@localhost:5432/rag
```

Start PostgreSQL:

```bash
docker start rag-postgres
```

## Add notes

Create a Markdown file in `data/`:

```md
# Topic title

## Question
The interview scenario or question.

## My answer
Your prepared answer.

## Topics
api design, pagination, postgresql

## Source
Optional original source reference.
```

Ingest all Markdown notes:

```bash
python src/ingest_markdown.py
```

The importer updates an existing note when its `source_file` and `question` match.

## Run

Start the web UI:

```bash
streamlit run app.py
```

Open the local URL shown by Streamlit, usually:

```text
http://localhost:8501
```

Ask a question such as:

```text
When should I use cursor pagination?
```

## Retrieval behavior

- The app uses `nomic-embed-text` for both stored notes and user questions.
- pgvector calculates cosine similarity.
- Notes below the configured similarity threshold are rejected.
- If no note qualifies, the app returns:

```text
My interview notes do not cover that.
```

## Project structure

```text
.
├── app.py
├── data/
│   └── support-ticket-dashboard.md
├── src/
│   ├── ask_rag.py
│   └── ingest_markdown.py
├── .env
└── README.md
```

## Current limitations

- Small local corpus.
- One embedding per Markdown note.
- No chat history or metadata filtering yet.
- No reranking or hybrid keyword search yet.