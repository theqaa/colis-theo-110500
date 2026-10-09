"""Version cloud : une vérification par exécution, notif push via ntfy.sh."""
import difflib
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://134.175.244.145:8082/trackIndex.htm"
NUMBER = os.environ["TRACK_NUMBER"]
TOPIC = os.environ["NTFY_TOPIC"]
STATE = Path(__file__).with_name("last_state.txt")


def notify(title: str, message: str) -> None:
    print(f"[NOTIF] {title}: {message}")
    req = urllib.request.Request(
        f"https://ntfy.sh/{TOPIC}",
        data=message[:900].encode("utf-8"),
        headers={"Title": title},
    )
    urllib.request.urlopen(req, timeout=30)


def fetch_lines(page) -> list[str]:
    page.goto(URL, wait_until="networkidle", timeout=90_000)
    box = page.locator("input[type=text], input:not([type]), textarea").first
    box.fill(NUMBER)
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


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        lines = fetch_lines(browser.new_page())
        browser.close()

    new = "\n".join(lines)
    if not STATE.exists():
        STATE.write_text(new, encoding="utf-8")
        notify("Suivi colis", "Surveillance démarrée")
        return

    old = STATE.read_text(encoding="utf-8")
    if new != old:
        added = [d[2:] for d in difflib.ndiff(old.splitlines(), lines) if d.startswith("+ ")]
        STATE.write_text(new, encoding="utf-8")
        notify("Suivi colis mis a jour", " | ".join(added) or "Contenu modifie")
    else:
        print("Aucun changement")


if __name__ == "__main__":
    main()
