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
# A senha pode ser definida em .streamlit/secrets.toml (chave: senha_acesso) para não ficar
# exposta no código-fonte. Sem o arquivo de secrets, usa a senha padrão abaixo.
def _senha_configurada() -> str:
    try:
        return str(st.secrets["senha_acesso"])
    except Exception:
        return "mfc.sjp"


senha = st.sidebar.text_input("🔒 Senha de Acesso:", type="password")
if senha != _senha_configurada():
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
    <p>Resultado do FRAX Brasil oficial + ajustes FRAXplus / ABRASSO (um fator por vez) + limiares híbridos do FRAX Brasil 2.0</p>
</div>
""", unsafe_allow_html=True)


# ==========================================
# 1. FUNÇÕES DE PADRONIZAÇÃO DXA (NHANES III)
# ==========================================
# Observação: os T-scores impressos nos laudos atuais de GE Lunar e Hologic já usam a
# referência NHANES III (mulheres brancas 20–29 a) no colo femoral. Sempre que possível,
# prefira o T-score do laudo. As conversões abaixo são aproximações entre fabricantes.
def converter_colo_para_tscore_nhanes(equipamento: str, valor_dmo: float) -> float:
    """
    Converte a DMO do colo femoral (g/cm²) para equivalente Hologic (equações de conversão
    entre fabricantes, aproximadas) e calcula o T-score NHANES III
    (Mulheres brancas 20–29 a: média 0,858 g/cm², DP 0,120 g/cm² — Looker et al., 1998).
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
# 2. LIMIARES ABRASSO / FRAX BRASIL 2.0 (VALORES OFICIAIS)
# ==========================================
def interpolar_decada(idade: float, tabela: dict) -> float:
    """Interpolação linear entre as idades da tabela; fora do intervalo usa o valor do extremo."""
    chaves = sorted(tabela)
    a = max(chaves[0], min(chaves[-1], idade))
    for i in range(len(chaves) - 1):
        lo, hi = chaves[i], chaves[i + 1]
        if lo <= a <= hi:
            return tabela[lo] + (a - lo) / (hi - lo) * (tabela[hi] - tabela[lo])
    return tabela[chaves[-1]]


# Valores obtidos na calculadora FRAX oficial (América Latina → Brasil), mulher, IMC 25
# (64 kg / 160 cm), sem DMO e sem outros fatores de risco.
# Metodologia NOGG adotada pela ABRASSO (FRAX Brasil 2.0, set/2024):
#   • Limiar de intervenção (LI) = mulher COM fratura prévia; varia com a idade até 70 anos e
#     fica FIXO de 70 a 90 anos (modelo híbrido). Aplicado também a homens.
#   • Limiar inferior de avaliação (LIA) = mulher SEM fatores de risco.
#   • Limiar superior de avaliação (LSA) = 1,2 × LI.  • Muito alto risco = 1,6 × LI.
FRAX_OFICIAL_COM_FRATURA = {  # idade: (MOF %, Quadril %)
    40: (0.9, 0.1), 45: (1.3, 0.2), 50: (2.0, 0.3), 55: (2.9, 0.5),
    60: (4.3, 0.9), 65: (5.9, 1.4), 70: (7.3, 2.3),
}
FRAX_OFICIAL_SEM_FATORES = {  # idade: (MOF %, Quadril %)
    40: (0.4, 0.0), 45: (0.6, 0.0), 50: (0.9, 0.1), 55: (1.4, 0.2), 60: (2.1, 0.3),
    65: (2.9, 0.6), 70: (3.8, 1.1), 75: (4.6, 2.0), 80: (5.5, 2.8), 85: (6.6, 3.2), 90: (7.4, 3.2),
}


def limiares_abrasso_brasil(idade: float) -> dict:
    # interpolar_decada aceita qualquer espaçamento e mantém o último valor após os 70 anos,
    # o que reproduz o limiar fixo de 70 a 90 anos do modelo híbrido.
    li_mof = interpolar_decada(idade, {a: v[0] for a, v in FRAX_OFICIAL_COM_FRATURA.items()})
    li_hip = interpolar_decada(idade, {a: v[1] for a, v in FRAX_OFICIAL_COM_FRATURA.items()})
    lia = min(interpolar_decada(idade, {a: v[0] for a, v in FRAX_OFICIAL_SEM_FATORES.items()}), li_mof)
    return {
        "lia": round(lia, 1),
        "li": round(li_mof, 1),
        "lsa": round(1.2 * li_mof, 1),
        "muito_alto": round(1.6 * li_mof, 1),
        "li_quadril": round(li_hip, 1),
    }


# ==========================================
# 3. TABELAS CIENTÍFICAS DOS AJUSTES (FRAXplus / ABRASSO)
# ==========================================
# Recência da fratura: razões de probabilidade publicadas no Apêndice (Tabelas 4–7) de
# Kanis et al., Osteoporos Int 2020;31:1817–28. Aplicam-se ao FRAX calculado COM "fratura
# prévia = sim". Formato: {sexo: {sítio: ({MOF por idade}, {Quadril por idade})}}
RECENCIA_KANIS_2020 = {
    "Feminino": {
        "Vertebral (Clínica)": ({40: 7.14, 50: 2.62, 60: 1.84, 70: 1.50, 80: 1.23, 90: 1.01},
                                {40: 2.08, 50: 1.88, 60: 1.75, 70: 1.40, 80: 1.10, 90: 0.98}),
        "Quadril":             ({40: 6.77, 50: 2.38, 60: 1.60, 70: 1.23, 80: 0.95, 90: 0.74},
                                {40: 7.83, 50: 4.99, 60: 3.26, 70: 1.84, 80: 1.04, 90: 0.73}),
        "Úmero Proximal":      ({40: 4.79, 50: 1.96, 60: 1.54, 70: 1.39, 80: 1.26, 90: 1.08},
                                {40: 1.57, 50: 1.51, 60: 1.52, 70: 1.33, 80: 1.13, 90: 1.04}),
        "Antebraço / Punho":   ({40: 3.53, 50: 1.46, 60: 1.16, 70: 1.09, 80: 1.01, 90: 0.81},
                                {40: 0.73, 50: 0.82, 60: 0.95, 70: 0.99, 80: 0.98, 90: 0.94}),
    },
    "Masculino": {
        "Vertebral (Clínica)": ({40: 4.18, 50: 1.92, 60: 1.57, 70: 1.48, 80: 1.24, 90: 0.89},
                                {40: 2.13, 50: 1.90, 60: 1.76, 70: 1.38, 80: 1.03, 90: 0.82}),
        "Quadril":             ({40: 5.31, 50: 2.28, 60: 1.73, 70: 1.46, 80: 1.08, 90: 0.72},
                                {40: 11.83, 50: 7.36, 60: 4.66, 70: 2.46, 80: 1.24, 90: 0.74}),
        "Úmero Proximal":      ({40: 3.08, 50: 1.56, 60: 1.42, 70: 1.45, 80: 1.25, 90: 0.85},
                                {40: 2.38, 50: 2.27, 60: 2.23, 70: 1.84, 80: 1.35, 90: 0.98}),
        "Antebraço / Punho":   ({40: 2.61, 50: 1.33, 60: 1.23, 70: 1.33, 80: 1.22, 90: 0.80},
                                {40: 0.94, 50: 1.05, 60: 1.21, 70: 1.23, 80: 1.12, 90: 0.88}),
    },
}


def multiplicador_fratura_recente(idade: int, sexo: str, sitio: str) -> tuple:
    """Multiplicadores (MOF, Quadril) para fratura recente (< 2 anos) — Kanis et al., 2020."""
    tab_mof, tab_hip = RECENCIA_KANIS_2020[sexo][sitio]
    return round(interpolar_decada(idade, tab_mof), 2), round(interpolar_decada(idade, tab_hip), 2)


# Número de fraturas prévias — tabela de ajustes do FRAX Brasil 2.0 (ABRASSO, 2024)
MULT_NUM_FRATURAS = {"1 fratura": 1.0, "2 fraturas": 1.1, "3 fraturas": 1.2, "4 ou mais fraturas": 1.3}

# Quedas no último ano — tabela de ajustes do FRAX Brasil 2.0 (ABRASSO, 2024),
# derivada de Kanis et al., 2023. (MOF, Quadril)
MULT_QUEDAS = {"1 queda": (1.2, 1.2), "2 quedas": (1.3, 1.5), "3 ou mais quedas": (1.7, 2.0)}


def arredondar_meio_para_cima(x: float) -> int:
    """Arredonda 0,5 para longe do zero (o round() do Python arredonda 0,5 para o par)."""
    return int(math.copysign(math.floor(abs(x) + 0.5), x))


def aplicar_multiplicadores(mof_b: float, hip_b: float, rr_mof: float, rr_hip: float) -> tuple:
    """
    Aplica um único fator diretamente sobre a PROBABILIDADE em 10 anos, como fazem o
    FRAXplus e a tabela da ABRASSO (ex.: Kanis 2020: 17% × 1,84 = 31,3%).
    """
    hip_adj = min(hip_b * rr_hip, 90.0)
    mof_adj = min(max(mof_b * rr_mof, hip_adj), 95.0)
    return round(mof_adj, 1), round(hip_adj, 1)


def gerar_svg_grafico_abrasso(idade_pac: int, valor_base: float, valor_plus: float,
                              com_dmo: bool, tipo: str = "mof") -> str:
    """
    Gráfico SVG das faixas ABRASSO / FRAX Brasil 2.0 (40 a 90 anos).
    tipo="mof": fraturas maiores (com ou sem DMO); tipo="quadril": fratura de quadril (só com DMO,
    como no FRAX Brasil 2.0).
    """
    idades = list(range(40, 91, 2))
    lims = {i: limiares_abrasso_brasil(i) for i in idades}
    if tipo == "quadril":
        com_dmo = True  # a ABRASSO só exibe o gráfico de quadril quando há DMO
        li = {i: lims[i]["li_quadril"] for i in idades}
        vha = {i: 1.6 * li[i] for i in idades}
        lsa, lia = li, li
    else:
        li = {i: lims[i]["li"] for i in idades}
        lsa = {i: lims[i]["lsa"] for i in idades}
        vha = {i: lims[i]["muito_alto"] for i in idades}
        lia = {i: min(lims[i]["lia"], li[i]) for i in idades}

    maior = max(max(vha.values()), valor_base, valor_plus) * 1.15
    y_min_escala = 5.0 if tipo == "quadril" else 15.0
    passo_arred = 1.0 if maior <= 10 else 5.0
    y_max = max(y_min_escala, math.ceil(maior / passo_arred) * passo_arred)

    def x_coord(id_val): return 50 + ((id_val - 40) / 50.0) * 440
    def y_coord(v): return 240 - (min(y_max, max(0.0, v)) / y_max) * 220
    def pts(serie): return [(x_coord(i), y_coord(serie[i])) for i in idades]
    def fmt(lista): return " ".join(f"{x:.1f},{y:.1f}" for x, y in lista)
    def faixa(inf, sup): return fmt(pts(inf)) + " " + fmt(list(reversed(pts(sup))))

    zero = {i: 0.0 for i in idades}
    topo = {i: y_max for i in idades}

    if com_dmo:
        poligonos = (
            f'<polygon points="{faixa(zero, li)}" fill="#27AE60" fill-opacity="0.28"/>'
            f'<polygon points="{faixa(li, vha)}" fill="#E67E22" fill-opacity="0.32"/>'
            f'<polygon points="{faixa(vha, topo)}" fill="#C0392B" fill-opacity="0.32"/>'
        )
        rotulos = [
            ((vha[90] + y_max) / 2, "#8B0000", "MUITO ALTO RISCO"),
            ((li[90] + vha[90]) / 2, "#B94600", "ALTO RISCO (TRATAR)"),
            (li[90] / 2, "#1E8449", "BAIXO RISCO"),
        ]
    else:
        poligonos = (
            f'<polygon points="{faixa(zero, lia)}" fill="#27AE60" fill-opacity="0.28"/>'
            f'<polygon points="{faixa(lia, lsa)}" fill="#F1C40F" fill-opacity="0.35"/>'
            f'<polygon points="{faixa(lsa, vha)}" fill="#E67E22" fill-opacity="0.32"/>'
            f'<polygon points="{faixa(vha, topo)}" fill="#C0392B" fill-opacity="0.32"/>'
        )
        rotulos = [
            ((vha[90] + y_max) / 2, "#8B0000", "MUITO ALTO RISCO"),
            ((lsa[90] + vha[90]) / 2, "#B94600", "ALTO RISCO (TRATAR)"),
            ((lia[90] + lsa[90]) / 2, "#9A7D0A", "INTERMEDIÁRIO (DXA)"),
            (lia[90] / 2, "#1E8449", "BAIXO RISCO"),
        ]

    textos_rotulos = "".join(
        f'<text x="485" y="{y_coord(v) + 4:.1f}" font-size="10.5" font-weight="bold" fill="{cor}" text-anchor="end">{txt}</text>'
        for v, cor, txt in rotulos
    )

    passo = 1 if y_max <= 6 else (2 if y_max <= 12 else (5 if y_max <= 30 else 10))
    grades_y = ""
    val = 0
    while val <= y_max:
        gy = y_coord(val)
        grades_y += f'<line x1="50" y1="{gy:.1f}" x2="490" y2="{gy:.1f}" stroke="#ffffff" stroke-opacity="0.4" stroke-dasharray="3,3"/>'
        grades_y += f'<text x="42" y="{gy + 4:.1f}" font-size="11" fill="#444" text-anchor="end">{val}%</text>'
        val += passo

    grades_x = ""
    for id_v in [40, 50, 60, 70, 80, 90]:
        gx = x_coord(id_v)
        grades_x += f'<text x="{gx:.1f}" y="258" font-size="11" fill="#444" text-anchor="middle">{id_v}</text>'

    xp = x_coord(idade_pac)
    yb = y_coord(valor_base)
    yp = y_coord(valor_plus)
    sigla = "Quadril" if tipo == "quadril" else "MOF"

    return f"""
    <svg viewBox="0 0 520 280" style="width:100%; height:auto; background:#fafafa; border:1px solid #ddd; border-radius:8px;">
        {poligonos}
        {grades_y}
        {grades_x}
        <polyline points="{fmt(pts(li))}" fill="none" stroke="#D35400" stroke-width="2.2"/>
        <polyline points="{fmt(pts(vha))}" fill="none" stroke="#8B0000" stroke-width="2.2" stroke-dasharray="5,3"/>
        <line x1="50" y1="240" x2="490" y2="240" stroke="#333" stroke-width="1.5"/>
        <line x1="50" y1="20" x2="50" y2="240" stroke="#333" stroke-width="1.5"/>
        <line x1="{xp:.1f}" y1="{yb:.1f}" x2="{xp:.1f}" y2="{yp:.1f}" stroke="#222" stroke-width="2" stroke-dasharray="2,2"/>
        <circle cx="{xp:.1f}" cy="{yb:.1f}" r="5.5" fill="#ffffff" stroke="#333333" stroke-width="2.2"/>
        <circle cx="{xp:.1f}" cy="{yp:.1f}" r="7" fill="#B22222" stroke="#ffffff" stroke-width="2"/>
        {textos_rotulos}
        <text x="270" y="275" font-size="11.5" font-weight="bold" fill="#333" text-anchor="middle">Idade (anos) — ○ {sigla} Base ({valor_base:.1f}%) | ● {sigla} Ajustado ({valor_plus:.1f}%) — linha laranja: limiar de intervenção</text>
    </svg>
    """


# ==========================================
# INTERFACE PRINCIPAL
# ==========================================
# Modo único: o FRAX base vem SEMPRE da calculadora oficial (digitado pelo usuário).
# Os limiares ABRASSO vêm da tabela oficial da seção 2.
URL_FRAX_OFICIAL = "https://fraxplus.org/calculation-tool"
URL_FRAX_ABRASSO = "https://abrasso.org.br/frax-brasil/"

st.divider()

col_frax, col_plus, col_res = st.columns([1.1, 1.25, 1.35], gap="large")

# ------------------------------------------
# COLUNA 1: VARIÁVEIS DO FRAX PADRÃO + DMO COLO FEMORAL
# ------------------------------------------
with col_frax:
    # O médico começa pelo resultado do FRAX oficial e depois completa os dados do paciente
    st.subheader("📋 1. Resultado FRAX oficial")
    b1, b2 = st.columns(2)
    with b1:
        st.link_button("🌐 Abrir FRAX oficial", URL_FRAX_OFICIAL, use_container_width=True)
    with b2:
        st.link_button("🇧🇷 FRAX Brasil (ABRASSO)", URL_FRAX_ABRASSO, use_container_width=True)
    st.caption("No site oficial, selecione **América Latina → Brasil**, preencha os dados do paciente e calcule. "
               "Depois copie os dois resultados para os campos abaixo. A lista de conferência no fim desta coluna "
               "mostra os dados na ordem do site.")
    mof_manual = st.number_input("Fratura Maior - MOF Oficial (%)", 0.1, 95.0, 14.0, step=0.1)
    hip_manual = st.number_input("Fratura de Quadril Oficial (%)", 0.1, 90.0, 3.5, step=0.1)
    if hip_manual > mof_manual:
        st.warning("O risco de quadril não pode ser maior que o de fratura maior (MOF inclui o quadril). Confira os valores.")
    st.markdown("---")
    st.markdown("**Agora complete os dados do paciente** (os mesmos usados no FRAX oficial — servem para os "
                "ajustes, os limiares e os gráficos):")
    c1, c2 = st.columns(2)
    with c1:
        idade = st.number_input("Idade (40–90 anos)", min_value=40, max_value=90, value=68)
        peso = st.number_input("Peso (kg)", min_value=25.0, max_value=200.0, value=60.0, step=0.5)
    with c2:
        sexo = st.selectbox("Sexo", ["Feminino", "Masculino"])
        altura = st.number_input("Altura (cm)", min_value=120.0, max_value=220.0, value=160.0, step=0.5)

    imc = peso / ((altura / 100.0) ** 2)
    st.caption(f"IMC Calculado: **{imc:.1f} kg/m²**")

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
        st.success(f"🔄 **T-score NHANES III (estimado):** `{t_colo:+.2f} DP`")
    elif metodo_dmo == "Hologic (g/cm²)":
        val_dmo = st.number_input("DMO Colo do Fêmur em g/cm² (Hologic):", 0.250, 1.500, 0.585, step=0.005, format="%.3f")
        t_colo = converter_colo_para_tscore_nhanes(metodo_dmo, val_dmo)
        st.success(f"🔄 **T-score NHANES III:** `{t_colo:+.2f} DP`")
    elif metodo_dmo == "Norland (g/cm²)":
        val_dmo = st.number_input("DMO Colo do Fêmur em g/cm² (Norland):", 0.250, 1.500, 0.655, step=0.005, format="%.3f")
        t_colo = converter_colo_para_tscore_nhanes(metodo_dmo, val_dmo)
        st.success(f"🔄 **T-score NHANES III (estimado):** `{t_colo:+.2f} DP`")
    elif metodo_dmo == "T-Score (NHANES III direto)":
        t_colo = st.slider("T-score do Colo Femoral (NHANES III)", -5.0, 2.0, -2.3, 0.1)

    if usar_dmo and metodo_dmo != "T-Score (NHANES III direto)":
        st.caption("Dica: o T-score do colo impresso no laudo (Lunar/Hologic) já usa NHANES III — se disponível, "
                   "prefira a opção 'T-Score direto'.")

    # Lista de conferência na ordem dos campos da calculadora oficial
    with st.expander("🔁 Conferência: dados para o FRAX oficial (na ordem do site)", expanded=False):
        def _sn(v): return "Sim" if v else "Não"
        if metodo_dmo == "Sem DMO":
            dmo_site = "deixar em branco (sem DMO)"
        elif metodo_dmo == "T-Score (NHANES III direto)":
            dmo_site = f"T-score {t_colo:+.1f}"
        else:
            dmo_site = f"{metodo_dmo.split(' (')[0]} — {val_dmo:.3f} g/cm²"
        st.markdown(
            f"1. **País:** América Latina → Brasil\n"
            f"2. **Idade:** {idade} anos · **Sexo:** {sexo}\n"
            f"3. **Peso:** {peso:.1f} kg · **Altura:** {altura:.1f} cm\n"
            f"4. **Fratura prévia:** {_sn(frat_prev)}\n"
            f"5. **Pais com fratura de quadril:** {_sn(pais_quadril)}\n"
            f"6. **Tabagismo atual:** {_sn(tabagismo)}\n"
            f"7. **Glicocorticoides:** {_sn(corticoide)} "
            f"<span style='color:#777'>(≥ 3 meses, ≥ 5 mg/d de prednisolona ou equivalente)</span>\n"
            f"8. **Artrite reumatoide:** {_sn(ar)}\n"
            f"9. **Osteoporose secundária:** {_sn(osteop_sec)}"
            + (" <span style='color:#777'>(ignorada pelo FRAX quando há DMO)</span>" if usar_dmo else "") + "\n"
            f"10. **Álcool ≥ 3 doses/dia:** {_sn(alcool)}\n"
            f"11. **DMO do colo femoral:** {dmo_site}",
            unsafe_allow_html=True
        )
        st.caption("Os valores de MOF e quadril digitados acima precisam ter sido calculados com exatamente estes dados.")


# ------------------------------------------
# COLUNA 2: MÓDULOS DE AJUSTE (FRAXplus / ABRASSO)
# ------------------------------------------
with col_plus:
    st.subheader("➕ 2. Fatores modificadores FRAXplus")
    st.caption("Ative os fatores presentes no caso para comparar o impacto individual de cada um.")

    # Módulo 1: Recência, sítio e número de fraturas prévias
    with st.expander("1️⃣ Fratura prévia: recência (< 2 anos), sítio e número", expanded=frat_prev):
        if frat_prev:
            frat_recente = st.checkbox("Fratura osteoporótica ocorreu nos últimos 24 meses", value=True)
            sitio_frat = st.selectbox(
                "Sítio da fratura recente:",
                ["Vertebral (Clínica)", "Quadril", "Úmero Proximal", "Antebraço / Punho"],
                disabled=not frat_recente
            )
            if frat_recente and idade < 50:
                st.caption("⚠️ Abaixo de 50 anos os multiplicadores de recência são muito altos e menos precisos.")
            num_fraturas = st.selectbox("Número total de fraturas prévias:", list(MULT_NUM_FRATURAS.keys()), index=0)
        else:
            st.caption("Habilite 'Fratura prévia' na coluna 1.")
            frat_recente = False
            sitio_frat = "Vertebral (Clínica)"
            num_fraturas = "1 fratura"

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
            if quedas_op == "0 quedas":
                st.caption("Sem ajuste (tabela ABRASSO). O FRAXplus reduz levemente o risco com 0 quedas, mas o "
                           "coeficiente exato não é público.")
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
                offset_prev = t_colo - t_coluna
                st.caption(f"Offset (Colo `{t_colo:+.1f}` − Coluna `{t_coluna:+.1f}`): **{offset_prev:+.2f} DP** "
                           f"→ arredondado **{arredondar_meio_para_cima(offset_prev):+d}** "
                           f"(±10% no MOF por DP arredondado). Exclua vértebras com artefato.")
            else:
                t_coluna = None
        else:
            st.caption("Requer DMO do Colo Femoral ativa na coluna 1.")
            t_coluna = None

    # Módulo 5: Trabecular Bone Score (TBS)
    with st.expander("5️⃣ Trabecular Bone Score (TBS L1–L4)", expanded=False):
        if usar_dmo:
            usar_tbs = st.checkbox("Avaliar ajuste por TBS (McCloskey et al., 2015/2016)", value=False)
            tbs_val = st.slider("Valor do TBS", 0.900, 1.500, 1.180, 0.010) if usar_tbs else None
            if usar_tbs:
                st.caption("⚠️ Aproximação: a fórmula exata do ajuste FRAX-TBS não é publicada. Usa os HR por DP "
                           "do TBS (MOF 1,18; quadril 1,23 — McCloskey 2015). Válido para IMC 15–37 kg/m².")
                if metodo_dmo == "Norland (g/cm²)":
                    st.caption("O FRAXplus só oferece ajuste TBS para GE Lunar ou Hologic.")
        else:
            st.caption("Requer DMO do Colo Femoral ativa na coluna 1 (o ajuste por TBS exige FRAX com DMO).")
            usar_tbs, tbs_val = False, None

    # Módulo 6: Diabetes tipo 2
    with st.expander("6️⃣ Diabetes Mellitus Tipo 2", expanded=False):
        dm2 = st.checkbox("Paciente com Diabetes Tipo 2", value=False)
        metodo_dm, dm_mof_oficial, dm_hip_oficial = None, 0.0, 0.0
        if dm2:
            # Método recomendado já vem selecionado: com DMO, T-score −0,5 (corrige melhor o risco de
            # quadril em Leslie 2018); sem DMO, AR = Sim (método recomendado pela ABRASSO).
            if usar_dmo:
                opcoes_dm = ["Reduzir T-score do colo em 0,5 DP (recomendado com DMO)",
                             "Marcar Artrite Reumatoide = Sim", "Somar 10 anos à idade"]
            else:
                opcoes_dm = ["Marcar Artrite Reumatoide = Sim (recomendado sem DMO)", "Somar 10 anos à idade"]
            metodo_dm = st.radio("Método de ajuste (ABRASSO 2.0 / Leslie et al., 2018):", opcoes_dm)

            # Por que o método recomendado de cada cenário (Leslie et al., JBMR 2018)
            if usar_dmo:
                st.caption("**Por que T-score −0,5 com DMO:** no estudo de Leslie 2018, a subestimação do risco de "
                           "quadril persistiu após os ajustes por AR e por TBS, mas não com T-score −0,5 ou idade +10. "
                           "O T-score −0,5 é o mais natural de aplicar quando há densitometria.")
            else:
                st.caption("**Por que AR = Sim sem DMO:** é o método indicado pela ABRASSO e, junto com a idade +10, "
                           "o único que não depende da densitometria.")

            # Avisos de cada método
            metodo_sem_efeito = False
            if metodo_dm.startswith("Marcar") and ar:
                metodo_sem_efeito = True
                st.warning("A artrite reumatoide já está marcada — o método \"AR = Sim\" não muda nada. "
                           "Escolha outro método.")
            if metodo_dm.startswith("Somar"):
                st.caption("⚠️ Idade +10 tende a dar o maior aumento no risco de quadril entre os métodos.")
                if idade > 80:
                    st.warning(f"Idade +10 = {idade + 10} anos, mas o FRAX limita a idade em 90 — o efeito será "
                               "menor que o esperado.")

            # Instrução precisa do que mudar no site oficial
            if not metodo_sem_efeito:
                if metodo_dm.startswith("Reduzir"):
                    t_novo = t_colo - 0.5
                    mudanca = (f"**DMO do colo**: troque para entrada por **T-score** e digite **{t_novo:+.1f}** "
                               f"(T-score atual {t_colo:+.1f} − 0,5)")
                    if metodo_dmo != "T-Score (NHANES III direto)":
                        mudanca += ". Se tiver o T-score do laudo, use-o − 0,5 (o T-score deste app é estimado a partir da DMO em g/cm²)"
                elif metodo_dm.startswith("Marcar"):
                    mudanca = "**Artrite reumatoide** → **Sim**"
                else:
                    mudanca = f"**Idade** → **{min(90, idade + 10)} anos**"
                st.info(f"👉 Volte à calculadora FRAX oficial, mantenha todos os outros dados iguais, altere apenas "
                        f"{mudanca}, recalcule e digite os novos resultados abaixo.")
                st.link_button("🌐 Abrir FRAX oficial", URL_FRAX_OFICIAL)
                dm_mof_oficial = st.number_input("MOF recalculado no FRAX oficial (%)", 0.0, 95.0, 0.0, 0.1, key="dm_mof")
                dm_hip_oficial = st.number_input("Quadril recalculado no FRAX oficial (%)", 0.0, 90.0, 0.0, 0.1, key="dm_hip")
                if dm_mof_oficial == 0 or dm_hip_oficial == 0:
                    st.caption("O ajuste por diabetes só entra na comparação depois que os dois valores forem digitados.")

    # Módulo 7: Comprimento do Eixo do Quadril (HAL)
    with st.expander("7️⃣ Comprimento do Eixo do Quadril (HAL - mm)", expanded=False):
        if usar_dmo:
            usar_hal = st.checkbox("Avaliar HAL medido na DXA (Leslie et al., 2016)", value=False)
            if usar_hal:
                media_hal_sexo = 104.7 if sexo == "Feminino" else 121.3
                hal_min, hal_max = (86.1, 123.3) if sexo == "Feminino" else (99.1, 143.5)
                hal_mm = st.number_input(f"HAL em mm (média de referência {sexo}: {media_hal_sexo:.1f} mm)",
                                         80.0, 150.0, round(media_hal_sexo + 6.0, 1), 0.5)
                if not (hal_min <= hal_mm <= hal_max):
                    st.caption(f"Valor fora da faixa válida ({hal_min}–{hal_max} mm); será limitado a ela.")
                st.caption("Médias derivadas em aparelho GE Lunar (Manitoba). Cautela com outros fabricantes, "
                           "não caucasianos e IMC extremo.")
            else:
                hal_mm = None
        else:
            st.caption("Requer DMO do Colo Femoral ativa na coluna 1.")
            usar_hal, hal_mm = False, None


# ==========================================
# PROCESSAMENTO MATEMÁTICO INDIVIDUAL (ESTRITAMENTE 1 FATOR POR VEZ)
# ==========================================
mof_base, hip_base = mof_manual, hip_manual

candidatos_plus = []


def registrar_fator(nome_curto: str, referencia: str, mof_adj: float, hip_adj: float,
                    rr_mof: float = None, rr_hip: float = None, aproximado: bool = False):
    """Registra um ajuste já calculado. Multiplicadores ausentes são derivados dos valores."""
    if rr_mof is None:
        rr_mof = mof_adj / mof_base if mof_base > 0 else 1.0
    if rr_hip is None:
        rr_hip = hip_adj / hip_base if hip_base > 0 else 1.0
    candidatos_plus.append({
        "nome": nome_curto + (" ⚠️" if aproximado else ""),
        "referencia": referencia,
        "rr_mof": rr_mof,
        "rr_hip": rr_hip,
        "mof_isolado": mof_adj,
        "hip_isolado": hip_adj,
        "delta_mof": round(mof_adj - mof_base, 1),
        "delta_hip": round(hip_adj - hip_base, 1),
        "aproximado": aproximado
    })


def registrar_multiplicador(nome_curto, referencia, rr_mof, rr_hip, aproximado=False):
    m, h = aplicar_multiplicadores(mof_base, hip_base, rr_mof, rr_hip)
    registrar_fator(nome_curto, referencia, m, h, rr_mof, rr_hip, aproximado)


# 1a. Recência e sítio da fratura (Kanis et al., 2020 — tabelas originais)
if frat_prev and frat_recente:
    r_mof, r_hip = multiplicador_fratura_recente(idade, sexo, sitio_frat)
    registrar_multiplicador(f"Fratura recente <2a ({sitio_frat})", "Kanis et al., 2020", r_mof, r_hip)

# 1b. Número de fraturas prévias (ABRASSO / FRAX Brasil 2.0)
if frat_prev and MULT_NUM_FRATURAS[num_fraturas] > 1.0:
    r_nf = MULT_NUM_FRATURAS[num_fraturas]
    registrar_multiplicador(f"Múltiplas fraturas ({num_fraturas})", "ABRASSO 2024 / Kanis et al., 2022", r_nf, r_nf)

# 2. Dose de Glicocorticoide (Kanis et al., 2011 — ajustes médios, adotados pela ABRASSO)
if corticoide:
    if dose_gc.startswith("Alta"):
        registrar_multiplicador("Corticoide Alta Dose (≥7,5 mg/d)", "Kanis et al., 2011 / ABRASSO 2024", 1.15, 1.20)
    elif dose_gc.startswith("Baixa"):
        registrar_multiplicador("Corticoide Baixa Dose (<2,5 mg/d)", "Kanis et al., 2011", 0.80, 0.65)

# 3. Histórico de Quedas (ABRASSO 2024, derivado de Kanis et al., 2023)
if aplicar_quedas and quedas_op in MULT_QUEDAS:
    rq_mof, rq_hip = MULT_QUEDAS[quedas_op]
    registrar_multiplicador(f"Histórico de Quedas ({quedas_op})", "ABRASSO 2024 / Kanis et al., 2023", rq_mof, rq_hip)

# 4. Discordância Coluna/Fêmur (Leslie et al., 2011 — regra adotada pela ABRASSO)
if usar_dmo and t_coluna is not None:
    offset_dmo = t_colo - t_coluna  # positivo = coluna mais baixa que o colo → aumenta o risco
    offset_arred = arredondar_meio_para_cima(offset_dmo)
    if offset_arred != 0:
        fator_leslie = round(max(0.5, 1.0 + 0.10 * offset_arred), 2)
        registrar_multiplicador(f"Discordância L1-L4 ({offset_dmo:+.1f} DP)", "Leslie et al., 2011 / ABRASSO 2024",
                                fator_leslie, 1.00)

# 5. TBS (aproximação a partir dos HR de McCloskey et al., 2015)
if tbs_val is not None:
    idade_tbs_hip = max(50, min(80, idade))
    def _z_tbs(a):
        tbs_ref = 1.300 - 0.004 * (a - 60)  # TBS médio esperado para a idade (aprox.)
        return max(-3.0, min(3.0, (tbs_ref - tbs_val) / 0.12))
    r_tbs_mof = round(math.pow(1.18, _z_tbs(idade)), 2)
    r_tbs_hip = round(math.pow(1.23, _z_tbs(idade_tbs_hip)), 2)
    registrar_multiplicador(f"TBS L1-L4 ({tbs_val:.3f})", "McCloskey et al., 2015/2016 (aprox.)",
                            r_tbs_mof, r_tbs_hip, aproximado=True)

# 6. Diabetes Mellitus Tipo 2 (Leslie et al., 2018 / ABRASSO 2024): recálculo do FRAX
if dm2 and metodo_dm is not None:
    nome_dm = "Diabetes Tipo 2 (" + ("AR = Sim" if metodo_dm.startswith("Marcar")
                                     else "idade +10a" if metodo_dm.startswith("Somar")
                                     else "T-score −0,5") + ")"
    # Só entra na comparação com o valor recalculado no FRAX oficial (sem estimativa automática)
    if dm_mof_oficial > 0 and dm_hip_oficial > 0:
        registrar_fator(nome_dm, "Leslie et al., 2018 / ABRASSO 2024",
                        round(max(dm_mof_oficial, dm_hip_oficial), 1), round(dm_hip_oficial, 1))

# 7. HAL - Hip Axis Length (Leslie et al., 2016): ajuste bilinear do risco de QUADRIL
if usar_hal and hal_mm is not None:
    media_hal = 104.7 if sexo == "Feminino" else 121.3
    hal_min, hal_max = (86.1, 123.3) if sexo == "Feminino" else (99.1, 143.5)
    dif_hal = max(hal_min, min(hal_max, hal_mm)) - media_hal
    r_hal_hip = 1.0 + 0.047 * dif_hal if dif_hal >= 0 else max(0.30, 1.0 + 0.038 * dif_hal)
    registrar_multiplicador(f"Eixo do Quadril HAL ({hal_mm:.1f} mm)", "Leslie et al., 2016", 1.00, round(r_hal_hip, 2))


# ------------------------------------------
# COLUNA 3: TABELA COMPARATIVA, SELETOR DE FATOR ÚNICO E RESULTADO FINAL
# ------------------------------------------
with col_res:
    st.subheader("📊 3. Seleção do fator de maior impacto e Resultado")

    # 1. Card FRAX Base
    rotulo_base = "FRAX BRASIL OFICIAL (SEM MODIFICADORES)"
    st.markdown(f"""
    <div class="result-card">
        <div style="font-size:12.5px; color:#555; font-weight:bold;">{rotulo_base}</div>
        <div style="display:flex; justify-content:space-between; margin-top:6px;">
            <div><span style="font-size:13.5px; color:#222;">Fratura Maior (MOF):</span><br><b style="font-size:22px; color:#222;">{mof_base:.1f}%</b></div>
            <div><span style="font-size:13.5px; color:#222;">Fratura de Quadril (FQ):</span><br><b style="font-size:22px; color:#222;">{hip_base:.1f}%</b></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 2. Tabela Comparativa de Impacto Individual + Seletor de Fator Único
    if candidatos_plus:
        # Ordena do maior MOF ajustado para o menor (desempate pelo quadril)
        candidatos_ordenados = sorted(candidatos_plus, key=lambda x: (x["mof_isolado"], x["hip_isolado"]), reverse=True)
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
        if any(c["aproximado"] for c in candidatos_plus):
            st.caption("⚠️ = ajuste aproximado (coeficientes oficiais não publicados).")

        opcoes_radio = [
            f"⭐ Automático — Fator Dominante: {fator_dominante['nome']} (MOF {fator_dominante['mof_isolado']:.1f}% | FQ {fator_dominante['hip_isolado']:.1f}%)"
        ] + [
            f"{c['nome']} → MOF {c['mof_isolado']:.1f}% | Quadril {c['hip_isolado']:.1f}%"
            for c in candidatos_ordenados
        ]

        escolha_medico = st.radio(
            "👆 Escolha o fator único que deseja aplicar ao cálculo final:",
            options=opcoes_radio,
            index=0,
            help="FRAXplus e ABRASSO: não há evidência para ajustes simultâneos — aplica-se apenas 1 ajuste, "
                 "normalmente o de maior impacto/relevância clínica."
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

    # 3. Card Resultado Final
    delta_mof = mof_plus - mof_base
    delta_hip = hip_plus - hip_base
    st.markdown(f"""
    <div class="plus-card">
        <div style="font-size:12.5px; color:#B22222; font-weight:bold;">✨ RESULTADO FINAL AJUSTADO (1 FATOR APLICADO)</div>
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

    # 4. Limiares e gráfico ABRASSO
    lim = limiares_abrasso_brasil(idade)
    li_pac = lim["li"]
    lsa_pac = lim["lsa"]
    vha_pac = lim["muito_alto"]
    lia_pac = min(lim["lia"], li_pac)
    li_hip_pac = lim["li_quadril"]
    vha_hip_pac = round(1.6 * lim["li_quadril"], 1)

    # Gráficos no formato do FRAX Brasil 2.0: fraturas maiores e fratura de quadril.
    # Como na ABRASSO, o gráfico de quadril só é exibido quando há DMO.
    st.markdown("##### 📈 Probabilidade de Fraturas Maiores (MOF)")
    st.markdown(gerar_svg_grafico_abrasso(idade, mof_base, mof_plus, usar_dmo, "mof"),
                unsafe_allow_html=True)
    st.markdown("##### 📈 Probabilidade de Fratura de Quadril")
    if usar_dmo:
        st.markdown(gerar_svg_grafico_abrasso(idade, hip_base, hip_plus, True, "quadril"),
                    unsafe_allow_html=True)
    else:
        st.caption("Sem DMO, o FRAX Brasil 2.0 (ABRASSO) exibe apenas o gráfico de fraturas maiores. "
                   "Informe a DMO do colo femoral para ver o gráfico de quadril.")

    # Critério fixo NOF/BHOF (EUA): exibido apenas como informação, pois é derivado de
    # custo-efetividade norte-americano e não faz parte da estratificação da ABRASSO.
    criterio_nof_fixo = (mof_plus >= 20.0 or hip_plus >= 3.0)
    fratura_recente = bool(frat_prev and frat_recente)
    osteoporose_dxa = bool(usar_dmo and (t_colo <= -2.5 or (t_coluna is not None and t_coluna <= -2.5)))

    quadril_muito_alto = bool(usar_dmo and hip_plus >= vha_hip_pac)
    if mof_plus >= vha_pac or quadril_muito_alto or fratura_recente:
        if mof_plus >= vha_pac:
            motivo = f"MOF ≥ {vha_pac}%"
        elif quadril_muito_alto:
            motivo = f"Quadril ≥ {vha_hip_pac}%"
        else:
            motivo = "fratura recente (< 2 anos)"
        categoria = f"MUITO ALTO RISCO ({motivo})"
        cor_badge = "#8B0000"
        conduta = "Considerar terapia sequencial iniciando com agente osteoformador / anabólico (Teriparatida ou Romosozumabe) ou antirreabsortivo parenteral potente (Ácido Zoledrônico / Denosumabe), conforme diretriz ABRASSO/PCDT."
    elif usar_dmo and (mof_plus >= li_pac or hip_plus >= li_hip_pac or osteoporose_dxa):
        categoria = "ALTO RISCO (Acima do Limiar de Intervenção)"
        cor_badge = "#D35400"
        conduta = "Indicado tratamento farmacológico (ex: Bisfosfonatos orais/injetáveis ou Denosumabe), suplementação adequada de cálcio/vitamina D e prevenção de quedas."
    elif (not usar_dmo) and mof_plus >= lsa_pac:
        categoria = "ALTO RISCO (Acima do Limiar Superior de Avaliação)"
        cor_badge = "#D35400"
        conduta = "Indicado tratamento farmacológico mesmo sem DXA (ex: Bisfosfonatos), suplementação adequada de cálcio/vitamina D e prevenção de quedas. A DXA ajuda a monitorar."
    elif (not usar_dmo) and mof_plus >= lia_pac:
        if mof_plus >= li_pac:
            categoria = "RISCO INTERMEDIÁRIO — acima da linha de intervenção"
            conduta = "Faixa amarela acima da linha de intervenção (FRAX Brasil 2.0): o tratamento pode ser iniciado; solicitar DXA e recalcular com a DMO do colo femoral."
        else:
            categoria = "RISCO INTERMEDIÁRIO (solicitar DXA)"
            conduta = "Solicitar densitometria (DXA) e recalcular o FRAX com a DMO do colo femoral antes de decidir o tratamento."
        cor_badge = "#B7950B"
    else:
        categoria = "BAIXO RISCO"
        cor_badge = "#27AE60"
        conduta = "Abaixo do limiar de intervenção farmacológica aos critérios atuais. Manter medidas não farmacológicas e monitorar."

    texto_limiares = (f"Intervenção ≥ <b>{li_pac}%</b> | Muito Alto Risco ≥ <b>{vha_pac}%</b>"
                      + (f" | Quadril: intervenção ≥ <b>{li_hip_pac}%</b>, muito alto ≥ <b>{vha_hip_pac}%</b>" if usar_dmo else
                         f" | Faixa DXA: <b>{lia_pac}%</b> a <b>{lsa_pac}%</b>"))
    origem_limiar = "FRAX oficial, modelo híbrido fixo ≥ 70 a"
    st.markdown(f"""
    <div style="margin-top:10px; margin-bottom:10px;">
        <div class="badge-risco" style="background-color:{cor_badge};">{categoria}</div>
        <div style="font-size:12px; color:#444; margin-top:6px;">
            <b>Limiares ABRASSO ({idade} anos, {origem_limiar}):</b> {texto_limiares}<br>
            <b>Critério Fixo NOF/BHOF (EUA, apenas informativo):</b> MOF ≥ 20% ou Quadril ≥ 3% ({'Atendido' if criterio_nof_fixo else 'Não atendido'})
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.info(f"**Conduta Sugerida:** {conduta}")

    with st.expander("📋 Resumo pronto para copiar para o prontuário", expanded=False):
        dmo_txt = f"T-score Colo Femoral (NHANES III) = {t_colo:+.2f} DP" if usar_dmo else "Sem DMO informada"
        col_txt = f" | T-score L1-L4 = {t_coluna:+.2f} DP" if (usar_dmo and t_coluna is not None) else ""
        outros_txt = ", ".join([f"{c['nome']} (MOF {c['mof_isolado']:.1f}%)" for c in candidatos_plus]) if candidatos_plus else "Nenhum"
        origem_base = "FRAX Brasil oficial"
        resumo_prontuario = (
            f"AVALIAÇÃO DE RISCO DE FRATURA EM 10 ANOS (FRAX BRASIL + AJUSTE FRAXplus/ABRASSO):\n"
            f"- Paciente: {sexo}, {idade} anos, IMC {imc:.1f} kg/m² | {dmo_txt}{col_txt}\n"
            f"- Risco FRAX Base ({origem_base}): Fratura Maior (MOF) = {mof_base:.1f}% | Quadril = {hip_base:.1f}%\n"
            f"- Simulação Individual dos ajustes: {outros_txt}\n"
            f"- Ajuste único aplicado: {nome_fator_final}\n"
            f"- Risco Final Ajustado: Fratura Maior (MOF) = {mof_plus:.1f}% | Quadril = {hip_plus:.1f}%\n"
            f"- Estratificação ABRASSO ({idade}a - Limiar de intervenção {li_pac}% / Muito alto {vha_pac}%): {categoria}."
        )
        st.code(resumo_prontuario, language="text")

    with st.expander("ℹ️ Notas metodológicas e fontes", expanded=False):
        st.markdown("""
**Ajustes com coeficientes publicados (✅):**
- Recência/sítio da fratura: razões de probabilidade das Tabelas 4–7 de Kanis et al., *Osteoporos Int* 2020 (por sexo e idade).
- Glicocorticoide: alta dose MOF ×1,15 / quadril ×1,20; baixa dose ×0,80 / ×0,65 (Kanis et al., 2011).
- Quedas, número de fraturas e discordância coluna–colo: tabela de ajustes do FRAX Brasil 2.0 (ABRASSO, 2024).
- HAL: +4,7%/mm acima e −3,8%/mm abaixo da média por sexo, só no quadril (Leslie et al., *J Clin Densitom* 2016).
- DM2: métodos validados por Leslie et al., *JBMR* 2018 (AR = sim, idade +10 anos ou T-score −0,5). O resultado vem do recálculo no site oficial com o parâmetro escolhido (T-score −0,5 recomendado com DMO; AR = Sim sem DMO).
- Limiares: valores da calculadora FRAX oficial (Brasil) para mulher com IMC 25 — com fratura prévia (limiar de intervenção, fixo a partir dos 70 anos) e sem fatores de risco (limite inferior da faixa amarela), conforme a metodologia NOGG adotada pela ABRASSO. Muito alto risco = 1,6 × limiar, para MOF e quadril.

**Aproximações (⚠️):**
- TBS: fórmula oficial não publicada; usa HR por DP de McCloskey et al., 2015.

Todos os ajustes multiplicam a **probabilidade** em 10 anos e apenas **um** é aplicado por vez (FRAXplus/ABRASSO).
""")
