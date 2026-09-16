import os
import re
import sys
from pathlib import Path


def read_version_from_pyproject() -> str:
    text = Path("pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        raise SystemExit("Could not find version in pyproject.toml")
    return m.group(1)


def normalize_tag(ref: str) -> str | None:
    prefix = "refs/tags/"
    if not ref.startswith(prefix):
        return None
    return ref[len(prefix) :]


def main() -> int:
    ref = os.environ.get("GITHUB_REF", "")
    tag = normalize_tag(ref)
    if tag is None:
        print("No tag ref detected; skipping tag/version consistency check.")
        return 0

    version = read_version_from_pyproject()
    expected = f"v{version}"
    if tag != expected:
        print(f"Error: tag '{tag}' does not match pyproject version '{version}' (expected '{expected}').")
        return 1

    print(f"OK: tag '{tag}' matches pyproject version '{version}'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
