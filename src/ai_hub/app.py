"""Main application - Gradio multimodal chat interface with session management."""

from pathlib import Path

import gradio as gr

from ai_hub.auth import authenticate, hash_password, seed_admin
from ai_hub.config import ALL_TOOLS, AVAILABLE_MODELS, PERMISSION_MODES, settings
from ai_hub.processors import UploadError
from ai_hub.security import audit_log

# Layout options
LAYOUT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("Focus", "focus"),
    ("Minimal", "minimal"),
    ("Productivity", "productivity"),
)
from ai_hub.database import Conversation, Database
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


def _tag_choices(user_id: int) -> list[tuple[str, str]]:
    tags = db.get_tags(user_id)
    return [(t.name, str(t.id)) for t in tags]


def _tag_filter_choices(user_id: int) -> list[tuple[str, str]]:
    return [("All", "")] + _tag_choices(user_id)


def _tags_dataframe(user_id: int) -> list[list]:
    tags = db.get_tags(user_id)
    return [[t.name, t.id] for t in tags]


def _search_results_dataframe(
    convos: list[Conversation],
) -> list[list]:
    return [[c.title, c.updated_at, c.id] for c in convos]


def _filtered_conversation_choices(
    user_id: int, tag_filter_value: str
) -> list[tuple[str, str]]:
    if tag_filter_value:
        convos = db.get_conversations_by_tag(user_id, int(tag_filter_value))
    else:
        convos = db.get_conversations(user_id)
    return [(c.title, str(c.id)) for c in convos]


def _extract_file_paths(text: str) -> list[str]:
    """Extract file paths mentioned in assistant response that exist on disk."""
    import re

    # Match common file path patterns
    patterns = [
        r'`(/[^`\s]+)`',  # Paths in backticks
        r'(?:^|\s)(/(?:home|tmp|var|usr)[^\s\n\)\"\'<>]+)',  # Unix paths
    ]

    paths = set()
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.MULTILINE):
            path = match.group(1).rstrip('.,;:')
            if Path(path).exists() and Path(path).is_file():
                paths.add(path)

    return sorted(paths)


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
    tag_filter = _tag_filter_choices(user_id)
    tag_ch = _tag_choices(user_id)
    tags_df = _tags_dataframe(user_id)

    # Load user settings (or defaults)
    user_settings = db.get_user_settings(user_id)
    if user_settings:
        model_val = user_settings.model
        # Handle empty tools string properly
        tools_val = [t for t in user_settings.tools.split(",") if t] if user_settings.tools else []
        perm_val = user_settings.permission_mode
        sys_prompt_val = user_settings.system_prompt
        add_dirs_val = user_settings.add_dirs
        layout_val = user_settings.ui_layout
    else:
        model_val = settings.default_model
        tools_val = list(settings.default_tools)
        perm_val = "default"
        sys_prompt_val = ""
        add_dirs_val = ""
        layout_val = "focus"

    # Get first values for dropdowns that need a selection
    first_conv = str(convo.id)
    first_tag = tag_ch[0][1] if tag_ch else None

    # Get current tags for the active conversation
    conv_tags = db.get_conversation_tags(convo.id)
    current_tags_str = ", ".join(t.name for t in conv_tags)

    # Layout-specific visibility
    show_sidebar = layout_val in ("focus", "productivity")
    show_header_controls = layout_val == "minimal"
    show_tags_prominent = layout_val == "productivity"

    return (
        gr.update(choices=choices, value=first_conv),     # conv_dropdown
        history,                                          # chatbot
        state,                                            # state
        gr.update(visible=show_admin),                    # admin_panel
        gr.update(choices=tag_filter, value=""),          # tag_filter_dropdown
        gr.update(choices=choices, value=first_conv),     # rename_conv_dropdown
        gr.update(choices=choices, value=first_conv),     # delete_conv_dropdown
        tags_df,                                          # tags_table
        gr.update(choices=tag_ch, value=first_tag),       # delete_tag_dropdown
        gr.update(choices=choices, value=first_conv),     # assign_conv_dropdown
        gr.update(choices=tag_ch, value=first_tag),       # assign_tag_dropdown
        current_tags_str,                                 # current_tags_display
        gr.update(value=model_val),                       # model_dropdown
        gr.update(value=tools_val),                       # tools_select
        gr.update(value=perm_val),                        # permission_mode_dropdown
        gr.update(value=sys_prompt_val),                  # system_prompt_input
        gr.update(value=add_dirs_val),                    # add_dirs_input
        gr.update(value=layout_val),                      # layout_dropdown
        gr.update(visible=show_sidebar),                  # sidebar
        gr.update(visible=show_header_controls),          # header_controls
        gr.update(open=show_tags_prominent),              # tags_accordion
        gr.update(choices=choices, value=first_conv),     # header_conv_dropdown
        gr.update(value=model_val),                       # header_model_dropdown
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
        gr.update(choices=choices, value=str(convo.id)),  # conv_dropdown
        [],                                                # chatbot
        state,                                             # state
        gr.update(choices=choices),                         # rename_conv_dropdown
        gr.update(choices=choices),                         # delete_conv_dropdown
        gr.update(choices=choices),                         # assign_conv_dropdown
        gr.update(choices=choices, value=str(convo.id)),  # header_conv_dropdown
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
) -> tuple:
    text = message.get("text", "").strip()
    files: list[str] = message.get("files", [])

    if not text and not files:
        return history, {"text": "", "files": []}, state, "", gr.update(visible=False), None

    # Validate and save uploads
    try:
        saved = [save_upload(f, settings.upload_dir) for f in files]
    except UploadError as e:
        error_msg = f"Upload failed: {e}"
        audit_log("UPLOAD_FAILED", request.username, str(e))
        history = history + [{"role": "assistant", "content": error_msg}]
        return history, {"text": "", "files": []}, state, "", gr.update(visible=False), None

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

    # Extract downloadable files from response
    detected_files = _extract_file_paths(resp.text)
    if detected_files:
        return (
            history,
            {"text": "", "files": []},
            state,
            _format_usage(resp),
            gr.update(visible=True),
            detected_files,
        )
    return (
        history,
        {"text": "", "files": []},
        state,
        _format_usage(resp),
        gr.update(visible=False),
        None,
    )


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
) -> tuple:
    if audio_path is None:
        return history, None, state, "", gr.update(visible=False), None

    try:
        text = transcribe_audio(audio_path, settings.whisper_model)
    except ImportError as exc:
        history = history + [
            {"role": "assistant", "content": str(exc)},
        ]
        return history, None, state, "", gr.update(visible=False), None

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

    # Extract downloadable files from response
    detected_files = _extract_file_paths(resp.text)
    if detected_files:
        return (
            history,
            None,
            state,
            _format_usage(resp),
            gr.update(visible=True),
            detected_files,
        )
    return (
        history,
        None,
        state,
        _format_usage(resp),
        gr.update(visible=False),
        None,
    )


# ---------------------------------------------------------------------------
# Conversation management handlers
# ---------------------------------------------------------------------------


def on_search_conversations(query: str, request: gr.Request) -> list[list]:
    if not query.strip():
        return []
    user_id = _get_user_id(request)
    results = db.search_conversations(user_id, query.strip())
    return _search_results_dataframe(results)


def on_rename_conversation(
    conv_id_str: str,
    new_title: str,
    state: dict,
    tag_filter_value: str,
    request: gr.Request,
) -> tuple:
    user_id = _get_user_id(request)
    if not conv_id_str or not new_title.strip():
        choices = _filtered_conversation_choices(user_id, tag_filter_value)
        all_choices = _conversation_choices(user_id)
        return (
            gr.update(choices=choices, value=state.get("conversation_id") and str(state["conversation_id"])),
            gr.update(choices=all_choices),
            gr.update(choices=all_choices),
            gr.update(choices=all_choices),
            "",
        )
    db.update_conversation(int(conv_id_str), title=new_title.strip())
    choices = _filtered_conversation_choices(user_id, tag_filter_value)
    all_choices = _conversation_choices(user_id)
    current = state.get("conversation_id")
    return (
        gr.update(choices=choices, value=str(current) if current else None),
        gr.update(choices=all_choices),
        gr.update(choices=all_choices),
        gr.update(choices=all_choices),
        "",
    )


def on_delete_conversation(
    conv_id_str: str,
    state: dict,
    tag_filter_value: str,
    request: gr.Request,
) -> tuple:
    user_id = _get_user_id(request)
    if not conv_id_str:
        choices = _filtered_conversation_choices(user_id, tag_filter_value)
        all_choices = _conversation_choices(user_id)
        current = state.get("conversation_id")
        history = _load_history(current) if current else []
        return (
            gr.update(choices=choices, value=str(current) if current else None),
            history,
            state,
            gr.update(choices=all_choices),
            gr.update(choices=all_choices),
            gr.update(choices=all_choices),
        )

    deleted_id = int(conv_id_str)
    db.delete_conversation(deleted_id)

    convos = db.get_conversations(user_id)
    if not convos:
        convo = db.create_conversation(user_id)
    else:
        convo = convos[0]

    current = state.get("conversation_id")
    if current == deleted_id:
        state = {
            "conversation_id": convo.id,
            "claude_session_id": convo.claude_session_id,
        }
        history = _load_history(convo.id)
        active_id = convo.id
    else:
        history = _load_history(current) if current else []
        active_id = current

    choices = _filtered_conversation_choices(user_id, tag_filter_value)
    all_choices = _conversation_choices(user_id)
    return (
        gr.update(choices=choices, value=str(active_id) if active_id else None),
        history,
        state,
        gr.update(choices=all_choices),
        gr.update(choices=all_choices),
        gr.update(choices=all_choices),
    )


def on_create_tag(name: str | None, request: gr.Request) -> tuple:
    user_id = _get_user_id(request)
    if not name or not name.strip():
        return (
            _tags_dataframe(user_id),
            gr.update(choices=_tag_choices(user_id)),
            gr.update(choices=_tag_choices(user_id)),
            gr.update(choices=_tag_filter_choices(user_id)),
            "",
            "Enter a tag name.",
        )
    tag_name = name.strip()
    try:
        db.create_tag(user_id, tag_name)
        status = f"Tag '{tag_name}' created."
    except Exception:
        status = f"Tag '{tag_name}' already exists."
    return (
        _tags_dataframe(user_id),
        gr.update(choices=_tag_choices(user_id)),
        gr.update(choices=_tag_choices(user_id)),
        gr.update(choices=_tag_filter_choices(user_id)),
        "",
        status,
    )


def on_delete_tag(tag_id_str: str, request: gr.Request) -> tuple:
    user_id = _get_user_id(request)
    if tag_id_str:
        db.delete_tag(int(tag_id_str))
    return (
        _tags_dataframe(user_id),
        gr.update(choices=_tag_choices(user_id)),
        gr.update(choices=_tag_choices(user_id)),
        gr.update(choices=_tag_filter_choices(user_id)),
    )


def on_assign_tag(
    conv_id_str: str | None, tag_id_str: str | None, request: gr.Request
) -> str:
    if not conv_id_str or not tag_id_str:
        return ""
    try:
        db.add_tag_to_conversation(int(conv_id_str), int(tag_id_str))
        tags = db.get_conversation_tags(int(conv_id_str))
        return ", ".join(t.name for t in tags)
    except Exception as e:
        return f"Error: {e}"


def on_unassign_tag(
    conv_id_str: str | None, tag_id_str: str | None, request: gr.Request
) -> str:
    if not conv_id_str or not tag_id_str:
        return ""
    try:
        db.remove_tag_from_conversation(int(conv_id_str), int(tag_id_str))
        tags = db.get_conversation_tags(int(conv_id_str))
        return ", ".join(t.name for t in tags)
    except Exception as e:
        return f"Error: {e}"


def on_select_assign_conversation(conv_id_str: str) -> str:
    if not conv_id_str:
        return ""
    tags = db.get_conversation_tags(int(conv_id_str))
    return ", ".join(t.name for t in tags)


def on_tag_filter_change(
    tag_filter_value: str | None, state: dict, request: gr.Request
) -> dict:
    user_id = _get_user_id(request)
    # Handle None or empty string as "show all"
    filter_val = tag_filter_value if tag_filter_value else ""
    choices = _filtered_conversation_choices(user_id, filter_val)
    current = state.get("conversation_id")
    current_str = str(current) if current else None
    # Keep current selection if it's in the filtered list
    values = [v for _, v in choices]
    if current_str not in values:
        current_str = values[0] if values else None
    return gr.update(choices=choices, value=current_str)


# ---------------------------------------------------------------------------
# Settings handlers
# ---------------------------------------------------------------------------


def on_save_settings(
    model: str,
    tools: list[str],
    permission_mode: str,
    system_prompt: str,
    add_dirs: str,
    layout: str,
    request: gr.Request,
) -> str:
    user_id = _get_user_id(request)
    db.save_user_settings(
        user_id,
        model=model,
        tools=tools,
        permission_mode=permission_mode,
        system_prompt=system_prompt.strip(),
        add_dirs=add_dirs.strip(),
        ui_layout=layout,
    )
    return "Settings saved."


def on_layout_change(layout: str, request: gr.Request) -> tuple:
    """Handle layout change - save preference and update visibility."""
    user_id = _get_user_id(request)
    db.save_user_layout(user_id, layout)

    show_sidebar = layout in ("focus", "productivity")
    show_header_controls = layout == "minimal"
    show_tags_prominent = layout == "productivity"

    return (
        gr.update(visible=show_sidebar),      # sidebar
        gr.update(visible=show_header_controls),  # header_controls
        gr.update(open=show_tags_prominent),  # tags_accordion
        f"Layout changed to {layout}. Some changes may require page refresh.",
    )


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
        audit_log("ADMIN_ACCESS_DENIED", request.username, "create_user attempt")
        return "Access denied.", _users_dataframe(), _whitelist_dataframe(), "", ""
    if not username or not password:
        return "Username and password are required.", _users_dataframe(), _whitelist_dataframe(), "", ""
    if db.get_user_by_username(username):
        return f"User '{username}' already exists.", _users_dataframe(), _whitelist_dataframe(), "", ""
    pw_hash = hash_password(password)
    db.create_user(username, pw_hash, is_admin=is_admin)
    db.add_to_whitelist(username)
    audit_log("USER_CREATED", request.username, f"created user '{username}' (admin={is_admin})")
    return (
        f"User '{username}' created and whitelisted.",
        _users_dataframe(),
        _whitelist_dataframe(),
        "",
        "",
    )


def on_delete_user(username: str, request: gr.Request) -> tuple:
    if not _is_admin(request):
        audit_log("ADMIN_ACCESS_DENIED", request.username, "delete_user attempt")
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
    audit_log("USER_DELETED", request.username, f"deleted user '{username}'")
    return (
        f"User '{username}' deleted.",
        _users_dataframe(),
        _whitelist_dataframe(),
        "",
    )


def on_add_whitelist(username: str, request: gr.Request) -> tuple:
    if not _is_admin(request):
        audit_log("ADMIN_ACCESS_DENIED", request.username, "add_whitelist attempt")
        return "Access denied.", _whitelist_dataframe(), ""
    if not username:
        return "Username is required.", _whitelist_dataframe(), ""
    db.add_to_whitelist(username)
    audit_log("WHITELIST_ADD", request.username, f"added '{username}'")
    return f"'{username}' added to whitelist.", _whitelist_dataframe(), ""


def on_remove_whitelist(username: str, request: gr.Request) -> tuple:
    if not _is_admin(request):
        audit_log("ADMIN_ACCESS_DENIED", request.username, "remove_whitelist attempt")
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
    audit_log("WHITELIST_REMOVE", request.username, f"removed '{username}'")
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

    with gr.Blocks(title="AI Hub") as app:
        state = gr.State({"conversation_id": None, "claude_session_id": None})
        sidebar_visible = gr.State(True)

        # -- Header ----------------------------------------------------------
        with gr.Row():
            gr.Markdown("## AI Hub")
            # Header controls for Minimal layout (hidden by default)
            with gr.Row(visible=False) as header_controls:
                header_conv_dropdown = gr.Dropdown(
                    label="Conversation",
                    choices=[],
                    interactive=True,
                    scale=2,
                )
                header_model_dropdown = gr.Dropdown(
                    label="Model",
                    choices=model_choices,
                    value=settings.default_model,
                    interactive=True,
                    scale=1,
                )
                header_new_btn = gr.Button("+", variant="primary", scale=0, min_width=40)
            toggle_sidebar_btn = gr.Button(
                "Hide Menu", variant="secondary", scale=0, min_width=100
            )

        with gr.Row():
            # -- Sidebar (collapsible) ---------------------------------------
            with gr.Column(scale=1, min_width=280) as sidebar:
                # Conversations section
                with gr.Group():
                    gr.Markdown("### Conversations")
                    conv_dropdown = gr.Dropdown(
                        label="Select",
                        choices=[],
                        interactive=True,
                    )
                    with gr.Row():
                        tag_filter_dropdown = gr.Dropdown(
                            label="Filter",
                            choices=[("All", "")],
                            value="",
                            interactive=True,
                            scale=2,
                        )
                        new_conv_btn = gr.Button("+", variant="primary", scale=0, min_width=40)

                    with gr.Accordion("Search", open=False):
                        search_input = gr.Textbox(
                            placeholder="Search...",
                            show_label=False,
                        )
                        search_btn = gr.Button("Search", size="sm")
                        search_results = gr.Dataframe(
                            headers=["Title", "Updated", "ID"],
                            interactive=False,
                        )

                    with gr.Accordion("Manage", open=False):
                        rename_conv_dropdown = gr.Dropdown(
                            label="Rename", choices=[], interactive=True
                        )
                        with gr.Row():
                            rename_input = gr.Textbox(
                                placeholder="New title...",
                                show_label=False,
                                scale=3,
                            )
                            rename_btn = gr.Button("OK", size="sm", scale=0)
                        delete_conv_dropdown = gr.Dropdown(
                            label="Delete", choices=[], interactive=True
                        )
                        delete_btn = gr.Button("Delete", variant="stop", size="sm")

                # Tags section
                with gr.Accordion("Tags", open=False) as tags_accordion:
                    with gr.Row():
                        new_tag_input = gr.Textbox(
                            placeholder="New tag...",
                            show_label=False,
                            scale=3,
                        )
                        create_tag_btn = gr.Button("+", variant="primary", scale=0, min_width=40)
                    tag_status_msg = gr.Textbox(
                        show_label=False, interactive=False, max_lines=1
                    )
                    tags_table = gr.Dataframe(
                        headers=["Name", "ID"],
                        interactive=False,
                    )
                    delete_tag_dropdown = gr.Dropdown(
                        label="Delete tag", choices=[], interactive=True
                    )
                    delete_tag_btn = gr.Button("Delete Tag", variant="stop", size="sm")

                    gr.Markdown("**Assign to conversation**")
                    assign_conv_dropdown = gr.Dropdown(
                        label="Conversation", choices=[], interactive=True
                    )
                    assign_tag_dropdown = gr.Dropdown(
                        label="Tag", choices=[], interactive=True
                    )
                    with gr.Row():
                        assign_btn = gr.Button("Assign", size="sm", variant="primary")
                        unassign_btn = gr.Button("Remove", size="sm")
                    current_tags_display = gr.Textbox(
                        label="Current tags", interactive=False, max_lines=1
                    )

                # Settings section
                with gr.Accordion("Settings", open=False):
                    layout_dropdown = gr.Dropdown(
                        label="UI Layout",
                        choices=[(label, value) for label, value in LAYOUT_OPTIONS],
                        value="focus",
                        interactive=True,
                    )
                    model_dropdown = gr.Dropdown(
                        label="Model",
                        choices=model_choices,
                        value=settings.default_model,
                        interactive=True,
                    )
                    tools_select = gr.CheckboxGroup(
                        label="Tools",
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
                        label="System prompt",
                        placeholder="e.g. Always respond in Spanish.",
                        lines=2,
                    )
                    add_dirs_input = gr.Textbox(
                        label="Additional directories",
                        placeholder="/path/to/dir",
                        lines=2,
                    )
                    save_settings_btn = gr.Button("Save Settings", variant="primary", size="sm")
                    settings_msg = gr.Textbox(
                        show_label=False, interactive=False, max_lines=1
                    )

                # Admin section (hidden by default)
                with gr.Accordion(
                    "Admin", open=False, visible=False
                ) as admin_panel:
                    refresh_admin_btn = gr.Button("Refresh", size="sm")

                    gr.Markdown("**Create User**")
                    create_username = gr.Textbox(
                        label="Username", placeholder="new_user"
                    )
                    create_password = gr.Textbox(
                        label="Password", type="password"
                    )
                    create_is_admin = gr.Checkbox(label="Admin", value=False)
                    create_btn = gr.Button("Create User", variant="primary", size="sm")
                    create_msg = gr.Textbox(show_label=False, interactive=False, max_lines=1)

                    gr.Markdown("**Whitelist**")
                    wl_username = gr.Textbox(
                        label="Username", placeholder="username"
                    )
                    with gr.Row():
                        wl_add_btn = gr.Button("Add", size="sm")
                        wl_remove_btn = gr.Button("Remove", size="sm")
                    wl_msg = gr.Textbox(show_label=False, interactive=False, max_lines=1)

                    gr.Markdown("**Delete User**")
                    del_username = gr.Textbox(
                        label="Username", placeholder="username"
                    )
                    del_btn = gr.Button("Delete User", variant="stop", size="sm")
                    del_msg = gr.Textbox(show_label=False, interactive=False, max_lines=1)

                    users_table = gr.Dataframe(
                        headers=["Username", "Admin", "WL", "Created"],
                        interactive=False,
                    )
                    whitelist_table = gr.Dataframe(
                        headers=["Username", "Created"],
                        interactive=False,
                    )

            # -- Main Chat Area ----------------------------------------------
            with gr.Column(scale=3):
                chatbot = gr.Chatbot(
                    height=550,
                    show_label=False,
                    container=True,
                )

                with gr.Tabs():
                    with gr.TabItem("Chat"):
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
                            show_label=False,
                        )

                    with gr.TabItem("Voice"):
                        audio_input = gr.Audio(
                            sources=["microphone"],
                            type="filepath",
                            label="Record your message",
                        )
                        send_voice_btn = gr.Button("Send Voice", variant="primary")

                usage_display = gr.Textbox(
                    show_label=False,
                    interactive=False,
                    max_lines=1,
                    placeholder="Usage info will appear here after sending a message",
                )

                # Downloadable files section
                with gr.Accordion("Generated Files", open=True, visible=False) as files_accordion:
                    downloadable_files = gr.File(
                        label="Download",
                        file_count="multiple",
                        interactive=False,
                    )

        # -- Toggle Sidebar Handler ------------------------------------------
        def toggle_sidebar(visible):
            new_visible = not visible
            btn_text = "Show Menu" if not new_visible else "Hide Menu"
            return (
                new_visible,
                gr.update(visible=new_visible),
                gr.update(value=btn_text),
            )

        toggle_sidebar_btn.click(
            fn=toggle_sidebar,
            inputs=[sidebar_visible],
            outputs=[sidebar_visible, sidebar, toggle_sidebar_btn],
        )

        # -- Events ----------------------------------------------------------

        app.load(
            fn=on_load,
            outputs=[
                conv_dropdown,
                chatbot,
                state,
                admin_panel,
                tag_filter_dropdown,
                rename_conv_dropdown,
                delete_conv_dropdown,
                tags_table,
                delete_tag_dropdown,
                assign_conv_dropdown,
                assign_tag_dropdown,
                current_tags_display,
                model_dropdown,
                tools_select,
                permission_mode_dropdown,
                system_prompt_input,
                add_dirs_input,
                layout_dropdown,
                sidebar,
                header_controls,
                tags_accordion,
                header_conv_dropdown,
                header_model_dropdown,
            ],
            show_progress="hidden",
        )

        new_conv_btn.click(
            fn=on_new_conversation,
            inputs=[state],
            outputs=[
                conv_dropdown,
                chatbot,
                state,
                rename_conv_dropdown,
                delete_conv_dropdown,
                assign_conv_dropdown,
                header_conv_dropdown,
            ],
        )

        conv_dropdown.change(
            fn=on_switch_conversation,
            inputs=[conv_dropdown, state],
            outputs=[chatbot, state],
            show_progress="hidden",
        )

        # Use .then() to chain file detection after chat to avoid multiple progress bars
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
            outputs=[chatbot, text_input, state, usage_display, files_accordion, downloadable_files],
            concurrency_limit=1,
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
            outputs=[chatbot, audio_input, state, usage_display, files_accordion, downloadable_files],
        )

        # Conversation management events
        search_btn.click(
            fn=on_search_conversations,
            inputs=[search_input],
            outputs=[search_results],
        )

        rename_btn.click(
            fn=on_rename_conversation,
            inputs=[rename_conv_dropdown, rename_input, state, tag_filter_dropdown],
            outputs=[
                conv_dropdown,
                rename_conv_dropdown,
                delete_conv_dropdown,
                assign_conv_dropdown,
                rename_input,
            ],
        )

        delete_btn.click(
            fn=on_delete_conversation,
            inputs=[delete_conv_dropdown, state, tag_filter_dropdown],
            outputs=[
                conv_dropdown,
                chatbot,
                state,
                rename_conv_dropdown,
                delete_conv_dropdown,
                assign_conv_dropdown,
            ],
        )

        create_tag_btn.click(
            fn=on_create_tag,
            inputs=[new_tag_input],
            outputs=[
                tags_table,
                delete_tag_dropdown,
                assign_tag_dropdown,
                tag_filter_dropdown,
                new_tag_input,
                tag_status_msg,
            ],
        )

        delete_tag_btn.click(
            fn=on_delete_tag,
            inputs=[delete_tag_dropdown],
            outputs=[
                tags_table,
                delete_tag_dropdown,
                assign_tag_dropdown,
                tag_filter_dropdown,
            ],
        )

        assign_btn.click(
            fn=on_assign_tag,
            inputs=[assign_conv_dropdown, assign_tag_dropdown],
            outputs=[current_tags_display],
        )

        unassign_btn.click(
            fn=on_unassign_tag,
            inputs=[assign_conv_dropdown, assign_tag_dropdown],
            outputs=[current_tags_display],
        )

        assign_conv_dropdown.change(
            fn=on_select_assign_conversation,
            inputs=[assign_conv_dropdown],
            outputs=[current_tags_display],
            show_progress="hidden",
        )

        tag_filter_dropdown.change(
            fn=on_tag_filter_change,
            inputs=[tag_filter_dropdown, state],
            outputs=[conv_dropdown],
            show_progress="hidden",
        )

        # Settings events
        save_settings_btn.click(
            fn=on_save_settings,
            inputs=[
                model_dropdown,
                tools_select,
                permission_mode_dropdown,
                system_prompt_input,
                add_dirs_input,
                layout_dropdown,
            ],
            outputs=[settings_msg],
        )

        layout_dropdown.change(
            fn=on_layout_change,
            inputs=[layout_dropdown],
            outputs=[sidebar, header_controls, tags_accordion, settings_msg],
            show_progress="hidden",
        )

        # Header controls for Minimal layout (no sync to sidebar - they're mutually exclusive)
        header_conv_dropdown.change(
            fn=on_switch_conversation,
            inputs=[header_conv_dropdown, state],
            outputs=[chatbot, state],
            show_progress="hidden",
        )

        header_new_btn.click(
            fn=on_new_conversation,
            inputs=[state],
            outputs=[
                conv_dropdown,
                chatbot,
                state,
                rename_conv_dropdown,
                delete_conv_dropdown,
                assign_conv_dropdown,
                header_conv_dropdown,
            ],
        )

        # Sync header model to sidebar (only one direction to avoid event loops)
        # Header controls are only visible in Minimal layout where sidebar is hidden
        def sync_header_to_sidebar_model(model_val):
            return gr.update(value=model_val)

        header_model_dropdown.change(
            fn=sync_header_to_sidebar_model,
            inputs=[header_model_dropdown],
            outputs=[model_dropdown],
            show_progress="hidden",
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
