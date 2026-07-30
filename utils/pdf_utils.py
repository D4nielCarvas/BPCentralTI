import os
from fpdf import FPDF
from datetime import datetime
import io

class TermoResponsabilidadePDF(FPDF):
    def header(self):
        # Configurar fonte
        self.set_font('helvetica', '', 9)
        
        # Larguras das colunas
        col1_w = 40
        col2_w = 120
        col3_w = 30
        
        x_start = self.get_x()
        y_start = self.get_y()
        
        # Desenhar bordas da tabela
        # Linha superior
        self.line(x_start, y_start, x_start + col1_w + col2_w + col3_w, y_start)
        
        # Coluna 1 (Logo + Codigo)
        self.set_xy(x_start, y_start)
        logo_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'logo.png')
        if os.path.exists(logo_path):
            self.image(logo_path, x=x_start + 10, y=y_start + 2, w=20)
            self.cell(col1_w, 20, '', border='LTR', align='C')
        else:
            self.cell(col1_w, 20, 'LOGO BP', border='LTR', align='C')
            
        self.set_xy(x_start, y_start + 20)
        self.set_font('helvetica', 'B', 8)
        self.cell(col1_w, 5, 'Código', border='LR', align='C')
        self.set_xy(x_start, y_start + 25)
        self.set_font('helvetica', '', 8)
        self.cell(col1_w, 5, 'BP - RH 001', border='LBR', align='C')
        
        # Coluna 2 (Título)
        self.set_xy(x_start + col1_w, y_start)
        self.set_font('helvetica', 'B', 14)
        self.set_text_color(100, 100, 100) # cinza
        self.multi_cell(col2_w, 15, 'TERMO DE CIÊNCIA E\nRESPONSABILIDADE', border=1, align='C')
        
        # Coluna 3 (Emissão e Versão)
        self.set_font('helvetica', 'B', 8)
        self.set_xy(x_start + col1_w + col2_w, y_start)
        self.cell(col3_w, 7, 'Emissão', border='LTR', align='C')
        self.set_xy(x_start + col1_w + col2_w, y_start + 7)
        self.set_font('helvetica', '', 8)
        hoje = datetime.now().strftime('%d/%m/%Y')
        self.cell(col3_w, 8, hoje, border='LBR', align='C')
        
        self.set_xy(x_start + col1_w + col2_w, y_start + 15)
        self.set_font('helvetica', 'B', 8)
        self.cell(col3_w, 7, 'Versão', border='LTR', align='C')
        self.set_xy(x_start + col1_w + col2_w, y_start + 22)
        self.set_font('helvetica', '', 8)
        self.cell(col3_w, 8, '1.00', border='LBR', align='C')
        
        self.set_text_color(0, 0, 0) # reset to black
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', '', 8)
        self.set_text_color(128)
        
        # Linha
        self.line(self.get_x(), self.get_y(), self.w - self.l_margin, self.get_y())
        self.ln(2)
        
        # Texto do footer
        self.cell(0, 10, 'Branco Peres Agronegocios - Termo de Ciência e Responsabilidade', 0, 0, 'C')
        
        # Numero da pagina
        self.set_x(-20)
        self.cell(0, 10, str(self.page_no()), 0, 0, 'R')

def gerar_termo_equipamentos_pdf(equipamentos):
    """
    Gera o Termo de Responsabilidade em PDF para uma lista de equipamentos.
    Retorna os bytes do PDF.
    
    equipamentos: list of dicts com chaves: tipo_equipamento, modelo, id_ativo, fazenda
    """
    pdf = TermoResponsabilidadePDF()
    pdf.add_page()
    
    # Titulo central
    pdf.ln(10)
    pdf.set_font('helvetica', 'B', 14)
    pdf.cell(0, 10, 'TERMO DE CIÊNCIA E RESPONSABILIDADE', 0, 1, 'C')
    pdf.ln(5)
    
    # Corpo do texto
    pdf.set_font('helvetica', '', 10)
    texto1 = (
        "Declaro para os devidos fins, que se fizerem necessários que recebi para uso durante o exercício "
        "das minhas atribuições ao qual fui contratado Equipamentos diversos tais como, Celular, Computador "
        "Desktop ou Notebook, Tablet, Equipamentos de Tecnologia utilizados para a Agricultura de precisão, "
        "Equipamentos de Proteção Individual, Ferramentas bem como veículos automotores."
    )
    
    texto2 = (
        "E de acordo com a minha função fui treinado e orientado para a correta utilização bem como a "
        "guarda e cuidados necessários para a melhor durabilidade dos Equipamentos/Ferramentas a minha "
        "disposição."
    )
    
    texto3 = (
        "Em caso de dano causado pelo empregado, fica a empregadora autorizada a efetivar o desconto da "
        "importância correspondente ao prejuízo, com fundamento no parágrafo 1º do artigo 462 da CLT, conforme "
        "constam também na Cartilha do Colaborador e Diretriz para Desconto por Prejuízo Causado."
    )
    
    # Justificado com identação na primeira linha
    pdf.multi_cell(0, 6, "        " + texto1, align='J')
    pdf.ln(4)
    pdf.multi_cell(0, 6, "        " + texto2, align='J')
    pdf.ln(4)
    pdf.multi_cell(0, 6, "        " + texto3, align='J')
    pdf.ln(10)
    
    # Tabela de Equipamentos Recebidos
    pdf.set_font('helvetica', 'B', 10)
    pdf.cell(0, 6, "Equipamentos Recebidos:", ln=1)
    pdf.set_font('helvetica', '', 9)
    
    # Cabeçalho da tabelinha de equipamentos
    col_tipo = 40
    col_mod = 70
    col_id = 40
    col_faz = 40
    
    pdf.set_font('helvetica', 'B', 9)
    pdf.cell(col_tipo, 6, "Tipo", border=1)
    pdf.cell(col_mod, 6, "Modelo", border=1)
    pdf.cell(col_id, 6, "ID/Série", border=1)
    pdf.cell(col_faz, 6, "Fazenda", border=1)
    pdf.ln()
    
    pdf.set_font('helvetica', '', 9)
    for eq in equipamentos:
        tipo = str(eq.get('tipo_equipamento') or '-')
        modelo = str(eq.get('modelo') or '-')
        id_ativo = str(eq.get('id_ativo') or '-')
        fazenda = str(eq.get('fazenda') or '-')
        
        pdf.cell(col_tipo, 6, tipo[:20], border=1)
        pdf.cell(col_mod, 6, modelo[:35], border=1)
        pdf.cell(col_id, 6, id_ativo[:20], border=1)
        pdf.cell(col_faz, 6, fazenda[:20], border=1)
        pdf.ln()
    
    pdf.ln(15)
    
    # Frase final
    pdf.set_font('helvetica', '', 10)
    pdf.cell(0, 6, "Por ser esta a expressão da verdade, firmo o presente.", align='R', ln=1)
    pdf.ln(10)
    
    # Local e Data
    hoje = datetime.now()
    meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
    mes_extenso = meses[hoje.month - 1]
    
    data_str = f"Itápolis-SP, {hoje.day:02d} de {mes_extenso} de {hoje.year}."
    pdf.cell(0, 6, data_str, align='R', ln=1)
    
    pdf.ln(25)
    
    # Assinaturas
    x_center = pdf.w / 2
    
    # Linha de assinatura
    pdf.line(x_center - 40, pdf.get_y(), x_center + 40, pdf.get_y())
    pdf.ln(2)
    
    pdf.set_font('helvetica', '', 10)
    
    # Usando cell vazio para alinhar os textos de forma centralizada ou com margin
    pdf.cell(0, 6, "Funcionário: " + ("_" * 40), align='C', ln=1)
    pdf.cell(0, 6, "RG: " + ("_" * 53), align='C', ln=1)
    pdf.cell(0, 6, "CPF: " + ("_" * 51), align='C', ln=1)
    pdf.cell(0, 6, "Unidade de Trabalho: " + ("_" * 32), align='C', ln=1)
    
    return pdf.output(dest='S')
