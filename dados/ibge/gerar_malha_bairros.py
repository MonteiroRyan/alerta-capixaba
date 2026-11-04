import json
import sqlite3
import struct
import sys
from pathlib import Path

TOLERANCIA = 0.0001
DESTINO = Path(__file__).with_name("malha-bairros-es-cd2022.geojson")


def ler_wkb(dados: bytes, pos: int = 0):
    ordem = "<" if dados[pos] == 1 else ">"
    tipo = struct.unpack_from(ordem + "I", dados, pos + 1)[0] % 1000
    pos += 5
    if tipo == 3:
        n_aneis = struct.unpack_from(ordem + "I", dados, pos)[0]
        pos += 4
        aneis = []
        for _ in range(n_aneis):
            n = struct.unpack_from(ordem + "I", dados, pos)[0]
            pos += 4
            pontos = struct.unpack_from(ordem + "d" * 2 * n, dados, pos)
            pos += 16 * n
            aneis.append([[pontos[i], pontos[i + 1]] for i in range(0, 2 * n, 2)])
        return [aneis], pos
    if tipo == 6:
        n = struct.unpack_from(ordem + "I", dados, pos)[0]
        pos += 4
        poligonos = []
        for _ in range(n):
            partes, pos = ler_wkb(dados, pos)
            poligonos += partes
        return poligonos, pos
    raise ValueError(f"Geometria WKB tipo {tipo} não suportada")


def geometria_gpkg(blob: bytes) -> list:
    flags = blob[3]
    envelope = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[(flags >> 1) & 0b111]
    return ler_wkb(blob, 8 + envelope)[0]


def simplificar(anel: list, tol: float) -> list:
    if len(anel) < 5:
        return anel
    manter = [False] * len(anel)
    manter[0] = manter[-1] = True
    pilha = [(0, len(anel) - 1)]
    while pilha:
        a, b = pilha.pop()
        (x1, y1), (x2, y2) = anel[a], anel[b]
        dx, dy = x2 - x1, y2 - y1
        norma = (dx * dx + dy * dy) ** 0.5 or 1e-12
        maior, idx = 0.0, None
        for i in range(a + 1, b):
            x, y = anel[i]
            d = abs(dy * x - dx * y + x2 * y1 - y2 * x1) / norma
            if d > maior:
                maior, idx = d, i
        if idx is not None and maior > tol:
            manter[idx] = True
            pilha += [(a, idx), (idx, b)]
    resultado = [[round(x, 5), round(y, 5)] for (x, y), m in zip(anel, manter) if m]
    return resultado if len(resultado) >= 4 else anel


def main(gpkg: Path) -> None:
    con = sqlite3.connect(gpkg)
    feicoes = []
    for cd_mun, cd_bairro, nome, blob in con.execute(
            "SELECT CD_MUN, CD_BAIRRO, NM_BAIRRO, geom FROM ES_bairros_CD2022 ORDER BY CD_BAIRRO"):
        poligonos = [[simplificar(anel, TOLERANCIA) for anel in p] for p in geometria_gpkg(blob)]
        feicoes.append({
            "type": "Feature",
            "properties": {"cd_bairro": cd_bairro, "cd_mun": cd_mun, "nome": nome},
            "geometry": {"type": "MultiPolygon", "coordinates": poligonos},
        })
    DESTINO.write_text(json.dumps({"type": "FeatureCollection", "features": feicoes}, ensure_ascii=False),
                       encoding="utf-8")
    print(f"{len(feicoes)} bairros -> {DESTINO.name} ({DESTINO.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
