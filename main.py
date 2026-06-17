import sys

try:
    from src import config
    print("CrisisLens AI — setup complete. API key loaded.")
    print("Run: streamlit run ui/app.py to launch.")
except EnvironmentError as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"Unexpected Error: {e}", file=sys.stderr)
    sys.exit(1)
