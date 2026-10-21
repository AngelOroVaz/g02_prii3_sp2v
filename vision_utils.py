from pathlib import Path
import re

import cv2
import numpy as np

def guardar_calibracion(ruta, matriz, distorsion, resolucion, rms, n_imagenes, tablero, lado_cuadro):
    ruta = str(ruta)
    fs = cv2.FileStorage(ruta, cv2.FILE_STORAGE_WRITE)
    if not fs.isOpened():
        raise OSError(f"No se puede escribir el archivo de calibración: {ruta}")
    fs.write("camera_matrix", matriz)
    fs.write("dist_coeffs", distorsion)
    fs.write("image_width", int(resolucion[0]))
    fs.write("image_height", int(resolucion[1]))
    fs.write("rms", float(rms))
    fs.write("num_images", int(n_imagenes))
    fs.write("board_cols", int(tablero[0]))
    fs.write("board_rows", int(tablero[1]))
    fs.write("square_size", float(lado_cuadro))
    fs.release()

def cargar_calibracion(ruta):
    ruta = Path(ruta)
    if not ruta.is_file():
        raise FileNotFoundError(f"No existe el archivo de calibración: {ruta}")
    fs = cv2.FileStorage(str(ruta), cv2.FILE_STORAGE_READ)
    if not fs.isOpened():
        raise ValueError(f"No se puede abrir el archivo de calibración: {ruta}")
    try:
        k = fs.getNode("camera_matrix").mat()
        d = fs.getNode("dist_coeffs").mat()
        ancho = int(fs.getNode("image_width").real())
        alto = int(fs.getNode("image_height").real())
    finally:
        fs.release()
    if k is None or d is None or k.shape != (3, 3) or not ancho or not alto:
        raise ValueError("Archivo .yml incompleto: faltan camera_matrix, dist_coeffs o dimensiones")
    return k.astype(np.float64), d.astype(np.float64), (ancho, alto)

def calibracion_para_imagen(k, resolucion_calibracion, resolucion_imagen):
    if resolucion_calibracion == resolucion_imagen:
        return k
    w0, h0 = resolucion_calibracion
    w1, h1 = resolucion_imagen
    fx, fy = w1 / w0, h1 / h0
    if abs(fx - fy) > 0.01:
        raise ValueError(
            f"La calibración es de {w0}x{h0}, pero la imagen es {w1}x{h1}. "
            "Cambiar el formato o el recorte invalida la calibración."
        )
    ajustada = k.copy()
    ajustada[0, :] *= fx
    ajustada[1, :] *= fy
    return ajustada

def diccionario_aruco(nombre):
    if not nombre.startswith("DICT_") or not hasattr(cv2.aruco, nombre):
        raise ValueError(f"Diccionario ArUco desconocido: {nombre}")
    return cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, nombre))

def _detectar_markers(imagen, nombre_diccionario):
    dicc = diccionario_aruco(nombre_diccionario)
    if hasattr(cv2.aruco, "ArucoDetector"):
        params = cv2.aruco.DetectorParameters()
        return cv2.aruco.ArucoDetector(dicc, params).detectMarkers(imagen)
    params = cv2.aruco.DetectorParameters_create()
    return cv2.aruco.detectMarkers(imagen, dicc, parameters=params)

def marcar_aruco(imagen, k, d, lado_marcador_m, nombre_diccionario="DICT_4X4_50"):
    resultado = imagen.copy()
    esquinas, ids, _ = _detectar_markers(imagen, nombre_diccionario)
    encontrados = []
    if ids is None:
        cv2.putText(resultado, "ArUco: ninguno detectado", (25, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 0, 255), 2)
        return resultado, encontrados

    cv2.aruco.drawDetectedMarkers(resultado, esquinas, ids)
    mitad = lado_marcador_m / 2.0
    puntos_3d = np.array([
        [-mitad, mitad, 0], [mitad, mitad, 0],
        [mitad, -mitad, 0], [-mitad, -mitad, 0]
    ], dtype=np.float32)
    for pts, id_marcador in zip(esquinas, ids.flatten()):
        id_marcador = int(id_marcador)
        encontrados.append(id_marcador)
        puntos_2d = pts.reshape(4, 2).astype(np.float32)
        valido, rot, transl = cv2.solvePnP(
            puntos_3d, puntos_2d, k, d, flags=cv2.SOLVEPNP_IPPE_SQUARE
        )
        if valido:
            cv2.drawFrameAxes(resultado, k, d, rot, transl, lado_marcador_m * 0.5, 2)
        x, y = np.round(puntos_2d[0]).astype(int)
        cv2.putText(resultado, f"ID: {id_marcador}", (max(0, x), max(25, y - 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 0, 255), 2)
    return resultado, encontrados

def tiene_gui():
    m = re.search(r"^\s*GUI:\s*(\S+)", cv2.getBuildInformation(), re.MULTILINE)
    return bool(m and m.group(1).upper() != "NONE")
