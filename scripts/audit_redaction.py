from __future__ import annotations

import argparse
import collections
import re
import sys
from pathlib import Path


TEXT_SUFFIXES = {
    "",
    ".c", ".cc", ".cfg", ".cmd", ".conf", ".cpp", ".css", ".csv",
    ".h", ".hpp", ".html", ".ini", ".js", ".json", ".jsx", ".md",
    ".mjs", ".ps1", ".py", ".rst", ".scss", ".sh", ".svg", ".toml",
    ".ts", ".tsx", ".txt", ".xml", ".yaml", ".yml",
}

BLOCKING_PATTERNS = {
    "original-user-home": re.compile(r"C:[\\/]+Users[\\/]+17937", re.IGNORECASE),
    "original-username": re.compile(r"(?<![A-Za-z0-9])17937(?![A-Za-z0-9])"),
    "github-owner": re.compile(r"(?<![A-Za-z0-9])Alooswr(?![A-Za-z0-9])", re.IGNORECASE),
    "openai-style-key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "github-token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    "aws-access-key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "google-api-key": re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    "slack-token": re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b"),
    "url-userinfo": re.compile(r"https?://[^\s/@:]+:[^\s/@]+@", re.IGNORECASE),
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "real-supabase-ref": re.compile(r"https://(?!<PROJECT_REF>)[a-z0-9]{12,}\.supabase\.co", re.IGNORECASE),
}

REVIEW_PATTERNS = {
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    "uuid": re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b", re.IGNORECASE),
    "private-ipv4": re.compile(r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b"),
    "serial-port": re.compile(r"\bCOM\d+\b", re.IGNORECASE),
    "long-decimal-id": re.compile(r"(?<!\d)\d{15,}(?!\d)"),
}

FORBIDDEN_NAMES = {
    ".env", "auth.json", "credentials.json", "id_rsa", "id_ed25519",
    "config.toml", "hooks.json", "devices.local.json",
}

FORBIDDEN_SUFFIXES = {".db", ".sqlite", ".pyc", ".pyo", ".pyd", ".log"}


def iter_text_files(root: Path):
    this_script = Path(__file__).resolve()
    for path in root.rglob("*"):
        if ".git" in path.parts:
            continue
        if path.is_symlink():
            yield "symlink", path, None
            continue
        if not path.is_file():
            continue
        lowered = path.name.lower()
        if lowered in FORBIDDEN_NAMES or path.suffix.lower() in FORBIDDEN_SUFFIXES:
            yield "forbidden-file", path, None
            continue
        if path.resolve() == this_script or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        yield "text", path, text


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a sanitized Codex snapshot without printing matched values.")
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--strict-review", action="store_true", help="Fail when review-only patterns are present.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    blockers: list[tuple[str, str, int | None]] = []
    reviews: dict[str, list[tuple[str, int]]] = collections.defaultdict(list)

    for kind, path, text in iter_text_files(root):
        relative = path.relative_to(root).as_posix()
        if kind != "text":
            blockers.append((kind, relative, None))
            continue
        assert text is not None
        for rule, pattern in BLOCKING_PATTERNS.items():
            for match in pattern.finditer(text):
                blockers.append((rule, relative, line_number(text, match.start())))
        for rule, pattern in REVIEW_PATTERNS.items():
            for match in pattern.finditer(text):
                reviews[rule].append((relative, line_number(text, match.start())))

    if blockers:
        print(f"BLOCKING findings: {len(blockers)}")
        for rule, relative, line in blockers:
            location = f"{relative}:{line}" if line else relative
            print(f"- {rule}: {location}")
    else:
        print("BLOCKING findings: 0")

    review_count = sum(len(items) for items in reviews.values())
    print(f"REVIEW findings: {review_count}")
    for rule in sorted(reviews):
        items = reviews[rule]
        files = sorted({relative for relative, _ in items})
        preview = ", ".join(files[:8])
        suffix = " ..." if len(files) > 8 else ""
        print(f"- {rule}: {len(items)} matches in {len(files)} files [{preview}{suffix}]")

    if blockers or (args.strict_review and review_count):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
