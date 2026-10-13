"""Utilitários de criptografia simétrica (Fernet) para campos sensíveis."""

from __future__ import annotations

import functools
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


@functools.lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """
    Inicializa e retorna a instância Fernet a partir da variável FERNET_KEY.

    Raises:
        RuntimeError: Se FERNET_KEY não estiver definida ou for inválida.
    """
    raw_key = os.environ.get("FERNET_KEY", "")
    if not raw_key:
        raise RuntimeError(
            "FERNET_KEY não definida. "
            "Gere com: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\" "
            "e adicione ao .env"
        )
    try:
        return Fernet(raw_key.encode())
    except Exception as exc:
        raise RuntimeError(f"FERNET_KEY inválida: {exc}") from exc


def encrypt_field(valor: Optional[str]) -> Optional[str]:
    """
    Criptografa um campo de texto com Fernet (AES-128-CBC + HMAC-SHA256).

    Args:
        valor: String em texto claro, ou None/vazio para não criptografar.

    Returns:
        String criptografada (prefixo 'gAAAAA...') ou None se entrada for None/vazia.

    Example:
        encrypt_field("minha_senha")  # → "gAAAAA..."
        encrypt_field(None)           # → None
    """
    if not valor:
        return valor  # Preserva None e string vazia sem criptografar
    f = _get_fernet()
    return f.encrypt(valor.encode("utf-8")).decode("utf-8")


def decrypt_field(valor: Optional[str]) -> Optional[str]:
    """
    Descriptografa um campo previamente criptografado com Fernet.

    Seguro para valores legados (texto claro): se a descriptografia falhar
    (InvalidToken), retorna o valor original sem modificação — permitindo
    migração gradual de dados existentes.

    Args:
        valor: String criptografada ('gAAAAA...'), texto legado ou None.

    Returns:
        String descriptografada ou o valor original se não for Fernet-encoded.

    Example:
        decrypt_field("gAAAAA...")  # → "minha_senha"
        decrypt_field(None)         # → None
        decrypt_field("legado")     # → "legado" (compatibilidade retroativa)
    """
    if not valor:
        return valor
    # Valores Fernet sempre começam com 'gAAAAA' (base64 de b'\x80\x00...')
    if not valor.startswith("gAAAAA"):
        return valor  # Compatibilidade retroativa: valor legado em texto claro
    try:
        f = _get_fernet()
        return f.decrypt(valor.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        # Falha silenciosa para não quebrar leituras com chave rotacionada
        return valor
