from app import app

print("Registered Routes:")
for rule in app.url_map.iter_rules():
    print(f"{rule.endpoint:50s} {rule.methods} {rule}")

# Specific check for the failing routes
failing = ["api_sugerir_id_turma", "listar_celulares_turma"]
print("\nChecking specifically for:")
for endpoint in failing:
    found = any(rule.endpoint == endpoint for rule in app.url_map.iter_rules())
    print(f"{endpoint}: {'FOUND' if found else 'NOT FOUND'}")
