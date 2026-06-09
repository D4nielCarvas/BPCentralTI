import csv
import io
from datetime import date
from typing import Any
from flask import Blueprint, jsonify, request, Response
from utils.auth_utils import login_required, admin_required
from utils.db_layer import acquire_conn, fetch_all, fetch_one
from utils.api_utils import log_historico

api_import_export_bp = Blueprint('api_import_export', __name__)

@api_import_export_bp.route("/api/exportar/<tabela>")
@login_required
def exportar(tabela: str) -> Response:
    """Exporta todos os dados de uma tabela em formato CSV. Datas em DD/MM/AAAA."""
    tabelas_validas = {
        "celulares", "celulares_ponto", "celulares_inspecao", "celulares_turma",
        "computadores", "impressoras",
        "estabilizadores", "starlink", "manutencoes", "descartes", "estoque", "toners",
        "transferencias", "historico", "estoque_equipamentos", "pedidos",
    }
    if tabela not in tabelas_validas:
        return jsonify({"ok": False, "msg": "Tabela inválida"}), 400

    _DATE_FIELDS = {
        "data_entrega", "data_devolucao", "data_transferencia", "data_recebimento",
        "data_descarte", "data_pedido", "data_instalacao", "data_aquisicao",
        "data_manutencao", "data_envio", "data_retorno", "data_ultima_troca",
    }

    def _fmt_date(val: Any) -> Any:
        if val is None:
            return ""
        if hasattr(val, "strftime"):
            return val.strftime("%d/%m/%Y")
        if isinstance(val, str) and len(val) >= 10 and val[4] == "-":
            try:
                parts = val[:10].split("-")
                return f"{parts[2]}/{parts[1]}/{parts[0]}"
            except (IndexError, ValueError):
                return val
        return val

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            if tabela == "estoque_equipamentos":
                tabelas = [
                    ("celulares",       "Celular"),
                    ("celulares_ponto", "Celular Ponto"),
                    ("celulares_inspecao", "Celular Inspeção"),
                    ("celulares_turma", "Celular Turma"),
                    ("computadores",    "Computador"),
                    ("impressoras",     "Impressora"),
                    ("estabilizadores", "Estabilizador"),
                    ("starlink",        "Starlink"),
                ]
                query_parts = []
                for tbl, label in tabelas:
                    query_parts.append(
                        f"SELECT id_ativo, modelo, fazenda, '{label}' as tipo_equipamento, status "
                        f"FROM {tbl} WHERE status = 'Estoque'"
                    )
                rows = fetch_all(cur, " UNION ALL ".join(query_parts) + " ORDER BY id_ativo ASC")
            else:
                rows = fetch_all(cur, f"SELECT * FROM {tabela}")

    if not rows:
        return jsonify({"ok": False, "msg": "Sem dados para exportar"}), 404

    rows_export = []
    for row in rows:
        row_conv = dict(row)
        for field in _DATE_FIELDS:
            if field in row_conv:
                row_conv[field] = _fmt_date(row_conv[field])
        rows_export.append(row_conv)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows_export[0].keys())
    writer.writeheader()
    writer.writerows(rows_export)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={tabela}.csv"},
    )


@api_import_export_bp.route("/api/importar_coleta", methods=["POST"])
@admin_required
def importar_coleta() -> Response:
    """Importa dados coletados automaticamente pelo COLETAR_PC.bat."""
    if "file" not in request.files:
        return jsonify({"ok": False, "msg": "Arquivo .txt não enviado"}), 400

    id_ativo = request.form.get("id_ativo", "").strip()
    fazenda = request.form.get("fazenda", "").strip()
    setor_form = request.form.get("setor", "").strip()

    if not id_ativo:
        return jsonify({"ok": False, "msg": "Campo id_ativo é obrigatório"}), 400

    file = request.files["file"]
    try:
        conteudo = file.read().decode("utf-8", errors="replace")
        dados_coleta: dict[str, str] = {}
        for linha in conteudo.splitlines():
            linha = linha.strip()
            if "=" in linha and not linha.startswith("#"):
                chave, _, valor = linha.partition("=")
                dados_coleta[chave.strip().lower()] = valor.strip()
    except Exception as exc:
        return jsonify({"ok": False, "msg": f"Erro ao processar arquivo: {exc}"}), 400

    campos_obrigatorios = ["num_serie", "modelo", "marca"]
    ausentes = [c for c in campos_obrigatorios if not dados_coleta.get(c)]
    if ausentes:
        return jsonify({"ok": False, "msg": f"Campos obrigatórios ausentes no .txt: {ausentes}"}), 400

    mapa: dict[str, str] = {
        "num_serie": dados_coleta.get("num_serie"),
        "marca": dados_coleta.get("marca"),
        "modelo": dados_coleta.get("modelo"),
        "processador": dados_coleta.get("processador"),
        "memoria_ram": dados_coleta.get("memoria_ram"),
        "armazenamento": dados_coleta.get("armazenamento"),
        "sistema_operacional": dados_coleta.get("sistema_operacional"),
        "versao_so": dados_coleta.get("versao_so"),
        "usuario_windows": dados_coleta.get("usuario"),
        "ip_rede": dados_coleta.get("ip"),
    }

    hoje = date.today().isoformat()

    with acquire_conn() as conn:
        with conn.cursor() as cur:
            existente_por_serie = fetch_one(
                cur,
                "SELECT id_ativo FROM computadores WHERE numero_serie=%s",
                (mapa["num_serie"],),
            )

            if existente_por_serie:
                id_existente = existente_por_serie["id_ativo"]
                cur.execute(
                    """UPDATE computadores SET
                       processador=%s,memoria_ram=%s,armazenamento=%s,
                       sistema_operacional=%s,versao_so=%s,usuario_windows=%s,
                       updated_at=NOW() WHERE numero_serie=%s""",
                    (
                        mapa["processador"], mapa["memoria_ram"], mapa["armazenamento"],
                        mapa["sistema_operacional"], mapa["versao_so"], mapa["usuario_windows"],
                        mapa["num_serie"],
                    ),
                )
                log_historico(
                    cur, id_existente, "Computador",
                    f"Atualização via Coleta Automática | IP: {mapa.get('ip_rede', '-')}",
                )
                acao = "atualizado"
                id_retorno = id_existente
            else:
                conflito = fetch_one(
                    cur,
                    "SELECT numero_serie FROM computadores WHERE id_ativo=%s",
                    (id_ativo,),
                )
                if conflito and conflito["numero_serie"] != mapa["num_serie"]:
                    return jsonify({
                        "ok": False,
                        "msg": f"ID {id_ativo} já existe com número de série diferente ({conflito['numero_serie']})",
                    }), 409

                cur.execute(
                    """INSERT INTO computadores
                       (id_ativo,fazenda,setor,marca,modelo,numero_serie,processador,
                        memoria_ram,armazenamento,sistema_operacional,versao_so,
                        usuario_windows,status,data_entrega)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'Ativo',%s)""",
                    (
                        id_ativo, fazenda, setor_form, mapa["marca"], mapa["modelo"],
                        mapa["num_serie"], mapa["processador"], mapa["memoria_ram"],
                        mapa["armazenamento"], mapa["sistema_operacional"], mapa["versao_so"],
                        mapa["usuario_windows"], hoje,
                    ),
                )
                log_historico(
                    cur, id_ativo, "Computador",
                    f"Cadastro via Coleta Automática | IP: {mapa.get('ip_rede', '-')}",
                )
                acao = "criado"
                id_retorno = id_ativo

    return jsonify({"ok": True, "acao": acao, "id_ativo": id_retorno, "dados": mapa})


@api_import_export_bp.route("/api/utils/parse-coleta", methods=["POST"])
def parse_coleta() -> Response:
    """Recebe um arquivo .txt gerado pelo COLETAR_PC.bat e retorna os campos mapeados."""
    if 'file' not in request.files:
        return jsonify({"ok": False, "msg": "Nenhum arquivo enviado"}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({"ok": False, "msg": "Arquivo vazio"}), 400

    try:
        content_bytes = file.read()
        try:
            content = content_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            content = content_bytes.decode("utf-8", errors="replace")

        mapping: dict[str, str] = {
            "tipo":                "tipo",
            "marca":               "marca",
            "modelo":              "modelo",
            "num_serie":           "numero_serie",
            "processador":         "processador",
            "memoria_ram":         "memoria_ram",
            "armazenamento":       "armazenamento",
            "sistema_operacional": "sistema_operacional",
            "versao_so":           "versao_so",
            "ip_rede":             "ip_rede",
            "mac_address":         "mac_address",
            "usuario":             "usuario_windows",
        }

        data: dict[str, Any] = {}
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("[") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip().lower()
            val = val.strip()
            if key in mapping and val:
                data[mapping[key]] = val

        if not data:
            return jsonify({"ok": False, "msg": "Arquivo inválido ou sem dados reconhecíveis"}), 422

        return jsonify({"ok": True, "data": data})
    except Exception as e:
        return jsonify({"ok": False, "msg": f"Erro ao processar arquivo: {str(e)}"}), 500
