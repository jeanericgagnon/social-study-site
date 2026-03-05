#!/usr/bin/env python3
"""Validate scrape targets against sandbox policy.

Usage:
  ALLOWLIST=example.com,docs.example.com ./validate_targets.py https://example.com
  ALLOWLIST=example.com ./validate_targets.py --file urls.txt
"""
import argparse
import ipaddress
import socket
import sys
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser


def parse_allowlist(raw: str):
    return [d.strip().lower().strip(".") for d in (raw or "").split(",") if d.strip()]


def host_allowed(host: str, allowlist):
    return any(host == d or host.endswith("." + d) for d in allowlist)


def resolve_ips(host: str):
    return {ai[4][0] for ai in socket.getaddrinfo(host, None)}


def ip_is_blocked(ip_s: str):
    ip = ipaddress.ip_address(ip_s)
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast


def robots_allowed(url: str, ua: str):
    p = urlparse(url)
    robots = f"{p.scheme}://{p.netloc}/robots.txt"
    rp = RobotFileParser()
    try:
        rp.set_url(robots)
        rp.read()
        return rp.can_fetch(ua, url)
    except Exception:
        # Fail-open on robots fetch errors, but report unknown in caller.
        return None


def validate_url(url: str, allowlist, ua: str):
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        return False, f"blocked scheme: {p.scheme}"
    host = (p.hostname or "").lower().strip(".")
    if not host:
        return False, "invalid host"
    if not host_allowed(host, allowlist):
        return False, f"host not in allowlist: {host}"
    try:
        ips = resolve_ips(host)
    except Exception as e:
        return False, f"dns resolution failed: {e}"
    for ip in ips:
        if ip_is_blocked(ip):
            return False, f"resolved blocked ip: {ip}"
    rob = robots_allowed(url, ua)
    if rob is False:
        return False, "disallowed by robots.txt"
    # True or None (unknown) accepted
    return True, "ok" if rob is True else "ok (robots unknown)"


def load_urls(single, file_path):
    urls = []
    if single:
        urls.append(single.strip())
    if file_path:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.append(line)
    return urls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url", nargs="?", help="single URL")
    ap.add_argument("--file", help="path to URL list (one per line)")
    ap.add_argument("--user-agent", default="OpenClawSafeScraper/1.0")
    args = ap.parse_args()

    allowlist = parse_allowlist(__import__("os").environ.get("ALLOWLIST", ""))
    if not allowlist:
        print("ERROR: ALLOWLIST env var required", file=sys.stderr)
        return 2

    urls = load_urls(args.url, args.file)
    if not urls:
        print("ERROR: provide a URL or --file", file=sys.stderr)
        return 2

    failures = 0
    for u in urls:
        ok, reason = validate_url(u, allowlist, args.user_agent)
        tag = "PASS" if ok else "FAIL"
        print(f"[{tag}] {u} :: {reason}")
        if not ok:
            failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
