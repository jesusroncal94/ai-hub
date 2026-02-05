"""Main application - Gradio multimodal chat interface."""

import gradio as gr

from ai_hub.config import settings
from ai_hub.processors import save_upload, transcribe_audio
from ai_hub.providers import ClaudeCodeProvider

provider = ClaudeCodeProvider(allowed_tools=settings.allowed_tools)


def handle_chat(
    message: dict,
    history: list[dict],
) -> tuple[list[dict], dict]:
    """Process a multimodal chat message (text and/or files)."""
    text = message.get("text", "").strip()
    files: list[str] = message.get("files", [])

    if not text and not files:
        return history, {"text": "", "files": []}

    saved = [save_upload(f, settings.upload_dir) for f in files]

    # Build display message for the user side
    user_display = text or "Please analyze the attached files."
    if saved:
        names = ", ".join(f.name for f in saved)
        user_display += f"\n\n[Attached: {names}]"

    history = history + [{"role": "user", "content": user_display}]

    # Reset session if this is the first message (user cleared chat)
    if len(history) == 1:
        provider.reset()

    prompt = text or "Analyze the attached files."
    response = provider.send(prompt, saved or None)

    history = history + [{"role": "assistant", "content": response}]
    return history, {"text": "", "files": []}


def handle_voice(
    audio_path: str | None,
    history: list[dict],
) -> tuple[list[dict], None]:
    """Process voice input: transcribe and send to the provider."""
    if audio_path is None:
        return history, None

    try:
        text = transcribe_audio(audio_path, settings.whisper_model)
    except ImportError as exc:
        history = history + [
            {"role": "assistant", "content": str(exc)},
        ]
        return history, None

    history = history + [{"role": "user", "content": f"[Voice] {text}"}]

    response = provider.send(text)
    history = history + [{"role": "assistant", "content": response}]

    return history, None


def handle_new_chat() -> list:
    """Clear chat history and reset the provider session."""
    provider.reset()
    return []


def build_app() -> gr.Blocks:
    """Build and return the Gradio application."""
    with gr.Blocks() as app:
        gr.Markdown(
            "# AI Hub\n"
            "Multimodal AI chat powered by Claude Code. "
            "Send text, images, PDFs, or voice."
        )

        chatbot = gr.Chatbot(height=500, label="Conversation")

        with gr.Tabs():
            with gr.TabItem("Text & Files"):
                text_input = gr.MultimodalTextbox(
                    placeholder="Type a message or attach files...",
                    file_types=[
                        "image",
                        ".pdf",
                        ".docx",
                        ".xlsx",
                        ".csv",
                        ".txt",
                        ".md",
                        ".json",
                        ".py",
                        ".js",
                        ".ts",
                    ],
                    sources=["upload"],
                    submit_btn="Send",
                )

            with gr.TabItem("Voice"):
                audio_input = gr.Audio(
                    sources=["microphone"],
                    type="filepath",
                    label="Record your message",
                )
                send_voice_btn = gr.Button("Send Voice", variant="primary")

        new_chat_btn = gr.Button("New Chat", variant="secondary")

        # Event handlers
        text_input.submit(
            fn=handle_chat,
            inputs=[text_input, chatbot],
            outputs=[chatbot, text_input],
        )
        send_voice_btn.click(
            fn=handle_voice,
            inputs=[audio_input, chatbot],
            outputs=[chatbot, audio_input],
        )
        new_chat_btn.click(
            fn=handle_new_chat,
            outputs=[chatbot],
        )

    return app


def main() -> None:
    """Launch the application."""
    settings.ensure_dirs()
    app = build_app()
    app.launch(
        server_name=settings.server_host,
        server_port=settings.server_port,
        theme=gr.themes.Soft(),
    )


if __name__ == "__main__":
    main()
