import os
import re
from pathlib import Path

import ollama
import psycopg
from dotenv import load_dotenv

load_dotenv()

DATA_DIRECTORY = Path("data")
EMBEDDING_MODEL = "nomic-embed-text"


def extract_section(content: str, heading: str) -> str:
    pattern = rf"^## {re.escape(heading)}\s*$([\s\S]*?)(?=^## |\Z)"
    match = re.search(pattern, content, flags=re.MULTILINE)

    if not match:
        raise ValueError(f"Missing section: ## {heading}")

    return match.group(1).strip()


def parse_markdown(file_path: Path) -> dict:
    content = file_path.read_text(encoding="utf-8")

    return {
        "question": extract_section(content, "Question"),
        "answer": extract_section(content, "My answer"),
        "topics": [
            topic.strip()
            for topic in extract_section(content, "Topics").split(",")
            if topic.strip()
        ],
        "source_file": str(file_path),
    }


def create_embedding(question: str, answer: str) -> list[float]:
    text = f"Question: {question}\n\nPrepared answer: {answer}"

    response = ollama.embed(
        model=EMBEDDING_MODEL,
        input=text,
    )

    return response["embeddings"][0]


def ingest_file(connection, file_path: Path) -> None:
    item = parse_markdown(file_path)
    embedding = create_embedding(item["question"], item["answer"])

    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO interview_questions
                (question, answer, topics, source_file, embedding)
            VALUES
                (%s, %s, %s, %s, %s::vector)
            ON CONFLICT (source_file, question)
            DO UPDATE SET
                answer = EXCLUDED.answer,
                topics = EXCLUDED.topics,
                embedding = EXCLUDED.embedding;
            """,
            (
                item["question"],
                item["answer"],
                item["topics"],
                item["source_file"],
                str(embedding),
            ),
        )

    print(f"Ingested: {file_path}")


def main() -> None:
    files = sorted(DATA_DIRECTORY.glob("*.md"))

    if not files:
        raise RuntimeError("No Markdown files found in data/")

    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        for file_path in files:
            ingest_file(connection, file_path)

        connection.commit()

    print(f"\nDone. Processed {len(files)} file(s).")


if __name__ == "__main__":
    main()