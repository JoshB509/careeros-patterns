"""Safety gate: run before every push. Exits 1 if anything that looks private would be published.

    python tools/check_public.py

It checks every file git would publish (tracked and untracked, minus .gitignore) for:
- keys, tokens, passwords and private keys
- email addresses, other than example and test ones
- Windows and home-folder paths that reveal a machine (C:\\Users\\..., E:\\...)
- any term listed in tools/private-terms.txt (one per line). That file is ignored by git, so the private list itself
  is never published. Put customer names, business figures, private hostnames and anything else to keep out.
- files over 5 MB
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BINARY = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.ico', '.woff', '.woff2', '.tflite', '.mp4', '.pdf'}
SECRET = re.compile(r'(sk-ant-[A-Za-z0-9_-]{10,}|sk-[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|xox[bap]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{30,}'
                    r'|-----BEGIN [A-Z ]*PRIVATE KEY|[MN][A-Za-z0-9_-]{23,25}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27,}'
                    r'|(?:client_secret|refresh_token|api_key|password|token)["\']?\s*[:=]\s*["\'][^"\']{8,})', re.I)
EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
ALLOWED_EMAIL = re.compile(r'@(example\.(com|org|net|test)|test|localhost|users\.noreply\.github\.com)$', re.I)
PATHS = re.compile(r'([A-Za-z]:\\\\?Users\\(?!\\?you\\)|/home/(?!claude/)[a-z]|/Users/[A-Za-z])')


def files():
    out = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=ROOT, capture_output=True, text=True, check=True)
    return [ROOT / f for f in out.stdout.splitlines() if f]


def main():
    terms_file = ROOT / 'tools' / 'private-terms.txt'
    terms = [t.strip() for t in terms_file.read_text(encoding='utf-8').splitlines() if t.strip() and not t.startswith('#')] if terms_file.exists() else []
    problems = []
    for f in files():
        rel = f.relative_to(ROOT).as_posix()
        if rel == 'tools/check_public.py':
            continue
        if f.stat().st_size > 5 * 1024 * 1024:
            problems.append(f'{rel}: larger than 5 MB')
        if f.suffix.lower() in BINARY:
            continue
        text = f.read_text(encoding='utf-8', errors='replace')
        for n, line in enumerate(text.splitlines(), 1):
            if SECRET.search(line):
                problems.append(f'{rel}:{n}: looks like a key, token or password')
            for m in EMAIL.findall(line):
                if not ALLOWED_EMAIL.search(m):
                    problems.append(f'{rel}:{n}: email address {m}')
            if PATHS.search(line):
                problems.append(f'{rel}:{n}: a home-folder path')
            low = line.lower()
            for t in terms:
                if t.lower() in low:
                    problems.append(f'{rel}:{n}: private term from private-terms.txt')
    if problems:
        print('Not safe to publish:')
        print('\n'.join('  ' + p for p in problems))
        return 1
    print(f'Safe to publish: {len(files())} files checked, {len(terms)} private terms.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
