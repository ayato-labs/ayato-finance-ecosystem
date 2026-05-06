import jquantsapi
import inspect

def inspect_client():
    if hasattr(jquantsapi, 'ClientV2'):
        cli = jquantsapi.ClientV2(api_key="dummy")
        methods = [m for m in dir(cli) if m.startswith('get_')]
        for m in methods:
            try:
                print(f"Method: {m}")
                print(f"Signature: {inspect.signature(getattr(cli, m))}")
            except Exception:
                print(f"Method: {m} (Could not get signature)")
    else:
        print("ClientV2 NOT FOUND")

if __name__ == "__main__":
    inspect_client()
