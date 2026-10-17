"""Generate a small EPANET-compatible *illustrative* water network INP file.
It is not a calibrated real distribution network.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NODE_META = {
    "R0": (45, 220, 0.0, 20),
    "J01": (170, 120, 1.2, 27), "J02": (170, 320, 1.2, 27),
    "J03": (320, 60, 0.8, 30), "J04": (320, 165, 1.3, 31),
    "J05": (320, 270, 1.1, 29), "J06": (320, 375, 0.9, 28),
    "J07": (470, 35, 0.8, 29), "J08": (470, 115, 1.6, 31),
    "J09": (470, 200, 1.4, 30), "J10": (470, 280, 0.6, 26),
    "J11": (470, 340, 1.3, 30), "J12": (470, 410, 0.7, 29),
    "J13": (640, 60, 1.1, 27), "J14": (640, 155, 1.2, 30),
    "J15": (640, 245, 0.9, 31), "J16": (640, 310, 1.2, 29),
    "J17": (640, 380, 1.0, 28), "J18": (640, 440, 0.7, 26),
    "J19": (810, 100, 1.5, 27), "J20": (810, 315, 1.7, 27),
}
# Directed in the educational surrogate; EPANET resolves actual flow direction independently.
EDGES = [
    ("R0","J01"),("R0","J02"),
    ("J01","J03"),("J01","J04"),("J02","J05"),("J02","J06"),
    ("J03","J07"),("J03","J08"),("J04","J08"),("J04","J09"),
    ("J05","J10"),("J05","J11"),("J06","J11"),("J06","J12"),
    ("J07","J13"),("J08","J13"),("J08","J14"),("J09","J14"),("J09","J15"),
    ("J10","J16"),("J11","J16"),("J11","J17"),("J12","J17"),("J12","J18"),
    ("J13","J19"),("J14","J19"),("J15","J20"),("J16","J20"),("J17","J20"),("J18","J20"),
]


def make_inp(path=ROOT / "data" / "demo_network.inp"):
    lines = [
        '[TITLE]',
        '; AquaSentinel educational distribution network. Synthetic, not field calibrated.',
        '[JUNCTIONS]',
        '; ID   Elev(m) Demand(LPS)',
    ]
    for node, (_, _, demand, elev) in NODE_META.items():
        if node != "R0":
            lines.append(f'{node:<8} {elev:<8} {demand:.3f}')
    lines += ['[RESERVOIRS]', 'R0   95.0', '[PIPES]', '; ID from to length(m) diameter(mm) roughness minorloss status']
    for idx, (u, v) in enumerate(EDGES, 1):
        x1,y1,_,_ = NODE_META[u]
        x2,y2,_,_ = NODE_META[v]
        # Coordinates represent synthetic meters, hence idealized straight-line lengths.
        length = round(((x2-x1)**2+(y2-y1)**2)**0.5 * 1.5, 1)
        lines.append(f'P{idx:03d} {u:<5} {v:<5} {length:<8} 200 125 0 OPEN')
    lines += [
        '[OPTIONS]',
        'UNITS LPS',
        'HEADLOSS H-W',
        'QUALITY CHEMICAL mg/L',
        'SPECIFIC GRAVITY 1.0',
        'VISCOSITY 1.0',
        '[TIMES]',
        'DURATION 24:00',
        'HYDRAULIC TIMESTEP 0:30',
        'QUALITY TIMESTEP 0:05',
        'PATTERN TIMESTEP 0:30',
        'REPORT TIMESTEP 0:30',
        'REPORT START 0:00',
        '[COORDINATES]',
    ]
    for n,(x,y,_,_) in NODE_META.items():
        lines.append(f'{n:<8} {x} {y}')
    lines += ['[END]', '']
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines), encoding='utf-8')
    return path

if __name__ == '__main__':
    print('Wrote:', make_inp())
