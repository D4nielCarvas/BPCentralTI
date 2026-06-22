import os
import uuid
from flask import Blueprint, request, jsonify, session
from werkzeug.utils import secure_filename
from utils.db_layer import acquire_conn, fetch_all, fetch_one
from utils.auth_utils import has_permission, get_usuario_id
from utils.storage_utils import upload_file_to_supabase, delete_file_from_supabase, get_public_url

bp = Blueprint('api_tutoriais', __name__, url_prefix='/api/tutoriais')

ALLOWED_EXTENSIONS = {'mp4', 'webm', 'png', 'jpg', 'jpeg', 'gif'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB em bytes

def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@bp.route('', methods=['GET'])
def listar_tutoriais():
    """
    Contextualização Técnica: Rota para listar todos os tutoriais disponíveis.
    Análise de Impacto: O(1) de tempo, filtrando apenas pela data de criação.
    """
    if 'usuario_id' not in session:
        return jsonify({"ok": False, "msg": "Não autenticado"}), 401

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            tutoriais = fetch_all(cur, """
                SELECT t.id, t.titulo, t.descricao, t.mimetype, t.url_arquivo, t.criado_em,
                       u.nome as autor
                FROM tutoriais t
                LEFT JOIN usuarios u ON t.criado_por = u.id
                ORDER BY t.criado_em DESC
            """)
            
    # Formata a data se necessário
    for t in tutoriais:
        if isinstance(t.get("criado_em"), str):
            t["criado_em"] = t["criado_em"][:16].replace("T", " ")
        elif t.get("criado_em"):
            t["criado_em"] = t["criado_em"].strftime("%Y-%m-%d %H:%M")

    return jsonify({"ok": True, "data": tutoriais})

@bp.route('/upload', methods=['POST'])
def upload_tutorial():
    """
    Contextualização Técnica: Rota para upload de um novo tutorial (vídeo/imagem).
    Acesso restrito a administradores. Limite de 50MB.
    Integração com Supabase Storage.
    Análise de Impacto: Carga de I/O O(N) no upload para bucket S3.
    """
    if not session.get('is_admin_master') and session.get('role') != 'admin':
        return jsonify({"ok": False, "msg": "Acesso negado."}), 403

    if 'file' not in request.files:
        return jsonify({"ok": False, "msg": "Nenhum arquivo enviado."}), 400

    file = request.files['file']
    titulo = request.form.get('titulo', '').strip()
    descricao = request.form.get('descricao', '').strip()

    if not titulo:
        return jsonify({"ok": False, "msg": "O título é obrigatório."}), 400

    if file.filename == '':
        return jsonify({"ok": False, "msg": "Nenhum arquivo selecionado."}), 400

    if not allowed_file(file.filename):
        return jsonify({"ok": False, "msg": "Extensão não permitida."}), 400

    # Validação de tamanho
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    if file_size > MAX_FILE_SIZE:
        return jsonify({"ok": False, "msg": "Arquivo excede o limite de 50MB."}), 400
    file.seek(0) # Volta o ponteiro
    
    file_bytes = file.read()
    mimetype = file.content_type
    
    # Gerar nome único para o Supabase
    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}.{ext}"
    
    bucket_name = "tutoriais"
    
    # Faz o upload para o bucket
    sucesso = upload_file_to_supabase(bucket_name, unique_filename, file_bytes, mimetype)
    if not sucesso:
        return jsonify({"ok": False, "msg": "Erro ao fazer upload para o Supabase Storage. Verifique SUPABASE_URL e SUPABASE_KEY no .env."}), 500

    url_arquivo = get_public_url(bucket_name, unique_filename)

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO tutoriais (titulo, descricao, nome_arquivo, mimetype, url_arquivo, tamanho_bytes, criado_por)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (titulo, descricao, unique_filename, mimetype, url_arquivo, file_size, get_usuario_id()))
            novo_id = cur.fetchone()["id"]
            conn.commit()

    return jsonify({"ok": True, "msg": "Tutorial criado com sucesso!", "id": novo_id})

@bp.route('/<tutorial_id>', methods=['DELETE'])
def delete_tutorial(tutorial_id):
    """
    Contextualização Técnica: Deleta um tutorial e o arquivo correspondente do Supabase.
    """
    if not session.get('is_admin_master') and session.get('role') != 'admin':
        return jsonify({"ok": False, "msg": "Acesso negado."}), 403

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            tut = fetch_one(cur, "SELECT nome_arquivo FROM tutoriais WHERE id = %s", (tutorial_id,))
            if not tut:
                return jsonify({"ok": False, "msg": "Tutorial não encontrado."}), 404
            
            nome_arquivo = tut["nome_arquivo"]
            
            # Deletar no Supabase Storage
            delete_file_from_supabase("tutoriais", nome_arquivo)
            
            # Deletar no banco
            cur.execute("DELETE FROM tutoriais WHERE id = %s", (tutorial_id,))
            conn.commit()

    return jsonify({"ok": True, "msg": "Tutorial deletado com sucesso."})
