"""Publica no Instagram os posts de social/fila.json cujo horário já chegou.

Roda no GitHub Actions a cada 30 minutos (ver .github/workflows/instagram.yml).
Imagens em midia/, lista em fila.json.
Não guarda estado: antes de publicar, confere os últimos posts da conta e pula
o que já saiu (compara o começo da legenda). Post com mais de 6 horas de atraso
é pulado, para não sair nada de madrugada.

Segredos: META_PAGE_TOKEN e META_IG_USER_ID.
"""
import datetime as dt
import json
import os
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request

G = "https://graph.facebook.com/v23.0"
TOKEN, IG = os.environ["META_PAGE_TOKEN"], os.environ["META_IG_USER_ID"]
FILA = pathlib.Path(__file__).resolve().parents[1] / "fila.json"
# Servido direto do GitHub (repositório público), sem depender do site.
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


def pronto(container):
    for _ in range(40):
        st = call("GET", container, fields="status_code")["status_code"]
        if st == "FINISHED":
            return
        if st == "ERROR":
            raise RuntimeError(f"mídia {container} com erro")
        time.sleep(3)
    raise RuntimeError("mídia demorou demais")


def chave(texto):
    return " ".join(texto.split())[:80]


def publicar(post):
    urls = [SITE + img for img in post["imagens"]]
    if len(urls) == 1:
        c = call("POST", f"{IG}/media", image_url=urls[0], caption=post["legenda"])["id"]
    else:
        filhos = [call("POST", f"{IG}/media", image_url=u, is_carousel_item="true")["id"] for u in urls]
        for f in filhos:
            pronto(f)
        c = call("POST", f"{IG}/media", media_type="CAROUSEL", children=",".join(filhos),
                 caption=post["legenda"])["id"]
    pronto(c)
    media = call("POST", f"{IG}/media_publish", creation_id=c)["id"]
    return call("GET", media, fields="permalink").get("permalink")


def main():
    agora = dt.datetime.now(BRT)
    fila = json.loads(FILA.read_text(encoding="utf-8"))
    recentes = call("GET", f"{IG}/media", fields="caption", limit=30).get("data", [])
    ja = {chave(m.get("caption") or "") for m in recentes}
    for post in fila:
        quando = dt.datetime.fromisoformat(post["quando"]).replace(tzinfo=BRT)
        if quando > agora or chave(post["legenda"]) in ja:
            continue
        if agora - quando > ATRASO_MAX:
            print(f"pulado (atrasado): {post['id']}")
            continue
        print(f"publicando {post['id']} ({post['quando']})")
        print(f"  {publicar(post)}")
        return  # um por rodada: nunca dois posts juntos


if __name__ == "__main__":
    main()
