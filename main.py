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


def get_browser_viewport(fallback_w, fallback_h):
    """Obtém o tamanho CSS do canvas sem depender de VIDEORESIZE no navegador."""
    if sys.platform == "emscripten":
        try:
            from platform import window
            canvas = window.canvas
            w = int(getattr(canvas, "clientWidth", 0) or 0)
            h = int(getattr(canvas, "clientHeight", 0) or 0)
            if w > 0 and h > 0:
                return w, h
        except Exception:
            pass
        try:
            from platform import window
            w = int(getattr(window, "innerWidth", 0) or 0)
            h = int(getattr(window, "innerHeight", 0) or 0)
            if w > 0 and h > 0:
                return w, h
        except Exception:
            pass
    return fallback_w, fallback_h


_VIEW_FONT_KEY = None


def update_fonts_for_view(view_w, view_h, surface_w, surface_h):
    """Renderiza fontes maiores quando o canvas interno é reduzido por CSS."""
    global font, font_small, _VIEW_FONT_KEY

    sx = surface_w / max(1.0, float(view_w))
    sy = surface_h / max(1.0, float(view_h))
    css_to_surface = max(1.0, min(sx, sy))

    main_css_px = max(14.0, min(18.0, view_w / 28.0))
    small_css_px = max(12.0, min(15.0, main_css_px - 2.0))

    key = (
        round(css_to_surface, 3),
        round(main_css_px, 2),
        round(small_css_px, 2),
    )
    if key == _VIEW_FONT_KEY:
        return css_to_surface

    _VIEW_FONT_KEY = key
    font = pygame.font.SysFont(
        "Arial", max(1, int(round(main_css_px * css_to_surface)))
    )
    font_small = pygame.font.SysFont(
        "Arial", max(1, int(round(small_css_px * css_to_surface)))
    )
    return css_to_surface


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


def _slider_specs(s):
    specs = [
        {
            "key": "C",
            "label": "Velocidade da luz (c)",
            "vmin": 40,
            "vmax": 800,
            "get": lambda s: s["C"],
            "set": lambda s, v: s.__setitem__("C", v),
            "fmt": lambda v: f"{v:.0f} px/s",
        }
    ]

    m = s["mode"]
    if m == "uniform":
        specs.append({
            "key": "uniform_vx",
            "label": "Velocidade",
            "vmin": 10,
            "vmax": 380,
            "get": lambda s: abs(s["uniform_vx"]),
            "set": lambda s, v: s.__setitem__(
                "uniform_vx", math.copysign(v, s["uniform_vx"] or 1.0)
            ),
            "fmt": lambda v: f"{v:.0f} px/s",
        })
    elif m == "kick":
        specs.extend([
            {
                "key": "kick_dist",
                "label": "Distancia do puxao",
                "vmin": 20,
                "vmax": 260,
                "get": lambda s: s["kick_dist"],
                "set": lambda s, v: s.__setitem__("kick_dist", v),
                "fmt": lambda v: f"{v:.0f} px",
            },
            {
                "key": "kick_dur",
                "label": "Duracao do puxao",
                "vmin": 0.05,
                "vmax": 0.5,
                "get": lambda s: s["kick_dur"],
                "set": lambda s, v: s.__setitem__("kick_dur", v),
                "fmt": lambda v: f"{v:.2f} s",
            },
        ])
    elif m == "oscillate":
        specs.extend([
            {
                "key": "osc_amp",
                "label": "Amplitude",
                "vmin": 20,
                "vmax": 280,
                "get": lambda s: s["osc_amp"],
                "set": lambda s, v: s.__setitem__("osc_amp", v),
                "fmt": lambda v: f"{v:.0f} px",
            },
            {
                "key": "osc_omega",
                "label": "Frequencia angular",
                "vmin": 0.3,
                "vmax": 6,
                "get": lambda s: s["osc_omega"],
                "set": lambda s, v: s.__setitem__("osc_omega", v),
                "fmt": lambda v: f"{v:.1f} rad/s",
            },
        ])
    elif m == "circle":
        specs.extend([
            {
                "key": "circ_r",
                "label": "Raio",
                "vmin": 20,
                "vmax": 240,
                "get": lambda s: s["circ_r"],
                "set": lambda s, v: s.__setitem__("circ_r", v),
                "fmt": lambda v: f"{v:.0f} px",
            },
            {
                "key": "circ_omega",
                "label": "Frequencia angular",
                "vmin": 0.3,
                "vmax": 6,
                "get": lambda s: s["circ_omega"],
                "set": lambda s, v: s.__setitem__("circ_omega", v),
                "fmt": lambda v: f"{v:.1f} rad/s",
            },
        ])
    return specs


def _wrap_instruction_lines(view_w, surface_w):
    max_width = max(200, surface_w - 24)
    lines = []

    for text in INSTRUCTIONS:
        words = text.split()
        if not words:
            lines.append("")
            continue

        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if font_small.size(candidate)[0] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)

    return lines


def _build_button_rows(view_w, surface_w, gap):
    items = MODE_BUTTONS + EXTRA_BUTTONS
    rows = []
    row = []
    row_width = 0
    max_width = max(200, surface_w - 24)

    for item in items:
        _, label = item
        button_width = font.size(label)[0] + 28
        proposed = button_width if not row else row_width + gap + button_width

        if row and proposed > max_width:
            rows.append(row)
            row = [(item, button_width)]
            row_width = button_width
        else:
            row.append((item, button_width))
            row_width = proposed

    if row:
        rows.append(row)

    return rows


def get_layout_metrics(s, view_w, view_h, surface_w, surface_h):
    """Calcula uma apresentação responsiva sem alterar as coordenadas físicas."""
    ui_scale = update_fonts_for_view(view_w, view_h, surface_w, surface_h)

    pad = max(8, int(round(12 * ui_scale)))
    gap = max(5, int(round(8 * ui_scale)))
    button_h = max(28, int(round(34 * ui_scale)))
    slider_h = max(8, int(round(12 * ui_scale)))
    row_h = max(34, int(round(44 * ui_scale)))

    instruction_lines = _wrap_instruction_lines(view_w, surface_w)
    line_h = max(font_small.get_linesize(), int(round(17 * ui_scale)))
    instruction_h = len(instruction_lines) * line_h + int(round(10 * ui_scale))

    specs = _slider_specs(s)
    slider_cols = 2 if view_w >= 720 and len(specs) > 1 else 1
    slider_cols = min(slider_cols, len(specs))
    usable_w = max(180, surface_w - 2 * pad)
    slider_w = max(
        120,
        int((usable_w - gap * (slider_cols - 1)) / slider_cols),
    )
    slider_rows = (len(specs) + slider_cols - 1) // slider_cols

    button_rows = _build_button_rows(view_w, surface_w, gap)

    panel_h = (
        int(round(10 * ui_scale))
        + slider_rows * row_h
        + int(round(8 * ui_scale))
        + len(button_rows) * (button_h + gap)
        + int(round(10 * ui_scale))
    )

    min_sim_h = max(
        int(round(110 * ui_scale)),
        int(round(110 * surface_h / max(1, view_h))),
    )

    panel_top = max(instruction_h + min_sim_h, surface_h - panel_h)
    panel_top = max(instruction_h + 1, min(panel_top, surface_h - 1))

    sim_rect = pygame.Rect(
        0,
        instruction_h,
        surface_w,
        max(1, panel_top - instruction_h),
    )
    panel_rect = pygame.Rect(
        0,
        panel_top,
        surface_w,
        max(0, surface_h - panel_top),
    )

    sliders = []
    slider_y = panel_top + int(round(8 * ui_scale))
    for i, spec in enumerate(specs):
        row_index = i // slider_cols
        col_index = i % slider_cols
        x = pad + col_index * (slider_w + gap)
        y = slider_y + row_index * row_h
        sliders.append((spec, pygame.Rect(x, y, slider_w, slider_h)))

    buttons = []
    buttons_y = slider_y + slider_rows * row_h + int(round(2 * ui_scale))
    for row_index, button_row in enumerate(button_rows):
        total_w = (
            sum(width for _, width in button_row)
            + gap * (len(button_row) - 1)
        )
        x = max(pad, (surface_w - total_w) // 2)
        y = buttons_y + row_index * (button_h + gap)

        for (key, label), width in button_row:
            buttons.append((key, label, pygame.Rect(
                x, y, width, button_h
            )))
            x += width + gap

    return {
        "sim_rect": sim_rect,
        "panel_rect": panel_rect,
        "sliders": sliders,
        "buttons": buttons,
        "instruction_lines": instruction_lines,
        "line_h": line_h,
        "ui_scale": ui_scale,
    }


def draw_sliders(s, surface, metrics):
    for spec, rect in metrics["sliders"]:
        value = spec["get"](s)
        label = font_small.render(
            f'{spec["label"]}: {spec["fmt"](value)}',
            True,
            MUTED,
        )
        surface.blit(
            label,
            (rect.x, rect.y - font_small.get_linesize() - 2),
        )

        pygame.draw.rect(
            surface,
            (28, 37, 56),
            rect,
            border_radius=max(3, int(4 * metrics["ui_scale"])),
        )

        span = spec["vmax"] - spec["vmin"]
        frac = max(
            0.0,
            min(1.0, (value - spec["vmin"]) / span if span else 0.0),
        )
        fill_w = int(rect.width * frac)

        if fill_w > 0:
            pygame.draw.rect(
                surface,
                ACCENT2,
                pygame.Rect(
                    rect.x, rect.y, fill_w, rect.height
                ),
                border_radius=max(3, int(4 * metrics["ui_scale"])),
            )

        draw_aa_circle(
            surface,
            TEXT,
            (rect.x + fill_w, rect.centery),
            max(5, int(6 * metrics["ui_scale"])),
        )


def draw_ui(s, surface, metrics):
    left = max(8, int(round(12 * metrics["ui_scale"])))
    y = 6

    for line in metrics["instruction_lines"]:
        surface.blit(
            font_small.render(line, True, MUTED),
            (left, y),
        )
        y += metrics["line_h"]

    bar = metrics["panel_rect"]
    pygame.draw.rect(surface, PANEL, bar)
    pygame.draw.line(
        surface,
        BORDER,
        (0, bar.top),
        (surface.get_width(), bar.top),
        1,
    )

    draw_sliders(s, surface, metrics)

    for key, label, rect in metrics["buttons"]:
        active = key == s["mode"]
        color = ACCENT if active else (28, 37, 56)
        pygame.draw.rect(
            surface,
            color,
            rect,
            border_radius=max(6, int(8 * metrics["ui_scale"])),
        )

        txt_color = BG if active else TEXT
        use_font = font
        if rect.width < font.size(label)[0] + 12:
            use_font = font_small

        text = use_font.render(label, True, txt_color)
        surface.blit(text, text.get_rect(center=rect.center))


def _world_to_surface(point, sim_rect):
    """Mapeia o mundo lógico 1200x624 para o retângulo de simulação."""
    world_w = W
    world_h = H - BAR_H
    sx = sim_rect.width / float(world_w)
    sy = sim_rect.height / float(world_h)
    scale = min(sx, sy)

    drawn_w = world_w * scale
    drawn_h = world_h * scale
    offset_x = sim_rect.centerx - drawn_w / 2.0
    offset_y = sim_rect.centery - drawn_h / 2.0

    return (
        offset_x + point[0] * scale,
        offset_y + point[1] * scale,
        scale,
    )


def _surface_to_world(point, sim_rect):
    _, _, scale = _world_to_surface((0, 0), sim_rect)
    if scale <= 0:
        return None

    world_h = H - BAR_H
    drawn_w = W * scale
    drawn_h = world_h * scale
    offset_x = sim_rect.centerx - drawn_w / 2.0
    offset_y = sim_rect.centery - drawn_h / 2.0

    x = (point[0] - offset_x) / scale
    y = (point[1] - offset_y) / scale

    if 0 <= x <= W and 0 <= y <= world_h:
        return x, y
    return None


def _world_points_to_surface(points, sim_rect):
    result = []
    for point in points:
        x, y, _ = _world_to_surface(point, sim_rect)
        result.append((x, y))
    return result


def draw(s, surface, view_w, view_h):
    surface_w, surface_h = surface.get_size()
    metrics = get_layout_metrics(
        s, view_w, view_h, surface_w, surface_h
    )
    sim_rect = metrics["sim_rect"]

    surface.fill(BG)

    old_clip = surface.get_clip()
    surface.set_clip(sim_rect)

    max_r = math.hypot(W, H - BAR_H) * 1.02
    _, _, world_scale = _world_to_surface((0, 0), sim_rect)
    line_width = max(1, int(round(1.4 * world_scale)))

    for i in range(N_LINES):
        theta = (i / N_LINES) * math.tau
        world_points = build_line_points(s, theta, max_r)

        if len(world_points) >= 2:
            points = _world_points_to_surface(
                world_points, sim_rect
            )
            if line_width > 1:
                pygame.draw.lines(
                    surface,
                    LINE_COLOR,
                    False,
                    points,
                    line_width,
                )
            pygame.draw.aalines(
                surface,
                LINE_COLOR,
                False,
                points,
            )

    cx_, cy_ = s["charge"]
    charge_x, charge_y, _ = _world_to_surface(
        (cx_, cy_), sim_rect
    )
    charge_radius = max(
        6, int(round(8 * metrics["ui_scale"]))
    )
    draw_aa_circle(
        surface,
        ACCENT,
        (charge_x, charge_y),
        charge_radius,
    )

    plus = font_small.render("+", True, BG)
    surface.blit(
        plus,
        plus.get_rect(
            center=(int(round(charge_x)), int(round(charge_y)))
        ),
    )

    surface.set_clip(old_clip)

    pygame.draw.rect(surface, BORDER, sim_rect, 1)
    draw_ui(s, surface, metrics)


def _event_pos(pos):
    return int(round(pos[0])), int(round(pos[1]))


def handle_slider_hit(s, view_w, view_h, surface_w, surface_h, pos):
    mx, my = _event_pos(pos)
    metrics = get_layout_metrics(
        s, view_w, view_h, surface_w, surface_h
    )

    for spec, rect in metrics["sliders"]:
        hit = rect.inflate(
            max(8, int(10 * metrics["ui_scale"])),
            max(10, int(18 * metrics["ui_scale"])),
        )
        if hit.collidepoint(mx, my):
            frac = max(
                0.0,
                min(1.0, (mx - rect.x) / rect.width),
            )
            spec["set"](
                s,
                spec["vmin"] + frac * (spec["vmax"] - spec["vmin"]),
            )
            s["_dragging_slider"] = spec["key"]
            return True

    return False


def update_dragging_slider(
    s, view_w, view_h, surface_w, surface_h, pos
):
    key = s.get("_dragging_slider")
    if not key:
        return

    mx, _ = _event_pos(pos)
    metrics = get_layout_metrics(
        s, view_w, view_h, surface_w, surface_h
    )

    for spec, rect in metrics["sliders"]:
        if spec["key"] == key:
            frac = max(
                0.0,
                min(1.0, (mx - rect.x) / rect.width),
            )
            spec["set"](
                s,
                spec["vmin"] + frac * (spec["vmax"] - spec["vmin"]),
            )
            return


def handle_click(
    s, view_w, view_h, surface_w, surface_h, pos
):
    mx, my = _event_pos(pos)
    metrics = get_layout_metrics(
        s, view_w, view_h, surface_w, surface_h
    )

    for key, label, rect in metrics["buttons"]:
        if rect.collidepoint(mx, my):
            if key == "reset":
                new_state = make_state(W, H)
                s.clear()
                s.update(new_state)
            else:
                set_mode(s, key, W, H)
            return

    if handle_slider_hit(
        s, view_w, view_h, surface_w, surface_h, pos
    ):
        return

    target = _surface_to_world(
        (mx, my),
        metrics["sim_rect"],
    )
    if target is not None:
        s["dragging"] = True
        s["pointer"] = target
        set_mode(s, "drag", W, H)


async def main():
    global screen
    running = True
    last = pygame.time.get_ticks() / 1000.0

    while running:
        now = pygame.time.get_ticks() / 1000.0
        dt = min(now - last, 0.05)
        last = now

        surface_w, surface_h = screen.get_size()
        view_w, view_h = get_browser_viewport(
            surface_w, surface_h
        )

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.VIDEORESIZE:
                # Mantido para desktop. No navegador, a apresentacao
                # consulta o viewport CSS diretamente.
                screen = pygame.display.set_mode(
                    (event.w, event.h),
                    pygame.RESIZABLE,
                )

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if not handle_slider_hit(
                    state,
                    view_w,
                    view_h,
                    surface_w,
                    surface_h,
                    event.pos,
                ):
                    handle_click(
                        state,
                        view_w,
                        view_h,
                        surface_w,
                        surface_h,
                        event.pos,
                    )

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                state["dragging"] = False
                state["_dragging_slider"] = None

            elif event.type == pygame.MOUSEMOTION:
                if state.get("_dragging_slider"):
                    update_dragging_slider(
                        state,
                        view_w,
                        view_h,
                        surface_w,
                        surface_h,
                        event.pos,
                    )
                elif state["dragging"] and state["mode"] == "drag":
                    metrics = get_layout_metrics(
                        state,
                        view_w,
                        view_h,
                        surface_w,
                        surface_h,
                    )
                    target = _surface_to_world(
                        _event_pos(event.pos),
                        metrics["sim_rect"],
                    )
                    if target is not None:
                        state["pointer"] = target

            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        # Fisica e historico continuam nas coordenadas originais 1200x720.
        step(state, dt, W, H)
        draw(state, screen, view_w, view_h)
        pygame.display.flip()

        await asyncio.sleep(0)

    pygame.quit()
if __name__ == "__main__":
    asyncio.run(main())
