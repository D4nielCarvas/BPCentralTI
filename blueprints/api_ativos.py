from flask import Blueprint, request, jsonify, Response
from typing import Any
from datetime import date
import psycopg2

from utils.db_layer import acquire_conn as get_db, fetch_all as _fetch_all, fetch_one as _fetch_one, row_to_dict
from utils.auth_utils import login_required, admin_required, get_fazenda_nome_filter
from utils.crypto_utils import encrypt_field, decrypt_field
from utils.api_utils import _list_table, log_historico, validate_file_mime
from werkzeug.utils import secure_filename

bp = Blueprint('api_ativos', __name__, url_prefix='')

# COMPUTADORES
# ═══════════════════════════════════════════════════════════════════════════════

@bp.route("/api/computadores", methods=["GET"])
@login_required  # P7: exige autenticação para listar
def listar_computadores() -> Response:
    """Lista computadores/notebooks com filtros."""
    return _list_table(
        "computadores",
        [
            "id_ativo", "fazenda", "setor", "responsavel", "cargo", "marca",
            "modelo", "processador", "memoria_ram", "armazenamento",
            "sistema_operacional", "numero_serie", "patrimonio", "usuario_windows",
            "usuario_anterior"
        ],
    )


@bp.route("/api/computadores", methods=["POST"])
@admin_required  # P7: apenas admin pode criar
def criar_computador() -> tuple[Response, int] | Response:
    """Cadastra um novo computador ou notebook."""
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """INSERT INTO computadores
                       (id_ativo,fazenda,setor,responsavel,tipo,modelo,marca,numero_serie,
                        patrimonio,processador,memoria_ram,armazenamento,sistema_operacional,
                        versao_so,status,data_aquisicao,data_entrega,data_devolucao,
                        usuario_windows,senha_windows,usuario_anterior,observacoes,termo_assinado,cargo)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        d["id_ativo"], d.get("fazenda"), d.get("setor"), d.get("responsavel"),
                        d.get("tipo"), d.get("modelo"), d.get("marca"), d.get("numero_serie"),
                        d.get("patrimonio"), d.get("processador"), d.get("memoria_ram"),
                        d.get("armazenamento"), d.get("sistema_operacional"), d.get("versao_so"),
                        d.get("status", "Ativo"), d.get("data_aquisicao"), d.get("data_entrega"),
                        d.get("data_devolucao"), d.get("usuario_windows"), d.get("senha_windows"),
                        d.get("usuario_anterior"), d.get("observacoes"), d.get("termo_assinado"), d.get("cargo"),
                    ),
                )
                log_historico(cur, d["id_ativo"], "Computador", "Cadastro")
            except psycopg2.IntegrityError:
                return jsonify({"ok": False, "msg": "ID de ativo já existe!"}), 400
    return jsonify({"ok": True, "msg": "Computador cadastrado!"})


@bp.route("/api/computadores/<id_ativo>", methods=["GET"])
@login_required  # P7: exige autenticação para consultar
def get_computador(id_ativo: str) -> Response:
    """Retorna dados de um computador pelo ID do ativo."""
    fazenda_nome = get_fazenda_nome_filter()
    with get_db() as conn:
        with conn.cursor() as cur:
            if fazenda_nome:
                row = _fetch_one(cur, "SELECT * FROM computadores WHERE id_ativo=%s AND fazenda=%s", (id_ativo, fazenda_nome))
            else:
                row = _fetch_one(cur, "SELECT * FROM computadores WHERE id_ativo=%s", (id_ativo,))
    return jsonify(row)


@bp.route("/api/computadores/<id_ativo>", methods=["PUT"])
@admin_required  # P7: apenas admin pode editar
def atualizar_computador(id_ativo: str) -> Response:
    """Atualiza dados de um computador existente."""
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE computadores SET
                   fazenda=%s,setor=%s,responsavel=%s,tipo=%s,modelo=%s,marca=%s,
                   numero_serie=%s,patrimonio=%s,processador=%s,memoria_ram=%s,
                   armazenamento=%s,sistema_operacional=%s,versao_so=%s,status=%s,
                   data_aquisicao=%s,data_entrega=%s,data_devolucao=%s,usuario_windows=%s,
                   senha_windows=%s,usuario_anterior=%s,observacoes=%s,termo_assinado=%s,
                   cargo=%s,updated_at=NOW() WHERE id_ativo=%s""",
                (
                    d.get("fazenda"), d.get("setor"), d.get("responsavel"), d.get("tipo"),
                    d.get("modelo"), d.get("marca"), d.get("numero_serie"), d.get("patrimonio"),
                    d.get("processador"), d.get("memoria_ram"), d.get("armazenamento"),
                    d.get("sistema_operacional"), d.get("versao_so"), d.get("status"),
                    d.get("data_aquisicao"), d.get("data_entrega"), d.get("data_devolucao"),
                    d.get("usuario_windows"), d.get("senha_windows"), d.get("usuario_anterior"),
                    d.get("observacoes"), d.get("termo_assinado"), d.get("cargo"), id_ativo,
                ),
            )
            log_historico(cur, id_ativo, "Computador", "Edição")
    return jsonify({"ok": True, "msg": "Computador atualizado!"})


# ═══════════════════════════════════════════════════════════════════════════════
# IMPRESSORAS
# ═══════════════════════════════════════════════════════════════════════════════

@bp.route("/api/impressoras", methods=["GET"])
@login_required  # P7: exige autenticação para listar
def listar_impressoras() -> Response:
    """Lista impressoras com filtros."""
    return _list_table(
        "impressoras",
        [
            "id_ativo", "fazenda", "setor", "responsavel", "marca", "modelo",
            "numero_serie", "ip_rede", "hostname", "patrimonio", "observacoes"
        ],
    )


@bp.route("/api/impressoras", methods=["POST"])
@admin_required  # P7: apenas admin pode criar
def criar_impressora() -> tuple[Response, int] | Response:
    """Cadastra uma nova impressora."""
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """INSERT INTO impressoras
                       (id_ativo,fazenda,setor,responsavel,marca,modelo,tipo,numero_serie,
                        patrimonio,ip_rede,hostname,status,data_aquisicao,data_instalacao,
                        suprimento_atual,observacoes)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        d["id_ativo"], d.get("fazenda"), d.get("setor"), d.get("responsavel"),
                        d.get("marca"), d.get("modelo"), d.get("tipo"), d.get("numero_serie"),
                        d.get("patrimonio"), d.get("ip_rede"), d.get("hostname"),
                        d.get("status", "Ativo"), d.get("data_aquisicao"), d.get("data_instalacao"),
                        d.get("suprimento_atual"), d.get("observacoes"),
                    ),
                )
                log_historico(cur, d["id_ativo"], "Impressora", "Cadastro")
            except psycopg2.IntegrityError:
                return jsonify({"ok": False, "msg": "ID de ativo já existe!"}), 400
    return jsonify({"ok": True, "msg": "Impressora cadastrada!"})


@bp.route("/api/impressoras/<id_ativo>", methods=["GET"])
@login_required  # P7: exige autenticação para consultar
def get_impressora(id_ativo: str) -> Response:
    """Retorna dados de uma impressora."""
    fazenda_nome = get_fazenda_nome_filter()
    with get_db() as conn:
        with conn.cursor() as cur:
            if fazenda_nome:
                row = _fetch_one(cur, "SELECT * FROM impressoras WHERE id_ativo=%s AND fazenda=%s", (id_ativo, fazenda_nome))
            else:
                row = _fetch_one(cur, "SELECT * FROM impressoras WHERE id_ativo=%s", (id_ativo,))
    return jsonify(row)


@bp.route("/api/impressoras/<id_ativo>", methods=["PUT"])
@admin_required  # P7: apenas admin pode editar
def atualizar_impressora(id_ativo: str) -> Response:
    """Atualiza dados de uma impressora."""
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE impressoras SET
                   fazenda=%s,setor=%s,responsavel=%s,marca=%s,modelo=%s,tipo=%s,
                   numero_serie=%s,patrimonio=%s,ip_rede=%s,hostname=%s,status=%s,
                   data_aquisicao=%s,data_instalacao=%s,suprimento_atual=%s,
                   observacoes=%s,updated_at=NOW() WHERE id_ativo=%s""",
                (
                    d.get("fazenda"), d.get("setor"), d.get("responsavel"), d.get("marca"),
                    d.get("modelo"), d.get("tipo"), d.get("numero_serie"), d.get("patrimonio"),
                    d.get("ip_rede"), d.get("hostname"), d.get("status"), d.get("data_aquisicao"),
                    d.get("data_instalacao"), d.get("suprimento_atual"), d.get("observacoes"),
                    id_ativo,
                ),
            )
            log_historico(cur, id_ativo, "Impressora", "Edição")
    return jsonify({"ok": True, "msg": "Impressora atualizada!"})


# ═══════════════════════════════════════════════════════════════════════════════
# ESTABILIZADORES
# ═══════════════════════════════════════════════════════════════════════════════

@bp.route("/api/estabilizadores", methods=["GET"])
@login_required  # P7: exige autenticação para listar
def listar_estabilizadores() -> Response:
    """Lista estabilizadores/nobreakes com filtros."""
    return _list_table(
        "estabilizadores",
        ["id_ativo", "fazenda", "setor", "modelo", "uso", "num_serie"]
    )


@bp.route("/api/estabilizadores", methods=["POST"])
@admin_required  # P7: apenas admin pode criar
def criar_estabilizador() -> tuple[Response, int] | Response:
    """Cadastra um novo estabilizador ou nobreak."""
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "INSERT INTO estabilizadores (id_ativo,fazenda,setor,modelo,status,uso,num_serie) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (
                        d["id_ativo"], d.get("fazenda"), d.get("setor"), d.get("modelo"),
                        d.get("status", "Ativo"), d.get("uso"), d.get("num_serie"),
                    ),
                )
                log_historico(cur, d["id_ativo"], "Estabilizador", "Cadastro")
            except psycopg2.IntegrityError:
                return jsonify({"ok": False, "msg": "ID de ativo já existe!"}), 400
    return jsonify({"ok": True, "msg": "Estabilizador cadastrado!"})


@bp.route("/api/estabilizadores/<id_ativo>", methods=["GET"])
@login_required  # P7: exige autenticação para consultar
def get_estabilizador(id_ativo: str) -> Response:
    """Retorna dados de um estabilizador."""
    fazenda_nome = get_fazenda_nome_filter()
    with get_db() as conn:
        with conn.cursor() as cur:
            if fazenda_nome:
                row = _fetch_one(cur, "SELECT * FROM estabilizadores WHERE id_ativo=%s AND fazenda=%s", (id_ativo, fazenda_nome))
            else:
                row = _fetch_one(cur, "SELECT * FROM estabilizadores WHERE id_ativo=%s", (id_ativo,))
    return jsonify(row)


@bp.route("/api/estabilizadores/<id_ativo>", methods=["PUT"])
@admin_required  # P7: apenas admin pode editar
def atualizar_estabilizador(id_ativo: str) -> Response:
    """Atualiza dados de um estabilizador."""
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE estabilizadores SET
                   fazenda=%s,setor=%s,modelo=%s,status=%s,uso=%s,num_serie=%s,
                   updated_at=NOW() WHERE id_ativo=%s""",
                (
                    d.get("fazenda"), d.get("setor"), d.get("modelo"), d.get("status"),
                    d.get("uso"), d.get("num_serie"), id_ativo,
                ),
            )
            log_historico(cur, id_ativo, "Estabilizador", "Edição")
    return jsonify({"ok": True, "msg": "Estabilizador atualizado!"})


# ═══════════════════════════════════════════════════════════════════════════════
# STARLINK
# ═══════════════════════════════════════════════════════════════════════════════

@bp.route("/api/starlink", methods=["GET"])
@login_required  # P7: exige autenticação para listar
def listar_starlink() -> Response:
    """Lista antenas Starlink com filtros."""
    return _list_table(
        "starlink",
        [
            "id_ativo", "fazenda", "setor", "responsavel", "modelo",
            "num_serie", "mac_address", "ip_rede", "plano", "observacoes"
        ]
    )


@bp.route("/api/starlink", methods=["POST"])
@admin_required  # P7: apenas admin pode criar
def criar_starlink() -> tuple[Response, int] | Response:
    """Cadastra uma nova antena Starlink. Item 7: inclui campos de login."""
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """INSERT INTO starlink
                       (id_ativo,fazenda,setor,responsavel,modelo,num_serie,mac_address,
                        ip_rede,status,data_instalacao,data_aquisicao,plano,observacoes,
                        id_starlink,numero_kit,email_login,senha_login)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        d["id_ativo"], d.get("fazenda"), d.get("setor"), d.get("responsavel"),
                        d.get("modelo"), d.get("num_serie"), d.get("mac_address"), d.get("ip_rede"),
                        d.get("status", "Ativo"), d.get("data_instalacao"), d.get("data_aquisicao"),
                        d.get("plano"), d.get("observacoes"),
                        d.get("id_starlink"), d.get("numero_kit"),
                        d.get("email_login"), encrypt_field(d.get("senha_login")),  # P1: criptografa antes de gravar
                    ),
                )
                log_historico(cur, d["id_ativo"], "Starlink", "Cadastro")
            except psycopg2.IntegrityError:
                return jsonify({"ok": False, "msg": "ID de ativo já existe!"}), 400
    return jsonify({"ok": True, "msg": "Starlink cadastrada!"})


@bp.route("/api/starlink/<id_ativo>", methods=["GET"])
@login_required  # P7: exige autenticação para consultar
def get_starlink(id_ativo: str) -> Response:
    """Retorna dados de uma antena Starlink. P1: descriptografa senha_login antes de retornar."""
    fazenda_nome = get_fazenda_nome_filter()
    with get_db() as conn:
        with conn.cursor() as cur:
            if fazenda_nome:
                row = _fetch_one(cur, "SELECT * FROM starlink WHERE id_ativo=%s AND fazenda=%s", (id_ativo, fazenda_nome))
            else:
                row = _fetch_one(cur, "SELECT * FROM starlink WHERE id_ativo=%s", (id_ativo,))
    if row and row.get("senha_login"):
        row["senha_login"] = decrypt_field(row["senha_login"])  # P1: descriptografa para exibição
    return jsonify(row)


@bp.route("/api/starlink/<id_ativo>", methods=["PUT"])
@admin_required  # P7: apenas admin pode editar
def atualizar_starlink(id_ativo: str) -> Response:
    """Atualiza dados de uma antena Starlink. Item 7: inclui campos de login."""
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE starlink SET
                   fazenda=%s,setor=%s,responsavel=%s,modelo=%s,num_serie=%s,mac_address=%s,
                   ip_rede=%s,status=%s,data_instalacao=%s,data_aquisicao=%s,plano=%s,
                   observacoes=%s,id_starlink=%s,numero_kit=%s,email_login=%s,senha_login=%s,
                   updated_at=NOW() WHERE id_ativo=%s""",
                (
                    d.get("fazenda"), d.get("setor"), d.get("responsavel"), d.get("modelo"),
                    d.get("num_serie"), d.get("mac_address"), d.get("ip_rede"), d.get("status"),
                    d.get("data_instalacao"), d.get("data_aquisicao"), d.get("plano"),
                    d.get("observacoes"),
                    d.get("id_starlink"), d.get("numero_kit"),
                    d.get("email_login"), encrypt_field(d.get("senha_login")),  # P1: criptografa antes de gravar
                    id_ativo,
                ),
            )
            log_historico(cur, id_ativo, "Starlink", "Edição")
    return jsonify({"ok": True, "msg": "Starlink atualizada!"})


# ═══════════════════════════════════════════════════════════════════════════════
# CELULARES TURMA (Item 4)
# ═══════════════════════════════════════════════════════════════════════════════

@bp.route("/api/celulares_turma", methods=["GET"])
@login_required  # P7: exige autenticação para listar
def listar_celulares_turma() -> Response:
    """Lista celulares de turma com filtros de status e busca textual."""
    return _list_table(
        "celulares_turma",
        [
            "id_ativo", "num_turma", "responsavel", "fazenda", "setor", "modelo",
            "num_serie", "imei_1", "gmail_clockin", "usuario_anterior"
        ],
    )


@bp.route("/api/celulares_turma", methods=["POST"])
@admin_required  # P7: apenas admin pode criar
def criar_celular_turma() -> tuple[Response, int] | Response:
    """Cadastra um novo celular de turma (ID no formato CL-TRM-NN)."""
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """INSERT INTO celulares_turma
                       (id_ativo,num_turma,responsavel,fazenda,setor,modelo,tipo,status,
                        uso_celular,carregador,termo_assinado,data_entrega,data_devolucao,
                        gmail_clockin,senha,usuario_anterior,imei_1,imei_2,num_serie,
                        armazenamento,observacoes)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        d["id_ativo"], d.get("num_turma"), d.get("responsavel"),
                        d.get("fazenda"), d.get("setor"), d.get("modelo"), d.get("tipo"),
                        d.get("status", "Ativo"), d.get("uso_celular"), d.get("carregador"),
                        d.get("termo_assinado"), d.get("data_entrega"), d.get("data_devolucao"),
                        d.get("gmail_clockin"), encrypt_field(d.get("senha")), d.get("usuario_anterior"),  # P1: criptografa senha
                        d.get("imei_1"), d.get("imei_2"), d.get("num_serie"),
                        d.get("armazenamento"), d.get("observacoes"),
                    ),
                )
                log_historico(cur, d["id_ativo"], "Celular Turma", "Cadastro")
            except psycopg2.IntegrityError:
                return jsonify({"ok": False, "msg": "ID de ativo já existe!"}), 400
    return jsonify({"ok": True, "msg": "Celular de turma cadastrado!"})


@bp.route("/api/celulares_turma/<id_ativo>", methods=["GET"])
@login_required  # P7: exige autenticação para consultar
def get_celular_turma(id_ativo: str) -> Response:
    """Retorna dados de um celular de turma. P1: descriptografa senha antes de retornar."""
    fazenda_nome = get_fazenda_nome_filter()
    with get_db() as conn:
        with conn.cursor() as cur:
            if fazenda_nome:
                row = _fetch_one(cur, "SELECT * FROM celulares_turma WHERE id_ativo=%s AND fazenda=%s", (id_ativo, fazenda_nome))
            else:
                row = _fetch_one(cur, "SELECT * FROM celulares_turma WHERE id_ativo=%s", (id_ativo,))
    if row and row.get("senha"):
        row["senha"] = decrypt_field(row["senha"])  # P1: descriptografa para exibição
    return jsonify(row)


@bp.route("/api/celulares_turma/<id_ativo>", methods=["PUT"])
@admin_required  # P7: apenas admin pode editar
def atualizar_celular_turma(id_ativo: str) -> Response:
    """Atualiza dados de um celular de turma."""
    d = request.json
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE celulares_turma SET
                   num_turma=%s,responsavel=%s,fazenda=%s,setor=%s,modelo=%s,tipo=%s,
                   status=%s,uso_celular=%s,carregador=%s,termo_assinado=%s,data_entrega=%s,
                   data_devolucao=%s,gmail_clockin=%s,senha=%s,usuario_anterior=%s,
                   imei_1=%s,imei_2=%s,num_serie=%s,armazenamento=%s,observacoes=%s,
                   updated_at=NOW() WHERE id_ativo=%s""",
                (
                    d.get("num_turma"), d.get("responsavel"), d.get("fazenda"), d.get("setor"),
                    d.get("modelo"), d.get("tipo"), d.get("status"), d.get("uso_celular"),
                    d.get("carregador"), d.get("termo_assinado"), d.get("data_entrega"),
                    d.get("data_devolucao"), d.get("gmail_clockin"), encrypt_field(d.get("senha")),  # P1: criptografa senha
                    d.get("usuario_anterior"), d.get("imei_1"), d.get("imei_2"),
                    d.get("num_serie"), d.get("armazenamento"), d.get("observacoes"),
                    id_ativo,
                ),
            )
            log_historico(cur, id_ativo, "Celular Turma", "Edição")
    return jsonify({"ok": True, "msg": "Celular de turma atualizado!"})


# ═══════════════════════════════════════════════════════════════════════════════


@bp.route("/api/ativos/<id_ativo>")
def get_ativo_universal(id_ativo: str) -> tuple[Response, int] | Response:
    """
    Busca um ativo em todas as tabelas de equipamentos pelo ID.

    Usado pela aba de Manutenção para autopreenchimento de campos.
    Complexidade: O(k) onde k = número de tabelas (~8 queries no pior caso).

    Args:
        id_ativo: ID do ativo no padrão TIPO-LOCAL-SETOR-NN ou CL-TRM-NN.

    Returns:
        JSON com os dados do ativo + campo 'tipo_equipamento', ou 404.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            for tabela, tipo_nome in _TABELAS_ATIVO_BUSCA:
                row = _fetch_one(
                    cur,
                    f"SELECT * FROM {tabela} WHERE id_ativo=%s",
                    (id_ativo,),
                )
                if row:
                    row["tipo_equipamento"] = tipo_nome
                    return jsonify(row)

    return jsonify({"ok": False, "msg": f"Ativo '{id_ativo}' não encontrado"}), 404


@bp.route("/api/upload_termo/<tipo>/<id_ativo>", methods=["POST"])
def upload_termo(tipo: str, id_ativo: str) -> tuple[Response, int] | Response:
    """
    Recebe e salva o PDF do termo de responsabilidade de um ativo.

    Atualiza o campo termo_pdf na tabela correspondente ao tipo informado.

    Args:
        tipo: Tipo do ativo ('celular', 'celular_ponto', 'computador').
        id_ativo: Identificador único do ativo.

    Returns:
        JSON com resultado da operação.
    """
    tipo_key = tipo.replace(" ", "_")
    
    if "file" not in request.files:
        return jsonify({"ok": False, "msg": "Nenhum arquivo enviado"}), 400

    file = request.files["file"]
    if not file.filename or not validate_file_mime(file, {"application/pdf"}):
        return jsonify({"ok": False, "msg": "Tipo de arquivo não permitido. Envie apenas PDF."}), 400

    safe_name = f"{tipo_key}_{secure_filename(id_ativo)}.pdf"
    
    file.seek(0)
    file_bytes = file.read()
    
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO arquivos_storage (nome_arquivo, dados, mimetype) 
                   VALUES (%s, %s, %s)
                   ON CONFLICT (nome_arquivo) DO UPDATE SET dados=EXCLUDED.dados, criado_em=CURRENT_TIMESTAMP""",
                (safe_name, psycopg2.Binary(file_bytes), file.mimetype)
            )

    tabela_map = {
        "celular": "celulares",
        "celular_ponto": "celulares_ponto",
        "celular_inspecao": "celulares_inspecao",
        "celular_turma": "celulares_turma",
        "computador": "computadores",
        "starlink": "starlink",
    }
    tabela = tabela_map.get(tipo_key)

    if tabela:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE {tabela} SET termo_pdf=%s WHERE id_ativo=%s",
                    (safe_name, id_ativo),
                )
                log_historico(cur, id_ativo, tipo_key, "PDF Termo Anexado")
    else:
        return jsonify({"ok": False, "msg": f"Tipo de ativo desconhecido: {tipo}"}), 400
 
    return jsonify({"ok": True, "msg": "PDF anexado!", "filename": safe_name})

