#!/usr/bin/env python3
"""
mcuserhunter — multi-platform username availability checker & claimer.
Platforms: Minecraft, Discord, Twitter/X

Install:
    pip install requests

Run:
    python mcuserhunter.py
"""

import itertools
import os
import sys
import time

try:
    import requests
except ImportError:
    print("missing dependency: requests")
    print("install with: pip install requests")
    sys.exit(1)


BANNER = r"""
                                                        ░████          ░██
                                                       ░██ ██          ░██
░██    ░██  ░███████   ░███████  ░██░████  ░███████   ░██  ██    ░████████  ░██████   ░██    ░██  ░███████
░██    ░██ ░██        ░██    ░██ ░███     ░██        ░██   ██   ░██    ░██       ░██  ░██    ░██ ░██
░██    ░██  ░███████  ░█████████ ░██       ░███████  ░█████████ ░██    ░██  ░███████  ░██    ░██  ░███████
░██   ░███        ░██ ░██        ░██             ░██      ░██   ░██   ░███ ░██   ░██  ░██   ░███        ░██
 ░█████░██  ░███████   ░███████  ░██       ░███████       ░██    ░█████░██  ░█████░██  ░█████░██  ░███████
                                                                                             ░██
                                                                                       ░███████

made and brought to you with love by cfwtt on ig
"""


CHARSETS = {
    "lower": "abcdefghijklmnopqrstuvwxyz",
    "upper": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "digits": "0123456789",
    "lower_digits": "abcdefghijklmnopqrstuvwxyz0123456789",
    "alnum": "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    "full": "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_",
}

PROGRESS_FILE = os.path.join(os.path.expanduser("~"), ".mcuserhunter_progress")




def clear():
    os.system("cls" if os.name == "nt" else "clear")


def header(subtitle=""):
    clear()
    print(BANNER)
    if subtitle:
        print(subtitle)
    print()


def ask(prompt, default=""):
    v = input(f"  {prompt}").strip()
    return v if v else default


def pause():
    ask("[enter] ")


def fmt_time(seconds):
    if not seconds or seconds < 0 or seconds != seconds:
        return "?"
    seconds = int(seconds)
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    if h >= 1:
        return f"{h}h{m:02d}m"
    if m >= 1:
        return f"{m}m{s:02d}s"
    return f"{s}s"




def generate(length, charset, start_from=None):
    resuming = start_from is not None
    for combo in itertools.product(charset, repeat=length):
        name = "".join(combo)
        if resuming:
            if name == start_from:
                resuming = False
            else:
                continue
        yield name


def load_progress():
    try:
        with open(PROGRESS_FILE) as f:
            n, name = f.read().strip().split("\t", 1)
            return int(n), name
    except Exception:
        return None, None


def save_progress(checked, name):
    try:
        with open(PROGRESS_FILE, "w") as f:
            f.write(f"{checked}\t{name}")
    except Exception:
        pass




class Platform:
    name = ""
    supports_check = True
    supports_claim = True

    def login(self):       raise NotImplementedError
    def check(self, u):    raise NotImplementedError
    def claim(self, u):    raise NotImplementedError
    def close(self):       pass




MICROSOFT_CLIENT_ID = "00000000402b5328"  


class Minecraft(Platform):
    name = "Minecraft"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "mcuserhunter/1.0"
        self.mc_token = None
        self.profile = None

    def login(self):
        print("  Minecraft login via Microsoft device-code flow\n")
        dc = requests.post(
            "https://login.microsoftonline.com/consumers/oauth2/v2.0/devicecode",
            data={
                "client_id": MICROSOFT_CLIENT_ID,
                "scope": "service::user.auth.xboxlive.com::MBI_SSL",
            },
            timeout=30,
        )
        dc.raise_for_status()
        info = dc.json()
        print(f"  Go to:      {info['verification_uri']}")
        print(f"  Enter code: {info['user_code']}\n")
        print("  waiting for authorization...")

        interval = info.get("interval", 5)
        deadline = time.time() + info.get("expires_in", 900)
        ms_token = None
        while time.time() < deadline:
            time.sleep(interval)
            r = requests.post(
                "https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "client_id": MICROSOFT_CLIENT_ID,
                    "device_code": info["device_code"],
                },
                timeout=30,
            )
            data = r.json()
            if "access_token" in data:
                ms_token = data["access_token"]
                break
            err = data.get("error")
            if err == "authorization_pending":
                continue
            if err == "slow_down":
                interval += 5
                continue
            print(f"  login error: {data.get('error_description', err)}")
            return False

        if not ms_token:
            print("  timed out waiting for authorization")
            return False

        # Xbox Live user auth
        r = requests.post(
            "https://user.auth.xboxlive.com/user/authenticate",
            json={
                "Properties": {
                    "AuthMethod": "RPS",
                    "SiteName": "user.auth.xboxlive.com",
                    "RpsTicket": f"d={ms_token}",
                },
                "RelyingParty": "http://auth.xboxlive.com",
                "TokenType": "JWT",
            },
            timeout=30,
        )
        if r.status_code != 200:
            print(f"  xbox live auth failed ({r.status_code})")
            return False
        xbl = r.json()
        uhs = xbl["DisplayClaims"]["xui"][0]["uhs"]

        # XSTS
        r = requests.post(
            "https://xsts.auth.xboxlive.com/xsts/authorize",
            json={
                "Properties": {"SandboxId": "RETAIL", "UserTokens": [xbl["Token"]]},
                "RelyingParty": "rp://api.minecraftservices.com/",
                "TokenType": "JWT",
            },
            timeout=30,
        )
        if r.status_code != 200:
            print(f"  xsts auth failed ({r.status_code})")
            return False
        xsts = r.json()

        # Minecraft services
        r = requests.post(
            "https://api.minecraftservices.com/authentication/login_with_xbox",
            json={"identityToken": f"XBL3.0 x={uhs};{xsts['Token']}"},
            timeout=30,
        )
        if r.status_code != 200:
            print(f"  minecraft auth failed ({r.status_code})")
            return False
        self.mc_token = r.json()["access_token"]

        # verify ownership
        r = requests.get(
            "https://api.minecraftservices.com/minecraft/profile",
            headers={"Authorization": f"Bearer {self.mc_token}"},
            timeout=30,
        )
        if r.status_code != 200:
            print("  this account does not own Minecraft: Java Edition")
            return False
        self.profile = r.json()
        print(f"  ✓ logged in as {self.profile.get('name')}")
        return True

    def check(self, username):
        for _ in range(3):
            r = self.session.get(
                f"https://api.mojang.com/users/profiles/minecraft/{username}",
                timeout=15,
            )
            if r.status_code == 429:
                time.sleep(10)
                continue
            if r.status_code in (204, 404):
                return True
            if r.status_code == 200:
                return False
            return False
        return False

    def claim(self, username):
        if not self.mc_token:
            return False
        r = self.session.put(
            f"https://api.minecraftservices.com/minecraft/profile/name/{username}",
            headers={"Authorization": f"Bearer {self.mc_token}"},
            timeout=30,
        )
        return r.status_code == 200




DISCORD_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class Discord(Platform):
    name = "Discord"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": DISCORD_UA, "Content-Type": "application/json"}
        )

    def login(self):
        print("  Discord does not expose a programmatic login.")
        print("  Grab your user token from the web client:\n")
        print("    1. open discord.com in a browser, log in")
        print("    2. DevTools (F12) -> Application -> Local Storage -> https://discord.com")
        print("    3. copy the value of 'token'\n")
        token = ask("token: ")
        if not token:
            return False
        self.session.headers["Authorization"] = token

        r = self.session.get("https://discord.com/api/v9/users/@me", timeout=15)
        if r.status_code != 200:
            print(f"  invalid token ({r.status_code})")
            return False
        me = r.json()
        print(f"  ✓ logged in as {me.get('username')}  (id {me.get('id')})")
        print("  note: discord username availability checks are best-effort;")
        print("        use 'auto-claim' mode for reliable results.")
        return True

    def check(self, username):
        
        try:
            r = self.session.post(
                "https://discord.com/api/v9/unique-username/username-attempt",
                json={"username": username},
                timeout=15,
            )
            if r.status_code == 200:
                return not r.json().get("taken", True)
            return False
        except Exception:
            return False

    def claim(self, username):
        r = self.session.patch(
            "https://discord.com/api/v9/users/@me",
            json={"username": username},
            timeout=30,
        )
        return r.status_code == 200




TWITTER_BEARER = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D"
    "1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)


class Twitter(Platform):
    name = "Twitter / X"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": DISCORD_UA,
                "Authorization": f"Bearer {TWITTER_BEARER}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "https://x.com/",
            }
        )

    def login(self):
        print("  Twitter / X uses cookie auth. Grab these from x.com (DevTools ->")
        print("  Application -> Cookies -> https://x.com):\n")
        auth_token = ask("auth_token: ")
        ct0 = ask("ct0:        ")
        if not auth_token or not ct0:
            return False
        self.session.cookies.set("auth_token", auth_token, domain=".x.com")
        self.session.cookies.set("ct0", ct0, domain=".x.com")
        self.session.headers["x-csrf-token"] = ct0

        r = self.session.get(
            "https://x.com/i/api/1.1/account/settings.json", timeout=15
        )
        if r.status_code != 200:
            print(f"  auth failed ({r.status_code})")
            return False
        print(f"  ✓ logged in as @{r.json().get('screen_name', '?')}")
        return True

    def check(self, username):
        r = self.session.get(
            f"https://x.com/i/api/1.1/users/show.json?screen_name={username}",
            timeout=15,
        )
        if r.status_code == 404:
            return True
        if r.status_code == 200:
            return False
        return False

    def claim(self, username):
        r = self.session.post(
            "https://x.com/i/api/1.1/account/settings.json",
            data={"screen_name": username},
            timeout=30,
        )
        return r.status_code == 200


PLATFORMS = {"1": Minecraft, "2": Discord, "3": Twitter}




def main_menu():
    header()
    print("  welcome. select a platform:\n")
    print("    [1] Minecraft")
    print("    [2] Discord")
    print("    [3] Twitter / X")
    print("    [0] exit\n")
    return ask("> ").lower()


def action_menu(platform):
    header(f"  platform: {platform.name}\n")
    print("    [1] check usernames & export available to file")
    print("    [2] auto-claim the first available")
    print("    [0] back\n")
    return ask("> ").lower()


def ask_config(platform, mode):
    header(f"  platform: {platform.name}  |  mode: {mode}\n")

    try:
        length = int(ask("username length [4]: ", "4"))
    except ValueError:
        length = 4

    print("\n  charset keys:")
    for k, v in CHARSETS.items():
        print(f"    {k:<14} {v}")
    key = ask("\n  charset key or raw string [lower]: ", "lower")
    charset = CHARSETS.get(key, key) or CHARSETS["lower"]

    total = len(charset) ** length
    print(f"\n  total combinations: {total:,}")

    try:
        rate = float(ask("requests/sec [1]: ", "1"))
    except ValueError:
        rate = 1.0
    if rate <= 0:
        rate = 1.0
    print(f"  estimated time @ {rate:g}/s: {fmt_time(total / rate)}")

    return length, charset, rate, total




def check_mode(platform):
    if not platform.supports_check:
        print("\n  this platform does not support availability checks.")
        pause()
        return

    length, charset, rate, total = ask_config(platform, "check & export")
    delay = 1.0 / rate
    out_path = ask("\n  output file [available.txt]: ", "available.txt")

    start_from = None
    if os.path.exists(PROGRESS_FILE):
        n, name = load_progress()
        if name and ask(f"\n  resume from '{name}' ({n} checked)? [Y/n]: ", "Y").lower() != "n":
            start_from = name
        else:
            try: os.remove(PROGRESS_FILE)
            except OSError: pass

    mode = "a" if start_from else "w"
    print("\n  scanning... (ctrl+c to stop)\n")

    found = 0
    checked = 0
    last = start_from
    started = time.time()

    try:
        with open(out_path, mode) as f:
            for name in generate(length, charset, start_from=start_from):
                checked += 1
                last = name
                hit = False
                try:
                    if platform.check(name):
                        f.write(name + "\n")
                        f.flush()
                        found += 1
                        hit = True
                except Exception:
                    pass

                if hit:
                    print(f"\r  + {name}  (available: {found})        ")
                else:
                    elapsed = time.time() - started
                    r_actual = checked / elapsed if elapsed > 0 else 0
                    eta = (total - checked) / r_actual if r_actual > 0 else 0
                    print(
                        f"\r  [{checked:,}/{total:,}] available={found} "
                        f"rate={r_actual:.2f}/s eta={fmt_time(eta)}    ",
                        end="", flush=True,
                    )

                if checked % 10 == 0:
                    save_progress(checked, last)
                time.sleep(delay)
    except KeyboardInterrupt:
        print("\n\n  interrupted; progress saved.")
        if last:
            save_progress(checked, last)
        pause()
        return

    print(f"\n\n  done. {found} available name(s) written to {out_path}")
    try: os.remove(PROGRESS_FILE)
    except OSError: pass
    pause()


def claim_mode(platform):
    if not platform.supports_claim:
        print("\n  this platform does not support claiming.")
        pause()
        return

    length, charset, rate, total = ask_config(platform, "auto-claim")
    delay = 1.0 / rate

    print(f"\n  will attempt to claim the first available name out of {total:,} combos.")
    if ask("  continue? [y/N]: ", "N").lower() != "y":
        return

    print("\n  scanning...\n")
    checked = 0
    started = time.time()

    try:
        for name in generate(length, charset):
            checked += 1

            if platform.supports_check:
                try:
                    available = platform.check(name)
                except Exception:
                    available = False
                if not available:
                    elapsed = time.time() - started
                    r_actual = checked / elapsed if elapsed > 0 else 0
                    print(
                        f"\r  [{checked:,}/{total:,}] rate={r_actual:.2f}/s",
                        end="", flush=True,
                    )
                    time.sleep(delay)
                    continue

            print(f"\n  found available: {name}")
            print("  attempting claim...")
            try:
                ok = platform.claim(name)
            except Exception as e:
                print(f"  claim error: {e}")
                ok = False

            if ok:
                print(f"\n  ✓ claimed: {name}")
                pause()
                return
            print("  claim failed (name likely taken); continuing")
            time.sleep(delay)
    except KeyboardInterrupt:
        print("\n\n  interrupted.")
        pause()
        return

    print("\n\n  no available names found in range.")
    pause()




def run_platform(platform):
    header(f"  platform: {platform.name}\n")
    try:
        if not platform.login():
            print("\n  login failed or cancelled.")
            pause()
            return
    except Exception as e:
        print(f"\n  login error: {e}")
        pause()
        return

    while True:
        a = action_menu(platform)
        if a == "0":
            return
        if a == "1":
            check_mode(platform)
        elif a == "2":
            claim_mode(platform)


def main():
    try:
        while True:
            choice = main_menu()
            if choice in ("0", "q", "quit", "exit"):
                print("\n  bye\n")
                return
            cls = PLATFORMS.get(choice)
            if not cls:
                continue
            platform = cls()
            try:
                run_platform(platform)
            finally:
                platform.close()
    except KeyboardInterrupt:
        print("\n\n  bye\n")
        sys.exit(0)


if __name__ == "__main__":
    main()