"""Gera board.html: todos os posts da fila, por dia, com todos os slides,
legenda e a simulação da grade do perfil. Abre direto no navegador.

  python3 board.py            → board.html (e abre)
  python3 board.py --extra DIR:ID:QUANDO   inclui um post ainda fora da fila (ex.: aguardando aprovação)
"""
import datetime as dt
import html
import json
import pathlib
import subprocess
import sys

AQUI = pathlib.Path(__file__).parent
DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]

fila = json.loads((AQUI / "fila.json").read_text(encoding="utf-8"))
for x in fila:
    x["imgs"] = [f"midia/{i}" for i in x.get("imagens", [])] or ([f"midia/{x['capa']}"] if x.get("capa") else [])
    x["status"] = "agendado" + (" · reel" if x.get("video") else "")

# rascunho.json: mesmo formato da fila, posts que ainda esperam a aprovação dela
rasc = AQUI / "rascunho.json"
if rasc.exists():
    for x in json.loads(rasc.read_text(encoding="utf-8")):
        x["imgs"] = [f"midia/{i}" for i in x["imagens"]]
        x["status"] = "aguardando aprovação"
        fila.append(x)

for arg in sys.argv[1:]:
    if arg.startswith("--extra="):
        pasta, pid, quando = arg.split("=", 1)[1].split("|")
        d = pathlib.Path(pasta).expanduser()
        imgs = sorted(str(f) for f in d.glob("*-0*.jpg"))
        leg = next(iter(d.glob("LEGENDA*.txt")), None)
        fila.append({"id": pid, "quando": quando, "imgs": [pathlib.Path(i).as_uri() for i in imgs],
                     "legenda": leg.read_text(encoding="utf-8") if leg else "", "status": "aguardando aprovação"})
fila.sort(key=lambda x: x["quando"])

# grade do perfil: o mais novo em cima, capa de cada post (corte 3:4 feito no CSS)
grade = "".join(f'<div class="g"><img src="{x["imgs"][0]}"><span>{x["quando"][8:10]}/{x["quando"][5:7]}</span></div>'
                for x in reversed(fila))

dias = {}
for x in fila:
    dias.setdefault(x["quando"][:10], []).append(x)
blocos = ""
for dia, posts in dias.items():
    d = dt.date.fromisoformat(dia)
    cards = ""
    for x in posts:
        slides = "".join(f'<img src="{s}" loading="lazy">' for s in x["imgs"])
        tag = "" if x["status"] == "agendado" else f'<b class="st">{x["status"]}</b>'
        cards += (f'<article><header><time>{x["quando"][11:16]}</time><h3>{html.escape(x["id"])}</h3>{tag}'
                  f'<small>{len(x["imgs"])} slide{"s" if len(x["imgs"]) > 1 else ""}</small></header>'
                  f'<div class="slides">{slides}</div>'
                  f'<details><summary>legenda</summary><pre>{html.escape(x["legenda"])}</pre></details></article>')
    blocos += f'<section><h2>{DIAS[d.weekday()]} {d.day:02d}/{d.month:02d}</h2>{cards}</section>'

agora = dt.datetime.now().strftime("%d/%m %H:%M")
(AQUI / "board.html").write_text(f"""<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Agenda do Instagram</title>
<style>
:root{{--bg:#F4ECE6;--ink:#0D0B0C;--mut:#6b625c;--card:#fff;--red:#C8322B}}
@media (prefers-color-scheme:dark){{:root{{--bg:#141213;--ink:#F4ECE6;--mut:#a39a93;--card:#1e1b1c}}}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.4 -apple-system,Inter,sans-serif}}
main{{max-width:1200px;margin:0 auto;padding:24px 16px 80px}}
h1{{font-size:28px;margin:0 0 4px}} .sub{{color:var(--mut);margin:0 0 24px}}
.grade{{display:grid;grid-template-columns:repeat(3,1fr);gap:3px;max-width:420px;margin:0 0 36px}}
.g{{position:relative;aspect-ratio:3/4;overflow:hidden;background:#000}} .g img{{width:100%;height:100%;object-fit:cover}}
.g span{{position:absolute;left:6px;bottom:6px;background:#000a;color:#fff;font-size:11px;padding:2px 6px;border-radius:4px}}
section{{margin:0 0 32px}} h2{{font-size:18px;text-transform:uppercase;letter-spacing:.06em;border-bottom:2px solid var(--ink);padding-bottom:6px}}
article{{background:var(--card);border-radius:12px;padding:14px;margin:12px 0;box-shadow:0 2px 10px #0001}}
header{{display:flex;flex-wrap:wrap;gap:10px;align-items:baseline;margin-bottom:10px}}
time{{font:700 20px ui-monospace,monospace}} h3{{margin:0;font-size:15px}} small{{color:var(--mut)}}
.st{{background:var(--red);color:#fff;font-size:12px;padding:2px 8px;border-radius:99px}}
.slides{{display:flex;gap:8px;overflow-x:auto;padding-bottom:6px;scroll-snap-type:x mandatory}}
.slides img{{height:300px;aspect-ratio:4/5;object-fit:cover;border-radius:6px;scroll-snap-align:start;flex:none}}
@media (max-width:600px){{.slides img{{height:220px}}}}
pre{{white-space:pre-wrap;font:14px/1.45 -apple-system,Inter,sans-serif;margin:8px 0 0}}
summary{{cursor:pointer;color:var(--mut)}}
</style><main><h1>Agenda do Instagram</h1>
<p class="sub">@myastrologica_ · {len(fila)} posts · gerado em {agora}. Em cima, como a grade do perfil vai ficar (o mais novo primeiro).</p>
<div class="grade">{grade}</div>{blocos}</main></html>""", encoding="utf-8")
print(AQUI / "board.html")
