import streamlit as st
import math

# ==========================================
# CONFIGURAÇÃO DA PÁGINA E ESTILO VISUAL
# ==========================================
st.set_page_config(
    page_title="Calculadora FRAX-FREE",
    page_icon="🦴",
    layout="wide"
)

# --- TRAVA OPCIONAL POR SENHA RÁPIDA ---
senha = st.sidebar.text_input("🔒 Senha de Acesso:", type="password")
if senha != "mfc.sjp":  # Troque "1234" pela sua senha pessoal
    st.warning("Digite a senha na barra lateral esquerda para liberar a calculadora.")
    st.stop()

st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #7A0000 0%, #B22222 100%);
        color: white;
        padding: 18px 24px;
        border-radius: 10px;
        margin-bottom: 18px;
    }
    .main-header h2 { color: white; margin: 0; font-size: 25px; }
    .main-header p { color: #f5dcdc; margin: 4px 0 0 0; font-size: 13.5px; }
    .result-card {
        background-color: #ffffff;
        border-left: 6px solid #555555;
        padding: 14px 16px;
        border-radius: 8px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.07);
        margin-bottom: 12px;
    }
    .plus-card {
        background-color: #fff6f5;
        border-left: 6px solid #B22222;
        padding: 14px 16px;
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(178,34,34,0.15);
        margin-bottom: 12px;
    }
    .badge-risco {
        display: inline-block;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: bold;
        color: white;
        font-size: 13.5px;
    }
    .factor-tag {
        background-color: #f8d7da;
        color: #721c24;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-header">
    <h2>🦴 Calculadora de Risco Osteoporótico (Coorte Brasil)</h2>
    <p>Calibração epidemiológica brasileira (Zerbini et al., 2015), padronização DXA ICSBM/NHANES III e aplicação estrita de fator único validado (fraxplus.org)</p>
</div>
""", unsafe_allow_html=True)


# ==========================================
# 1. FUNÇÕES DE PADRONIZAÇÃO DXA (ICSBM / HANSON 1997 & NHANES III)
# ==========================================
def converter_colo_para_tscore_nhanes(equipamento: str, valor_dmo: float) -> float:
    """
    Converte a DMO do colo femoral (g/cm²) para equivalente Hologic usando as equações
    oficiais sBMD (Hanson 1997 / ICSBM) e calcula o T-score NHANES III (Mulheres brancas 20-29a:
    Média = 0.858 g/cm², DP = 0.120 g/cm² - Looker et al., 1998).
    """
    if equipamento == "Hologic (g/cm²)":
        dmo_hol = valor_dmo
    elif equipamento == "GE Lunar (g/cm²)":
        dmo_hol = (0.8638 * valor_dmo) - 0.0386
    elif equipamento == "Norland (g/cm²)":
        dmo_hol = (0.9062 * valor_dmo) - 0.0120
    else:
        return valor_dmo

    return round((dmo_hol - 0.858) / 0.120, 2)


def converter_coluna_para_tscore(equipamento: str, valor_dmo: float) -> float:
    """Converte DMO L1-L4 (g/cm²) por fabricante para T-score aproximado da coluna lombar."""
    if equipamento == "Hologic (g/cm²)":
        return round((valor_dmo - 1.047) / 0.110, 2)
    elif equipamento == "GE Lunar (g/cm²)":
        return round((valor_dmo - 1.180) / 0.120, 2)
    elif equipamento == "Norland (g/cm²)":
        return round((valor_dmo - 1.085) / 0.115, 2)
    return valor_dmo


# ==========================================
# 2. CURVAS DA COORTE BRASILEIRA (ZERBINI ET AL., 2015 / ABRASSO 2017)
# ==========================================
def interpolar_curva(idade: int, tabela: dict) -> float:
    idade_c = max(40, min(90, idade))
    i_inf = (idade_c // 5) * 5
    i_sup = min(90, i_inf + 5)
    if i_inf == i_sup:
        return tabela[i_inf]
    fator = (idade_c - i_inf) / 5.0
    return tabela[i_inf] + fator * (tabela[i_sup] - tabela[i_inf])


def limiares_nogg_abrasso_brasil(idade: int) -> tuple:
    """Limiar de Intervenção (Alto Risco) e Muito Alto Risco (1.6x) segundo a ABRASSO."""
    limiar_intervencao = {
        40: 4.0, 45: 4.6, 50: 5.5, 55: 6.9, 60: 8.8,
        65: 11.4, 70: 14.8, 75: 19.1, 80: 22.5, 85: 24.0, 90: 23.0
    }
    alto = interpolar_curva(idade, limiar_intervencao)
    muito_alto = alto * 1.60
    return round(alto, 1), round(muito_alto, 1)


def calcular_motor_base_brasil(idade, sexo, imc, usar_dmo, t_colo,
                               frat_prev, pais_quadril, tabagismo, corticoide,
                               ar, osteop_sec, alcool) -> tuple:
    """Motor base calibrado para a Coorte Brasileira (Zerbini et al., 2015)."""
    if sexo == "Feminino":
        tab_mof = {40: 2.0, 45: 2.4, 50: 3.0, 55: 3.9, 60: 5.1, 65: 6.7, 70: 8.9, 75: 11.8, 80: 14.3, 85: 15.5, 90: 14.8}
        tab_hip = {40: 0.15, 45: 0.25, 50: 0.42, 55: 0.70, 60: 1.15, 65: 1.85, 70: 3.10, 75: 5.10, 80: 7.30, 85: 8.70, 90: 8.30}
        t_esperado_idade = -0.35 - 0.038 * (idade - 40)
    else:
        tab_mof = {40: 1.7, 45: 1.9, 50: 2.2, 55: 2.6, 60: 3.2, 65: 4.0, 70: 5.1, 75: 6.5, 80: 7.7, 85: 8.2, 90: 7.6}
        tab_hip = {40: 0.12, 45: 0.20, 50: 0.33, 55: 0.52, 60: 0.85, 65: 1.40, 70: 2.35, 75: 3.80, 80: 5.30, 85: 6.20, 90: 5.80}
        t_esperado_idade = +0.15 - 0.027 * (idade - 40)

    base_mof = interpolar_curva(idade, tab_mof)
    base_hip = interpolar_curva(idade, tab_hip)

    rr_mof_dmo, rr_hip_dmo = 1.0, 1.0
    if usar_dmo and t_colo is not None:
        delta_z = t_esperado_idade - t_colo
        gradiente_hip = max(1.75, min(4.00, 3.68 - 0.045 * (idade - 50)))
        gradiente_mof = 1.55 - 0.005 * (idade - 50)
        rr_hip_dmo = math.pow(gradiente_hip, delta_z)
        rr_mof_dmo = math.pow(gradiente_mof, delta_z)
    else:
        if imc < 25.0:
            rr_mof_dmo = math.pow(1.03, (25.0 - imc))
            rr_hip_dmo = math.pow(1.10, (25.0 - imc))
        elif imc > 25.0:
            rr_mof_dmo = math.pow(0.985, min(15.0, imc - 25.0))
            rr_hip_dmo = math.pow(0.960, min(15.0, imc - 25.0))

    aten = 0.86 if usar_dmo else 1.0
    rr_mof_clin, rr_hip_clin = 1.0, 1.0

    if frat_prev:
        rr_fp_mof = max(1.45, 1.95 - 0.009 * (idade - 40))
        rr_fp_hip = max(1.40, 2.15 - 0.015 * (idade - 40))
        rr_mof_clin *= (rr_fp_mof * (0.92 if usar_dmo else 1.0))
        rr_hip_clin *= (rr_fp_hip * (0.90 if usar_dmo else 1.0))
    if pais_quadril:
        rr_mof_clin *= 1.48
        rr_hip_clin *= 1.95
    if tabagismo:
        rr_mof_clin *= (1.22 * aten)
        rr_hip_clin *= (1.60 * aten)
    if corticoide:
        rr_mof_clin *= (1.65 * aten)
        rr_hip_clin *= (1.95 * aten)
    if ar:
        rr_mof_clin *= (1.42 * aten)
        rr_hip_clin *= (1.70 * aten)
    if (not usar_dmo) and osteop_sec:
        rr_mof_clin *= 1.42
        rr_hip_clin *= 1.70
    if alcool:
        rr_mof_clin *= (1.35 * aten)
        rr_hip_clin *= (1.62 * aten)

    h_base_mof = -math.log(1.0 - (base_mof / 100.0))
    h_base_hip = -math.log(1.0 - (base_hip / 100.0))

    prob_mof = (1.0 - math.exp(-h_base_mof * rr_mof_dmo * rr_mof_clin)) * 100.0
    prob_hip = (1.0 - math.exp(-h_base_hip * rr_hip_dmo * rr_hip_clin)) * 100.0
    prob_mof = max(prob_mof, prob_hip)

    return round(min(prob_mof, 95.0), 1), round(min(prob_hip, 90.0), 1)


# ==========================================
# 3. TABELAS CIENTÍFICAS DO MÓDULO FRAXPLUS
# ==========================================
def multiplicador_fratura_recente(idade: int, sitio: str) -> tuple:
    """Multiplicadores (MOF, Quadril) para fratura recente (< 2 anos) - Kanis et al., 2020."""
    tab_mof_sitio = {
        "Vertebral (Clínica)": {40: 2.10, 50: 1.92, 60: 1.66, 70: 1.44, 80: 1.24, 90: 1.10},
        "Quadril":             {40: 1.95, 50: 1.75, 60: 1.55, 70: 1.35, 80: 1.18, 90: 1.06},
        "Úmero Proximal":      {40: 1.80, 50: 1.63, 60: 1.46, 70: 1.28, 80: 1.15, 90: 1.05},
        "Antebraço / Punho":   {40: 1.55, 50: 1.43, 60: 1.32, 70: 1.21, 80: 1.10, 90: 1.03},
    }
    tab_hip_sitio = {
        "Vertebral (Clínica)": {40: 1.85, 50: 1.70, 60: 1.52, 70: 1.36, 80: 1.20, 90: 1.08},
        "Quadril":             {40: 2.10, 50: 1.88, 60: 1.65, 70: 1.42, 80: 1.22, 90: 1.08},
        "Úmero Proximal":      {40: 1.65, 50: 1.50, 60: 1.36, 70: 1.24, 80: 1.12, 90: 1.04},
        "Antebraço / Punho":   {40: 1.35, 50: 1.28, 60: 1.20, 70: 1.12, 80: 1.06, 90: 1.02},
    }
    idade_c = max(40, min(90, idade))
    i_inf = (idade_c // 10) * 10
    i_sup = min(90, i_inf + 10)
    fator = 0.0 if i_inf == i_sup else (idade_c - i_inf) / 10.0

    m_mof = tab_mof_sitio[sitio][i_inf] + fator * (tab_mof_sitio[sitio][i_sup] - tab_mof_sitio[sitio][i_inf])
    m_hip = tab_hip_sitio[sitio][i_inf] + fator * (tab_hip_sitio[sitio][i_sup] - tab_hip_sitio[sitio][i_inf])
    return round(m_mof, 2), round(m_hip, 2)


def calcular_prob_isolada(mof_b: float, hip_b: float, rr_mof: float, rr_hip: float) -> tuple:
    """Aplica um único fator modificador sobre o risco basal em escala de hazard."""
    h_mof = -math.log(1.0 - min(0.99, mof_b / 100.0))
    h_hip = -math.log(1.0 - min(0.99, hip_b / 100.0))

    mof_adj = (1.0 - math.exp(-h_mof * rr_mof)) * 100.0
    hip_adj = (1.0 - math.exp(-h_hip * rr_hip)) * 100.0

    mof_adj = round(min(max(mof_adj, hip_adj), 95.0), 1)
    hip_adj = round(min(hip_adj, 90.0), 1)
    return mof_adj, hip_adj


def gerar_svg_grafico_abrasso(idade_pac: int, mof_base: float, mof_plus: float) -> str:
    """Gera o gráfico vetorial SVG nativo da Curva NOGG / ABRASSO Brasil (40 a 90 anos)."""
    idades = list(range(40, 95, 5))
    def x_coord(id_val): return 50 + ((id_val - 40) / 50.0) * 440
    def y_coord(mof_val): return 240 - (min(45.0, max(0.0, mof_val)) / 45.0) * 220

    pts_alto = [(x_coord(i), y_coord(limiares_nogg_abrasso_brasil(i)[0])) for i in idades]
    pts_muito_alto = [(x_coord(i), y_coord(limiares_nogg_abrasso_brasil(i)[1])) for i in idades]

    poly_verde = " ".join([f"{x:.1f},{y:.1f}" for x, y in pts_alto]) + f" {x_coord(90):.1f},240 {x_coord(40):.1f},240"
    poly_laranja = " ".join([f"{x:.1f},{y:.1f}" for x, y in pts_alto]) + " " + " ".join([f"{x:.1f},{y:.1f}" for x, y in reversed(pts_muito_alto)])
    poly_vermelho = " ".join([f"{x:.1f},{y:.1f}" for x, y in pts_muito_alto]) + f" {x_coord(90):.1f},20 {x_coord(40):.1f},20"

    linha_alto = " ".join([f"{x:.1f},{y:.1f}" for x, y in pts_alto])
    linha_muito_alto = " ".join([f"{x:.1f},{y:.1f}" for x, y in pts_muito_alto])

    xp = x_coord(idade_pac)
    yb = y_coord(mof_base)
    yp = y_coord(mof_plus)

    grades_y = ""
    for val in [0, 10, 20, 30, 40]:
        gy = y_coord(val)
        grades_y += f'<line x1="50" y1="{gy:.1f}" x2="490" y2="{gy:.1f}" stroke="#ffffff" stroke-opacity="0.4" stroke-dasharray="3,3"/>'
        grades_y += f'<text x="42" y="{gy+4:.1f}" font-size="11" fill="#444" text-anchor="end">{val}%</text>'

    grades_x = ""
    for id_v in [40, 50, 60, 70, 80, 90]:
        gx = x_coord(id_v)
        grades_x += f'<text x="{gx:.1f}" y="258" font-size="11" fill="#444" text-anchor="middle">{id_v}</text>'

    svg = f"""
    <svg viewBox="0 0 520 280" style="width:100%; height:auto; background:#fafafa; border:1px solid #ddd; border-radius:8px;">
        <polygon points="{poly_verde}" fill="#27AE60" fill-opacity="0.28"/>
        <polygon points="{poly_laranja}" fill="#E67E22" fill-opacity="0.32"/>
        <polygon points="{poly_vermelho}" fill="#C0392B" fill-opacity="0.32"/>
        {grades_y}
        {grades_x}
        <polyline points="{linha_alto}" fill="none" stroke="#D35400" stroke-width="2.2"/>
        <polyline points="{linha_muito_alto}" fill="none" stroke="#8B0000" stroke-width="2.2" stroke-dasharray="5,3"/>
        <line x1="50" y1="240" x2="490" y2="240" stroke="#333" stroke-width="1.5"/>
        <line x1="50" y1="20" x2="50" y2="240" stroke="#333" stroke-width="1.5"/>
        <line x1="{xp:.1f}" y1="{yb:.1f}" x2="{xp:.1f}" y2="{yp:.1f}" stroke="#222" stroke-width="2" stroke-dasharray="2,2"/>
        <circle cx="{xp:.1f}" cy="{yb:.1f}" r="5.5" fill="#ffffff" stroke="#333333" stroke-width="2.2"/>
        <circle cx="{xp:.1f}" cy="{yp:.1f}" r="7" fill="#B22222" stroke="#ffffff" stroke-width="2"/>
        <text x="480" y="38" font-size="11" font-weight="bold" fill="#8B0000" text-anchor="end">MUITO ALTO RISCO</text>
        <text x="480" y="138" font-size="11" font-weight="bold" fill="#B94600" text-anchor="end">ALTO RISCO (TRATAR)</text>
        <text x="480" y="225" font-size="11" font-weight="bold" fill="#1E8449" text-anchor="end">BAIXO RISCO</text>
        <text x="270" y="275" font-size="11.5" font-weight="bold" fill="#333" text-anchor="middle">Idade (anos) — ○ FRAX Base ({mof_base:.1f}%) | ● FRAXplus ({mof_plus:.1f}%)</text>
    </svg>
    """
    return svg


# ==========================================
# INTERFACE PRINCIPAL (SELETOR DE MODO BASE)
# ==========================================
modo_calculo = st.radio(
    "Modos de Operação (modo híbrido mais recomendado):",
    [
        "1. Autônomo (Curva Epidemiológica FRAX Brasil + Conversão DMO + FRAXplus)",
        "2. Híbrido (Inserir resultado da calculadora FRAX + Aplicar ajustes FRAXplus)"
    ],
    horizontal=True
)

st.divider()

col_frax, col_plus, col_res = st.columns([1.1, 1.25, 1.35], gap="large")

# ------------------------------------------
# COLUNA 1: VARIÁVEIS DO FRAX PADRÃO + DMO COLO FEMORAL
# ------------------------------------------
with col_frax:
    st.subheader("📋 1. Fatores FRAX Padrão")
    c1, c2 = st.columns(2)
    with c1:
        idade = st.number_input("Idade (40–90 anos)", min_value=40, max_value=90, value=68)
        peso = st.number_input("Peso (kg)", min_value=25.0, max_value=200.0, value=60.0, step=0.5)
    with c2:
        sexo = st.selectbox("Sexo", ["Feminino", "Masculino"])
        altura = st.number_input("Altura (cm)", min_value=120.0, max_value=220.0, value=160.0, step=0.5)

    imc = peso / ((altura / 100.0) ** 2)
    st.caption(f"IMC Calculado: **{imc:.1f} kg/m²**")

    if modo_calculo.startswith("2."):
        st.info("Insira abaixo o resultado obtido gratuitamente no site do FRAX Brasil / ABRASSO:")
        mof_manual = st.number_input("Fratura Maior - MOF Oficial (%)", 0.1, 95.0, 14.0, step=0.1)
        hip_manual = st.number_input("Fratura de Quadril Oficial (%)", 0.1, 90.0, 3.5, step=0.1)

    st.markdown("**Fatores de Risco Clínicos:**")
    frat_prev = st.toggle("Fratura prévia por fragilidade", value=True)
    pais_quadril = st.toggle("Pais com fratura de quadril", value=False)
    tabagismo = st.toggle("Tabagismo atual", value=False)
    corticoide = st.toggle("Uso de Glicocorticoides", value=True)
    ar = st.toggle("Artrite Reumatoide", value=False)
    osteop_sec = st.toggle("Osteoporose Secundária", value=False)
    alcool = st.toggle("Álcool (3 ou mais doses/dia)", value=False)

    st.markdown("---")
    st.markdown("**DMO do Colo do Fêmur (Aparelho DXA):**")
    metodo_dmo = st.selectbox(
        "Equipamento DXA:",
        [
            "Sem DMO",
            "GE Lunar (g/cm²)",
            "Hologic (g/cm²)",
            "Norland (g/cm²)",
            "T-Score (NHANES III direto)"
        ],
        index=1
    )

    usar_dmo = (metodo_dmo != "Sem DMO")
    t_colo = None

    if metodo_dmo == "GE Lunar (g/cm²)":
        val_dmo = st.number_input("DMO Colo do Fêmur em g/cm² (GE Lunar):", 0.300, 1.600, 0.720, step=0.005, format="%.3f")
        t_colo = converter_colo_para_tscore_nhanes(metodo_dmo, val_dmo)
        st.success(f"🔄 **T-score NHANES III (ICSBM):** `{t_colo:+.2f} DP`")
    elif metodo_dmo == "Hologic (g/cm²)":
        val_dmo = st.number_input("DMO Colo do Fêmur em g/cm² (Hologic):", 0.250, 1.500, 0.585, step=0.005, format="%.3f")
        t_colo = converter_colo_para_tscore_nhanes(metodo_dmo, val_dmo)
        st.success(f"🔄 **T-score NHANES III:** `{t_colo:+.2f} DP`")
    elif metodo_dmo == "Norland (g/cm²)":
        val_dmo = st.number_input("DMO Colo do Fêmur em g/cm² (Norland):", 0.250, 1.500, 0.655, step=0.005, format="%.3f")
        t_colo = converter_colo_para_tscore_nhanes(metodo_dmo, val_dmo)
        st.success(f"🔄 **T-score NHANES III (ICSBM):** `{t_colo:+.2f} DP`")
    elif metodo_dmo == "T-Score (NHANES III direto)":
        t_colo = st.slider("T-score do Colo Femoral (NHANES III)", -5.0, 2.0, -2.3, 0.1)


# ------------------------------------------
# COLUNA 2: OS 7 MÓDULOS OFICIAIS DO FRAXPLUS
# ------------------------------------------
with col_plus:
    st.subheader("➕ 2. Fatores modificadores FRAXplus")
    st.caption("Ative os fatores presentes no caso para comparar o impacto individual de cada um.")

    # Módulo 1: Recência e Sítio da Fratura
    with st.expander("1️⃣ Sítio da Fratura Prévia (< 2 anos)", expanded=frat_prev):
        if frat_prev:
            frat_recente = st.checkbox("Fratura osteoporótica ocorreu nos últimos 24 meses", value=True)
            sitio_frat = st.selectbox(
                "Sítio da fratura recente:",
                ["Vertebral (Clínica)", "Quadril", "Úmero Proximal", "Antebraço / Punho"]
            )
        else:
            st.caption("Habilite 'Fratura prévia' na coluna 1.")
            frat_recente = False
            sitio_frat = "Vertebral (Clínica)"

    # Módulo 2: Dose de Glicocorticoide
    with st.expander("2️⃣ Dose diária de glicocorticoide", expanded=corticoide):
        if corticoide:
            dose_gc = st.radio(
                "Dose equivalente de Prednisolona:",
                ["Baixa (< 2,5 mg/dia)", "Média (2,5 a 7,5 mg/dia - Padrão FRAX)", "Alta (>= 7,5 mg/dia)"],
                index=2
            )
        else:
            st.caption("Habilite 'Uso de Glicocorticoides' na coluna 1.")
            dose_gc = "Média (2,5 a 7,5 mg/dia - Padrão FRAX)"

    # Módulo 3: Quedas no último ano
    with st.expander("3️⃣ Número de quedas nos últimos 12 meses", expanded=True):
        aplicar_quedas = st.checkbox("Incluir avaliação de quedas no último ano", value=True)
        if aplicar_quedas:
            quedas_op = st.select_slider(
                "Quedas nos últimos 12 meses:",
                options=["0 quedas", "1 queda", "2 quedas", "3 ou mais quedas"],
                value="2 quedas"
            )
        else:
            quedas_op = None

    # Módulo 4: Discordância Coluna Lombar (L1-L4)
    with st.expander("4️⃣ Discordância DMO coluna lombar (L1–L4)", expanded=usar_dmo):
        if usar_dmo:
            usar_coluna = st.checkbox("Avaliar discordância da Coluna Lombar (Regra de Leslie)", value=True)
            if usar_coluna:
                modo_col = st.radio("Formato de entrada L1-L4:", ["T-score L1-L4 direto", "DMO L1-L4 em g/cm²"], horizontal=True)
                if modo_col == "T-score L1-L4 direto":
                    t_coluna = st.slider("T-score da Coluna Lombar (L1-L4)", -5.0, 2.0, -3.5, 0.1)
                else:
                    eq_col = metodo_dmo if "g/cm²" in metodo_dmo else "GE Lunar (g/cm²)"
                    dmo_col_val = st.number_input(f"DMO L1-L4 em {eq_col}:", 0.400, 1.800, 0.800, 0.005, format="%.3f")
                    t_coluna = converter_coluna_para_tscore(eq_col, dmo_col_val)
                    st.caption(f"T-score L1-L4 estimado: `{t_coluna:+.2f} DP`")
                st.caption(f"Offset (Colo `{t_colo:+.1f}` − Coluna `{t_coluna:+.1f}`): **{t_colo - t_coluna:+.2f} DP**")
            else:
                t_coluna = None
        else:
            st.caption("Requer DMO do Colo Femoral ativa na coluna 1.")
            t_coluna = None

    # Módulo 5: Trabecular Bone Score (TBS)
    with st.expander("5️⃣ Trabecular Bone Score (TBS L1–L4)", expanded=False):
        usar_tbs = st.checkbox("Avaliar ajuste por TBS (McCloskey et al., 2016)", value=False)
        tbs_val = st.slider("Valor do TBS", 0.900, 1.500, 1.180, 0.010) if usar_tbs else None

    # Módulo 6: Diabetes tipo 2 e duração
    with st.expander("6️⃣ Diabetes Mellitus Tipo 2 e Tempo de Doença", expanded=False):
        dm2 = st.checkbox("Paciente com Diabetes Tipo 2", value=False)
        duracao_dm2 = st.selectbox(
            "Tempo de diagnóstico do DM2:",
            ["Menos de 5 anos", "Entre 5 e 10 anos", "Mais de 10 anos"],
            index=1
        ) if dm2 else None

    # Módulo 7: Comprimento do Eixo do Quadril (HAL)
    with st.expander("7️⃣ Comprimento do Eixo do Quadril (HAL - mm)", expanded=False):
        usar_hal = st.checkbox("Avaliar HAL medido na DXA (Leslie et al., 2016)", value=False)
        if usar_hal:
            media_hal_sexo = 105.0 if sexo == "Feminino" else 118.0
            hal_mm = st.number_input(f"HAL em mm (Média esperada {sexo}: {media_hal_sexo:.0f} mm)", 85.0, 145.0, media_hal_sexo + 6.5, 0.5)
        else:
            hal_mm = None


# ==========================================
# PROCESSAMENTO MATEMÁTICO INDIVIDUAL (ESTRITAMENTE 1 FATOR POR VEZ)
# ==========================================
if modo_calculo.startswith("1."):
    mof_base, hip_base = calcular_motor_base_brasil(
        idade, sexo, imc, usar_dmo, t_colo,
        frat_prev, pais_quadril, tabagismo, corticoide,
        ar, osteop_sec, alcool
    )
else:
    mof_base, hip_base = mof_manual, hip_manual

# Lista de dicionários com o cálculo isolado de cada fator ativo
candidatos_plus = []

def registrar_fator(nome_curto: str, referencia: str, rr_mof: float, rr_hip: float):
    m_isol, h_isol = calcular_prob_isolada(mof_base, hip_base, rr_mof, rr_hip)
    candidatos_plus.append({
        "nome": nome_curto,
        "referencia": referencia,
        "rr_mof": rr_mof,
        "rr_hip": rr_hip,
        "mof_isolado": m_isol,
        "hip_isolado": h_isol,
        "delta_mof": round(m_isol - mof_base, 1),
        "delta_hip": round(h_isol - hip_base, 1)
    })

# 1. Recência da Fratura (Kanis et al., 2020)
if frat_prev and frat_recente:
    r_mof, r_hip = multiplicador_fratura_recente(idade, sitio_frat)
    registrar_fator(f"Fratura recente <2a ({sitio_frat})", "Kanis et al., 2020", r_mof, r_hip)

# 2. Dose de Glicocorticoide (Kanis et al., 2011)
if corticoide:
    if dose_gc.startswith("Alta"):
        r_gc_mof = 1.20 if idade < 60 else (1.15 if idade < 80 else 1.10)
        r_gc_hip = 1.25 if idade < 60 else (1.20 if idade < 80 else 1.15)
        registrar_fator("Corticoide Alta Dose (≥7,5 mg/d)", "Kanis et al., 2011", r_gc_mof, r_gc_hip)
    elif dose_gc.startswith("Baixa"):
        registrar_fator("Corticoide Baixa Dose (<2,5 mg/d)", "Kanis et al., 2011", 0.80, 0.65)

# 3. Histórico de Quedas (Kanis et al., 2023)
if aplicar_quedas and quedas_op is not None:
    mapa_quedas = {
        "0 quedas": (0.92, 0.90),
        "1 queda": (1.12, 1.16),
        "2 quedas": (1.22, 1.30),
        "3 ou mais quedas": (1.32, 1.42)
    }
    rq_mof, rq_hip = mapa_quedas[quedas_op]
    registrar_fator(f"Histórico de Quedas ({quedas_op})", "Kanis et al., 2023", rq_mof, rq_hip)

# 4. Discordância Coluna/Fêmur (Leslie et al., 2011 / Johansson et al., 2014)
if usar_dmo and t_coluna is not None:
    offset_dmo = t_colo - t_coluna
    if abs(offset_dmo) >= 0.5:
        fator_leslie = round(max(0.70, min(1.50, 1.0 + 0.10 * offset_dmo)), 2)
        registrar_fator(f"Discordância L1-L4 ({offset_dmo:+.1f} DP)", "Leslie et al., 2011", fator_leslie, 1.00)

# 5. TBS (McCloskey et al., 2016)
if tbs_val is not None:
    tbs_ref_idade = 1.310 - 0.002 * (idade - 40)
    delta_tbs = (tbs_ref_idade - tbs_val) / 0.100
    fator_idade_tbs = max(0.65, 1.20 - 0.01 * (idade - 50))
    r_tbs_mof = round(max(0.85, min(1.60, 1.0 + 0.16 * delta_tbs * fator_idade_tbs)), 2)
    r_tbs_hip = round(max(0.88, min(1.45, 1.0 + 0.12 * delta_tbs * fator_idade_tbs)), 2)
    registrar_fator(f"TBS L1-L4 ({tbs_val:.3f})", "McCloskey et al., 2016", r_tbs_mof, r_tbs_hip)

# 6. Diabetes Mellitus Tipo 2 (Leslie et al., 2018 / 2023)
if dm2:
    mapa_dm = {
        "Menos de 5 anos": (1.15, 1.25),
        "Entre 5 e 10 anos": (1.25, 1.40),
        "Mais de 10 anos": (1.35, 1.55)
    }
    rdm_mof, rdm_hip = mapa_dm[duracao_dm2]
    registrar_fator(f"Diabetes Tipo 2 ({duracao_dm2})", "Leslie et al., 2018", rdm_mof, rdm_hip)

# 7. HAL - Hip Axis Length (Leslie et al., 2016)
if usar_hal and hal_mm is not None:
    media_hal = 105.0 if sexo == "Feminino" else 118.0
    z_hal = (hal_mm - media_hal) / 6.5
    r_hal_mof = round(max(0.80, min(1.45, math.pow(1.12, z_hal))), 2)
    r_hal_hip = round(max(0.70, min(1.80, math.pow(1.30, z_hal))), 2)
    registrar_fator(f"Eixo do Quadril HAL ({hal_mm:.1f} mm)", "Leslie et al., 2016", r_hal_mof, r_hal_hip)


# ------------------------------------------
# COLUNA 3: TABELA COMPARATIVA, SELETOR DE FATOR ÚNICO E RESULTADO FINAL
# ------------------------------------------
with col_res:
    st.subheader("📊 3. Seleção do fator de maior impacto e Resultado")

    # 1. Card FRAX Base
    st.markdown(f"""
    <div class="result-card">
        <div style="font-size:12.5px; color:#555; font-weight:bold;">FRAX BRASIL PADRÃO (SEM MODIFICADORES)</div>
        <div style="display:flex; justify-content:space-between; margin-top:6px;">
            <div><span style="font-size:13.5px; color:#222;">Fratura Maior (MOF):</span><br><b style="font-size:22px; color:#222;">{mof_base:.1f}%</b></div>
            <div><span style="font-size:13.5px; color:#222;">Fratura de Quadril (FQ):</span><br><b style="font-size:22px; color:#222;">{hip_base:.1f}%</b></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 2. Tabela Comparativa de Impacto Individual + Seletor de Fator Único Validado
    if candidatos_plus:
        # Ordena os candidatos do maior impacto em MOF para o menor
        candidatos_ordenados = sorted(candidatos_plus, key=lambda x: x["mof_isolado"], reverse=True)
        fator_dominante = candidatos_ordenados[0]

        st.markdown("##### 🔬 Impacto individual de cada fator ativo isoladamente")
        linhas_md = "| Fator Modificador (Isolado) | Mult. (MOF / FQ) | MOF Ajustado | FQ Ajustado |\n"
        linhas_md += "| :--- | :---: | :---: | :---: |\n"
        for idx, c in enumerate(candidatos_ordenados):
            destaque = "⭐ " if idx == 0 else ""
            linhas_md += (
                f"| {destaque}**{c['nome']}** | `×{c['rr_mof']:.2f}` / `×{c['rr_hip']:.2f}` "
                f"| **{c['mof_isolado']:.1f}%** ({c['delta_mof']:+.1f}%) "
                f"| **{c['hip_isolado']:.1f}%** ({c['delta_hip']:+.1f}%) |\n"
            )
        st.markdown(linhas_md)

        # Seletor interativo de clique único para o médico escolher qual fator aplicar
        opcoes_radio = [
            f"⭐ Automático — Fator Dominante: {fator_dominante['nome']} (MOF {fator_dominante['mof_isolado']:.1f}% | FQ {fator_dominante['hip_isolado']:.1f}%)"
        ] + [
            f"{c['nome']} → MOF {c['mof_isolado']:.1f}% | Quadril {c['hip_isolado']:.1f}%"
            for c in candidatos_ordenados
        ]

        escolha_medico = st.radio(
            "👆 Escolha o fator único FRAXplus que deseja aplicar ao cálculo final:",
            options=opcoes_radio,
            index=0,
            help="Seguindo a validação científica de Kanis, McCloskey e Leslie (fraxplus.org), apenas 1 ajuste pós-teste deve ser aplicado por vez para evitar superestimação por colinearidade."
        )

        if escolha_medico.startswith("⭐ Automático"):
            fator_aplicado = fator_dominante
        else:
            idx_escolhido = opcoes_radio.index(escolha_medico) - 1
            fator_aplicado = candidatos_ordenados[idx_escolhido]

        mof_plus = fator_aplicado["mof_isolado"]
        hip_plus = fator_aplicado["hip_isolado"]
        nome_fator_final = f"{fator_aplicado['nome']} ({fator_aplicado['referencia']})"
    else:
        st.info("Nenhum fator modificador ativado na Coluna 2. O resultado final permanece igual ao FRAX Padrão.")
        mof_plus = mof_base
        hip_plus = hip_base
        nome_fator_final = "Nenhum fator adicional aplicado"

    # 3. Card Resultado Final FRAXplus
    delta_mof = mof_plus - mof_base
    delta_hip = hip_plus - hip_base
    st.markdown(f"""
    <div class="plus-card">
        <div style="font-size:12.5px; color:#B22222; font-weight:bold;">✨ RESULTADO FINAL FRAXplus (1 FATOR VALIDADO APLICADO)</div>
        <div style="margin-top:4px; margin-bottom:8px;">
            <span class="factor-tag">Fator aplicado: {nome_fator_final}</span>
        </div>
        <div style="display:flex; justify-content:space-between;">
            <div>
                <span style="font-size:13.5px; color:#B22222;">Fratura Maior (MOF):</span><br>
                <b style="font-size:27px; color:#B22222;">{mof_plus:.1f}%</b>
                <span style="font-size:13px; color:#d9534f; font-weight:bold;">({delta_mof:+.1f}%)</span>
            </div>
            <div>
                <span style="font-size:13.5px; color:#B22222;">Fratura de Quadril (FQ):</span><br>
                <b style="font-size:27px; color:#B22222;">{hip_plus:.1f}%</b>
                <span style="font-size:13px; color:#d9534f; font-weight:bold;">({delta_hip:+.1f}%)</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 4. Gráfico SVG NOGG / ABRASSO
    st.markdown(gerar_svg_grafico_abrasso(idade, mof_base, mof_plus), unsafe_allow_html=True)

    lim_alto, lim_muito_alto = limiares_nogg_abrasso_brasil(idade)
    criterio_nof_fixo = (mof_plus >= 20.0 or hip_plus >= 3.0)

    if mof_plus >= lim_muito_alto or (frat_prev and frat_recente):
        categoria = "MUITO ALTO RISCO (NOGG / ABRASSO)"
        cor_badge = "#8B0000"
        conduta = "Considerar terapia sequencial iniciando com agente osteoformador / anabólico (Teriparatida ou Romosozumabe) ou antirreabsortivo parenteral potente (Ácido Zoledrônico / Denosumabe), conforme diretriz ABRASSO/PCDT."
    elif mof_plus >= lim_alto or criterio_nof_fixo or (usar_dmo and t_colo <= -2.5) or (usar_dmo and t_coluna is not None and t_coluna <= -2.5):
        categoria = "ALTO RISCO (Acima do Limiar de Intervenção)"
        cor_badge = "#D35400"
        conduta = "Indicado tratamento farmacológico (ex: Bisfosfonatos orais/injetáveis ou Denosumabe), suplementação adequada de cálcio/vitamina D e prevenção de quedas."
    else:
        categoria = "BAIXO A MODERADO RISCO"
        cor_badge = "#27AE60"
        conduta = "Abaixo do limiar de intervenção farmacológica aos critérios atuais. Manter medidas não farmacológicas e monitorar."

    st.markdown(f"""
    <div style="margin-top:10px; margin-bottom:10px;">
        <div class="badge-risco" style="background-color:{cor_badge};">{categoria}</div>
        <div style="font-size:12px; color:#444; margin-top:6px;">
            <b>Limiares ABRASSO ({idade} anos):</b> Alto Risco ≥ <b>{lim_alto}%</b> | Muito Alto Risco ≥ <b>{lim_muito_alto}%</b><br>
            <b>Critério Fixo Complementar (NOF/BHOF):</b> MOF ≥ 20% ou Quadril ≥ 3% ({'Atendido' if criterio_nof_fixo else 'Não atendido'})
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.info(f"**Conduta Sugerida:** {conduta}")

    with st.expander("📋 Resumo Pronto para Copiar para o Prontuário", expanded=False):
        dmo_txt = f"T-score Colo Femoral (NHANES III) = {t_colo:+.2f} DP" if usar_dmo else "Sem DMO informada"
        col_txt = f" | T-score L1-L4 = {t_coluna:+.2f} DP" if (usar_dmo and t_coluna is not None) else ""
        outros_txt = ", ".join([f"{c['nome']} (MOF {c['mof_isolado']:.1f}%)" for c in candidatos_plus]) if candidatos_plus else "Nenhum"
        resumo_prontuario = (
            f"AVALIAÇÃO DE RISCO DE FRATURA EM 10 ANOS (FRAX BRASIL + FRAXplus):\n"
            f"- Paciente: {sexo}, {idade} anos, IMC {imc:.1f} kg/m² | {dmo_txt}{col_txt}\n"
            f"- Risco FRAX Padrão (Base): Fratura Maior (MOF) = {mof_base:.1f}% | Quadril = {hip_base:.1f}%\n"
            f"- Simulação Individual FRAXplus: {outros_txt}\n"
            f"- Fator Único Selecionado (Padrão Validado fraxplus.org): {nome_fator_final}\n"
            f"- Risco Final Ajustado FRAXplus: Fratura Maior (MOF) = {mof_plus:.1f}% | Quadril = {hip_plus:.1f}%\n"
            f"- Estratificação ABRASSO ({idade}a - Limiares {lim_alto}% / {lim_muito_alto}%): {categoria}."
        )
        st.code(resumo_prontuario, language="text")
