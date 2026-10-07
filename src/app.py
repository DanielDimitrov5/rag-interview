import os

import ollama
import psycopg
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

EMBEDDING_MODEL = "nomic-embed-text"
CHAT_MODEL = "qwen2.5:7b"
MIN_SIMILARITY = 0.30

st.set_page_config(page_title="Interview RAG", page_icon="📚")
st.title("Interview RAG")
st.caption("Ask questions about your saved interview-preparation notes.")

question = st.chat_input("Ask an interview-preparation question")

if question:
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Searching your notes..."):
            embedding = ollama.embed(
                model=EMBEDDING_MODEL,
                input=question,
            )["embeddings"][0]

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
                        (
                            str(embedding),
                            str(embedding),
                            MIN_SIMILARITY,
                            str(embedding),
                        ),
                    )
                    rows = cursor.fetchall()

        if not rows:
            st.write("My interview notes do not cover that.")
        else:
            context = "\n\n".join(
                f"[Source ID: {item_id} | File: {source_file}]\n"
                f"Interview question: {saved_question}\n"
                f"Prepared answer: {answer}"
                for item_id, source_file, saved_question, answer, _ in rows
            )

            answer = ollama.chat(
                model=CHAT_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an interview-preparation assistant. "
                            "Answer only using the supplied prepared-answer context. "
                            "Do not add facts not present in it. "
                            "If the context is insufficient, say: "
                            "'My interview notes do not cover that.'"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Prepared-answer context:\n{context}\n\n"
                            f"Question: {question}"
                        ),
                    },
                ],
            ).message.content

            st.write(answer)

            with st.expander("Retrieved sources"):
                for item_id, source_file, saved_question, _, similarity in rows:
                    st.write(
                        f"**{similarity:.3f}** — "
                        f"`{source_file}` — {saved_question}"
                    )