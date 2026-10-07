import os

import ollama
import psycopg
from dotenv import load_dotenv

load_dotenv()

question = "When would you use cursor-based pagination instead of offset pagination?"

answer = """
Use cursor pagination for large or frequently changing datasets.
It avoids expensive high offsets and reduces duplicate or missing records when
new rows are inserted during paging. Use a stable indexed ordering such as
created_at plus id.
""".strip()

topics = ["PostgreSQL", "REST", "scalability"]
source_file = "data/interview-questions.md"

text_to_embed = f"Question: {question}\n\nAnswer: {answer}"

embedding_response = ollama.embed(
    model="nomic-embed-text",
    input=text_to_embed,
)

embedding = embedding_response["embeddings"][0]

with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO interview_questions
                (question, answer, topics, source_file, embedding)
            VALUES
                (%s, %s, %s, %s, %s::vector)
            RETURNING id;
            """,
            (
                question,
                answer,
                topics,
                source_file,
                str(embedding),
            ),
        )

        question_id = cursor.fetchone()[0]
        connection.commit()

print(f"Inserted interview question with id: {question_id}")
print(f"Embedding dimensions: {len(embedding)}")