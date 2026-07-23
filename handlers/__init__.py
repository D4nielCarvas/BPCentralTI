"""handlers/__init__.py — Exportações públicas do pacote de handlers."""

from handlers.base_handler import TransferenciaHandler
from handlers.handler_estoque_usuario import EstoqueParaUsuarioHandler
from handlers.handler_usuario_estoque import UsuarioParaEstoqueHandler
from handlers.handler_usuario_usuario import UsuarioParaUsuarioHandler
from handlers.handler_usuario_turma import UsuarioParaTurmaHandler

__all__ = [
    "TransferenciaHandler",
    "EstoqueParaUsuarioHandler",
    "UsuarioParaEstoqueHandler",
    "UsuarioParaUsuarioHandler",
    "UsuarioParaTurmaHandler",
]
