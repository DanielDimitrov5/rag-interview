import os

import ollama
import psycopg
import streamlit as st
from dotenv import load_dotenv
from psycopg.types.json import Jsonb

load_dotenv()

EMBEDDING_MODEL = "nomic-embed-text"
CHAT_MODEL = "qwen2.5:7b"
MIN_SIMILARITY = 0.60
MAX_HISTORY_MESSAGES = 12


def get_connection():
    return psycopg.connect(os.environ["DATABASE_URL"])


def ensure_chat_tables():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id BIGSERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id BIGSERIAL PRIMARY KEY,
                    session_id BIGINT NOT NULL
                        REFERENCES chat_sessions(id)
                        ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    sources JSONB,
                    used_notes BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )

            cursor.execute(
                """
                ALTER TABLE chat_messages
                ADD COLUMN IF NOT EXISTS sources JSONB;
                """
            )

            cursor.execute(
                """
                ALTER TABLE chat_messages
                ADD COLUMN IF NOT EXISTS used_notes BOOLEAN NOT NULL DEFAULT TRUE;
                """
            )

            cursor.execute(
                """
                DELETE FROM chat_sessions
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM chat_messages
                    WHERE chat_messages.session_id = chat_sessions.id
                );
                """
            )

        connection.commit()


def create_session(title: str) -> int:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO chat_sessions (title)
                VALUES (%s)
                RETURNING id;
                """,
                (title,),
            )

            session_id = cursor.fetchone()[0]

        connection.commit()

    return session_id


def list_sessions():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, title, created_at
                FROM chat_sessions
                ORDER BY created_at DESC;
                """
            )

            return cursor.fetchall()


def load_messages(session_id: int):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT role, content, sources, used_notes
                FROM chat_messages
                WHERE session_id = %s
                ORDER BY id ASC;
                """,
                (session_id,),
            )

            return [
                {
                    "role": role,
                    "content": content,
                    "sources": sources or [],
                    "used_notes": used_notes,
                }
                for role, content, sources, used_notes in cursor.fetchall()
            ]


def save_message(
    session_id: int,
    role: str,
    content: str,
    sources: list | None = None,
    used_notes: bool = True,
):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO chat_messages (
                    session_id,
                    role,
                    content,
                    sources,
                    used_notes
                )
                VALUES (%s, %s, %s, %s, %s);
                """,
                (
                    session_id,
                    role,
                    content,
                    Jsonb(sources) if sources else None,
                    used_notes,
                ),
            )

        connection.commit()


def retrieve_notes(question: str):
    embedding = ollama.embed(
        model=EMBEDDING_MODEL,
        input=question,
    )["embeddings"][0]

    with get_connection() as connection:
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

            return cursor.fetchall()


def serialize_sources(rows):
    return [
        {
            "id": item_id,
            "source_file": source_file,
            "question": saved_question,
            "similarity": float(similarity),
        }
        for item_id, source_file, saved_question, _, similarity in rows
    ]


def get_conversation_history(messages: list[dict]):
    recent_messages = messages[-MAX_HISTORY_MESSAGES:]

    return [
        {
            "role": message["role"],
            "content": message["content"],
        }
        for message in recent_messages
    ]


def answer_question(
    question: str,
    use_notes: bool,
    conversation_history: list[dict],
):
    history = get_conversation_history(conversation_history)

    if not use_notes:
        response = ollama.chat(
            model=CHAT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful interview-preparation assistant. "
                        "Give clear, practical answers in at most 2 short paragraphs. "
                        "Use the conversation history to understand follow-up questions."
                    ),
                },
                *history,
                {
                    "role": "user",
                    "content": question,
                },
            ],
            options={
                "temperature": 0.3,
                "num_predict": 200,
            },
        )

        return response.message.content, []

    rows = retrieve_notes(question)

    if not rows:
        return "My interview notes do not cover that.", []

    context = "\n\n".join(
        f"[Source ID: {item_id} | File: {source_file}]\n"
        f"Interview question: {saved_question}\n"
        f"Prepared answer: {answer}"
        for item_id, source_file, saved_question, answer, _ in rows
    )

    response = ollama.chat(
        model=CHAT_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an interview-preparation assistant. "
                    "Answer in at most 2 short paragraphs. "
                    "Use the conversation history to understand follow-up questions. "
                    "Answer only using the supplied prepared-answer context. "
                    "Do not add facts not present in it. "
                    "If the context is insufficient, say exactly: "
                    "'My interview notes do not cover that.'"
                ),
            },
            *history,
            {
                "role": "user",
                "content": (
                    f"Prepared-answer context:\n{context}\n\n"
                    f"Current question: {question}"
                ),
            },
        ],
        options={
            "temperature": 0,
            "num_predict": 120,
        },
    )

    return response.message.content, rows


def render_sources(sources):
    if not sources:
        return

    with st.expander("Retrieved sources"):
        for source in sources:
            st.write(
                f"**{source['similarity']:.3f}** — "
                f"`{source['source_file']}` — "
                f"{source['question']}"
            )


st.set_page_config(
    page_title="Interview RAG",
    page_icon="📚",
)

st.title("Interview RAG")
st.caption("Ask questions about your saved interview-preparation notes.")

ensure_chat_tables()

if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "use_notes" not in st.session_state:
    st.session_state.use_notes = True

sessions = list_sessions()

with st.sidebar:
    st.header("Conversations")

    st.session_state.use_notes = st.toggle(
        "Use interview notes",
        value=st.session_state.use_notes,
        help=(
            "When enabled, answers use your saved interview notes. "
            "When disabled, Ollama answers directly without note retrieval."
        ),
    )

    if st.session_state.use_notes:
        st.caption("Mode: RAG answers from your saved notes.")
    else:
        st.caption("Mode: Direct model answers with conversation context.")

    st.divider()

    if st.button("New conversation", use_container_width=True):
        st.session_state.current_session_id = None
        st.session_state.messages = []

        st.rerun()

    if sessions:
        st.divider()

    for session_id, title, created_at in sessions:
        created_label = created_at.strftime("%Y-%m-%d %H:%M")
        label = f"{title} — {created_label}"

        if st.button(
            label,
            key=f"session-{session_id}",
            use_container_width=True,
        ):
            st.session_state.current_session_id = session_id
            st.session_state.messages = load_messages(session_id)

            st.rerun()

if st.session_state.current_session_id is None:
    st.info("Start a new conversation by asking a question.")
else:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

            if message["role"] == "assistant":
                render_sources(message.get("sources", []))

prompt = st.chat_input("Ask an interview-preparation question")

if prompt:
    if st.session_state.current_session_id is None:
        new_title = prompt.strip().replace("\n", " ")[:50]

        st.session_state.current_session_id = create_session(
            new_title if new_title else "New conversation"
        )

    current_session_id = st.session_state.current_session_id
    history_before_current_question = st.session_state.messages.copy()

    user_message = {
        "role": "user",
        "content": prompt,
        "sources": [],
        "used_notes": st.session_state.use_notes,
    }

    st.session_state.messages.append(user_message)

    save_message(
        session_id=current_session_id,
        role="user",
        content=prompt,
        used_notes=st.session_state.use_notes,
    )

    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        spinner_text = (
            "Searching your notes..."
            if st.session_state.use_notes
            else "Thinking..."
        )

        with st.spinner(spinner_text):
            answer, retrieved_rows = answer_question(
                question=prompt,
                use_notes=st.session_state.use_notes,
                conversation_history=history_before_current_question,
            )

        saved_sources = serialize_sources(retrieved_rows)

        st.write(answer)
        render_sources(saved_sources)

    assistant_message = {
        "role": "assistant",
        "content": answer,
        "sources": saved_sources,
        "used_notes": st.session_state.use_notes,
    }

    st.session_state.messages.append(assistant_message)

    save_message(
        session_id=current_session_id,
        role="assistant",
        content=answer,
        sources=saved_sources,
        used_notes=st.session_state.use_notes,
    )