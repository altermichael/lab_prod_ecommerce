#!/usr/bin/env python3
"""verify.py — Deployment lab self-check.

    python verify.py                         # checks 1-7 (local prod stack)
    python verify.py https://you.onrender.com  # also runs check 8 (live URL)

"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

COMPOSE_FILE = "compose.prod.yaml"

if os.name == "nt":
    os.system("")

USE_COLOR = sys.stdout.isatty()
GREEN  = "\033[0;32m" if USE_COLOR else ""
RED    = "\033[0;31m" if USE_COLOR else ""
GRAY   = "\033[0;90m" if USE_COLOR else ""
YELLOW = "\033[0;33m" if USE_COLOR else ""
NC     = "\033[0m"    if USE_COLOR else ""

ok = 0
fail = 0
skip = 0


def step(n, total, desc):
    print(f"[{n}/{total}] {desc:<52} ", end="", flush=True)


def pass_(extra=""):
    global ok
    print(f"{GREEN}OK{NC}" + (f" ({extra})" if extra else ""))
    ok += 1


def fail_(msg):
    global fail
    print(f"{RED}FAIL{NC}  {msg}")
    fail += 1


def skip_(msg):
    global skip
    print(f"{GRAY}SKIP{NC}  {msg}")
    skip += 1


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def dc(*args):
    """docker compose -f compose.prod.yaml ..."""
    return run(["docker", "compose", "-f", COMPOSE_FILE, *args])


def http_get(url, timeout=10):
    """Return (status, body) or (None, error_string)."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as e:
        return None, str(e)


# ── Prerequisites ──────────────────────────────────────────────────────────
def check_prereqs():
    if shutil.which("docker") is None:
        print(f"{RED}Docker is not installed or not in PATH.{NC}")
        sys.exit(2)
    if run(["docker", "compose", "version"]).returncode != 0:
        print(f"{RED}Docker Compose v2 not available.{NC}")
        sys.exit(2)
    if not os.path.isfile(COMPOSE_FILE):
        print(f"{YELLOW}No {COMPOSE_FILE} found — most checks will fail.{NC}")
    if not os.path.isfile("Dockerfile"):
        print(f"{YELLOW}No Dockerfile found — all checks will fail.{NC}")


# ── 1. Multi-stage build ───────────────────────────────────────────────────
def check_build():
    step(1, 8, "multi-stage image builds")
    if dc("build").returncode == 0:
        pass_()
        return True
    fail_(f"build failed (run 'docker compose -f {COMPOSE_FILE} build')")
    return False


# ── 2. Image size < 250 MB ─────────────────────────────────────────────────
def check_size(prev_ok):
    step(2, 8, "image size under 250 MB")
    if not prev_ok:
        skip_("skipped (build failed)")
        return
    r = dc("images", "web", "--quiet")
    image_id = r.stdout.strip().splitlines()[0] if r.stdout.strip() else ""
    if not image_id:
        # Fallback: the stack may not be 'up' yet. Compose tags the built
        # image as <project>-web; project defaults to the sanitized dir name.
        proj = re.sub(r"[^a-z0-9_-]", "", os.path.basename(os.getcwd()).lower())
        imgs = run(["docker", "images", "--format", "{{.Repository}} {{.ID}}"])
        exact, anyweb = "", ""
        for line in imgs.stdout.splitlines():
            parts = line.split()
            if len(parts) != 2:
                continue
            repo, iid = parts
            if repo == f"{proj}-web":
                exact = iid
                break
            if repo.endswith("-web"):
                anyweb = iid
        image_id = exact or anyweb
    if not image_id:
        skip_("couldn't find web image")
        return
    insp = run(["docker", "image", "inspect", image_id, "--format", "{{.Size}}"])
    try:
        size_mb = int(insp.stdout.strip()) // (1024 * 1024)
    except ValueError:
        skip_("couldn't read image size")
        return
    if size_mb < 250:
        pass_(f"{size_mb} MB")
    else:
        fail_(f"image is {size_mb} MB — is this a multi-stage build?")


# ── 3. Stack up: web + nginx + db ──────────────────────────────────────────
def check_up(prev_ok):
    step(3, 8, "stack up (web + nginx + db)")
    if not prev_ok:
        skip_("skipped (build failed)")
        return False
    if dc("up", "-d").returncode != 0:
        fail_(f"up failed (check 'docker compose -f {COMPOSE_FILE} logs')")
        return False
    # wait for db healthy + nginx reachable
    for _ in range(40):
        ps = dc("ps", "--format", "json")
        services = set()
        healthy_db = False
        if ps.returncode == 0 and ps.stdout.strip():
            text = ps.stdout.strip()
            try:
                parsed = json.loads(text)
                entries = parsed if isinstance(parsed, list) else [parsed]
            except json.JSONDecodeError:
                entries = []
                for line in text.splitlines():
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
            for e in entries:
                services.add(e.get("Service"))
                if e.get("Service") == "db" and e.get("Health") == "healthy":
                    healthy_db = True
        if {"web", "nginx", "db"}.issubset(services) and healthy_db:
            # Prep the DB so the API/static/audit checks are meaningful.
            # migrations are baked into the image at build (as root); at
            # runtime we only migrate + load data (DB-only, fine as non-root).
            mg = dc("exec", "-T", "web", "python", "manage.py",
                    "migrate", "--noinput")
            if mg.returncode != 0:
                fail_("migrate failed — are migrations baked into the image?")
                return False
            dc("exec", "-T", "web", "python", "manage.py", "load_db")
            pass_()
            return True
        time.sleep(1)
    fail_("web/nginx/db not all up+healthy in 40s")
    return False


# ── 4. API 200 through Nginx ───────────────────────────────────────────────
def check_api(prev_ok):
    step(4, 8, "GET /api/products/ through Nginx → 200")
    if not prev_ok:
        skip_("skipped (stack not up)")
        return
    time.sleep(2)
    status, body = http_get("http://localhost/api/products/")
    if status == 200:
        pass_()
    elif status is None:
        fail_(f"connection failed ({body}) — is Nginx on port 80?")
    else:
        fail_(f"HTTP {status} (Nginx → Gunicorn → Django path broken?)")


# ── 5. DEBUG=False (no traceback leak) ─────────────────────────────────────
def check_debug_off(prev_ok):
    step(5, 8, "DEBUG=False (no debug leak)")
    if not prev_ok:
        skip_("skipped (stack not up)")
        return
    status, body = http_get("http://localhost/this-path-does-not-exist-xyz/")
    leak_markers = ("Using the URLconf defined in", "Traceback (most recent call last)",
                    "Django tried these URL patterns")
    if any(m in body for m in leak_markers):
        fail_("debug page leaked — set DJANGO_DEBUG=0 / DEBUG=False")
    elif status in (404, 400):
        pass_()
    else:
        # Some setups return 200 generic page; accept as long as no leak
        pass_()


# ── 6. Static served through the stack ─────────────────────────────────────
def check_static(prev_ok):
    step(6, 8, "static served (admin CSS → 200)")
    if not prev_ok:
        skip_("skipped (stack not up)")
        return
    status, _ = http_get("http://localhost/static/admin/css/base.css")
    if status == 200:
        pass_()
    else:
        fail_(f"static returned {status} — WhiteNoise + collectstatic done?")


# ── 7. check --deploy clean ────────────────────────────────────────────────
def check_deploy_audit(prev_ok):
    step(7, 8, "manage.py check --deploy clean")
    if not prev_ok:
        skip_("skipped (stack not up)")
        return
    r = dc("exec", "-T", "web", "python", "manage.py", "check", "--deploy")
    out = (r.stdout or "") + (r.stderr or "")
    # The critical ones that mean an unsafe deploy (HSTS/SSL-redirect are
    # handled by the platform edge and are not required for this lab).
    critical = ("W018",  # DEBUG = True
                "W020",  # ALLOWED_HOSTS empty
                "W009")  # SECRET_KEY insecure / default
    hits = [c for c in critical if c in out]
    if hits:
        fail_(f"critical issues still present: {', '.join(hits)}")
    else:
        pass_()


# ── 8. Live Render URL (GRADED) ────────────────────────────────────────────
def check_live(url):
    step(8, 8, "live HTTPS URL → 200")
    if not url:
        fail_("no URL given — run: python verify.py https://your-app.onrender.com")
        return
    if not url.startswith("https://"):
        fail_("URL must be https:// (Render gives you HTTPS automatically)")
        return
    target = url.rstrip("/") + "/api/products/"
    # free tier cold-start: retry a few times with patience
    for attempt in range(4):
        status, body = http_get(target, timeout=40)
        if status == 200:
            pass_("live")
            return
        time.sleep(5)
    if status is None:
        fail_(f"could not reach {target} ({body})")
    else:
        fail_(f"{target} returned HTTP {status}")


# ── Main ───────────────────────────────────────────────────────────────────
def main():
    live_url = sys.argv[1] if len(sys.argv) > 1 else ""
    check_prereqs()
    print()

    built = check_build()
    check_size(built)
    up = check_up(built)
    check_api(up)
    check_debug_off(up)
    check_static(up)
    check_deploy_audit(up)
    check_live(live_url)

    print()
    print("--------------------------------------------------------------")
    if ok == 8:
        print(f"{GREEN}Result: {ok}/8 OK — deployment lab complete!{NC}")
        sys.exit(0)
    print(f"Result: {GREEN}{ok} OK{NC}  {RED}{fail} FAIL{NC}  {GRAY}{skip} skipped{NC}")
    if not live_url:
        print(f"{YELLOW}Tip:{NC} check 8 is graded — re-run with your live URL:")
        print("     python verify.py https://your-app.onrender.com")
    print("Re-run after each fix: python verify.py [live-url]")
    sys.exit(1)


if __name__ == "__main__":
    main()
