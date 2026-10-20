"""Token do Threads, uma vez só (depois renova sozinho).

Antes, no developers.facebook.com, no app da Astrológica:
  1. Casos de uso → Adicionar → "Acessar a API do Threads" (threads_basic,
     threads_content_publish).
  2. Nesse caso de uso → Configurações: copiar "ID do app do Threads" e
     "Chave secreta do app do Threads" pra ~/.astrologica.env como
     THREADS_APP_ID e THREADS_APP_SECRET; em "URIs de redirecionamento" pôr
     https://myastrologica.me/ ; "URI de desautorização" e "exclusão de dados"
     podem ser a mesma.
  3. Funções do app → Funções → adicionar @myastrologica_ como "Testador do
     Threads"; aceitar no app do Threads (Configurações → Conta → Permissões
     do site → Convites).

Depois:
  python3 scripts/threads_auth.py login     imprime a URL; abre, autoriza, copia o
                                            "code=" da URL de retorno (sem o "#_")
  python3 scripts/threads_auth.py code XXX  troca por token de 60 dias, grava no
                                            ~/.astrologica.env e nos segredos do GitHub
  python3 scripts/threads_auth.py refresh   renova (launchd faz toda segunda)
"""
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.parse
import urllib.request

ENV = pathlib.Path.home() / ".astrologica.env"
REPO = "bianca-c-paula/astrologica-social"
REDIRECT = "https://myastrologica.me/"
env = dict(re.findall(r'^(\w+)="?([^"\n]*)"?$', ENV.read_text(), re.M)) if ENV.exists() else {}


def get(url, **q):
    with urllib.request.urlopen(url + "?" + urllib.parse.urlencode(q), timeout=60) as r:
        return json.load(r)


def post(url, **q):
    with urllib.request.urlopen(urllib.request.Request(url, data=urllib.parse.urlencode(q).encode()), timeout=60) as r:
        return json.load(r)


def gravar(**kv):
    linhas = [l for l in ENV.read_text().splitlines() if l.split("=")[0] not in kv]
    linhas += [f"{k}={v}" for k, v in kv.items()]
    ENV.write_text("\n".join(linhas) + "\n")
    for k, v in kv.items():
        subprocess.run(["gh", "secret", "set", k, "-R", REPO, "-b", v], check=True)
    print("gravado em ~/.astrologica.env e nos segredos do GitHub:", ", ".join(kv))


cmd = sys.argv[1] if len(sys.argv) > 1 else "login"
if cmd == "login":
    print("https://threads.net/oauth/authorize?" + urllib.parse.urlencode(dict(
        client_id=env["THREADS_APP_ID"], redirect_uri=REDIRECT,
        scope="threads_basic,threads_content_publish", response_type="code")))
elif cmd == "code":
    code = sys.argv[2].split("#")[0]
    curto = post("https://graph.threads.net/oauth/access_token", client_id=env["THREADS_APP_ID"],
                 client_secret=env["THREADS_APP_SECRET"], grant_type="authorization_code",
                 redirect_uri=REDIRECT, code=code)
    longo = get("https://graph.threads.net/access_token", grant_type="th_exchange_token",
                client_secret=env["THREADS_APP_SECRET"], access_token=curto["access_token"])
    gravar(THREADS_TOKEN=longo["access_token"], THREADS_USER_ID=str(curto["user_id"]))
elif cmd == "refresh":
    if not env.get("THREADS_TOKEN"):
        sys.exit("sem THREADS_TOKEN ainda")
    novo = get("https://graph.threads.net/refresh_access_token", grant_type="th_refresh_token",
               access_token=env["THREADS_TOKEN"])
    gravar(THREADS_TOKEN=novo["access_token"])
