"""
Carga acelerada e radiacao eletromagnetica
--------------------------------------------
Demonstracao interativa para sala de aula.

Como as linhas de campo sao construidas:
Cada linha guarda, para cada direcao fixa no espaco, o ponto que "saiu" da
carga ha um tempo r/c (c = velocidade da luz simulada, ajustavel na barra
de parametros). Perto da carga, o ponto reflete sua posicao atual; longe,
reflete uma posicao passada. Quando a carga muda de velocidade, aparece
uma dobra (kink) que se afasta a velocidade c: essa dobra E a radiacao se
propagando. Antes do inicio da simulacao, presume-se que a carga estava
parada (para preencher a tela inteira desde o primeiro quadro).

Um limitador universal de velocidade garante que a carga (em qualquer
modo, inclusive arrastada com o mouse) nunca se mova mais rapido que c --
sem isso, a matematica de tempo retardado deixa de fazer sentido. Para
isso funcionar mesmo ao arrastar, o mouse so atualiza um "alvo" -- e a
propria carga so se move dentro de step(), onde o limitador roda.

Requisitos:  pip install pygame
Executar:    python carga_acelerada_radiacao.py

Nota sobre nitidez em telas de alta densidade (Retina/4K): este script
tenta ativar o reconhecimento de DPI no Windows automaticamente. Em Macs
Retina, o pygame historicamente tem suporte inconsistente a isso entre
versoes -- se a janela ainda parecer com pouca definicao, tente atualizar
o pygame (`pip install -U pygame`) ou o fork pygame-ce, ou rodar em tela
cheia (altere RESIZABLE para FULLSCREEN abaixo).
"""

import asyncio
import math
import random
import sys
from collections import deque

if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import pygame
import pygame.gfxdraw

pygame.init()

W, H = 1200, 720
screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
pygame.display.set_caption("Carga acelerada e radiacao eletromagnetica")
clock = pygame.time.Clock()

# A interface agora se adapta ao tamanho real do canvas/iframe.
# As fontes também são recalculadas para evitar texto minúsculo em telas grandes.
font = pygame.font.SysFont("Arial", 16)
font_small = pygame.font.SysFont("Arial", 13)

MIN_SIM_HEIGHT = 190
UI_PAD = 12
UI_GAP = 8
BUTTON_H = 34
SLIDER_ROW_H = 44


BG = (7, 11, 20)
PANEL = (13, 20, 36)
BORDER = (24, 33, 52)
LINE_COLOR = (125, 211, 252)
TEXT = (230, 237, 247)
MUTED = (150, 163, 186)
ACCENT = (245, 165, 36)
ACCENT2 = (94, 234, 212)

N_LINES = 40
SPEED_CAP = 0.92   # nenhum movimento pode exceder este % de c

MODE_BUTTONS = [
    ("static", "Estatica"),
    ("uniform", "Velocidade constante"),
    ("kick", "Puxao unico"),
    ("oscillate", "Oscilacao"),
    ("circle", "Circulo"),
    ("drag", "Arrastar"),
]
EXTRA_BUTTONS = [
    ("reset", "Reiniciar"),
]

INSTRUCTIONS = [
    'Arraste a carga laranja ou escolha um movimento -- nada se move mais rapido que c (ajustavel na barra',
    'abaixo do grafico). As linhas mostram ate onde a "noticia" sobre a posicao da carga ja chegou, viajando',
    'a velocidade da luz, e preenchem a tela toda desde o primeiro quadro.',
]


def draw_aa_circle(surface, color, pos, radius):
    x, y = int(round(pos[0])), int(round(pos[1]))
    pygame.gfxdraw.aacircle(surface, x, y, radius, color)
    pygame.gfxdraw.filled_circle(surface, x, y, radius, color)


def make_state(w, h):
    cx, cy = w / 2, h / 2
    return {
        "charge": [cx, cy],
        "anchor": [cx, cy],
        "cx": cx, "cy": cy,
        "mode": "static",
        "t": 0.0,
        "origin_t": 0.0,
        "history": deque(),          # (x, y, t)
        "kick": None,
        "C": 320.0,
        "uniform_vx": 170.0,
        "kick_dist": 90.0,
        "kick_dur": 0.12,
        "osc_amp": 140.0,
        "osc_omega": 2.1,
        "circ_r": 100.0,
        "circ_omega": 2.4,
        "pointer": None,
        "dragging": False,
        "_dragging_slider": None,
        "_layout_center": (cx, cy),
    }


def ease_in_out(p):
    return 2 * p * p if p < 0.5 else 1 - (-2 * p + 2) ** 2 / 2


def set_mode(s, m, w, h):
    s["mode"] = m
    if m == "kick":
        ang = random.random() * math.tau
        x0, y0 = s["charge"]
        dist = s["kick_dist"]
        s["kick"] = {
            "x0": x0, "y0": y0,
            "x1": x0 + math.cos(ang) * dist, "y1": y0 + math.sin(ang) * dist,
            "elapsed": 0.0, "duration": s["kick_dur"],
        }


def step(s, dt, w, h):
    s["t"] += dt
    C = s["C"]
    prev_x, prev_y = s["charge"][0], s["charge"][1]
    m = s["mode"]
    if m == "uniform":
        s["charge"][0] += s["uniform_vx"] * dt
        margin = min(sim_rect.width, sim_rect.height) * 0.08 + 12
        if s["charge"][0] < margin or s["charge"][0] > sim_rect.width - margin:
            s["uniform_vx"] *= -1
    elif m == "kick" and s["kick"]:
        k = s["kick"]
        k["elapsed"] += dt
        p = min(1.0, k["elapsed"] / k["duration"])
        e = ease_in_out(p)
        s["charge"][0] = k["x0"] + (k["x1"] - k["x0"]) * e
        s["charge"][1] = k["y0"] + (k["y1"] - k["y0"]) * e
        if p >= 1.0:
            s["kick"] = None
    elif m == "oscillate":
        s["charge"][0] = s["cx"] + s["osc_amp"] * math.sin(s["osc_omega"] * s["t"])
        s["charge"][1] = s["cy"]
    elif m == "circle":
        s["charge"][0] = s["cx"] + s["circ_r"] * math.cos(s["circ_omega"] * s["t"])
        s["charge"][1] = s["cy"] + s["circ_r"] * math.sin(s["circ_omega"] * s["t"])
    elif m == "drag":
        # a carga persegue o alvo do mouse; o limitador abaixo garante que
        # ela nunca "teleporte" mais rapido que c, mesmo com um flick rapido
        if s["dragging"] and s["pointer"]:
            s["charge"][0], s["charge"][1] = s["pointer"]
    # 'static': posicao mantida

    # limitador universal: nada pode se mover mais rapido que c, em nenhum modo
    mvx = s["charge"][0] - prev_x
    mvy = s["charge"][1] - prev_y
    mv = math.hypot(mvx, mvy)
    max_move = C * SPEED_CAP * dt
    if mv > max_move and mv > 1e-9:
        s["charge"][0] = prev_x + mvx / mv * max_move
        s["charge"][1] = prev_y + mvy / mv * max_move

    hist = s["history"]
    hist.append((s["charge"][0], s["charge"][1], s["t"]))
    max_r = math.hypot(sim_rect.width, sim_rect.height) * 1.08
    max_age = max_r / max(C, 1.0) + 0.15
    while hist and (s["t"] - hist[0][2]) > max_age:
        hist.popleft()


def build_line_points(s, theta, max_r):
    cs, sn = math.cos(theta), math.sin(theta)
    pts = []
    hist = s["history"]
    t = s["t"]
    C = s["C"]
    reached_end = False
    for k in range(len(hist) - 1, -1, -1):
        hx, hy, ht = hist[k]
        r = C * (t - ht)
        if r > max_r:
            reached_end = True
            break
        pts.append((hx + r * cs, hy + r * sn))
    if not reached_end:
        ax, ay = s["anchor"]
        r_start = C * (t - hist[0][2]) if hist else max(0.0, C * (t - s["origin_t"]))
        pts.append((ax + r_start * cs, ay + r_start * sn))
        pts.append((ax + max_r * cs, ay + max_r * sn))
    return pts



def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def update_fonts(w):
    """Escala a tipografia com a largura disponível, sem ficar minúscula no celular."""
    global font, font_small
    base = int(clamp(w / 68.0, 12, 18))
    small = int(clamp(base - 2, 11, 16))
    font = pygame.font.SysFont("Arial", base)
    font_small = pygame.font.SysFont("Arial", small)


def wrap_text(text, font_obj, max_width):
    """Quebra uma linha longa em linhas que cabem na largura disponível."""
    words = text.split()
    if not words:
        return [""]
    lines = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if font_obj.size(candidate)[0] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def instruction_lines(w):
    max_width = max(220, w - 2 * UI_PAD)
    out = []
    for text in INSTRUCTIONS:
        out.extend(wrap_text(text, font_small, max_width))
    return out


def get_slider_specs(s):
    specs = [
        {
            "key": "C", "label": "Velocidade da luz (c)", "vmin": 40, "vmax": 800,
            "get": lambda s: s["C"],
            "set": lambda s, v: s.__setitem__("C", v),
            "fmt": lambda v: f"{v:.0f} px/s",
        }
    ]

    m = s["mode"]
    if m == "uniform":
        specs.append({
            "key": "uniform_vx", "label": "Velocidade", "vmin": 10, "vmax": 380,
            "get": lambda s: abs(s["uniform_vx"]),
            "set": lambda s, v: s.__setitem__("uniform_vx", math.copysign(v, s["uniform_vx"] or 1.0)),
            "fmt": lambda v: f"{v:.0f} px/s",
        })
    elif m == "kick":
        specs.extend([
            {
                "key": "kick_dist", "label": "Distância do puxão", "vmin": 20, "vmax": 260,
                "get": lambda s: s["kick_dist"],
                "set": lambda s, v: s.__setitem__("kick_dist", v),
                "fmt": lambda v: f"{v:.0f} px",
            },
            {
                "key": "kick_dur", "label": "Duração do puxão", "vmin": 0.05, "vmax": 0.5,
                "get": lambda s: s["kick_dur"],
                "set": lambda s, v: s.__setitem__("kick_dur", v),
                "fmt": lambda v: f"{v:.2f} s",
            },
        ])
    elif m == "oscillate":
        specs.extend([
            {
                "key": "osc_amp", "label": "Amplitude", "vmin": 20, "vmax": 280,
                "get": lambda s: s["osc_amp"],
                "set": lambda s, v: s.__setitem__("osc_amp", v),
                "fmt": lambda v: f"{v:.0f} px",
            },
            {
                "key": "osc_omega", "label": "Frequência angular", "vmin": 0.3, "vmax": 6,
                "get": lambda s: s["osc_omega"],
                "set": lambda s, v: s.__setitem__("osc_omega", v),
                "fmt": lambda v: f"{v:.1f} rad/s",
            },
        ])
    elif m == "circle":
        specs.extend([
            {
                "key": "circ_r", "label": "Raio", "vmin": 20, "vmax": 240,
                "get": lambda s: s["circ_r"],
                "set": lambda s, v: s.__setitem__("circ_r", v),
                "fmt": lambda v: f"{v:.0f} px",
            },
            {
                "key": "circ_omega", "label": "Frequência angular", "vmin": 0.3, "vmax": 6,
                "get": lambda s: s["circ_omega"],
                "set": lambda s, v: s.__setitem__("circ_omega", v),
                "fmt": lambda v: f"{v:.1f} rad/s",
            },
        ])

    return specs


def get_layout_metrics(s, w, h):
    """
    Calcula um layout responsivo compartilhado por desenho e interação.
    A região de simulação nunca fica embaixo dos controles.
    """
    update_fonts(w)

    lines = instruction_lines(w)
    line_h = font_small.get_linesize()
    instructions_h = len(lines) * line_h + 16
    sim_top = instructions_h

    slider_specs = get_slider_specs(s)
    avail = max(180, w - 2 * UI_PAD)

    desired_slider_w = 185 if w >= 900 else 165 if w >= 650 else 145
    slider_cols = max(1, min(
        len(slider_specs),
        int((avail + UI_GAP) // (desired_slider_w + UI_GAP)),
    ))
    slider_w = int((avail - UI_GAP * (slider_cols - 1)) / slider_cols)
    slider_rows = (len(slider_specs) + slider_cols - 1) // slider_cols

    button_specs = MODE_BUTTONS + EXTRA_BUTTONS
    button_widths = [
        max(66, font.size(label)[0] + 22)
        for _, label in button_specs
    ]

    button_rows = []
    row = []
    row_w = 0
    for item, bw in zip(button_specs, button_widths):
        proposed = bw if not row else row_w + UI_GAP + bw
        if row and proposed > avail:
            button_rows.append(row)
            row = [(item, bw)]
            row_w = bw
        else:
            row.append((item, bw))
            row_w = proposed
    if row:
        button_rows.append(row)

    controls_h = (
        14
        + slider_rows * SLIDER_ROW_H
        + 10
        + len(button_rows) * (BUTTON_H + UI_GAP)
        + 10
    )

    panel_top = h - controls_h

    # Em versões estreitas, ainda preservamos uma área de simulação mínima.
    # Se a janela for muito baixa, os controles ocupam o espaço restante sem
    # invadir a área de desenho.
    if panel_top < sim_top + MIN_SIM_HEIGHT:
        panel_top = max(sim_top + 120, h - controls_h)

    sim_rect = pygame.Rect(
        0,
        int(sim_top),
        w,
        max(1, int(panel_top - sim_top)),
    )

    slider_rects = []
    slider_y = panel_top + 14
    for i, spec in enumerate(slider_specs):
        row_i = i // slider_cols
        col_i = i % slider_cols
        x = UI_PAD + col_i * (slider_w + UI_GAP)
        y = slider_y + row_i * SLIDER_ROW_H
        slider_rects.append((spec, pygame.Rect(x, y, slider_w, 12)))

    button_rects = []
    buttons_y = slider_y + slider_rows * SLIDER_ROW_H + 6
    for row_i, items in enumerate(button_rows):
        total_w = sum(bw for _, bw in items) + UI_GAP * (len(items) - 1)
        x = max(UI_PAD, (w - total_w) // 2)
        y = buttons_y + row_i * (BUTTON_H + UI_GAP)
        for (key, label), bw in items:
            button_rects.append(
                (key, label, pygame.Rect(x, y, bw, BUTTON_H))
            )
            x += bw + UI_GAP

    return {
        "sim_rect": sim_rect,
        "panel_top": int(panel_top),
        "panel_rect": pygame.Rect(0, int(panel_top), w, max(0, h - int(panel_top))),
        "sliders": slider_rects,
        "buttons": button_rects,
        "instruction_lines": lines,
        "line_h": line_h,
    }


def adapt_state_to_layout(s, sim_rect):
    """Mantém o referencial da simulação centrado quando o iframe é redimensionado."""
    new_cx = sim_rect.centerx
    new_cy = sim_rect.centery

    old_center = s.get("_layout_center")
    if old_center is None:
        dx = new_cx - s["cx"]
        dy = new_cy - s["cy"]
    else:
        dx = new_cx - old_center[0]
        dy = new_cy - old_center[1]

    if abs(dx) > 0.5 or abs(dy) > 0.5:
        s["cx"] += dx
        s["cy"] += dy
        s["anchor"][0] += dx
        s["anchor"][1] += dy
        s["charge"][0] += dx
        s["charge"][1] += dy

    s["_layout_center"] = (new_cx, new_cy)


def make_slider_objects(s, w, h):
    metrics = get_layout_metrics(s, w, h)
    return metrics["sliders"]


def step(s, dt, w, h):
    metrics = get_layout_metrics(s, w, h)
    sim_rect = metrics["sim_rect"]
    adapt_state_to_layout(s, sim_rect)

    s["t"] += dt
    C = s["C"]
    prev_x, prev_y = s["charge"][0], s["charge"][1]
    m = s["mode"]

    if m == "uniform":
        s["charge"][0] += s["uniform_vx"] * dt
        margin = min(sim_rect.width, sim_rect.height) * 0.08 + 12
        if s["charge"][0] < margin or s["charge"][0] > w - margin:
            s["uniform_vx"] *= -1
    elif m == "kick" and s["kick"]:
        k = s["kick"]
        k["elapsed"] += dt
        p = min(1.0, k["elapsed"] / k["duration"])
        e = ease_in_out(p)
        s["charge"][0] = k["x0"] + (k["x1"] - k["x0"]) * e
        s["charge"][1] = k["y0"] + (k["y1"] - k["y0"]) * e
        if p >= 1.0:
            s["kick"] = None
    elif m == "oscillate":
        s["charge"][0] = s["cx"] + s["osc_amp"] * math.sin(s["osc_omega"] * s["t"])
        s["charge"][1] = s["cy"]
    elif m == "circle":
        s["charge"][0] = s["cx"] + s["circ_r"] * math.cos(s["circ_omega"] * s["t"])
        s["charge"][1] = s["cy"] + s["circ_r"] * math.sin(s["circ_omega"] * s["t"])
    elif m == "drag":
        if s["dragging"] and s["pointer"]:
            s["charge"][0], s["charge"][1] = s["pointer"]

    # Limite universal de velocidade.
    mvx = s["charge"][0] - prev_x
    mvy = s["charge"][1] - prev_y
    mv = math.hypot(mvx, mvy)
    max_move = C * SPEED_CAP * dt
    if mv > max_move and mv > 1e-9:
        s["charge"][0] = prev_x + mvx / mv * max_move
        s["charge"][1] = prev_y + mvy / mv * max_move

    # Mantém a carga dentro da área de simulação.
    margin = 14
    left = margin
    right = max(left + 1, sim_rect.width - margin)
    top = sim_rect.top + margin
    bottom = max(top + 1, sim_rect.bottom - margin)
    s["charge"][0] = clamp(s["charge"][0], left, right)
    s["charge"][1] = clamp(s["charge"][1], top, bottom)

    hist = s["history"]
    hist.append((s["charge"][0], s["charge"][1], s["t"]))

    max_r = math.hypot(sim_rect.width, sim_rect.height) * 1.08
    max_age = max_r / max(C, 1.0) + 0.15
    while hist and (s["t"] - hist[0][2]) > max_age:
        hist.popleft()


def layout_buttons(s, w, h):
    return get_layout_metrics(s, w, h)["buttons"]


def build_sliders(s, w, h):
    return get_layout_metrics(s, w, h)["sliders"]


def draw_sliders(s, surface, metrics):
    for spec, rect in metrics["sliders"]:
        val = spec["get"](s)
        label_surf = font_small.render(
            f'{spec["label"]}: {spec["fmt"](val)}',
            True,
            MUTED,
        )
        surface.blit(label_surf, (rect.x, rect.y - font_small.get_linesize() - 2))

        track = pygame.Rect(rect.x, rect.y, rect.width, rect.height)
        pygame.draw.rect(surface, (28, 37, 56), track, border_radius=5)

        span = spec["vmax"] - spec["vmin"]
        frac = max(
            0.0,
            min(1.0, (val - spec["vmin"]) / span if span else 0.0),
        )
        fill_w = int(track.width * frac)
        if fill_w > 0:
            pygame.draw.rect(
                surface,
                ACCENT2,
                pygame.Rect(track.x, track.y, fill_w, track.height),
                border_radius=5,
            )

        draw_aa_circle(
            surface,
            TEXT,
            (track.x + fill_w, track.centery),
            max(5, int(font_small.get_height() * 0.38)),
        )


def draw_ui(s, surface, w, h, metrics):
    # Instruções no topo.
    y = 8
    for line in metrics["instruction_lines"]:
        surface.blit(font_small.render(line, True, MUTED), (UI_PAD, y))
        y += metrics["line_h"]

    # Painel de controles.
    bar = metrics["panel_rect"]
    pygame.draw.rect(surface, PANEL, bar)
    pygame.draw.line(surface, BORDER, (0, bar.top), (w, bar.top), 1)

    draw_sliders(s, surface, metrics)

    for key, label, rect in metrics["buttons"]:
        active = key == s["mode"]
        color = ACCENT if active else (28, 37, 56)
        pygame.draw.rect(surface, color, rect, border_radius=8)

        txt_color = BG if active else TEXT
        label_font = font if rect.width >= font.size(label)[0] + 16 else font_small
        surf = label_font.render(label, True, txt_color)
        surface.blit(surf, surf.get_rect(center=rect.center))


def draw(s, surface, w, h):
    metrics = get_layout_metrics(s, w, h)
    sim_rect = metrics["sim_rect"]
    adapt_state_to_layout(s, sim_rect)

    surface.fill(BG)

    # Clipping explícito: ondas e carga jamais são desenhadas sobre os controles.
    old_clip = surface.get_clip()
    surface.set_clip(sim_rect)

    max_r = math.hypot(sim_rect.width, sim_rect.height) * 1.08
    line_width = 2 if w >= 700 else 1

    for i in range(N_LINES):
        theta = (i / N_LINES) * math.tau
        pts = build_line_points(s, theta, max_r)
        if len(pts) >= 2:
            # A linha AA continua sendo desenhada sobre uma linha discreta mais
            # espessa para preservar legibilidade quando o canvas é reduzido.
            if line_width > 1:
                pygame.draw.lines(surface, LINE_COLOR, False, pts, line_width)
            pygame.draw.aalines(surface, LINE_COLOR, False, pts)

    cx_, cy_ = s["charge"]
    charge_r = max(8, int(clamp(w / 110.0, 8, 12)))
    draw_aa_circle(surface, ACCENT, (cx_, cy_), charge_r)

    plus_font = font if charge_r >= 10 else font_small
    plus = plus_font.render("+", True, BG)
    surface.blit(
        plus,
        plus.get_rect(center=(int(cx_), int(cy_))),
    )

    surface.set_clip(old_clip)

    # Moldura sutil da área de simulação.
    pygame.draw.rect(surface, BORDER, sim_rect, 1)

    draw_ui(s, surface, w, h, metrics)


def handle_click(s, w, h, pos):
    mx, my = pos
    metrics = get_layout_metrics(s, w, h)

    for key, label, rect in metrics["buttons"]:
        if rect.collidepoint(mx, my):
            if key == "reset":
                new_s = make_state(w, h)
                s.clear()
                s.update(new_s)
            else:
                set_mode(s, key, w, h)
            return

    for spec, rect in metrics["sliders"]:
        hit_rect = rect.inflate(10, 18)
        if hit_rect.collidepoint(mx, my):
            frac = max(
                0.0,
                min(1.0, (mx - rect.x) / rect.width),
            )
            spec["set"](s, spec["vmin"] + frac * (spec["vmax"] - spec["vmin"]))
            s["_dragging_slider"] = spec["key"]
            return

    if metrics["sim_rect"].collidepoint(mx, my):
        s["dragging"] = True
        s["pointer"] = (mx, my)
        set_mode(s, "drag", w, h)


def handle_slider_hit(s, w, h, pos):
    mx, my = pos
    metrics = get_layout_metrics(s, w, h)
    for spec, rect in metrics["sliders"]:
        if rect.inflate(10, 18).collidepoint(mx, my):
            s["_dragging_slider"] = spec["key"]
            frac = max(
                0.0,
                min(1.0, (mx - rect.x) / rect.width),
            )
            spec["set"](s, spec["vmin"] + frac * (spec["vmax"] - spec["vmin"]))
            return True
    return False


def update_dragging_slider(s, w, h, pos):
    key = s.get("_dragging_slider")
    if not key:
        return

    metrics = get_layout_metrics(s, w, h)
    for spec, rect in metrics["sliders"]:
        if spec["key"] == key:
            frac = max(
                0.0,
                min(1.0, (pos[0] - rect.x) / rect.width),
            )
            spec["set"](s, spec["vmin"] + frac * (spec["vmax"] - spec["vmin"]))
            return


async def main():
    global screen
    running = True
    last = pygame.time.get_ticks() / 1000.0

    while running:
        now = pygame.time.get_ticks() / 1000.0
        dt = min(now - last, 0.05)
        last = now
        w, h = screen.get_size()
        update_fonts(w)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode((max(320, event.w), max(360, event.h)), pygame.RESIZABLE)
                new_metrics = get_layout_metrics(state, max(320, event.w), max(360, event.h))
                adapt_state_to_layout(state, new_metrics["sim_rect"])
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if not handle_slider_hit(state, w, h, event.pos):
                    handle_click(state, w, h, event.pos)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                state["dragging"] = False
                state["_dragging_slider"] = None
            elif event.type == pygame.MOUSEMOTION:
                if state.get("_dragging_slider"):
                    update_dragging_slider(state, w, h, event.pos)
                elif state["dragging"] and state["mode"] == "drag":
                    state["pointer"] = event.pos
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        step(state, dt, w, h)
        draw(state, screen, w, h)
        pygame.display.flip()

        # Entrega o controle ao loop do navegador / WebAssembly.
        await asyncio.sleep(0)

    pygame.quit()


if __name__ == "__main__":
    asyncio.run(main())
