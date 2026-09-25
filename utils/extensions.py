"""
Extensões do Flask compartilhadas entre a aplicação e os blueprints.
Evita importações circulares entre app.py e os módulos em blueprints/.
"""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri="memory://",
)
