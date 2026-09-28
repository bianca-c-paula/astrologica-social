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
PUBLICADOS = pathlib.Path(__file__).resolve().parent.parent / "publicados.json"
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


def extras(post, i=None):
    """Marcação na foto ("marcar": {"<índice da imagem>": [{"username", "x", "y"}]}) e
    convite de colaboração ("colaboradores": ["usuario"], vai no post, não no slide)."""
    q = {}
    tags = post.get("marcar", {}).get(str(i if i is not None else 0))
    if tags:
        q["user_tags"] = json.dumps(tags)
    if i is None and post.get("colaboradores"):
        q["collaborators"] = json.dumps(post["colaboradores"])
    return q


def publicar(post):
    urls = [SITE + img for img in post["imagens"]]
    if len(urls) == 1:
        c = call("POST", f"{IG}/media", image_url=urls[0], caption=post["legenda"], **extras(post))["id"]
    else:
        filhos = [call("POST", f"{IG}/media", image_url=u, is_carousel_item="true", **extras(post, i))["id"]
                  for i, u in enumerate(urls)]
        for f in filhos:
            pronto(f)
        q = extras(post)
        q.pop("user_tags", None)
        c = call("POST", f"{IG}/media", media_type="CAROUSEL", children=",".join(filhos),
                 caption=post["legenda"], **q)["id"]
    pronto(c)
    media = call("POST", f"{IG}/media_publish", creation_id=c)["id"]
    return call("GET", media, fields="permalink").get("permalink")


def primeira_linha(texto):
    return " ".join((texto or "").strip().split("\n")[0].split())[:50]


def main():
    """Nunca repete post: o registro principal é publicados.json (id da fila → link),
    commitado pelo workflow. A legenda pode ser editada no app depois (foi o que
    causou as repetições de 28/09), então a checagem por legenda é só reforço e
    olha apenas a primeira linha."""
    agora = dt.datetime.now(BRT)
    fila = json.loads(FILA.read_text(encoding="utf-8"))
    feitos = json.loads(PUBLICADOS.read_text(encoding="utf-8")) if PUBLICADOS.exists() else {}
    recentes = call("GET", f"{IG}/media", fields="caption", limit=30).get("data", [])
    ja = {primeira_linha(m.get("caption")) for m in recentes}
    for post in fila:
        quando = dt.datetime.fromisoformat(post["quando"]).replace(tzinfo=BRT)
        if quando > agora or post["id"] in feitos or primeira_linha(post["legenda"]) in ja:
            continue
        if agora - quando > ATRASO_MAX:
            print(f"pulado (atrasado): {post['id']}")
            continue
        print(f"publicando {post['id']} ({post['quando']})")
        # Marca antes de publicar: se o workflow cair no meio, o pior caso é
        # um post faltando (visível), nunca um post repetido.
        feitos[post["id"]] = {"em": agora.isoformat(timespec="minutes")}
        PUBLICADOS.write_text(json.dumps(feitos, ensure_ascii=False, indent=2), encoding="utf-8")
        link = publicar(post)
        feitos[post["id"]]["link"] = link
        PUBLICADOS.write_text(json.dumps(feitos, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  {link}")
        return  # um por rodada: nunca dois posts juntos


if __name__ == "__main__":
    main()
