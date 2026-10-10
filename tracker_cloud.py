"""Version cloud multi-colis : une verification par execution, notif push via ntfy.sh."""
import difflib
import os
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

TOPIC = os.environ["NTFY_TOPIC"]
HERE = Path(__file__).parent

# (libelle, url, variable secrete du numero, fichier d'etat)
JOBS = [
    ("Colis 1", "http://134.175.244.145:8082/trackIndex.htm", "TRACK_NUMBER", "last_state.txt"),
    ("Colis 2", "http://120.78.2.65:8082/trackIndex.htm", "TRACK_NUMBER_2", "last_state_2.txt"),
]


def notify(title: str, message: str) -> None:
    print(f"[NOTIF] {title}: {message}")
    req = urllib.request.Request(
        f"https://ntfy.sh/{TOPIC}",
        data=message[:900].encode("utf-8"),
        headers={"Title": title},
    )
    urllib.request.urlopen(req, timeout=30)


def fetch_lines(page, url: str, number: str) -> list[str]:
    page.goto(url, wait_until="networkidle", timeout=90_000)
    box = page.locator("input[type=text], input:not([type]), textarea").first
    box.fill(number)
    btn = page.locator(
        "input[type=submit], input[type=button], button, "
        "a:has-text('Search'), a:has-text('Track'), a:has-text('Query'), a:has-text('查询')"
    )
    if btn.count():
        btn.first.click()
    else:
        box.press("Enter")
    page.wait_for_load_state("networkidle", timeout=90_000)
    page.wait_for_timeout(3000)
    text = page.inner_text("body")
    return [l.strip() for l in text.splitlines() if l.strip()]


def check(browser, label: str, url: str, number: str, state_file: Path) -> None:
    page = browser.new_page()
    try:
        lines = fetch_lines(page, url, number)
    finally:
        page.close()

    new = "\n".join(lines)
    if not state_file.exists():
        state_file.write_text(new, encoding="utf-8")
        notify(f"Suivi {label}", "Surveillance demarree")
        return

    old = state_file.read_text(encoding="utf-8")
    if new != old:
        added = [d[2:] for d in difflib.ndiff(old.splitlines(), lines) if d.startswith("+ ")]
        state_file.write_text(new, encoding="utf-8")
        notify(f"Suivi {label} mis a jour", " | ".join(added) or "Contenu modifie")
    else:
        print(f"{label}: aucun changement")


def main() -> None:
    failed = False
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for label, url, env_var, state_name in JOBS:
            number = os.environ.get(env_var, "").strip()
            if not number:
                print(f"{label}: secret {env_var} absent, ignore")
                continue
            try:
                check(browser, label, url, number, HERE / state_name)
            except Exception as e:
                failed = True
                print(f"{label}: erreur: {e}")
        browser.close()
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
