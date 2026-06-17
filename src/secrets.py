import os


def _find_nested_secret(value, name: str):
    if not isinstance(value, dict):
        return None
    for key, child in value.items():
        if str(key).upper() == name.upper() and child:
            return str(child)
        found = _find_nested_secret(child, name)
        if found:
            return found
    return None


def get_secret(name: str, default: str | None = None) -> str | None:
    try:
        import streamlit as st

        for candidate in (name, name.upper(), name.lower()):
            value = st.secrets.get(candidate)
            if value:
                return str(value)

        nested_value = _find_nested_secret(dict(st.secrets), name)
        if nested_value:
            return nested_value
    except Exception:
        pass

    for candidate in (name, name.upper(), name.lower()):
        value = os.getenv(candidate)
        if value:
            return value

    return default
