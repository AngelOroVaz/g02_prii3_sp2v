import argparse
import os
import shutil
import subprocess
from pathlib import Path

import cv2
import numpy as np

from vision_utils import cargar_calibracion, calibracion_para_imagen


def main():
    parser = argparse.ArgumentParser(description="Compara en una sola imagen el tablero Eurobot original y rectificado.")
    parser.add_argument("--imagen", required=True)
    parser.add_argument("--calibracion", default="resultados/calibracion.yml")
    parser.add_argument("--salida", default="resultados/rectificacion")
    parser.add_argument("--no-abrir", action="store_true")
    args = parser.parse_args()

    original = cv2.imread(args.imagen)
    if original is None:
        parser.error(f"No se puede abrir la imagen: {args.imagen}")

    matriz, distorsion, resolucion = cargar_calibracion(args.calibracion)
    alto, ancho = original.shape[:2]
    matriz = calibracion_para_imagen(matriz, resolucion, (ancho, alto))
    matriz_nueva, _ = cv2.getOptimalNewCameraMatrix(
        matriz, distorsion, (ancho, alto), 1, (ancho, alto)
    )
    corregida = cv2.undistort(original, matriz, distorsion, None, matriz_nueva)

    altura_titulo = 60
    comparacion = np.zeros((alto + altura_titulo, 2 * ancho, 3), dtype=np.uint8)
    comparacion[altura_titulo:, :ancho] = original
    comparacion[altura_titulo:, ancho:] = corregida
    cv2.putText(comparacion, "SIN CORREGIR", (25, 43), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(comparacion, "CORREGIDA", (ancho + 25, 43), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.line(comparacion, (ancho, 0), (ancho, alto + altura_titulo), (255, 255, 255), 3)

    carpeta = Path(args.salida)
    carpeta.mkdir(parents=True, exist_ok=True)
    archivos = {
        "original.jpg": original,
        "rectificada.jpg": corregida,
        "comparacion.jpg": comparacion,
    }
    for nombre, imagen in archivos.items():
        if not cv2.imwrite(str(carpeta / nombre), imagen):
            raise OSError(f"No se pudo guardar: {carpeta / nombre}")

    ruta_comparacion = (carpeta / "comparacion.jpg").resolve()
    print(f"Comparación original/corregida: {ruta_comparacion}")
    if not args.no_abrir and shutil.which("xdg-open") and (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        subprocess.Popen(["xdg-open", str(ruta_comparacion)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
