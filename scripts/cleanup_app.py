import sys

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read().splitlines()

new_bps_imports = '''
from blueprints.core import core_bp
from blueprints.api_dashboard import api_dashboard_bp
from blueprints.api_descartes import api_descartes_bp
from blueprints.api_transferencias import api_transferencias_bp
from blueprints.api_historico import api_historico_bp
from blueprints.api_import_export import api_import_export_bp
from blueprints.api_busca import api_busca_bp
'''

new_bps_registers = '''
app.register_blueprint(core_bp)
app.register_blueprint(api_dashboard_bp)
app.register_blueprint(api_descartes_bp)
app.register_blueprint(api_transferencias_bp)
app.register_blueprint(api_historico_bp)
app.register_blueprint(api_import_export_bp)
app.register_blueprint(api_busca_bp)
'''

out = []
i = 0
while i < len(content):
    line = content[i]
    if line == 'app.register_blueprint(remessas_bp)':
        out.append(line)
        out.append(new_bps_imports)
        out.append(new_bps_registers)
        i += 1
    elif line.startswith('@app.route("/")'):
        # Skip until @app.errorhandler
        while i < len(content) and not content[i].startswith('@app.errorhandler(Exception)'):
            i += 1
    elif line.startswith('@app.route("/chamados/<int:chamado_id>/poll")'):
        # Skip until def _abrir_navegador() or if __name__ == '__main__':
        while i < len(content) and not content[i].startswith('    def _abrir_navegador()'):
            i += 1
    else:
        out.append(line)
        i += 1

with open('app.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
