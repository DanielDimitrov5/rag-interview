import os

import ollama
import psycopg
from dotenv import load_dotenv

load_dotenv()

query = "How can I paginate a large list when records change frequently?"

response = ollama.embed(
    model="nomic-embed-text",
    input=query,
)

query_embedding = response["embeddings"][0]

with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                id,
                question,
                answer,
                1 - (embedding <=> %s::vector) AS similarity
            FROM interview_questions
            ORDER BY embedding <=> %s::vector
            LIMIT 3;
            """,
            (str(query_embedding), str(query_embedding)),
        )

        results = cursor.fetchall()

for question_id, question, answer, similarity in results:
    print(f"\nID: {question_id}")
    print(f"Similarity: {similarity:.3f}")
    print(f"Question: {question}")
    print(f"Answer: {answer}")