"""
scripts/seed_localidades.py - Seed completo: localidades + primeiro admin.

Execucao:
    python scripts/seed_localidades.py

O que faz:
    1. Insere as 15 localidades padrao (idempotente por nome).
    2. Cria o PRIMEIRO USUARIO ADMIN padrao se nao existir nenhum admin.
       Login: admin | Senha: admin123

ATENCAO: Troque a senha do admin na primeira execucao em producao
         acessando /admin/usuarios e criando um novo admin.

Seguranca:
    - Senha armazenada com generate_password_hash (werkzeug - pbkdf2:sha256).
    - Idempotente: nao duplica localidades nem usuarios existentes.

Complexidade: O(n) - n = 15 localidades.
"""

from __future__ import annotations

import os
import sys

# Garante que modulos do projeto sejam encontrados ao executar via scripts/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from werkzeug.security import generate_password_hash

from utils.db_layer import acquire_conn, fetch_all, fetch_one, init_pool


# Localidades padrao - alinhadas com SIGLAS_LOCAL de id_generator.py
LOCALIDADES: list[dict] = [
    {"nome": "Sao Manoel",    "sigla": "SMN", "tipo": "fazenda"},
    {"nome": "Tangara",       "sigla": "TNG", "tipo": "fazenda"},
    {"nome": "Sao Pedro",     "sigla": "SPD", "tipo": "fazenda"},
    {"nome": "Sao Judas",     "sigla": "SJU", "tipo": "fazenda"},
    {"nome": "Sao Francisco", "sigla": "SFR", "tipo": "fazenda"},
    {"nome": "Santana",       "sigla": "STN", "tipo": "fazenda"},
    {"nome": "Santa Eliza",   "sigla": "SEL", "tipo": "fazenda"},
    {"nome": "Santa Lucia",   "sigla": "SLU", "tipo": "fazenda"},
    {"nome": "Santa Lucia 2", "sigla": "SL2", "tipo": "fazenda"},
    {"nome": "Caroline",      "sigla": "CLN", "tipo": "fazenda"},
    {"nome": "Sao Joao",      "sigla": "SJO", "tipo": "fazenda"},
    {"nome": "Santa Luzia",   "sigla": "SLZ", "tipo": "fazenda"},
    {"nome": "Santa Adelina", "sigla": "SAD", "tipo": "fazenda"},
    {"nome": "CD",            "sigla": "CD",  "tipo": "cd"},
    {"nome": "Central",       "sigla": "CEN", "tipo": "central"},
]

# Credenciais do admin padrao
ADMIN_LOGIN = "admin"
ADMIN_NOME  = "Administrador TI"
ADMIN_SENHA = "admin123"   # TROQUE APOS O PRIMEIRO ACESSO


# ─────────────────────────────────────────────────────────────────────────────

def seed_localidades(cur) -> tuple[int, int]:
    """Insere localidades ausentes. Retorna (inseridos, ignorados)."""
    existentes = {r["nome"] for r in fetch_all(cur, "SELECT nome FROM localidades")}
    inseridos = ignorados = 0

    for loc in LOCALIDADES:
        if loc["nome"] in existentes:
            print(f"  [IGNORADO]  Localidade '{loc['nome']}' ja existe.")
            ignorados += 1
            continue
        cur.execute(
            "INSERT INTO localidades (nome, sigla, tipo) VALUES (%s, %s, %s)",
            (loc["nome"], loc["sigla"], loc["tipo"]),
        )
        print(f"  [INSERIDO]  Localidade '{loc['nome']}' ({loc['sigla']}) - {loc['tipo']}")
        inseridos += 1

    return inseridos, ignorados


def seed_admin(cur) -> bool:
    """
    Cria o primeiro usuario admin se nao existir nenhum.
    Retorna True se criou, False se ja havia um admin.
    """
    admin_existente = fetch_one(
        cur, "SELECT id FROM usuarios WHERE role = 'admin' LIMIT 1"
    )
    if admin_existente:
        print("  [IGNORADO]  Ja existe pelo menos 1 admin no sistema.")
        return False

    senha_hash = generate_password_hash(ADMIN_SENHA)
    cur.execute(
        """
        INSERT INTO usuarios (nome, login, senha_hash, role, localidade_id, ativo)
        VALUES (%s, %s, %s, 'admin', NULL, TRUE)
        """,
        (ADMIN_NOME, ADMIN_LOGIN, senha_hash),
    )
    print(f"  [CRIADO]    Admin '{ADMIN_LOGIN}' - senha: {ADMIN_SENHA}")
    print("  ATENCAO: Troque a senha apos o primeiro acesso!")
    return True


# ─────────────────────────────────────────────────────────────────────────────

def seed() -> None:
    init_pool(minconn=1, maxconn=2)

    loc_ins = loc_ign = 0
    admin_criado = False

    print("\n--- Passo 1: Localidades ---")
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            loc_ins, loc_ign = seed_localidades(cur)

    print("\n--- Passo 2: Usuario Admin ---")
    with acquire_conn() as conn:
        with conn.cursor() as cur:
            admin_criado = seed_admin(cur)

    print("\n" + "=" * 50)
    print("  Seed concluido:")
    print(f"  Localidades - inseridas: {loc_ins} | ignoradas: {loc_ign}")
    if admin_criado:
        print(f"  Admin criado - login: '{ADMIN_LOGIN}' / senha: '{ADMIN_SENHA}'")
        print("  !! Troque a senha apos o primeiro acesso !!")
    else:
        print("  Admin - ja existia, nenhuma acao necessaria.")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  Seed Inicial - BP Central TI")
    print("=" * 50)
    seed()
