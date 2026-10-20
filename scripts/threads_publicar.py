"""Repete no Threads o que sai no Instagram, de graça, pelo mesmo fila.json.

Threads é texto primeiro e dá alcance pra conta pequena (não depende de seguidor).
Cada item da fila com legenda vira um post: texto (até 500 caracteres, sem o
bloco de hashtags) + primeira imagem, ou o vídeo quando for Reel. Stories não vão.
Sai na mesma rodada do Instagram, um por vez. Registro em threads.json.

Segredos: THREADS_TOKEN e THREADS_USER_ID (scripts/threads_auth.py gera os dois).
Sem eles, o script só avisa e sai: o workflow não quebra.
"""
import datetime as dt
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request

G = "https://graph.threads.net/v1.0"
TOKEN, USER = os.environ.get("THREADS_TOKEN"), os.environ.get("THREADS_USER_ID")
RAIZ = pathlib.Path(__file__).resolve().parents[1]
FILA, FEITOS = RAIZ / "fila.json", RAIZ / "threads.json"
SITE = "https://raw.githubusercontent.com/bianca-c-paula/astrologica-social/main/midia/"
BRT = dt.timezone(dt.timedelta(hours=-3))
ATRASO_MAX = dt.timedelta(hours=6)


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


def texto(legenda):
    """Sem o bloco de hashtags, até 500 caracteres cortando em fim de frase."""
    linhas = [l for l in legenda.strip().split("\n") if not re.fullmatch(r"(\s*#\S+)+\s*", l)]
    t = "\n".join(linhas).strip()
    if len(t) <= 500:
        return t
    corte = max(t.rfind(". ", 0, 480), t.rfind("\n", 0, 480))
    return t[: corte + 1].strip() if corte > 200 else t[:497] + "…"


def publicar(post):
    q = {"text": texto(post["legenda"])}
    if post.get("video"):
        q.update(media_type="VIDEO", video_url=SITE + post["video"])
    elif post.get("imagens"):
        q.update(media_type="IMAGE", image_url=SITE + post["imagens"][0])
    else:
        q["media_type"] = "TEXT"
    c = call("POST", f"{USER}/threads", **q)["id"]
    for _ in range(60):
        st = call("GET", c, fields="status").get("status")
        if st == "FINISHED":
            break
        if st == "ERROR":
            raise RuntimeError(f"mídia {c} com erro no Threads")
        time.sleep(5)
    media = call("POST", f"{USER}/threads_publish", creation_id=c)["id"]
    return call("GET", media, fields="permalink").get("permalink")


def main():
    if not (TOKEN and USER):
        print("Threads: sem THREADS_TOKEN/THREADS_USER_ID, pulando")
        return
    agora = dt.datetime.now(BRT)
    fila = json.loads(FILA.read_text(encoding="utf-8"))
    feitos = json.loads(FEITOS.read_text(encoding="utf-8")) if FEITOS.exists() else {}
    for post in fila:
        if not post.get("legenda") or post["id"] in feitos:
            continue
        quando = dt.datetime.fromisoformat(post["quando"]).replace(tzinfo=BRT)
        if quando > agora or agora - quando > ATRASO_MAX:
            continue
        print(f"threads: {post['id']}")
        feitos[post["id"]] = {"em": agora.isoformat(timespec="minutes")}
        FEITOS.write_text(json.dumps(feitos, ensure_ascii=False, indent=2), encoding="utf-8")
        feitos[post["id"]]["link"] = publicar(post)
        FEITOS.write_text(json.dumps(feitos, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  {feitos[post['id']]['link']}")
        return


if __name__ == "__main__":
    main()
