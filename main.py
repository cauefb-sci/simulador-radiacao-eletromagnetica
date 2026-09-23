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
BAR_H = 96
screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
pygame.display.set_caption("Carga acelerada e radiacao eletromagnetica")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 15)
font_small = pygame.font.SysFont("Arial", 13)

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
    cx, cy = w / 2, (h - BAR_H) / 2
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
        "pointer": None,             # alvo do mouse em modo "drag"
        "dragging": False,
        "_dragging_slider": None,
    }


state = make_state(W, H)


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
        margin = min(w, h - BAR_H) * 0.08 + 30
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
    max_r = math.hypot(w, h - BAR_H) * 1.02
    max_age = max_r / C + 0.15
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


def layout_buttons(w, h):
    rects = []
    x, y = 14, h - BAR_H + 46
    for key, label in MODE_BUTTONS:
        surf = font.render(label, True, TEXT)
        bw = surf.get_width() + 22
        rects.append((key, label, pygame.Rect(x, y, bw, 32)))
        x += bw + 8
    x += 20
    for key, label in EXTRA_BUTTONS:
        surf = font.render(label, True, TEXT)
        bw = surf.get_width() + 22
        rects.append((key, label, pygame.Rect(x, y, bw, 32)))
        x += bw + 8
    return rects


def build_sliders(s, w, h):
    sliders = []
    x = 16
    y = h - BAR_H + 26

    def add(key, label, vmin, vmax, get, set_, fmt):
        nonlocal x
        sliders.append({
            "key": key, "label": label, "vmin": vmin, "vmax": vmax,
            "rect": pygame.Rect(x, y, 130, 12), "get": get, "set": set_, "fmt": fmt,
        })
        x += 190

    add("C", "Velocidade da luz (c)", 40, 800,
        lambda s: s["C"], lambda s, v: s.__setitem__("C", v),
        lambda v: f"{v:.0f} px/s")

    m = s["mode"]
    if m == "uniform":
        add("uniform_vx", "Velocidade", 10, 380,
            lambda s: abs(s["uniform_vx"]),
            lambda s, v: s.__setitem__("uniform_vx", math.copysign(v, s["uniform_vx"] or 1.0)),
            lambda v: f"{v:.0f} px/s")
    elif m == "kick":
        add("kick_dist", "Distancia do puxao", 20, 260,
            lambda s: s["kick_dist"], lambda s, v: s.__setitem__("kick_dist", v),
            lambda v: f"{v:.0f} px")
        add("kick_dur", "Duracao do puxao", 0.05, 0.5,
            lambda s: s["kick_dur"], lambda s, v: s.__setitem__("kick_dur", v),
            lambda v: f"{v:.2f} s")
    elif m == "oscillate":
        add("osc_amp", "Amplitude", 20, 280,
            lambda s: s["osc_amp"], lambda s, v: s.__setitem__("osc_amp", v),
            lambda v: f"{v:.0f} px")
        add("osc_omega", "Frequencia angular", 0.3, 6,
            lambda s: s["osc_omega"], lambda s, v: s.__setitem__("osc_omega", v),
            lambda v: f"{v:.1f} rad/s")
    elif m == "circle":
        add("circ_r", "Raio", 20, 240,
            lambda s: s["circ_r"], lambda s, v: s.__setitem__("circ_r", v),
            lambda v: f"{v:.0f} px")
        add("circ_omega", "Frequencia angular", 0.3, 6,
            lambda s: s["circ_omega"], lambda s, v: s.__setitem__("circ_omega", v),
            lambda v: f"{v:.1f} rad/s")
    return sliders


def draw_sliders(s, surface, w, h):
    for sl in build_sliders(s, w, h):
        val = sl["get"](s)
        label_surf = font_small.render(f'{sl["label"]}: {sl["fmt"](val)}', True, MUTED)
        surface.blit(label_surf, (sl["rect"].x, sl["rect"].y - 16))
        pygame.draw.rect(surface, (28, 37, 56), sl["rect"], border_radius=4)
        span = sl["vmax"] - sl["vmin"]
        frac = max(0.0, min(1.0, (val - sl["vmin"]) / span if span else 0.0))
        fill_w = int(sl["rect"].width * frac)
        if fill_w > 0:
            pygame.draw.rect(surface, ACCENT2, pygame.Rect(sl["rect"].x, sl["rect"].y, fill_w, sl["rect"].height), border_radius=4)
        draw_aa_circle(surface, TEXT, (sl["rect"].x + fill_w, sl["rect"].centery), 6)


def draw_ui(s, surface, w, h):
    yy = 10
    for line in INSTRUCTIONS:
        surface.blit(font_small.render(line, True, MUTED), (16, yy))
        yy += 17

    bar = pygame.Rect(0, h - BAR_H, w, BAR_H)
    pygame.draw.rect(surface, PANEL, bar)
    pygame.draw.line(surface, BORDER, (0, h - BAR_H), (w, h - BAR_H), 1)

    draw_sliders(s, surface, w, h)

    for key, label, rect in layout_buttons(w, h):
        active = key == s["mode"]
        color = ACCENT if active else (28, 37, 56)
        pygame.draw.rect(surface, color, rect, border_radius=8)
        txt_color = BG if active else TEXT
        surf = font.render(label, True, txt_color)
        surface.blit(surf, surf.get_rect(center=rect.center))


def draw(s, surface, w, h):
    surface.fill(BG)
    max_r = math.hypot(w, h - BAR_H) * 1.02
    for i in range(N_LINES):
        theta = (i / N_LINES) * math.tau
        pts = build_line_points(s, theta, max_r)
        if len(pts) >= 2:
            pygame.draw.aalines(surface, LINE_COLOR, False, pts)

    cx_, cy_ = s["charge"]
    draw_aa_circle(surface, ACCENT, (cx_, cy_), 9)
    plus = font.render("+", True, BG)
    surface.blit(plus, plus.get_rect(center=(int(cx_), int(cy_))))

    draw_ui(s, surface, w, h)


def handle_click(s, w, h, pos):
    mx, my = pos
    for key, label, rect in layout_buttons(w, h):
        if rect.collidepoint(mx, my):
            if key == "reset":
                new_s = make_state(w, h)
                s.clear()
                s.update(new_s)
            else:
                set_mode(s, key, w, h)
            return
    if my >= h - BAR_H:
        return
    s["dragging"] = True
    s["pointer"] = (mx, my)
    set_mode(s, "drag", w, h)


def handle_slider_hit(s, w, h, pos):
    mx, my = pos
    for sl in build_sliders(s, w, h):
        hit_rect = sl["rect"].inflate(12, 16)
        if hit_rect.collidepoint(mx, my):
            s["_dragging_slider"] = sl["key"]
            frac = max(0.0, min(1.0, (mx - sl["rect"].x) / sl["rect"].width))
            sl["set"](s, sl["vmin"] + frac * (sl["vmax"] - sl["vmin"]))
            return True
    return False


def update_dragging_slider(s, w, h, pos):
    key = s.get("_dragging_slider")
    if not key:
        return
    for sl in build_sliders(s, w, h):
        if sl["key"] == key:
            frac = max(0.0, min(1.0, (pos[0] - sl["rect"].x) / sl["rect"].width))
            sl["set"](s, sl["vmin"] + frac * (sl["vmax"] - sl["vmin"]))
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

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
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
