"""
Sistema de detección anti-robo / anti-vandalismo de libros para "Detección Libros".

Uso:
    C:\\venv_deteccion\\Scripts\\python.exe deteccion_libros\\vision\\capturar.py

Lee deteccion_libros/vision/camaras.json y abre un hilo de captura por cada
cámara activa (webcam local, stream HTTP de celular, o RTSP de cámara de
seguridad cuando esté disponible). Cada hilo corre YOLO (detección + tracking)
para localizar personas/libros/mochilas, y YOLO-pose para las muñecas, aplica
las heurísticas de deteccion_libros/vision/rastreo.py y guarda evidencia con
deteccion_libros/vision/evidencia.py cuando detecta un evento.

Cada cámara también transmite su video anotado por HTTP (MJPEG) vía
deteccion_libros/vision/streaming.py, para que la "Vista de seguridad" del
admin de Django la muestre en vivo en el navegador (ver --puerto-stream).
"""
import argparse
import json
import os
import sys
import threading
import time
from collections import deque
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proyecto.settings')

import django  # noqa: E402
django.setup()

from ultralytics import YOLO  # noqa: E402

from deteccion_libros.vision.rastreo import (  # noqa: E402
    SeguimientoPersona, bboxes_cercanos, centro, distancia, punto_en_poligono,
)
from deteccion_libros.vision.evidencia import anotar_frame, crear_evento  # noqa: E402
from deteccion_libros.vision.streaming import ConcentradorFrames, iniciar_servidor  # noqa: E402

RUTA_CAMARAS = Path(__file__).with_name('camaras.json')

UMBRAL_VELOCIDAD_RUPTURA = 18.0
UMBRAL_ZIGZAG_RUPTURA = 3
COOLDOWN_EVENTO = 20.0
DURACION_CLIP_ANTES = 3.0
DURACION_CLIP_DESPUES = 2.0
DURACION_ALERTA_VISUAL = 6.0
COLOR_LIBRO = (0, 0, 255)
COLOR_ROBO = (0, 0, 200)
COLOR_RUPTURA = (0, 140, 200)


def cargar_camaras():
    with open(RUTA_CAMARAS, 'r', encoding='utf-8') as f:
        return json.load(f)


def guardar_camaras(camaras):
    with open(RUTA_CAMARAS, 'w', encoding='utf-8') as f:
        json.dump(camaras, f, indent=4, ensure_ascii=False)


def calibrar_zona_salida(cam):
    """Deja que el operador marque 4 puntos sobre un frame en vivo para definir la zona de salida."""
    captura = cv2.VideoCapture(cam['source'])
    ok, frame = captura.read()
    if not ok:
        captura.release()
        print(f"[{cam['nombre']}] no se pudo leer un frame para calibrar, se omite la zona de salida.")
        return None

    puntos = []

    def click(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and len(puntos) < 4:
            puntos.append([x, y])

    ventana = f"Calibrar zona de salida - {cam['nombre']}"
    cv2.namedWindow(ventana)
    cv2.setMouseCallback(ventana, click)
    print(f"[{cam['nombre']}] Haz clic en 4 puntos que delimiten la zona de salida (ESC para omitir).")

    while True:
        vista = frame.copy()
        for p in puntos:
            cv2.circle(vista, tuple(p), 5, (0, 255, 0), -1)
        if len(puntos) > 1:
            cv2.polylines(vista, [np.array(puntos, dtype=np.int32)], len(puntos) == 4, (0, 255, 0), 2)
        cv2.imshow(ventana, vista)
        tecla = cv2.waitKey(20) & 0xFF
        if tecla == 27 or len(puntos) == 4:
            break

    cv2.destroyWindow(ventana)
    captura.release()
    return puntos if len(puntos) == 4 else None


class HiloCamara(threading.Thread):
    def __init__(self, cam, modelo_deteccion, modelo_pose, hub=None, mostrar_ventana=False):
        super().__init__(daemon=True)
        self.cam = cam
        self.modelo_deteccion = modelo_deteccion
        self.modelo_pose = modelo_pose
        self.hub = hub
        self.mostrar_ventana = mostrar_ventana
        self.seguimientos = {}
        self.libros_visibles = []
        self.buffer_frames = deque(maxlen=int(DURACION_CLIP_ANTES * 15))
        self.clips_pendientes = []
        self.detener = threading.Event()
        self.numeros_persona = {}
        self.conteo_actual = 0
        self.personas_en_alerta = {}

    def zona_activa(self):
        return self.cam.get('zona_salida')

    def procesar_frame(self, frame):
        self.buffer_frames.append(frame.copy())

        resultado_det = self.modelo_deteccion.track(
            frame, persist=True, verbose=False,
            classes=self._clases_relevantes(self.modelo_deteccion),
        )[0]
        resultado_pose = self.modelo_pose(frame, verbose=False)[0]

        personas = {}
        personas_contornos = {}
        self.libros_visibles = []
        mochilas = []

        # yolov8n-seg.pt devuelve .masks.xy alineado por índice con .boxes: el
        # polígono real de la silueta de cada detección (no solo su rectángulo).
        mascaras = resultado_det.masks.xy if resultado_det.masks is not None else None

        nombres = resultado_det.names
        for i, caja in enumerate(resultado_det.boxes):
            clase = nombres[int(caja.cls[0])]
            bbox = [float(v) for v in caja.xyxy[0]]
            track_id = int(caja.id[0]) if caja.id is not None else None
            if clase == 'person' and track_id is not None:
                personas[track_id] = bbox
                if mascaras is not None and i < len(mascaras) and len(mascaras[i]) > 0:
                    personas_contornos[track_id] = mascaras[i]
            elif clase == 'book':
                self.libros_visibles.append(bbox)
            elif clase in ('backpack', 'handbag'):
                mochilas.append(bbox)

        self.conteo_actual = len(personas)
        # libera números de personas que ya no están en cuadro, para que se reasignen
        # (así el conteo se mantiene compacto: 1, 2, 3... sin huecos permanentes)
        for track_id in list(self.numeros_persona):
            if track_id not in personas:
                del self.numeros_persona[track_id]
        for track_id in personas:
            if track_id not in self.numeros_persona:
                usados = set(self.numeros_persona.values())
                numero = 1
                while numero in usados:
                    numero += 1
                self.numeros_persona[track_id] = numero

        frame_anotado = frame.copy()
        ahora = time.time()

        # limpia alertas visuales de personas cuya ventana de aviso ya expiró
        for track_id in list(self.personas_en_alerta):
            if ahora > self.personas_en_alerta[track_id]['hasta']:
                del self.personas_en_alerta[track_id]

        for bbox_libro in self.libros_visibles:
            self._dibujar_libro(frame_anotado, bbox_libro)

        for track_id, bbox_persona in personas.items():
            seg = self.seguimientos.setdefault(track_id, SeguimientoPersona())

            libro_cerca = any(bboxes_cercanos(bbox_persona, lb) for lb in self.libros_visibles)
            seg.actualizar_posesion(libro_cerca)

            if seg.en_posesion and not seg.evento_robo_disparado:
                punto = centro(bbox_persona)
                zona = self.zona_activa()
                en_zona = punto_en_poligono(punto, zona) if zona else self._cerca_del_borde(frame, bbox_persona)
                if en_zona:
                    self._disparar_robo(frame_anotado, track_id)
                    seg.evento_robo_disparado = True

            alerta = self.personas_en_alerta.get(track_id)
            color = alerta['color'] if alerta else (67, 160, 71)

            contorno = personas_contornos.get(track_id)
            if contorno is not None:
                puntos = contorno.astype(np.int32).reshape((-1, 1, 2))
                capa = frame_anotado.copy()
                cv2.fillPoly(capa, [puntos], color)
                cv2.addWeighted(capa, 0.45, frame_anotado, 0.55, 0, dst=frame_anotado)
                cv2.polylines(frame_anotado, [puntos], True, color, 2)
            else:
                # sin máscara disponible para esta detección (raro): usa el rectángulo como respaldo
                cv2.rectangle(frame_anotado, (int(bbox_persona[0]), int(bbox_persona[1])),
                              (int(bbox_persona[2]), int(bbox_persona[3])), color, 2)

            etiqueta = f"¡{alerta['tipo']}! Persona {self.numeros_persona[track_id]}" if alerta else None
            self._dibujar_etiqueta_persona(frame_anotado, bbox_persona, self.numeros_persona[track_id], color, etiqueta)

        # muñecas (pose) para la heurística de ruptura de páginas
        # El modelo de pose corre por separado del tracker, así que no comparte IDs:
        # cada detección de pose se empareja con la persona rastreada cuya caja
        # contiene el centro de sus keypoints (no por posición en la lista).
        if resultado_pose.keypoints is not None:
            cajas_pose = resultado_pose.boxes.xyxy.tolist() if resultado_pose.boxes is not None else []
            for i, kpts in enumerate(resultado_pose.keypoints.xy):
                if i >= len(cajas_pose):
                    continue
                punto_pose = centro(cajas_pose[i])
                track_id = self._persona_mas_cercana(punto_pose, personas)
                if track_id is None or track_id not in self.seguimientos:
                    continue
                seg = self.seguimientos[track_id]
                if len(kpts) < 11:
                    continue
                muneca_izq = tuple(kpts[9].tolist())
                muneca_der = tuple(kpts[10].tolist())

                for lado, punto in (('izquierda', muneca_izq), ('derecha', muneca_der)):
                    if punto[0] == 0 and punto[1] == 0:
                        continue
                    seg.registrar_muneca(lado, punto)
                    cerca_de_libro = any(
                        lb[0] - 30 <= punto[0] <= lb[2] + 30 and lb[1] - 30 <= punto[1] <= lb[3] + 30
                        for lb in self.libros_visibles
                    )
                    if cerca_de_libro and ahora > seg.evento_ruptura_cooldown:
                        rapidez, zigzag = seg.velocidad_y_zigzag(lado)
                        if rapidez > UMBRAL_VELOCIDAD_RUPTURA and zigzag >= UMBRAL_ZIGZAG_RUPTURA:
                            self._disparar_ruptura(frame_anotado, track_id, rapidez)
                            seg.evento_ruptura_cooldown = ahora + COOLDOWN_EVENTO

        self._avanzar_clips_pendientes(frame)
        return frame_anotado

    def _dibujar_etiqueta_persona(self, frame, bbox, numero, color=(67, 160, 71), texto=None):
        texto = texto or f'Persona {numero}'
        x1, y1 = int(bbox[0]), int(bbox[1])
        alto, ancho = frame.shape[:2]
        (tw, th), _ = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        px, py = max(0, min(x1, ancho - tw - 10)), max(th + 10, y1)
        cv2.rectangle(frame, (px, py - th - 10), (px + tw + 10, py), color, -1)
        cv2.putText(frame, texto, (px + 5, py - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)

    def _dibujar_libro(self, frame, bbox):
        x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
        cv2.rectangle(frame, (x1, y1), (x2, y2), COLOR_LIBRO, 2)
        texto = 'Libro'
        (tw, th), _ = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
        cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 8, y1), COLOR_LIBRO, -1)
        cv2.putText(frame, texto, (x1 + 4, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)

    def _persona_mas_cercana(self, punto, personas, margen=60):
        """Empareja un punto (centro de una detección de pose) con el track_id de
        la persona cuya caja lo contiene, o la más cercana dentro de un margen."""
        mejor_id, mejor_dist = None, None
        for track_id, bbox in personas.items():
            x1, y1, x2, y2 = bbox
            if x1 - margen <= punto[0] <= x2 + margen and y1 - margen <= punto[1] <= y2 + margen:
                dist = distancia(punto, centro(bbox))
                if mejor_dist is None or dist < mejor_dist:
                    mejor_id, mejor_dist = track_id, dist
        return mejor_id

    def _clases_relevantes(self, modelo):
        deseadas = ('person', 'book', 'backpack', 'handbag')
        nombres = modelo.names
        return [i for i, n in nombres.items() if n in deseadas]

    def _cerca_del_borde(self, frame, bbox, margen=25):
        alto, ancho = frame.shape[:2]
        x1, y1, x2, y2 = bbox
        return x1 <= margen or y1 <= margen or x2 >= ancho - margen or y2 >= alto - margen

    def _marcar_alerta_visual(self, track_id, tipo, color, texto):
        self.personas_en_alerta[track_id] = {
            'tipo': tipo, 'color': color, 'hasta': time.time() + DURACION_ALERTA_VISUAL,
        }
        if self.hub is not None:
            self.hub.registrar_alerta(self.cam['nombre'], tipo, texto, duracion=DURACION_ALERTA_VISUAL)

    def _disparar_robo(self, frame, track_id):
        numero = self.numeros_persona.get(track_id, track_id)
        anotado = anotar_frame(frame, f"Posible sustracción de libro (persona #{track_id})", COLOR_ROBO)
        self._programar_clip('robo', anotado, confianza=0.7,
                              notas=f'Persona rastreada #{track_id} salió de la zona con un libro previamente detectado cerca.')
        self._marcar_alerta_visual(track_id, 'ROBO', COLOR_ROBO, f'Posible robo de libro — Persona {numero}')
        print(f"[{self.cam['nombre']}] Evento ROBO registrado (persona #{track_id}).")

    def _disparar_ruptura(self, frame, track_id, rapidez):
        numero = self.numeros_persona.get(track_id, track_id)
        anotado = anotar_frame(frame, f"Posible ruptura de páginas (persona #{track_id})", COLOR_RUPTURA)
        confianza = min(0.95, 0.5 + rapidez / 100)
        self._programar_clip('ruptura', anotado, confianza=confianza,
                              notas=f'Movimiento brusco de mano cerca de un libro (persona #{track_id}).')
        self._marcar_alerta_visual(track_id, 'RUPTURA', COLOR_RUPTURA, f'Movimiento indebido cerca de un libro — Persona {numero}')
        print(f"[{self.cam['nombre']}] Evento RUPTURA registrado (persona #{track_id}).")

    def _programar_clip(self, tipo, frame_anotado, confianza, notas):
        self.clips_pendientes.append({
            'tipo': tipo,
            'frame_anotado': frame_anotado,
            'confianza': confianza,
            'notas': notas,
            'frames': list(self.buffer_frames),
            'faltantes': int(DURACION_CLIP_DESPUES * 15),
        })

    def _avanzar_clips_pendientes(self, frame_actual):
        listos = []
        for clip in self.clips_pendientes:
            clip['frames'].append(frame_actual.copy())
            clip['faltantes'] -= 1
            if clip['faltantes'] <= 0:
                listos.append(clip)
        for clip in listos:
            self.clips_pendientes.remove(clip)
            crear_evento(
                tipo=clip['tipo'], fuente=self.cam['nombre'], confianza=clip['confianza'],
                frame_anotado=clip['frame_anotado'], frames_clip=clip['frames'], notas=clip['notas'],
            )

    def run(self):
        nombre = self.cam['nombre']
        captura = cv2.VideoCapture(self.cam['source'])
        abierta = captura.isOpened()
        if not abierta:
            print(f"[{nombre}] no se pudo abrir la fuente de video: {self.cam['source']}")
            return

        print(f"[{nombre}] cámara activa, procesando y transmitiendo...")
        ventana = f"Detección Libros - {nombre}"
        while not self.detener.is_set():
            # "apagar" desde el panel libera de verdad el dispositivo (cv2.VideoCapture.release()),
            # no solo deja de dibujar: así el LED/uso de la cámara física también se apaga.
            if self.hub is not None and self.hub.esta_pausada(nombre):
                if abierta:
                    captura.release()
                    abierta = False
                    self.conteo_actual = 0
                    self.hub.actualizar_personas(nombre, 0)
                    print(f"[{nombre}] cámara apagada desde el panel.")
                time.sleep(0.3)
                continue

            if not abierta:
                captura = cv2.VideoCapture(self.cam['source'])
                abierta = captura.isOpened()
                if not abierta:
                    time.sleep(1.0)
                    continue
                print(f"[{nombre}] cámara encendida desde el panel.")

            ok, frame = captura.read()
            if not ok:
                print(f"[{nombre}] se perdió la señal de video.")
                break
            anotado = self.procesar_frame(frame)

            if self.hub is not None:
                ok_jpg, buffer = cv2.imencode('.jpg', anotado, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ok_jpg:
                    self.hub.actualizar(nombre, buffer.tobytes())
                self.hub.actualizar_personas(nombre, self.conteo_actual)

            if self.mostrar_ventana:
                cv2.imshow(ventana, anotado)
                if cv2.waitKey(1) & 0xFF == 27:
                    break

        if abierta:
            captura.release()
        if self.mostrar_ventana:
            cv2.destroyWindow(ventana)


def main():
    parser = argparse.ArgumentParser(description='Detección de robo/ruptura de libros con YOLO.')
    parser.add_argument('--puerto-stream', type=int, default=8090,
                         help='Puerto del servidor de streaming MJPEG para la Vista de seguridad (default 8090).')
    parser.add_argument('--ventanas', action='store_true',
                         help='Además del streaming web, abre una ventana local de OpenCV por cámara (debug).')
    parser.add_argument('--calibrar', metavar='NOMBRE_CAMARA',
                         help='Abre una ventana local para marcar 4 puntos de la zona de salida de esa '
                              'cámara y guarda el resultado en camaras.json, luego termina (no inicia streaming). '
                              'Sin esto, las cámaras sin zona calibrada usan el borde del cuadro como zona de salida.')
    args = parser.parse_args()

    if args.calibrar:
        camaras_todas = cargar_camaras()
        cam = next((c for c in camaras_todas if c['nombre'] == args.calibrar), None)
        if cam is None:
            print(f"No existe una cámara llamada '{args.calibrar}' en camaras.json.")
            return
        puntos = calibrar_zona_salida(cam)
        if puntos:
            cam['zona_salida'] = puntos
            guardar_camaras(camaras_todas)
            print(f"[{cam['nombre']}] zona de salida guardada.")
        else:
            print(f"[{cam['nombre']}] calibración omitida, no se guardó ninguna zona.")
        return

    camaras = [c for c in cargar_camaras() if c.get('activa')]

    hub = ConcentradorFrames()
    iniciar_servidor(hub, puerto=args.puerto_stream)

    print('Cargando modelos YOLO (primera vez puede tardar, descarga los pesos)...')
    hilos = {}
    for cam in camaras:
        h = _crear_hilo(cam, hub, args.ventanas)
        h.start()
        hilos[cam['nombre']] = h

    try:
        ultima_mtime = RUTA_CAMARAS.stat().st_mtime
    except FileNotFoundError:
        ultima_mtime = None

    print('Escuchando cambios en camaras.json (agregar/activar/desactivar cámaras sin reiniciar)...')
    try:
        while True:
            time.sleep(0.5)

            for nombre in list(hilos):
                if not hilos[nombre].is_alive():
                    del hilos[nombre]

            try:
                mtime = RUTA_CAMARAS.stat().st_mtime
            except FileNotFoundError:
                continue
            if mtime != ultima_mtime:
                ultima_mtime = mtime
                _recargar_camaras(hilos, hub, args.ventanas)
    except KeyboardInterrupt:
        print('\nDeteniendo cámaras...')
        for h in hilos.values():
            h.detener.set()
        for h in hilos.values():
            h.join(timeout=5)


def _crear_hilo(cam, hub, mostrar_ventana):
    # Se crea una instancia de modelo nueva por cámara: el tracker de .track(persist=True)
    # guarda su estado (IDs) en la propia instancia de YOLO, así que compartir un modelo
    # entre hilos de cámaras distintas mezclaría los IDs de personas de una cámara con
    # los de otra. yolov8n-seg.pt (en vez de yolov8n.pt) agrega máscaras de silueta.
    return HiloCamara(cam, YOLO('yolov8n-seg.pt'), YOLO('yolov8n-pose.pt'), hub=hub, mostrar_ventana=mostrar_ventana)


def _recargar_camaras(hilos, hub, mostrar_ventana):
    """Sincroniza los hilos en ejecución con el contenido actual de camaras.json,
    para que activar/desactivar/agregar una cámara desde el panel (celular, cámaras
    de la escuela) surta efecto sin reiniciar este proceso."""
    activas = {c['nombre']: c for c in cargar_camaras() if c.get('activa')}

    for nombre in list(hilos):
        if nombre not in activas:
            print(f"[{nombre}] desactivada desde el panel, deteniendo hilo...")
            hilos[nombre].detener.set()
            hilos[nombre].join(timeout=5)
            del hilos[nombre]

    for nombre, cam in activas.items():
        hilo_actual = hilos.get(nombre)
        if hilo_actual is not None and hilo_actual.is_alive() and hilo_actual.cam.get('source') == cam.get('source'):
            continue
        if hilo_actual is not None:
            hilo_actual.detener.set()
            hilo_actual.join(timeout=5)
        print(f"[{nombre}] iniciando cámara desde el panel...")
        nuevo = _crear_hilo(cam, hub, mostrar_ventana)
        nuevo.start()
        hilos[nombre] = nuevo


if __name__ == '__main__':
    main()
