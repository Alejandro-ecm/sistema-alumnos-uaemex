"""Servidor HTTP ligero que transmite en vivo (MJPEG) el video anotado por YOLO
de cada cámara activa, para que la "Vista de seguridad" del admin de Django
pueda mostrarlas embebidas en <img> tags sin necesitar Django Channels/websockets.

Corre dentro del mismo proceso que capturar.py (venv_deteccion), en un puerto
aparte (por defecto 8090). El admin de Django (otro proceso, otro venv) solo
apunta <img src="http://127.0.0.1:8090/stream/<nombre>"> — nunca importa este
módulo directamente.
"""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PUERTO_POR_DEFECTO = 8090


class ConcentradorFrames:
    """Guarda el último frame JPEG (bytes) de cada cámara, protegido por lock."""

    def __init__(self):
        self._lock = threading.Lock()
        self._frames = {}
        self._ultima_actualizacion = {}
        self._pausadas = set()
        self._personas = {}
        self._alertas = {}

    def actualizar(self, nombre_camara, jpeg_bytes):
        with self._lock:
            self._frames[nombre_camara] = jpeg_bytes
            self._ultima_actualizacion[nombre_camara] = time.time()

    def obtener(self, nombre_camara):
        with self._lock:
            return self._frames.get(nombre_camara)

    def pausar(self, nombre_camara):
        """Marca una cámara como apagada; capturar.py libera el dispositivo físico."""
        with self._lock:
            self._pausadas.add(nombre_camara)

    def reanudar(self, nombre_camara):
        with self._lock:
            self._pausadas.discard(nombre_camara)

    def esta_pausada(self, nombre_camara):
        with self._lock:
            return nombre_camara in self._pausadas

    def actualizar_personas(self, nombre_camara, cantidad):
        with self._lock:
            self._personas[nombre_camara] = cantidad

    def registrar_alerta(self, nombre_camara, tipo, texto, duracion=6.0):
        """Marca una alerta (robo/ruptura) activa para esta cámara durante `duracion`
        segundos, para que el panel web la muestre en un banner rojo aunque el
        evento ya haya terminado de procesarse en el hilo de video."""
        with self._lock:
            self._alertas[nombre_camara] = {
                'tipo': tipo,
                'texto': texto,
                'hasta': time.time() + duracion,
            }

    def estado(self):
        with self._lock:
            ahora = time.time()
            nombres = set(self._ultima_actualizacion) | self._pausadas | set(self._personas) | set(self._alertas)
            return {
                nombre: {
                    'conectada': (ahora - self._ultima_actualizacion.get(nombre, 0)) < 5,
                    'hace_segundos': round(ahora - self._ultima_actualizacion.get(nombre, ahora), 1),
                    'pausada': nombre in self._pausadas,
                    'personas': self._personas.get(nombre, 0),
                    'alerta': (
                        {'tipo': self._alertas[nombre]['tipo'], 'texto': self._alertas[nombre]['texto']}
                        if nombre in self._alertas and ahora < self._alertas[nombre]['hasta']
                        else None
                    ),
                }
                for nombre in nombres
            }


def _crear_handler(hub):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, formato, *args):
            pass  # silencia el log de acceso por request, muy ruidoso en consola

        def _cors(self):
            self.send_header('Access-Control-Allow-Origin', '*')

        def do_GET(self):
            partes = self.path.strip('/').split('/')

            if self.path == '/estado':
                cuerpo = json.dumps(hub.estado()).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self._cors()
                self.send_header('Content-Length', str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)
                return

            if len(partes) == 3 and partes[0] == 'control' and partes[2] in ('encender', 'apagar'):
                nombre, accion = partes[1], partes[2]
                if accion == 'apagar':
                    hub.pausar(nombre)
                else:
                    hub.reanudar(nombre)
                cuerpo = json.dumps({'ok': True, 'nombre': nombre, 'pausada': hub.esta_pausada(nombre)}).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self._cors()
                self.send_header('Content-Length', str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)
                return

            if len(partes) == 2 and partes[0] == 'snapshot':
                nombre = partes[1]
                frame = hub.obtener(nombre)
                if frame is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header('Content-Type', 'image/jpeg')
                self._cors()
                self.send_header('Content-Length', str(len(frame)))
                self.end_headers()
                self.wfile.write(frame)
                return

            if len(partes) == 2 and partes[0] == 'stream':
                nombre = partes[1]
                self.send_response(200)
                self.send_header(
                    'Content-Type', 'multipart/x-mixed-replace; boundary=frame'
                )
                self._cors()
                self.end_headers()
                try:
                    while True:
                        frame = hub.obtener(nombre)
                        if frame is not None:
                            self.wfile.write(b'--frame\r\n')
                            self.wfile.write(b'Content-Type: image/jpeg\r\n')
                            self.wfile.write(f'Content-Length: {len(frame)}\r\n\r\n'.encode())
                            self.wfile.write(frame)
                            self.wfile.write(b'\r\n')
                        time.sleep(0.08)  # ~12 fps de salida hacia el navegador
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass
                return

            self.send_response(404)
            self.end_headers()

    return Handler


def iniciar_servidor(hub, puerto=PUERTO_POR_DEFECTO):
    """Arranca el servidor de streaming en un hilo daemon y devuelve la instancia."""
    servidor = ThreadingHTTPServer(('0.0.0.0', puerto), _crear_handler(hub))
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    print(f'Servidor de streaming en vivo: http://0.0.0.0:{puerto}/stream/<camara>')
    return servidor
