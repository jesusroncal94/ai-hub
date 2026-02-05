"""Main application - Gradio multimodal chat interface with session management."""

from pathlib import Path

import gradio as gr

from ai_hub.auth import authenticate, hash_password, seed_admin
from ai_hub.config import ALL_TOOLS, AVAILABLE_MODELS, PERMISSION_MODES, settings
from ai_hub.database import Database
from ai_hub.processors import extract_text, save_upload, transcribe_audio
from ai_hub.providers import ClaudeCodeProvider, ProviderResponse

provider = ClaudeCodeProvider(default_tools=settings.default_tools)
db = Database(settings.db_path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_user_id(request: gr.Request) -> int:
    user = db.get_user_by_username(request.username)
    return user.id  # type: ignore[union-attr]


def _is_admin(request: gr.Request) -> bool:
    user = db.get_user_by_username(request.username)
    return user is not None and user.is_admin


def _conversation_choices(user_id: int) -> list[tuple[str, str]]:
    convos = db.get_conversations(user_id)
    return [(c.title, str(c.id)) for c in convos]


def _load_history(conversation_id: int) -> list[dict]:
    msgs = db.get_messages(conversation_id)
    return [{"role": m.role, "content": m.content} for m in msgs]


def _auto_title(conversation_id: int, text: str) -> None:
    convo = db.get_conversation(conversation_id)
    if convo and convo.title == "New conversation" and text.strip():
        title = text.strip()[:50]
        db.update_conversation(conversation_id, title=title)


def _users_dataframe() -> list[list]:
    users = db.get_all_users()
    return [
        [
            u.username,
            "Yes" if u.is_admin else "No",
            "Yes" if db.is_whitelisted(u.username) else "No",
            u.created_at,
        ]
        for u in users
    ]


def _whitelist_dataframe() -> list[list]:
    entries = db.get_whitelist()
    return [[e.username, e.created_at] for e in entries]


def _format_usage(resp: ProviderResponse) -> str:
    parts = []
    if resp.model:
        parts.append(resp.model)
    if resp.cost_usd is not None:
        parts.append(f"${resp.cost_usd:.4f}")
    if resp.input_tokens or resp.output_tokens:
        parts.append(f"{resp.input_tokens} in → {resp.output_tokens} out")
    return " | ".join(parts) if parts else ""


# ---------------------------------------------------------------------------
# Chat event handlers
# ---------------------------------------------------------------------------


def on_load(request: gr.Request) -> tuple:
    user_id = _get_user_id(request)
    convos = db.get_conversations(user_id)

    if not convos:
        convo = db.create_conversation(user_id)
    else:
        convo = convos[0]

    choices = _conversation_choices(user_id)
    state = {
        "conversation_id": convo.id,
        "claude_session_id": convo.claude_session_id,
    }
    history = _load_history(convo.id)
    show_admin = _is_admin(request)
    return (
        gr.update(choices=choices, value=str(convo.id)),
        history,
        state,
        gr.update(visible=show_admin),
    )


def on_new_conversation(state: dict, request: gr.Request) -> tuple:
    user_id = _get_user_id(request)
    convo = db.create_conversation(user_id)
    choices = _conversation_choices(user_id)
    state = {
        "conversation_id": convo.id,
        "claude_session_id": convo.claude_session_id,
    }
    return (
        gr.update(choices=choices, value=str(convo.id)),
        [],
        state,
    )


def on_switch_conversation(
    conv_id_str: str, state: dict, request: gr.Request
) -> tuple:
    if not conv_id_str:
        return [], state

    conv_id = int(conv_id_str)
    convo = db.get_conversation(conv_id)
    if convo is None:
        return [], state

    state = {
        "conversation_id": convo.id,
        "claude_session_id": convo.claude_session_id,
    }
    history = _load_history(convo.id)
    return history, state


def _parse_dirs(raw: str | None) -> list[str] | None:
    """Parse newline-separated directory paths, ignoring blanks."""
    if not raw:
        return None
    dirs = [d.strip() for d in raw.splitlines() if d.strip()]
    return dirs or None


def handle_chat(
    message: dict,
    history: list[dict],
    state: dict,
    model: str,
    tools: list[str],
    system_prompt: str,
    add_dirs_raw: str,
    permission_mode: str,
    request: gr.Request,
) -> tuple[list[dict], dict, dict, str]:
    text = message.get("text", "").strip()
    files: list[str] = message.get("files", [])

    if not text and not files:
        return history, {"text": "", "files": []}, state, ""

    saved = [save_upload(f, settings.upload_dir) for f in files]

    image_files: list[Path] = []
    extracted_parts: list[str] = []
    for f in saved:
        content = extract_text(f)
        if content is not None:
            extracted_parts.append(f"--- Content of {f.name} ---\n{content}")
        else:
            image_files.append(f)

    user_display = text or "Please analyze the attached files."
    if saved:
        names = ", ".join(f.name for f in saved)
        user_display += f"\n\n[Attached: {names}]"

    history = history + [{"role": "user", "content": user_display}]

    conv_id = state["conversation_id"]
    db.add_message(conv_id, "user", user_display)
    _auto_title(conv_id, text or (saved[0].name if saved else ""))

    prompt_parts = [text] if text else ["Analyze the following content."]
    prompt_parts.extend(extracted_parts)
    prompt = "\n\n".join(prompt_parts)

    sp = system_prompt.strip() if system_prompt else None
    pm = permission_mode if permission_mode else None
    resp = provider.send(
        prompt,
        image_files or None,
        state.get("claude_session_id"),
        model=model or None,
        system_prompt=sp,
        allowed_tools=tuple(tools) if tools else None,
        add_dirs=_parse_dirs(add_dirs_raw),
        permission_mode=pm,
    )

    if resp.session_id and resp.session_id != state.get("claude_session_id"):
        state = {**state, "claude_session_id": resp.session_id}
        db.update_conversation(conv_id, claude_session_id=resp.session_id)

    history = history + [{"role": "assistant", "content": resp.text}]
    db.add_message(conv_id, "assistant", resp.text)

    return history, {"text": "", "files": []}, state, _format_usage(resp)


def handle_voice(
    audio_path: str | None,
    history: list[dict],
    state: dict,
    model: str,
    tools: list[str],
    system_prompt: str,
    add_dirs_raw: str,
    permission_mode: str,
    request: gr.Request,
) -> tuple[list[dict], None, dict, str]:
    if audio_path is None:
        return history, None, state, ""

    try:
        text = transcribe_audio(audio_path, settings.whisper_model)
    except ImportError as exc:
        history = history + [
            {"role": "assistant", "content": str(exc)},
        ]
        return history, None, state, ""

    user_display = f"[Voice] {text}"
    history = history + [{"role": "user", "content": user_display}]

    conv_id = state["conversation_id"]
    db.add_message(conv_id, "user", user_display)
    _auto_title(conv_id, text)

    sp = system_prompt.strip() if system_prompt else None
    pm = permission_mode if permission_mode else None
    resp = provider.send(
        text,
        session_id=state.get("claude_session_id"),
        model=model or None,
        system_prompt=sp,
        allowed_tools=tuple(tools) if tools else None,
        add_dirs=_parse_dirs(add_dirs_raw),
        permission_mode=pm,
    )

    if resp.session_id and resp.session_id != state.get("claude_session_id"):
        state = {**state, "claude_session_id": resp.session_id}
        db.update_conversation(conv_id, claude_session_id=resp.session_id)

    history = history + [{"role": "assistant", "content": resp.text}]
    db.add_message(conv_id, "assistant", resp.text)

    return history, None, state, _format_usage(resp)


# ---------------------------------------------------------------------------
# Admin panel handlers
# ---------------------------------------------------------------------------


def on_create_user(
    username: str,
    password: str,
    is_admin: bool,
    request: gr.Request,
) -> tuple:
    if not _is_admin(request):
        return "Access denied.", _users_dataframe(), _whitelist_dataframe(), "", ""
    if not username or not password:
        return "Username and password are required.", _users_dataframe(), _whitelist_dataframe(), "", ""
    if db.get_user_by_username(username):
        return f"User '{username}' already exists.", _users_dataframe(), _whitelist_dataframe(), "", ""
    pw_hash = hash_password(password)
    db.create_user(username, pw_hash, is_admin=is_admin)
    db.add_to_whitelist(username)
    return (
        f"User '{username}' created and whitelisted.",
        _users_dataframe(),
        _whitelist_dataframe(),
        "",
        "",
    )


def on_delete_user(username: str, request: gr.Request) -> tuple:
    if not _is_admin(request):
        return "Access denied.", _users_dataframe(), _whitelist_dataframe(), ""
    if not username:
        return "Username is required.", _users_dataframe(), _whitelist_dataframe(), ""
    user = db.get_user_by_username(username)
    if not user:
        return f"User '{username}' not found.", _users_dataframe(), _whitelist_dataframe(), ""
    if user.username == request.username:
        return "Cannot delete yourself.", _users_dataframe(), _whitelist_dataframe(), ""
    db.delete_user(user.id)
    db.remove_from_whitelist(username)
    return (
        f"User '{username}' deleted.",
        _users_dataframe(),
        _whitelist_dataframe(),
        "",
    )


def on_add_whitelist(username: str, request: gr.Request) -> tuple:
    if not _is_admin(request):
        return "Access denied.", _whitelist_dataframe(), ""
    if not username:
        return "Username is required.", _whitelist_dataframe(), ""
    db.add_to_whitelist(username)
    return f"'{username}' added to whitelist.", _whitelist_dataframe(), ""


def on_remove_whitelist(username: str, request: gr.Request) -> tuple:
    if not _is_admin(request):
        return "Access denied.", _whitelist_dataframe(), ""
    if not username:
        return "Username is required.", _whitelist_dataframe(), ""
    user = db.get_user_by_username(username)
    if user and user.is_admin:
        admins_wl = sum(
            1
            for u in db.get_all_users()
            if u.is_admin and db.is_whitelisted(u.username)
        )
        if admins_wl <= 1:
            return (
                "Cannot remove the last whitelisted admin.",
                _whitelist_dataframe(),
                "",
            )
    db.remove_from_whitelist(username)
    return f"'{username}' removed from whitelist.", _whitelist_dataframe(), ""


def on_refresh_admin(request: gr.Request) -> tuple:
    if not _is_admin(request):
        return [], []
    return _users_dataframe(), _whitelist_dataframe()


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------


def build_app(auth_fn) -> gr.Blocks:
    """Build and return the Gradio application."""
    model_choices = [(label, value) for label, value in AVAILABLE_MODELS]

    with gr.Blocks() as app:
        gr.Markdown(
            "# AI Hub\n"
            "Multimodal AI chat powered by Claude Code. "
            "Send text, images, PDFs, or voice."
        )

        state = gr.State({"conversation_id": None, "claude_session_id": None})

        with gr.Row():
            conv_dropdown = gr.Dropdown(
                label="Conversation",
                choices=[],
                interactive=True,
                scale=3,
            )
            model_dropdown = gr.Dropdown(
                label="Model",
                choices=model_choices,
                value=settings.default_model,
                interactive=True,
                scale=1,
            )
            new_conv_btn = gr.Button("+ New", variant="secondary", scale=1)

        chatbot = gr.Chatbot(height=500, label="Conversation")

        usage_display = gr.Textbox(
            label="Last response",
            interactive=False,
            max_lines=1,
        )

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

        # -- Settings --------------------------------------------------------

        with gr.Accordion("Settings", open=False):
            tools_select = gr.CheckboxGroup(
                label="Allowed tools",
                choices=list(ALL_TOOLS),
                value=list(settings.default_tools),
            )
            permission_mode_dropdown = gr.Dropdown(
                label="Permission mode",
                choices=[(label, value) for label, value in PERMISSION_MODES],
                value="default",
                interactive=True,
            )
            system_prompt_input = gr.Textbox(
                label="System prompt (appended to default)",
                placeholder="e.g. Always respond in Spanish.",
                lines=2,
            )
            add_dirs_input = gr.Textbox(
                label="Additional directories (one per line)",
                placeholder="/home/user/other-project\n/home/user/docs",
                lines=3,
            )

        # -- Admin Panel -----------------------------------------------------

        with gr.Accordion(
            "Admin Panel", open=False, visible=False
        ) as admin_panel:
            refresh_admin_btn = gr.Button("Refresh tables")

            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Create User")
                    create_username = gr.Textbox(
                        label="Username", placeholder="new_user"
                    )
                    create_password = gr.Textbox(
                        label="Password", type="password"
                    )
                    create_is_admin = gr.Checkbox(label="Admin", value=False)
                    create_btn = gr.Button("Create User", variant="primary")
                    create_msg = gr.Textbox(
                        label="Status", interactive=False
                    )

                with gr.Column():
                    gr.Markdown("### Whitelist")
                    wl_username = gr.Textbox(
                        label="Username", placeholder="username"
                    )
                    with gr.Row():
                        wl_add_btn = gr.Button("Add to Whitelist")
                        wl_remove_btn = gr.Button("Remove from Whitelist")
                    wl_msg = gr.Textbox(label="Status", interactive=False)

                with gr.Column():
                    gr.Markdown("### Delete User")
                    del_username = gr.Textbox(
                        label="Username", placeholder="username"
                    )
                    del_btn = gr.Button("Delete User", variant="stop")
                    del_msg = gr.Textbox(label="Status", interactive=False)

            gr.Markdown("### Registered Users")
            users_table = gr.Dataframe(
                headers=["Username", "Admin", "Whitelisted", "Created"],
                interactive=False,
            )
            gr.Markdown("### Whitelist")
            whitelist_table = gr.Dataframe(
                headers=["Username", "Created"],
                interactive=False,
            )

        # -- Events ----------------------------------------------------------

        app.load(
            fn=on_load,
            outputs=[conv_dropdown, chatbot, state, admin_panel],
        )

        new_conv_btn.click(
            fn=on_new_conversation,
            inputs=[state],
            outputs=[conv_dropdown, chatbot, state],
        )

        conv_dropdown.change(
            fn=on_switch_conversation,
            inputs=[conv_dropdown, state],
            outputs=[chatbot, state],
        )

        text_input.submit(
            fn=handle_chat,
            inputs=[
                text_input,
                chatbot,
                state,
                model_dropdown,
                tools_select,
                system_prompt_input,
                add_dirs_input,
                permission_mode_dropdown,
            ],
            outputs=[chatbot, text_input, state, usage_display],
        )

        send_voice_btn.click(
            fn=handle_voice,
            inputs=[
                audio_input,
                chatbot,
                state,
                model_dropdown,
                tools_select,
                system_prompt_input,
                add_dirs_input,
                permission_mode_dropdown,
            ],
            outputs=[chatbot, audio_input, state, usage_display],
        )

        # Admin events
        create_btn.click(
            fn=on_create_user,
            inputs=[create_username, create_password, create_is_admin],
            outputs=[
                create_msg,
                users_table,
                whitelist_table,
                create_username,
                create_password,
            ],
        )

        del_btn.click(
            fn=on_delete_user,
            inputs=[del_username],
            outputs=[del_msg, users_table, whitelist_table, del_username],
        )

        wl_add_btn.click(
            fn=on_add_whitelist,
            inputs=[wl_username],
            outputs=[wl_msg, whitelist_table, wl_username],
        )

        wl_remove_btn.click(
            fn=on_remove_whitelist,
            inputs=[wl_username],
            outputs=[wl_msg, whitelist_table, wl_username],
        )

        refresh_admin_btn.click(
            fn=on_refresh_admin,
            outputs=[users_table, whitelist_table],
        )

    return app


def main() -> None:
    """Launch the application."""
    settings.ensure_dirs()
    seed_admin(db)

    def auth_fn(username: str, password: str) -> bool:
        return authenticate(username, password, db)

    app = build_app(auth_fn)
    app.launch(
        server_name=settings.server_host,
        server_port=settings.server_port,
        theme=gr.themes.Soft(),
        auth=auth_fn,
    )


if __name__ == "__main__":
    main()
