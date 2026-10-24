"""Terminal version of the agent, handy for quick tests.

Run:  python cli.py
"""
from dotenv import load_dotenv

from agent import has_api_key, run_agent

load_dotenv()


def main() -> None:
    if not has_api_key():
        print("Chat needs an Anthropic API key (paid) in .env. For the free version run: streamlit run app.py")
        return
    print("BTO Affordability Agent. Type 'quit' to exit.\n")
    messages: list = []
    while True:
        try:
            user = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if user.lower() in {"quit", "exit"}:
            break
        if not user:
            continue
        messages.append({"role": "user", "content": user})
        turn = run_agent(messages)
        for c in turn.tool_calls:
            print(f"  [tool] {c.name}({', '.join(f'{k}={v}' for k, v in c.input.items())})")
        print(f"\nAgent: {turn.text}\n")


if __name__ == "__main__":
    main()
