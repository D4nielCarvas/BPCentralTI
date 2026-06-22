import os
import json
import urllib.request
import urllib.error
from typing import Optional

def get_supabase_storage_url() -> Optional[str]:
    """Retorna a URL base do Supabase Storage ou None se não configurado."""
    supabase_url = os.environ.get("SUPABASE_URL")
    if not supabase_url:
        return None
    # Remove barra final se existir
    return f"{supabase_url.rstrip('/')}/storage/v1/object"

def get_supabase_headers() -> dict:
    """Retorna os headers necessários para a API REST do Supabase."""
    supabase_key = os.environ.get("SUPABASE_KEY")
    return {
        "Authorization": f"Bearer {supabase_key}",
        "apikey": supabase_key,
    }

def upload_file_to_supabase(bucket: str, file_path: str, file_bytes: bytes, content_type: str) -> bool:
    """
    Faz upload de um arquivo para o bucket do Supabase via REST API.
    
    Complexidade: O(N) onde N é o tamanho do arquivo em bytes (enviado via rede).
    
    Args:
        bucket: Nome do bucket (ex: 'tutoriais')
        file_path: Caminho do arquivo dentro do bucket (ex: 'video.mp4')
        file_bytes: Conteúdo do arquivo em bytes
        content_type: Mimetype do arquivo (ex: 'video/mp4')
        
    Returns:
        True se sucesso, False caso contrário.
    """
    base_url = get_supabase_storage_url()
    if not base_url:
        raise ValueError("SUPABASE_URL não configurado no .env")
        
    url = f"{base_url}/{bucket}/{file_path}"
    headers = get_supabase_headers()
    headers["Content-Type"] = content_type
    
    req = urllib.request.Request(url, data=file_bytes, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as response:
            return response.status in (200, 201)
    except urllib.error.HTTPError as e:
        # Se retornar 400+, houve erro. 409 significa que já existe.
        print(f"Erro no upload para Supabase: {e.code} - {e.read().decode('utf-8')}")
        return False
    except Exception as e:
        print(f"Erro na conexão com Supabase: {e}")
        return False

def delete_file_from_supabase(bucket: str, file_path: str) -> bool:
    """Remove um arquivo do bucket do Supabase."""
    base_url = get_supabase_storage_url()
    if not base_url:
        return False
        
    url = f"{base_url}/{bucket}/{file_path}"
    headers = get_supabase_headers()
    
    req = urllib.request.Request(url, headers=headers, method="DELETE")
    try:
        with urllib.request.urlopen(req) as response:
            return response.status in (200, 204)
    except urllib.error.HTTPError as e:
        print(f"Erro na deleção do Supabase: {e.code} - {e.read().decode('utf-8')}")
        return False
    except Exception as e:
        return False

def get_public_url(bucket: str, file_path: str) -> Optional[str]:
    """Retorna a URL pública do arquivo (assumindo que o bucket é público)."""
    supabase_url = os.environ.get("SUPABASE_URL")
    if not supabase_url:
        return None
    return f"{supabase_url.rstrip('/')}/storage/v1/object/public/{bucket}/{file_path}"
