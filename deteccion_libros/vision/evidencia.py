"""Guardado de evidencia (imagen + clip) y creación del registro EventoDeteccion en Django."""
import os
import time
import uuid

import cv2
from django.core.files.base import ContentFile

from deteccion_libros.models import EventoDeteccion


def anotar_frame(frame, texto, color):
    anotado = frame.copy()
    cv2.rectangle(anotado, (0, 0), (anotado.shape[1], 40), color, -1)
    cv2.putText(anotado, texto, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    return anotado


def guardar_clip_temporal(frames, fps=15):
    """Escribe una lista de frames a un mp4 temporal y devuelve la ruta."""
    if not frames:
        return None
    alto, ancho = frames[0].shape[:2]
    nombre_temp = os.path.join(os.environ.get('TEMP', '.'), f'clip_{uuid.uuid4().hex}.mp4')
    escritor = cv2.VideoWriter(nombre_temp, cv2.VideoWriter_fourcc(*'mp4v'), fps, (ancho, alto))
    for f in frames:
        escritor.write(f)
    escritor.release()
    return nombre_temp


def crear_evento(tipo, fuente, confianza, frame_anotado, frames_clip=None, notas=''):
    evento = EventoDeteccion(tipo=tipo, fuente=fuente, confianza=confianza, notas=notas)

    ok, buffer = cv2.imencode('.jpg', frame_anotado)
    if ok:
        nombre_img = f'{tipo}_{fuente}_{int(time.time())}.jpg'.replace(' ', '_')
        evento.imagen_evidencia.save(nombre_img, ContentFile(buffer.tobytes()), save=False)

    evento.save()

    if frames_clip:
        ruta_temp = guardar_clip_temporal(frames_clip)
        if ruta_temp:
            with open(ruta_temp, 'rb') as f:
                nombre_clip = f'{tipo}_{fuente}_{int(time.time())}.mp4'.replace(' ', '_')
                evento.clip_evidencia.save(nombre_clip, ContentFile(f.read()), save=True)
            os.remove(ruta_temp)

    return evento
