"""Responde comentários do Instagram na hora, sem IA e sem inventar.

Roda junto com publicar_fila.py (GitHub Actions, a cada 30 min). Olha os posts
dos últimos 14 dias, pega os comentários sem resposta nossa e responde só o que
dá pra responder com fato:

  comentário com signo   → casa solar + texto do horóscopo da semana (horoscopo.json,
                           exportado pelo horoscopo_linhas.py toda segunda)
  pergunta sobre o mapa  → PDF, preço e link da bio
  pergunta sobre tiragem → Jessica (@_jessica_butterfly_)

O resto não recebe resposta automática: vai pra pendentes.json, que o relatório
de segunda lista pra Bianca responder à mão. Registro em respondidos.json
(commitado pelo workflow) pra nunca responder duas vezes.

  python3 scripts/responder_comentarios.py --dry   só mostra o que responderia

Segredos: META_PAGE_TOKEN e META_IG_USER_ID.
"""
import datetime as dt
import json
import os
import pathlib
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

G = "https://graph.facebook.com/v23.0"
TOKEN, IG = os.environ["META_PAGE_TOKEN"], os.environ["META_IG_USER_ID"]
RAIZ = pathlib.Path(__file__).resolve().parents[1]
RESPONDIDOS = RAIZ / "respondidos.json"
PENDENTES = RAIZ / "pendentes.json"
HOROSCOPO = RAIZ / "horoscopo.json"
JANELA = dt.timedelta(days=14)
MAX_POR_RODADA = 15
DRY = "--dry" in sys.argv

SIGNOS = ["Áries", "Touro", "Gêmeos", "Câncer", "Leão", "Virgem", "Libra", "Escorpião",
          "Sagitário", "Capricórnio", "Aquário", "Peixes"]
GLIFO = "♈♉♊♋♌♍♎♏♐♑♒♓"
# raízes sem acento: pega "áries", "ariana", "taurino", "sou de gêmeos", "escorpiana"...
RAIZES = [r"\barie[sn]|\bariano|\bariana", r"\btouro\b|\btaurin", r"\bgemeos\b|\bgeminian",
          r"\bcancer\b|\bcancerian", r"\bleao\b|\bleonin", r"\bvirgem\b|\bvirginian",
          r"\blibra\b|\blibrian", r"\bescorpi", r"\bsagit", r"\bcapric", r"\baquari", r"\bpeixes\b|\bpiscian"]
MAPA = re.compile(r"mapa (astral|completo)|\bpdf\b|hora (de nascimento|que nasci)|nao sei (a|minha) hora|quanto (custa|e|é)|\bvalor\b|\bpreco\b")
TIRAGEM = re.compile(r"\btiragem|\bconsulta|\bleitura|\bjessica|\bjogo de (tarot|taro|cartas)|\bbaralho cigano|\bagendar")


def call(method, path, **q):
    q["access_token"] = TOKEN
    data = urllib.parse.urlencode(q)
    url = f"{G}/{path}" + ("" if method == "POST" else "?" + data)
    req = urllib.request.Request(url, data=data.encode() if method == "POST" else None, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{path}: {json.load(e).get('error', {}).get('message')}")


def plano(texto):
    """minúsculas, sem acento, sem emoji de signo convertido: 'Sou Áries!' → 'sou aries!'"""
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
    return t


def signo_em(texto):
    """Índice do primeiro signo citado (nome ou glifo); None se nenhum."""
    achados = []
    for i, g in enumerate(GLIFO):
        if g in (texto or ""):
            achados.append(((texto or "").index(g), i))
    t = plano(texto)
    for i, rx in enumerate(RAIZES):
        m = re.search(rx, t)
        if m:
            achados.append((m.start(), i))
    return min(achados)[1] if achados else None


def semana_atual(hoje):
    """Semana do horóscopo mais recente já começada (até 10 dias de idade)."""
    if not HOROSCOPO.exists():
        return None
    semanas = json.loads(HOROSCOPO.read_text(encoding="utf-8"))
    ok = [d for d in semanas if dt.date.fromisoformat(d) <= hoje and (hoje - dt.date.fromisoformat(d)).days <= 10]
    return semanas[max(ok)] if ok else None


def resposta(texto, semana):
    i = signo_em(texto)
    if i is not None and semana:
        return f"{SIGNOS[i]} {GLIFO[i]} · {semana['casas'][i]}. {semana['textos'][i]} (semana {semana['titulo']})"
    if i is not None:
        return f"{SIGNOS[i]} {GLIFO[i]} · o horóscopo da sua semana sai toda segunda às 20h aqui no feed."
    t = plano(texto)
    if MAPA.search(t):
        return ("O mapa astral completo é um PDF de 15 páginas, R$ 29,90, no link da bio (myastrologica.me). "
                "Sem a hora de nascimento também dá: só ficam de fora as casas e o ascendente.")
    if TIRAGEM.search(t):
        return "As tiragens são com a @_jessica_butterfly_: o link tá na bio, ou chama ela no direct."
    return None


def main():
    agora = dt.datetime.now(dt.timezone.utc)
    hoje = (agora - dt.timedelta(hours=3)).date()
    eu = call("GET", IG, fields="username")["username"]
    feitos = json.loads(RESPONDIDOS.read_text(encoding="utf-8")) if RESPONDIDOS.exists() else {}
    pendentes = json.loads(PENDENTES.read_text(encoding="utf-8")) if PENDENTES.exists() else {}
    semana = semana_atual(hoje)
    posts = call("GET", f"{IG}/media", fields="id,timestamp,permalink,comments_count", limit=25).get("data", [])
    n = 0
    for p in posts:
        if not p.get("comments_count") or agora - dt.datetime.fromisoformat(p["timestamp"]) > JANELA:
            continue
        coms = call("GET", f"{p['id']}/comments", fields="id,text,username,timestamp,replies{username}", limit=50).get("data", [])
        for c in coms:
            if c["username"] == eu or c["id"] in feitos:
                continue
            if any(r["username"] == eu for r in c.get("replies", {}).get("data", [])):
                continue
            if agora - dt.datetime.fromisoformat(c["timestamp"]) > JANELA:
                continue
            r = resposta(c.get("text"), semana)
            if not r:
                pendentes.setdefault(c["id"], {"quando": c["timestamp"], "de": c["username"],
                                               "texto": c.get("text", ""), "post": p.get("permalink")})
                continue
            if n >= MAX_POR_RODADA:
                return
            print(f"@{c['username']}: {c.get('text', '')[:60]!r}\n  → {r}")
            if not DRY:
                call("POST", f"{c['id']}/replies", message=r)
                feitos[c["id"]] = {"em": agora.isoformat(timespec="minutes"), "de": c["username"], "resposta": r}
                pendentes.pop(c["id"], None)
                RESPONDIDOS.write_text(json.dumps(feitos, ensure_ascii=False, indent=2), encoding="utf-8")
                time.sleep(2)
            n += 1
    if not DRY:
        PENDENTES.write_text(json.dumps(pendentes, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{n} resposta(s); {len(pendentes)} pendente(s) pra responder à mão")


if __name__ == "__main__":
    main()
