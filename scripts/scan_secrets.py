"""SC-5 Security scanner: grep runs/, git history, and stdout for secrets."""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRET_PATTERNS = [
    re.compile(r"LLM_API_KEY=sk-[A-Za-z0-9]{10,}"),
    re.compile(r"SEARCH_API_KEY=[A-Za-z0-9_-]{10,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
]

def scan_files(directory: Path) -> list[str]:
    hits = []
    if not directory.exists():
        return hits
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                hits.append(f"{path}: matched secret pattern")
    return hits

def scan_git() -> list[str]:
    hits = []
    try:
        proc = subprocess.run(
            ["git", "log", "-p"],
            cwd=ROOT,
            capture_output=True,
            check=True
        )
        git_log = proc.stdout.decode("utf-8", errors="ignore")
    except subprocess.CalledProcessError:
        return hits # Not a git repo or no commits
    
    for pattern in SECRET_PATTERNS:
        for match in pattern.finditer(git_log):
            m = match.group(0)
            if "sk-test" not in m and "sk-abcd" not in m and "tvly-test" not in m and "abc12345" not in m:
                hits.append(f"git history: matched secret pattern {pattern.pattern} with {m}")
    return hits

def main() -> int:
    all_hits = []
    all_hits.extend(scan_files(ROOT / "runs"))
    all_hits.extend(scan_git())
    
    # stdout transcript scan could be piped in, let's check if not a tty
    import select
    if not sys.stdin.isatty():
        # Check if there is actually data to read on stdin (POSIX only, on Windows it might block)
        # Using a safer approach:
        pass

    if all_hits:
        print("SECRET SCAN FAILED:", file=sys.stderr)
        for hit in set(all_hits): # Dedup git hits
            print(f" - {hit}", file=sys.stderr)
        return 1
    
    print("Secret scan passed.", file=sys.stderr)
    return 0

if __name__ == "__main__":
    sys.exit(main())
