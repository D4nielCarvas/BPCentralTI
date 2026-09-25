"""
Testes de conformidade e integridade do sistema de temas (Theme Toggle)
Valida a presença de seletores CSS, variáveis da Branco Peres, scripts anti-FOUC e integração nos templates.
"""
import os
import re
import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_theme_js_exists_and_implements_singleton():
    theme_js_path = os.path.join(BASE_DIR, "static", "js", "theme.js")
    assert os.path.exists(theme_js_path), "Arquivo static/js/theme.js deve existir."
    
    with open(theme_js_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Validações estruturais e de boas práticas
    assert "ThemeManager" in content, "ThemeManager deve ser exportado."
    assert "toggleTheme" in content, "Método toggleTheme deve estar presente."
    assert "setTheme" in content, "Método setTheme deve estar presente."
    assert "sanitizeTheme" in content, "Função de sanitização contra injeção de estado deve existir."
    assert "bp_central_ti_theme" in content, "Chave do localStorage deve ser 'bp_central_ti_theme'."
    assert "data-theme" in content, "Manipulação do atributo data-theme deve estar presente."


def test_admin_css_has_light_and_dark_themes():
    css_path = os.path.join(BASE_DIR, "static", "css", "admin.css")
    assert os.path.exists(css_path), "static/css/admin.css deve existir."

    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()

    # Valida seletores de tema
    assert 'html[data-theme="dark"]' in css or ':root' in css
    assert 'html[data-theme="light"]' in css, "Modo claro deve estar declarado em admin.css."
    
    # Valida a cor institucional Branco Peres no modo claro
    assert "#005221" in css, "Cor institucional Branco Peres (#005221) deve estar presente no tema claro."
    assert ".theme-toggle-btn" in css, "Estilos do botão theme-toggle-btn devem estar em admin.css."


def test_global_css_has_light_and_dark_themes():
    css_path = os.path.join(BASE_DIR, "static", "css", "global.css")
    assert os.path.exists(css_path), "static/css/global.css deve existir."

    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()

    assert 'html[data-theme="light"]' in css, "Modo claro deve estar declarado em global.css."
    assert "#005221" in css, "Cor institucional Branco Peres (#005221) deve estar presente em global.css."


def test_index_html_has_anti_fouc_and_toggle_button():
    index_path = os.path.join(BASE_DIR, "templates", "index.html")
    assert os.path.exists(index_path), "templates/index.html deve existir."

    with open(index_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Anti-FOUC no head
    head_match = re.search(r"<head>(.*?)</head>", html, re.DOTALL | re.IGNORECASE)
    assert head_match is not None, "Tag <head> deve estar presente."
    head_content = head_match.group(1)

    assert "bp_central_ti_theme" in head_content, "Anti-FOUC deve ler 'bp_central_ti_theme' dentro do <head>."
    assert "data-theme" in head_content, "Anti-FOUC deve setar data-theme antes do render do body."
    assert "theme.js" in head_content, "theme.js deve ser importado no <head>."

    # Botão de toggle
    assert 'id="theme-toggle-btn"' in html, "Botão com id theme-toggle-btn deve existir."
    assert "ThemeManager.toggleTheme()" in html, "Clique do botão deve invocar ThemeManager.toggleTheme()."


def test_base_fazenda_has_anti_fouc_and_toggle_button():
    fazenda_path = os.path.join(BASE_DIR, "templates", "fazenda", "base_fazenda.html")
    assert os.path.exists(fazenda_path), "templates/fazenda/base_fazenda.html deve existir."

    with open(fazenda_path, "r", encoding="utf-8") as f:
        html = f.read()

    assert "bp_central_ti_theme" in html, "Anti-FOUC deve estar presente no base_fazenda.html."
    assert 'id="theme-toggle-btn"' in html, "Botão de tema deve estar presente no portal fazenda."
