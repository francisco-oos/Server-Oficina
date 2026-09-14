from pathlib import Path
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parent.parent
html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")

class IdParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids=set(); self.remote=[]
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if "id" in a: self.ids.add(a["id"])
        for key in ("src","href"):
            val=a.get(key)
            if val and (val.startswith("http://") or val.startswith("https://")):
                self.remote.append(val)

p=IdParser(); p.feed(html)
required_ids={"setup","setupForm","login","loginForm","app","content","who","logout","usersNav","title"}
missing=sorted(required_ids-p.ids)
if missing: raise SystemExit(f"Faltan IDs de UI: {missing}")
if p.remote: raise SystemExit(f"Frontend depende de recursos remotos: {p.remote}")
required_api=["/api/setup/status","/api/setup/first-admin","/api/auth/login","/api/me","/api/dashboard","/api/persons"]
missing_api=[x for x in required_api if x not in js]
if missing_api: raise SystemExit(f"Faltan contratos API en app.js: {missing_api}")
for forbidden in ("const EMPLOYEES = [", "106 colaboradores"):
    if forbidden in html or forbidden in js:
        raise SystemExit("Se detectaron datos demo incrustados prohibidos")
print("FRONTEND_CONTRACT_OK")
