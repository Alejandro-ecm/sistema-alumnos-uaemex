"""Heurísticas de seguimiento: asociación libro-persona, ocultamiento y gesto de ruptura."""
import math
import time
from collections import deque


def punto_en_poligono(punto, poligono):
    x, y = punto
    dentro = False
    n = len(poligono)
    for i in range(n):
        x1, y1 = poligono[i]
        x2, y2 = poligono[(i + 1) % n]
        if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-9) + x1):
            dentro = not dentro
    return dentro


def centro(bbox):
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def distancia(p1, p2):
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def bboxes_cercanos(a, b, margen=40):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return not (ax2 + margen < bx1 or bx2 + margen < ax1 or ay2 + margen < by1 or by2 + margen < ay1)


class SeguimientoPersona:
    """Estado acumulado por cada ID de persona rastreado por el tracker de YOLO."""

    def __init__(self, umbral_posesion=15, umbral_oculto=20):
        self.umbral_posesion = umbral_posesion
        self.umbral_oculto = umbral_oculto
        self.frames_con_libro = 0
        self.frames_sin_libro = 0
        self.en_posesion = False
        self.libro_confirmado = False
        self.ultimo_visto = time.time()
        self.evento_robo_disparado = False
        # historial corto de posiciones de muñeca para detectar el gesto de ruptura
        self.historial_munecas = {'izquierda': deque(maxlen=15), 'derecha': deque(maxlen=15)}
        self.evento_ruptura_cooldown = 0.0

    def actualizar_posesion(self, libro_cerca):
        self.ultimo_visto = time.time()
        if libro_cerca:
            self.frames_con_libro += 1
            self.frames_sin_libro = 0
            if self.frames_con_libro >= self.umbral_posesion:
                self.libro_confirmado = True
        else:
            if self.libro_confirmado:
                self.frames_sin_libro += 1
                if self.frames_sin_libro >= self.umbral_oculto:
                    self.en_posesion = True
            else:
                self.frames_con_libro = 0

    def registrar_muneca(self, lado, punto):
        self.historial_munecas[lado].append(punto)

    def velocidad_y_zigzag(self, lado):
        """Velocidad promedio y número de cambios de dirección en la ventana reciente."""
        hist = self.historial_munecas[lado]
        if len(hist) < 4:
            return 0.0, 0
        velocidades = []
        for i in range(1, len(hist)):
            velocidades.append((hist[i][0] - hist[i - 1][0], hist[i][1] - hist[i - 1][1]))
        rapidez_prom = sum(math.hypot(vx, vy) for vx, vy in velocidades) / len(velocidades)
        cambios = 0
        for i in range(1, len(velocidades)):
            vx1, vy1 = velocidades[i - 1]
            vx2, vy2 = velocidades[i]
            producto = vx1 * vx2 + vy1 * vy2
            if producto < 0:
                cambios += 1
        return rapidez_prom, cambios
