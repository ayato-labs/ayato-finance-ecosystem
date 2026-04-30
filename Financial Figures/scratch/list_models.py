from google import genai


def get_api_key():
    try:
        with open(".env") as f:
            for line in f:
                if line.startswith("GEMINI_API_KEY="):
                    return line.split("=")[1].strip()
    except Exception:
        pass
    return None


def list_available_models():
    api_key = get_api_key()
    if not api_key:
        print("Error: GEMINI_API_KEY not found in .env.")
        return

    client = genai.Client(api_key=api_key)

    print("Checking for Gemma models...")
    try:
        found = False
        for model in client.models.list():
            if "gemma" in model.name.lower():
                print(f"Found: {model.name}")
                found = True
        if not found:
            print("No Gemma models found in the available list.")
    except Exception as e:
        print(f"Error fetching models: {e}")


if __name__ == "__main__":
    list_available_models()
