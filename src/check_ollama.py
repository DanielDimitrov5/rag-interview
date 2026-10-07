from ollama import chat

response = chat(
    model="qwen2.5:7b",
    messages=[
        {
            "role": "user",
            "content": "How to say Hello in Ukrainian?",
        }
    ],
)

print(response.message.content)