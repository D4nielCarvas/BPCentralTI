"""
crypto_utils.py — Utilitários de criptografia simétrica para campos sensíveis.

Usa Fernet (AES-128-CBC + HMAC-SHA256) da biblioteca `cryptography`.
A chave é lida da variável de ambiente FERNET_KEY, gerada uma vez e
armazenada no .env.

Gere a chave com:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Uso:
    from crypto_utils import encrypt_field, decrypt_field

    # Antes de gravar no banco
    senha_enc = encrypt_field(senha_plain)  # → "gAAAAA..."

    # Ao ler do banco para exibir
    senha_plain = decrypt_field(senha_enc)  # → "senha original"

Segurança:
    - Nunca armazene a FERNET_KEY no controle de versão.
    - Se a chave for comprometida, rotacione com MultiFernet.
    - Campos criptografados não são pesquisáveis (ILIKE não funciona).

Complexidade:
    - encrypt/decrypt: O(n) onde n = tamanho do campo — desprezível para senhas.
"""

from __future__ import annotations

import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


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
