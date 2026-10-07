import os

import ollama
import psycopg
import argparse
from dotenv import load_dotenv

load_dotenv()

parser = argparse.ArgumentParser(
    description="Ask questions about your interview-preparation notes."
)

parser.add_argument(
    "question",
    help="The interview question or topic to search for.",
)

args = parser.parse_args()

user_question = args.question

embedding_response = ollama.embed(
    model="nomic-embed-text",
    input=user_question,
)

query_embedding = embedding_response["embeddings"][0]

MIN_SIMILARITY = 0.60

with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                id,
                source_file,
                question,
                answer,
                1 - (embedding <=> %s::vector) AS similarity
            FROM interview_questions
            WHERE 1 - (embedding <=> %s::vector) >= %s
            ORDER BY embedding <=> %s::vector
            LIMIT 3;
            """,
        (   str(query_embedding),
            str(query_embedding),
            MIN_SIMILARITY,
            str(query_embedding),
        ),
    )
        rows = cursor.fetchall()

if not rows:
    print("My interview notes do not cover that.")
    raise SystemExit(0)

context = "\n\n".join(
    f"[Source ID: {question_id} | Similarity: {similarity:.3f} | File: {source_file}]\n"
    f"Interview question: {question}\n"
    f"Prepared answer: {answer}"
    for question_id, source_file, question, answer, similarity in rows
)

response = ollama.chat(
    model="qwen2.5:7b",
    messages=[
        {
            "role": "system",
            "content": (
                "You are an interview-preparation assistant. "
                "Answer only using the supplied prepared-answer context. "
                "Do not add facts that are absent from it. "
                "If context is insufficient, say: "
                "'My interview notes do not cover that.'"
            ),
        },
        {
            "role": "user",
            "content": (
                f"Prepared-answer context:\n{context}\n\n"
                f"Question: {user_question}"
            ),
        },
    ],
)

print("\nRetrieved context:\n")
print(context)
print("\nRAG answer:\n")
print(response.message.content)
print("\nSources:")
for question_id, source_file, question, _ in rows:
    print(f"- [{question_id}] {question} ({source_file})")