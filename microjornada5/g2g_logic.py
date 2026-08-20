"""
==============================================================================
 g2g_logic.py  —  Lógica canônica G2G / Passeio / IPAR  (BAERI 5064)
 Para uso como TOOLS de um agente Google ADK (Agent Development Kit).
------------------------------------------------------------------------------
 Regras canônicas (Microjornada 5 · v3.2 / ADR-030):
   D1) Fonte  = rw_mdriver.programacao   (NUNCA td_mdriver — retém ~40 dias)
   D1) G2G    = hora_saida_patio_interno − hora_entrada_patio_interno (minutos)
   - Dedupe por 'programacao', mantendo a maior 'sequencia_publicacao'
   - Filtro de centro: cod_centro == '5064'
==============================================================================
"""

from datetime import datetime
from collections import defaultdict, Counter
import statistics as stt

# ---------------------------------------------------------------------------
# 0) HELPERS
# ---------------------------------------------------------------------------
def _dt(s):
    """Converte string 'YYYY-MM-DD HH:MM:SS' -> datetime (ou None)."""
    s = (s or "").strip().split(".")[0]
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _mins(ini, fim):
    """Diferença em minutos entre dois timestamps; descarta lixo (<=0 ou >24h)."""
    a, b = _dt(ini), _dt(fim)
    if a and b:
        d = (b - a).total_seconds() / 60.0
        return d if 0 < d <= 1440 else None
    return None


def _dedupe(records, centro="5064"):
    """
    Filtra pelo centro e mantém, por 'programacao', o registro de maior
    'sequencia_publicacao' (versão mais recente da publicação).
    """
    by_prog = {}
    for r in records:
        if centro and r.get("cod_centro") != centro:
            continue
        p = r.get("programacao")
        seq = int(r.get("sequencia_publicacao") or 0)
        if p not in by_prog or seq > int(by_prog[p].get("sequencia_publicacao") or 0):
            by_prog[p] = r
    return list(by_prog.values())


# ---------------------------------------------------------------------------
# 1) TOOL: quebra do G2G por fase
# ---------------------------------------------------------------------------
def analisar_g2g(records, centro="5064"):
    """
    Retorna o G2G (média/mediana/máx) e a quebra por fase, em minutos.
    Fases:
      fila         = entrada_patio_interno − liberacao
      setup        = inicio_carregamento   − entrada_patio_interno
      carregamento = fim_carregamento      − inicio_carregamento
      pos_carreg   = saida_patio_interno   − fim_carregamento
      g2g          = saida_patio_interno   − entrada_patio_interno   (D1)
    """
    U = _dedupe(records, centro)
    g2g, fila, setup, carreg, pos = [], [], [], [], []

    for p in U:
        g = _mins(p.get("hora_entrada_patio_interno"), p.get("hora_saida_patio_interno"))
        if g: g2g.append(g)
        f = _mins(p.get("hora_liberacao"), p.get("hora_entrada_patio_interno"))
        if f: fila.append(f)
        s = _mins(p.get("hora_entrada_patio_interno"), p.get("hora_inicio_carregamento"))
        if s: setup.append(s)
        c = _mins(p.get("hora_inicio_carregamento"), p.get("hora_fim_carregamento"))
        if c: carreg.append(c)
        o = _mins(p.get("hora_fim_carregamento"), p.get("hora_saida_patio_interno"))
        if o: pos.append(o)

    med = lambda x: round(stt.mean(x), 1) if x else 0
    p50 = lambda x: round(stt.median(x), 1) if x else 0

    return {
        "n_programacoes": len(U),
        "g2g": {"media": med(g2g), "mediana": p50(g2g),
                "max": round(max(g2g), 1) if g2g else 0, "n": len(g2g)},
        "fases_min": {
            "fila": med(fila),
            "setup": med(setup),               # inclui passeio + coleta de amostra
            "carregamento": med(carreg),
            "pos_carregamento": med(pos),
        },
        "meta_min": 39,
        "gap_media_vs_meta": round(med(g2g) - 39, 1),
    }


# ---------------------------------------------------------------------------
# 2) TOOL: detecção de PASSEIO (duplo encoste)
# ---------------------------------------------------------------------------
def detectar_passeio(records, centro="5064"):
    """
    Passeio = mesma PLACA carregando em MAIS DE UMA baia no mesmo dia.
    Só é detectável quando o campo 'baia' vem nomeado (ex.: 'PE 09 A').

    Retorna a lista de placas com passeio, as baias percorridas e a taxa.
    """
    U = _dedupe(records, centro)
    placa_baias = defaultdict(set)

    for p in U:
        placa = (p.get("placa") or "").strip()
        baia = (p.get("baia") or "").strip()
        if placa and baia:
            placa_baias[placa].add(baia)

    passeios = {pl: sorted(bs) for pl, bs in placa_baias.items() if len(bs) > 1}
    placas_com_baia = len(placa_baias)
    taxa = round(100 * len(passeios) / placas_com_baia, 1) if placas_com_baia else 0

    return {
        "passeios": passeios,                       # {placa: [baia1, baia2, ...]}
        "n_passeios": len(passeios),
        "placas_com_baia": placas_com_baia,
        "taxa_passeio_pct": taxa,
        "baias_utilizadas": dict(
            Counter((p.get("baia") or "").strip() for p in U if (p.get("baia") or "").strip())
        ),
    }


# ---------------------------------------------------------------------------
# 3) TOOL: aderência ao IPAR e motivos de exclusão
# ---------------------------------------------------------------------------
def analisar_ipar(records, centro="5064"):
    """
    Calcula a aderência ao IPAR (entra_no_ipar == '1') e ranqueia
    os motivos de exclusão (motivo_ipar) para os que ficam de fora.
    """
    U = _dedupe(records, centro)
    total = len(U)
    entram = sum(1 for p in U if p.get("entra_no_ipar") == "1")
    excedido = sum(1 for p in U if p.get("limite_ipar_excedido") == "True")

    motivos = Counter()
    for p in U:
        if p.get("entra_no_ipar") != "1":
            m = p.get("motivo_ipar", "")
            if m:
                motivos[m] += 1

    return {
        "total": total,
        "entram": entram,
        "aderencia_pct": round(100 * entram / total, 1) if total else 0,
        "limite_excedido": excedido,
        "motivos_exclusao": [
            {"motivo": m, "qtd": c, "pct": round(100 * c / total, 1)}
            for m, c in motivos.most_common()
        ],
    }


# ---------------------------------------------------------------------------
# 4) ORQUESTRADOR (o agente pode chamar só este)
# ---------------------------------------------------------------------------
def painel_operacional(records, centro="5064"):
    """Consolida as 3 análises num único dicionário pronto para o agente."""
    return {
        "centro": centro,
        "g2g": analisar_g2g(records, centro),
        "passeio": detectar_passeio(records, centro),
        "ipar": analisar_ipar(records, centro),
    }
