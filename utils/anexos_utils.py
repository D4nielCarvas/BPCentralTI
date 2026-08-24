"""
utils/anexos_utils.py — Validação e armazenamento de anexos e capturas de tela.
"""

from __future__ import annotations

import uuid
from typing import Any
import psycopg2
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'pdf', 'zip', 'rar', 'txt', 'csv'
}

def allowed_file(filename: str) -> bool:
    """Verifica se o arquivo possui extensão permitida."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_anexo(arquivo: Any, chamado_id: int, mensagem_id: int | None, usuario_id: int, cur: Any) -> dict[str, str] | None:
    """
    Grava anexo/imagem no storage do PostgreSQL e vincula ao chamado_anexos.
    Retorna dicionário com caminhos e nome do arquivo ou None.
    """
    if not arquivo or not getattr(arquivo, "filename", None):
        return None

    if not allowed_file(arquivo.filename):
        return None

    filename = secure_filename(arquivo.filename)
    if not filename:
        filename = f"anexo_{uuid.uuid4().hex[:6]}.dat"

    unique_name = f"{uuid.uuid4().hex[:8]}_{filename}"

    arquivo.seek(0)
    file_bytes = arquivo.read()
    if not file_bytes:
        return None

    mimetype = getattr(arquivo, "mimetype", "application/octet-stream") or "application/octet-stream"

    cur.execute(
        """
        INSERT INTO arquivos_storage (nome_arquivo, dados, mimetype) 
        VALUES (%s, %s, %s)
        ON CONFLICT (nome_arquivo) DO NOTHING
        """,
        (unique_name, psycopg2.Binary(file_bytes), mimetype),
    )

    caminho_db = f"/arquivos/{unique_name}"
    cur.execute(
        """
        INSERT INTO chamado_anexos (chamado_id, mensagem_id, usuario_id, nome_arquivo, caminho_arquivo)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (chamado_id, mensagem_id, usuario_id, filename, caminho_db),
    )

    return {
        "nome_arquivo": filename,
        "caminho_arquivo": caminho_db,
    }
