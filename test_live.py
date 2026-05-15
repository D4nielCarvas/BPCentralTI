import subprocess
import time
import requests

# Start the app
print("Iniciando app...")
proc = subprocess.Popen(["python", "app.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
time.sleep(3) # Wait for startup

# Try to make a request
try:
    # Need to login first to get cookies!
    session = requests.Session()
    print("Criando usuario e logando...")
    # Register viewer
    session.post("http://localhost:5000/cadastro", data={
        "nome": "Test Viewer",
        "username": "testviewer",
        "email": "testviewer@empresa.com",
        "senha": "password123",
        "localidade_id": "1"
    })
    login_resp = session.post("http://localhost:5000/login", data={
        "email": "testviewer@empresa.com",
        "senha": "password123"
    })
    print("Login status:", login_resp.status_code)
    
    # Now try to create order
    print("Tentando POST pedido...")
    resp = session.post("http://localhost:5000/fazenda/pedidos/novo", data={
        "descricao": "Teste server real",
        "localidade_id": "1"
    })
    print("POST pedido status:", resp.status_code)
    if resp.status_code == 500:
        print(resp.text)
        
    print("Tentando POST chamado...")
    resp2 = session.post("http://localhost:5000/fazenda/chamados/novo", data={
        "titulo": "Teste",
        "descricao": "Teste server real chamado",
        "prioridade": "media",
        "localidade_id": "1"
    })
    print("POST chamado status:", resp2.status_code)
    if resp2.status_code == 500:
        print(resp2.text)

except Exception as e:
    print("Erro no script:", e)

# Terminate app
proc.terminate()
stdout, stderr = proc.communicate()
print("\n--- STDERR ---")
print(stderr)
