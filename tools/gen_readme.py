from __future__ import annotations
import pathlib

def main():
    draft = pathlib.Path(".sisyphus/drafts/README-content.md")
    readme = pathlib.Path("README.md")
    if draft.exists():
        content = draft.read_text(encoding="utf-8")
        readme.write_text(content, encoding="utf-8")
        print(f"Wrote README.md from {draft}")
    else:
        print("Draft README-content.md not found; no action taken.")

if __name__ == "__main__":
    main()
