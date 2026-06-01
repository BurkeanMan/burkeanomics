import streamlit as st
from supabase import create_client


def get_supabase():
    """Return a Supabase client with the current user's session restored."""
    client = create_client(
        st.secrets["supabase"]["url"],
        st.secrets["supabase"]["key"],
    )
    if "sb_access_token" in st.session_state:
        try:
            client.auth.set_session(
                st.session_state["sb_access_token"],
                st.session_state["sb_refresh_token"],
            )
        except Exception:
            st.session_state.pop("sb_access_token", None)
            st.session_state.pop("sb_refresh_token", None)
            st.session_state.pop("sb_user", None)
    return client


def sign_in(email: str, password: str):
    response = get_supabase().auth.sign_in_with_password(
        {"email": email, "password": password}
    )
    _store_session(response)
    return response


def sign_up(email: str, password: str):
    response = get_supabase().auth.sign_up(
        {"email": email, "password": password}
    )
    _store_session(response)
    return response


def sign_out():
    try:
        get_supabase().auth.sign_out()
    except Exception:
        pass
    st.session_state.pop("sb_access_token", None)
    st.session_state.pop("sb_refresh_token", None)
    st.session_state.pop("sb_user", None)


def _store_session(response):
    if response.session:
        st.session_state["sb_access_token"] = response.session.access_token
        st.session_state["sb_refresh_token"] = response.session.refresh_token
        st.session_state["sb_user"] = {
            "id": response.user.id,
            "email": response.user.email,
        }


def is_logged_in() -> bool:
    return "sb_user" in st.session_state


def current_user() -> dict | None:
    return st.session_state.get("sb_user")


def is_admin() -> bool:
    user = current_user()
    if not user:
        return False
    admin_cfg = st.secrets.get("admin", {})
    admin_emails = admin_cfg.get("emails", [])
    if isinstance(admin_emails, str):
        admin_emails = [e.strip() for e in admin_emails.split(",")]
    return user["email"] in admin_emails


# ── Universe CRUD ──────────────────────────────────────────────────────────────

def list_universes() -> list:
    response = (
        get_supabase()
        .table("universes")
        .select("id, name, updated_at, is_default")
        .order("updated_at", desc=True)
        .execute()
    )
    return response.data or []


def get_default_universe() -> dict | None:
    try:
        response = (
            get_supabase()
            .table("universes")
            .select("*")
            .eq("is_default", True)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None
    except Exception:
        return None


def set_default_universe(universe_id: str):
    client = get_supabase()
    client.table("universes").update({"is_default": False}).eq("is_default", True).execute()
    client.table("universes").update({"is_default": True}).eq("id", universe_id).execute()


def save_universe(name: str, params: dict) -> str | None:
    """Upsert a universe by name for the current user. Returns the universe id."""
    client = get_supabase()
    user_id = current_user()["id"]
    existing = (
        client.table("universes")
        .select("id")
        .eq("user_id", user_id)
        .eq("name", name)
        .execute()
    )
    if existing.data:
        uid = existing.data[0]["id"]
        client.table("universes").update({"params": params}).eq("id", uid).execute()
        return uid
    response = (
        client.table("universes")
        .insert({"user_id": user_id, "name": name, "params": params})
        .execute()
    )
    return response.data[0]["id"] if response.data else None


def load_universe(universe_id: str) -> dict | None:
    response = (
        get_supabase()
        .table("universes")
        .select("*")
        .eq("id", universe_id)
        .single()
        .execute()
    )
    return response.data


def delete_universe(universe_id: str):
    get_supabase().table("universes").delete().eq("id", universe_id).execute()


def send_password_reset(email: str):
    """Send a password-reset email. Supabase redirects to the configured Site URL."""
    get_supabase().auth.reset_password_for_email(email)


def update_password(access_token: str, refresh_token: str, new_password: str):
    """Set a new password using the recovery tokens from the reset link."""
    client = get_supabase()
    client.auth.set_session(access_token, refresh_token)
    client.auth.update_user({"password": new_password})
