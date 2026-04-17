from __future__ import annotations
from urllib.parse import urljoin
import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0"
class CookieJar:
    def __init__(self): self.store = {}
    def _domain_match(self, cookie_domain, hostname): return cookie_domain == hostname or (cookie_domain.startswith(".") and (hostname == cookie_domain[1:] or hostname.endswith(cookie_domain)))
    def set_from_response(self, request_url, response):
        hostname = requests.utils.urlparse(request_url).hostname or ""
        for c in response.cookies:
            domain = c.domain or hostname
            if domain and not domain.startswith(".") and domain != hostname: domain = "." + domain
            if c.value in ("null", ""): self.store.get(domain, {}).pop(c.name, None); continue
            self.store.setdefault(domain, {})[c.name] = {"name": c.name, "value": c.value, "expires": c.expires}
    def get_cookie_string(self, request_url):
        hostname = requests.utils.urlparse(request_url).hostname or ""; pairs = []
        for dom, cookies in self.store.items():
            if not self._domain_match(dom, hostname): continue
            for c in cookies.values():
                if c.get("expires") and float(c["expires"]) < __import__("time").time(): continue
                pairs.append(f'{c["name"]}={c["value"]}')
        return "; ".join(pairs)
def fetch_cookie(jar, url, opts=None):
    opts = opts or {}
    headers = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9", **opts.get("headers", {})}
    cookies = jar.get_cookie_string(url)
    if cookies: headers["Cookie"] = cookies
    res = requests.request(opts.get("method", "GET"), url, headers=headers, data=opts.get("data"), allow_redirects=False, timeout=30)
    jar.set_from_response(url, res); return res
def fetch_redirect(jar, url, opts=None, max_hops=15):
    opts = opts or {}; res = fetch_cookie(jar, url, opts); cur = url; hops = 0
    while res.status_code in (301, 302, 303, 307, 308) and hops < max_hops:
        loc = res.headers.get("location")
        if not loc: break
        _ = res.text
        cur = urljoin(cur, loc)
        method = "GET" if res.status_code in (301, 302, 303) else opts.get("method", "GET")
        res = fetch_cookie(jar, cur, {"headers": opts.get("headers", {}), "method": method})
        hops += 1
    return res, cur
