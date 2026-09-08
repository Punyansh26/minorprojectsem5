#!/usr/bin/env python
"""Drive the Kisan Saathi demo headlessly: MCP tools, the Streamlit script, or a real browser.

Layers, cheapest first:
  tool     one MCP stdio call against a throwaway JSON store (no browser, no API key)
  apptest  the whole app.py script through streamlit.testing.v1 (no browser)
  flow     real `streamlit run` + headless Chromium over CDP, with screenshots
  repl     line-oriented browser control for exploring the running UI

Requires the Conda `minor` interpreter; it needs streamlit, mcp and websockets.
Runtime artifacts (log, throwaway JSON, Chromium profile, screenshots) stay in
$KISAN_RUN_DIR (default /tmp/kisan-demo-run), never in the repository.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEMO = HERE.parents[2]
RUN = Path(os.environ.get("KISAN_RUN_DIR", "/tmp/kisan-demo-run"))
SHOTS = RUN / "screenshots"
DB = RUN / "driver-shop.json"
LOG = RUN / "streamlit.log"
CHROMIUM = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")

def free_port() -> int:
    """Pick a port the kernel says is free so a human's demo on 8501 keeps running."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_http(url: str, timeout: float = 90.0) -> str:
    """Poll an endpoint instead of sleeping a guessed number of seconds."""
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status == 200:
                    return response.read().decode()
        except Exception as exc:  # connection refused until the server binds
            last = type(exc).__name__
        time.sleep(0.3)
    raise SystemExit(f"timed out waiting for {url} ({last}); see {LOG}")


def demo_python() -> None:
    """Fail loudly on the wrong interpreter rather than mid-flow with an ImportError."""
    sys.path.insert(0, str(DEMO))
    missing = [name for name in ("streamlit", "mcp", "websockets")
               if __import__("importlib.util", fromlist=["util"]).find_spec(name) is None]
    if missing:
        raise SystemExit("missing " + ", ".join(missing) + " — run this with the Conda "
                         "minor interpreter, e.g. /home/rtx/miniconda3/envs/minor/bin/python")


class Server:
    """Own one `streamlit run` process bound to localhost with a throwaway JSON store."""

    def __init__(self, port: int | None = None, db: Path = DB, fresh: bool = True):
        self.port = port or free_port()
        self.db = db
        self.fresh = fresh
        self.proc: subprocess.Popen | None = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> "Server":
        """Launch headless so Streamlit never waits on the e-mail prompt or a browser."""
        RUN.mkdir(parents=True, exist_ok=True)
        if self.fresh and self.db.exists():
            self.db.unlink()  # a confirmed demo order decrements stock permanently
        env = {**os.environ, "DEMO_STATE_PATH": str(self.db)}
        self.log = LOG.open("wb")
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "app.py",
             "--server.address", "127.0.0.1", "--server.port", str(self.port),
             "--server.headless", "true", "--browser.gatherUsageStats", "false",
             "--server.fileWatcherType", "none"],
            cwd=DEMO, env=env, stdout=self.log, stderr=subprocess.STDOUT)
        wait_http(self.url + "/_stcore/health")
        return self

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if getattr(self, "log", None):
            self.log.close()


class Browser:
    """Speak CDP to a headless Chromium directly; no Playwright/Selenium install needed."""

    def __init__(self, width: int = 1500, height: int = 1200):
        binary = next((shutil.which(name) for name in CHROMIUM if shutil.which(name)), None)
        if not binary:
            raise SystemExit("no Chromium found; install one of " + ", ".join(CHROMIUM))
        port = free_port()
        profile = RUN / "chromium-profile"
        profile.mkdir(parents=True, exist_ok=True)
        self.proc = subprocess.Popen(
            [binary, "--headless=new", f"--remote-debugging-port={port}",
             f"--user-data-dir={profile}", "--remote-allow-origins=*", "--no-first-run",
             "--no-default-browser-check", "--disable-gpu", "--hide-scrollbars",
             "--disable-dev-shm-usage", f"--window-size={width},{height}", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=(RUN / "chromium.log").open("wb"))
        wait_http(f"http://127.0.0.1:{port}/json/version", timeout=30)
        targets = json.loads(wait_http(f"http://127.0.0.1:{port}/json/list", timeout=30))
        page = next(t for t in targets if t["type"] == "page")
        from websockets.sync.client import connect
        self.ws = connect(page["webSocketDebuggerUrl"], max_size=None, open_timeout=20)
        self.counter = 0
        self.current_tab = ""
        self.send("Page.enable")
        self.send("Runtime.enable")

    def send(self, method: str, **params):
        """Match replies by id because CDP interleaves events with command results."""
        self.counter += 1
        self.ws.send(json.dumps({"id": self.counter, "method": method, "params": params}))
        deadline = time.time() + 60
        while time.time() < deadline:
            frame = json.loads(self.ws.recv(timeout=max(1.0, deadline - time.time())))
            if frame.get("id") == self.counter:
                if "error" in frame:
                    raise RuntimeError(f"{method}: {frame['error']}")
                return frame.get("result", {})
        raise RuntimeError(f"{method}: no CDP reply")


    def js(self, expression: str):
        """Evaluate in the page and return a plain value, raising page exceptions."""
        result = self.send("Runtime.evaluate", expression=expression, returnByValue=True,
                           awaitPromise=True, userGesture=True)
        if result.get("exceptionDetails"):
            raise RuntimeError(result["exceptionDetails"].get("text", "page exception"))
        return result.get("result", {}).get("value")

    def open(self, url: str) -> None:
        """Navigate, then wait for Streamlit's first script run to finish."""
        self.send("Page.navigate", url=url)
        self.wait(lambda: self.js("!!document.querySelector('[data-testid=\"stAppViewContainer\"]')"))
        self.idle()

    def wait(self, predicate, timeout: float = 60.0, label: str = "condition") -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if predicate():
                    return
            except RuntimeError:
                pass  # navigation can destroy the execution context mid-poll
            time.sleep(0.25)
        raise RuntimeError(f"timed out waiting for {label}")

    def idle(self, quiet: int = 3) -> None:
        """Wait for the running indicator to stay gone; Streamlit reruns the whole script."""
        seen = 0
        deadline = time.time() + 90
        while time.time() < deadline:
            busy = self.js("!!document.querySelector('[data-testid=\"stStatusWidget\"]')")
            seen = 0 if busy else seen + 1
            if seen >= quiet:
                return
            time.sleep(0.2)
        raise RuntimeError("Streamlit never went idle")


    def shot(self, name: str, full: bool = True) -> Path:
        """Save a PNG and report its size/colour spread so a blank page is obvious."""
        SHOTS.mkdir(parents=True, exist_ok=True)
        data = self.send("Page.captureScreenshot", format="png", captureBeyondViewport=full)
        path = SHOTS / (name if name.endswith(".png") else name + ".png")
        path.write_bytes(base64.b64decode(data["data"]))
        note = ""
        try:
            from PIL import Image
            with Image.open(path) as image:
                colours = image.convert("RGB").getcolors(maxcolors=1 << 20)
                note = f" {image.width}x{image.height} colours={len(colours) if colours else '>1M'}"
        except Exception:
            pass
        print(f"shot {path}{note}", flush=True)
        return path

    def click(self, text: str) -> None:
        """Click a button/tab by visible label, then put the selected tab back."""
        self._click(text)
        self.restore_tab()

    def _click(self, text: str) -> None:
        if not self.js(FIND_CLICK % json.dumps(text)):
            raise RuntimeError(f"no enabled clickable element matching {text!r}; try `labels`")
        self.idle()

    def tab(self, name: str) -> None:
        """Select a tab and remember it: every st.rerun() snaps back to the first tab."""
        self.current_tab = name
        self._click(name)

    def restore_tab(self) -> None:
        if self.current_tab and self.current_tab not in self.active_tab():
            self._click(self.current_tab)

    def active_tab(self) -> str:
        return (self.js("(document.querySelector('[role=\"tab\"][aria-selected=\"true\"]')"
                        " || {}).innerText") or "").strip()

    def expander(self, text: str) -> None:
        """Open a collapsed expander; its children are absent from the DOM until then."""
        self.js(OPEN_EXPANDER % json.dumps(text))

    def click_key(self, key: str) -> None:
        """Click a widget by its Streamlit `key=`, which lands as an st-key- class."""
        hit = self.js("(() => { const e = document.querySelector('.st-key-%s button');"
                      " if (!e) return false; e.scrollIntoView(); e.click(); return true; })()" % key)
        if not hit:
            raise RuntimeError(f"no widget with key {key!r}")
        self.idle()
        self.restore_tab()

    def text(self) -> str:
        return self.js("document.querySelector('[data-testid=\"stAppViewContainer\"]').innerText")

    def labels(self) -> list:
        return self.js("[...document.querySelectorAll('button,[role=tab]')]"
                       ".map(e => e.innerText.trim()).filter(Boolean)")

    def fill(self, label: str, value: str, commit: str = "enter") -> None:
        """Type with real key events; assigning .value leaves React's state untouched."""
        if not self.js(FOCUS_INPUT % json.dumps(label)):
            raise RuntimeError(f"no input labelled {label!r}")
        self.send("Input.insertText", text=value)
        if commit == "enter":
            for kind in ("keyDown", "keyUp"):
                self.send("Input.dispatchKeyEvent", type=kind, key="Enter", code="Enter",
                          windowsVirtualKeyCode=13, nativeVirtualKeyCode=13, text="\r")
        else:
            self.js("document.activeElement.blur()")
        self.idle()
        self.restore_tab()

    def close(self) -> None:
        try:
            self.send("Browser.close")
        except Exception:
            self.proc.terminate()
        try:
            self.ws.close()
        except Exception:
            pass


FIND_CLICK = """(() => {
  const want = %s;
  const els = [...document.querySelectorAll('button,[role="tab"]')];
  const el = els.find(e => e.innerText.trim() === want) || els.find(e => e.innerText.includes(want));
  if (!el || el.disabled) return false;
  el.scrollIntoView({block: 'center'});
  el.click();
  return true;
})()"""

FOCUS_INPUT = """(() => {
  const want = %s;
  const els = [...document.querySelectorAll('input,textarea')];
  const el = els.find(e => (e.getAttribute('aria-label') || '').includes(want))
          || els.find(e => (e.closest('[data-testid="stElementContainer"]')?.innerText || '').includes(want));
  if (!el) return false;
  el.scrollIntoView({block: 'center'});
  el.focus();
  el.select();
  return true;
})()"""

OPEN_EXPANDER = """(() => {
  const want = %s;
  const el = [...document.querySelectorAll('summary,[data-testid="stExpander"] > div')]
    .find(e => e.innerText.includes(want));
  if (!el) return false;
  const details = el.closest('details');
  if (details && !details.open) el.click();
  else if (!details && el.getAttribute('aria-expanded') === 'false') el.click();
  return true;
})()"""


def cmd_tool(args) -> int:
    """Call one MCP tool over real stdio transport, bypassing browser and model."""
    demo_python()
    os.environ["DEMO_STATE_PATH"] = str(args.db)
    from mcp_client import direct, inspect_server
    if args.name == "@discover":
        report = inspect_server("driver", "discover", state_path=args.db)
        report["tools"] = [t["name"] for t in report["tools"]]
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    output, traces = direct("driver", args.turn, args.name, json.loads(args.arguments),
                            state_path=args.db, confirmation_token=args.token)
    print(json.dumps({"output": output, "traces": traces}, ensure_ascii=False, indent=2))
    return 0 if output.get("ok") else 1


def cmd_apptest(args) -> int:
    """Run the whole app.py script headlessly; fastest check that the UI wiring works."""
    demo_python()
    os.environ["DEMO_STATE_PATH"] = str(args.db)
    if args.db.exists():
        args.db.unlink()
    os.chdir(DEMO)
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(str(DEMO / "app.py"), default_timeout=60).run()
    steps = {"launched": not app.exception, "connected": "Connected" in app.success[0].value,
             "tools": len(app.session_state["discovery"]["tools"])}
    app.button(key="add_SEED01").click().run()
    app.button(key="add_SEED01").click().run()
    steps["cart_paise"] = app.session_state["discovery"]["cart"]["total_paise"]
    next(b for b in app.button if b.label.endswith("Checkout")).click().run()
    steps["preview"] = bool(app.session_state["preview"])
    app.button(key="confirm_shop").click().run()
    steps["order"] = any("DEMO-" in m["content"] for m in app.session_state["messages"])
    steps["cart_cleared"] = app.session_state["discovery"]["cart"]["items"] == []
    steps["no_exception"] = not app.exception
    print(json.dumps(steps, ensure_ascii=False, indent=2))
    return 0 if steps["cart_paise"] == 90000 and steps["order"] and steps["cart_cleared"] else 1


def cmd_flow(args) -> int:
    """Do the presentation walkthrough in a real browser and screenshot every stage."""
    demo_python()
    server = Server(args.port, args.db).start()
    print(f"serving {server.url} (db {args.db}, log {LOG})", flush=True)
    page = Browser()
    checks: dict = {}
    try:
        page.open(server.url)
        page.shot("01-talk-tab")
        page.tab("MCP proof / Developer")
        body = page.text()
        checks["mcp_connected"] = "Connected: Farmer Shopping Demo" in body
        checks["protocol"] = "MCP 2025-06-18" in body
        checks["twelve_tools"] = "Discovered tools (12)" in body
        page.shot("02-mcp-proof")
        page.tab("सामान और टोकरी / Shop")
        page.fill("खोजें / Search", "धान")
        page.click("खोजें / Find")
        page.shot("03-search-dhaan")
        checks["search_found_paddy"] = "SEED01" in page.text()
        page.click_key("add_SEED01")
        page.click_key("add_SEED01")
        page.shot("04-cart-two-packs")
        checks["cart_total_900"] = "₹900.00" in page.text()
        page.click("डेमो चेकआउट / Checkout")
        page.shot("05-checkout-preview")
        checks["preview_shown"] = "पुष्टि / Confirm demo order" in page.labels()
        page.click_key("confirm_shop")
        body = page.text()
        checks["order_created"] = "DEMO-" in body
        checks["cart_cleared"] = "टोकरी खाली है" in body
        page.shot("06-order-confirmed")
        checks.update(talk_turn(page, args.key) if args.key else {"talk_turn": "skipped (no --key)"})
    finally:
        page.shot("99-final")
        if not args.keep:
            page.close()
            server.stop()
        else:
            print(f"left running: {server.url}", flush=True)
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if all(v is True or v == "skipped (no --key)" for v in checks.values()) else 1


def talk_turn(page: "Browser", key: str) -> dict:
    """Drive one Groq-routed turn; the Send button stays disabled without a key."""
    if "Groq key loaded from server configuration." not in page.text():
        page.fill("Groq API key", key)
    page.tab("बातचीत / Talk")
    page.expander("या लिखें / Type instead")
    page.fill("आपकी बात / Your request", "मोला धान के बीज के दाम बतावव", commit="blur")
    page.click("भेजें / Send")
    body = page.text()
    page.shot("07-talk-price")
    return {"talk_replied": "₹" in body, "talk_no_error": "could not finish" not in body}


def cmd_repl(args) -> int:
    """Expose the browser as line commands so an agent can explore without new code."""
    demo_python()
    server = Server(args.port, args.db).start()
    page = Browser()
    page.open(server.url)
    print(f"ready {server.url}\ncommands: ss NAME | click TEXT | key KEY | fill LABEL=VALUE |"
          " blurfill LABEL=VALUE | text | labels | js EXPR | shots | quit", flush=True)
    try:
        for line in sys.stdin:
            verb, _, rest = line.strip().partition(" ")
            try:
                print(repl_step(page, verb, rest), flush=True)
            except StopIteration:
                break
            except Exception as exc:
                print(f"error {type(exc).__name__}: {exc}", flush=True)
    finally:
        page.close()
        server.stop()
    return 0


def repl_step(page: "Browser", verb: str, rest: str) -> str:
    """Map one REPL line onto the browser, returning whatever the agent should read."""
    if verb in {"quit", "exit", ""}:
        raise StopIteration
    if verb == "ss":
        return str(page.shot(rest or f"repl-{int(time.time())}"))
    if verb == "click":
        page.click(rest)
    elif verb == "key":
        page.click_key(rest)
    elif verb in {"fill", "blurfill"}:
        label, _, value = rest.partition("=")
        page.fill(label, value, commit="blur" if verb == "blurfill" else "enter")
    elif verb == "text":
        return page.text()
    elif verb == "labels":
        return json.dumps(page.labels(), ensure_ascii=False)
    elif verb == "js":
        return json.dumps(page.js(rest), ensure_ascii=False)
    elif verb == "shots":
        return str(SHOTS)
    else:
        return f"unknown command {verb!r}"
    return "ok"


def cmd_serve(args) -> int:
    """Hold a server open on a printed URL for a human browser or a separate driver."""
    demo_python()
    server = Server(args.port, args.db).start()
    print(f"{server.url}\ndb {args.db}\nlog {LOG}\nCtrl-C to stop", flush=True)
    try:
        server.proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
    return 0


def main() -> int:
    """Expose every layer as a subcommand so nothing needs an interactive terminal."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=DB,
                        help="throwaway JSON path; never the user's demo state")
    parser.add_argument("--port", type=int, default=None, help="default: a free port, not 8501")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("apptest", help="run app.py through streamlit.testing, no browser")
    flow = sub.add_parser("flow", help="real server + headless Chromium + screenshots")
    flow.add_argument("--key", default=os.getenv("GROQ_API_KEY", ""),
                      help="also drive one Groq Talk turn")
    flow.add_argument("--keep", action="store_true", help="leave the server running afterwards")
    sub.add_parser("repl", help="line-oriented browser control on stdin")
    sub.add_parser("serve", help="start the server and block")
    tool = sub.add_parser("tool", help="one MCP stdio call, or @discover")
    tool.add_argument("name")
    tool.add_argument("arguments", nargs="?", default="{}")
    tool.add_argument("--turn", default="driver-turn", help="idempotency key; reuse to test replay")
    tool.add_argument("--token", default="", help="confirmation token for confirm_checkout")
    args = parser.parse_args()
    return {"apptest": cmd_apptest, "flow": cmd_flow, "repl": cmd_repl,
            "serve": cmd_serve, "tool": cmd_tool}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
