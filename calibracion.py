import argparse
import csv
from pathlib import Path

import cv2
import numpy as np

from vision_utils import guardar_calibracion

TABLERO = (13, 9)
EXTENSIONES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

def detectar(gris):
    flags = cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE
    correcto, esquinas = cv2.findChessboardCorners(gris, TABLERO, flags)
    if not correcto:

        if hasattr(cv2, "findChessboardCornersSB"):
            correcto, esquinas = cv2.findChessboardCornersSB(gris, TABLERO)
        if not correcto:
            return None
    criterios = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.001)
    esquinas = cv2.cornerSubPix(gris, esquinas, (11, 11), (-1, -1), criterios)
    return esquinas

def ajustar(registros, indices, puntos_3d):
    tamano = registros[indices[0]]["tamano"]
    obj = [puntos_3d.copy() for _ in indices]
    img = [registros[i]["esquinas"] for i in indices]
    rms, k, d, rvecs, tvecs = cv2.calibrateCamera(obj, img, tamano, None, None)
    errores = {}
    for i, rvec, tvec in zip(indices, rvecs, tvecs):
        reproy, _ = cv2.projectPoints(puntos_3d, rvec, tvec, k, d)
        delta = registros[i]["esquinas"].reshape(-1, 2) - reproy.reshape(-1, 2)
        errores[i] = float(np.sqrt(np.mean(np.sum(delta ** 2, axis=1))))
    return float(rms), k, d, errores

def main():
    parser = argparse.ArgumentParser(description='Calibración 13x9: esquinas coloreadas, errores por imagen, descarte y YAML.')
    parser.add_argument("--imagenes", default="imagenes", help="Carpeta con las fotos del tablero")
    parser.add_argument("--salida", default="resultados", help="Carpeta donde guardar todo")
    parser.add_argument("--lado-cuadro", type=float, default=1.0,
                        help="Lado REAL de un cuadrado, en metros; 1.0 = unidad arbitraria")
    parser.add_argument("--umbral", type=float, default=2.0,
                        help="Se intenta descartar una vista si su error supera este umbral (px)")
    parser.add_argument("--max-descartes", type=float, default=0.25,
                        help="Máxima fracción de vistas a descartar, entre 0 y 0.5")
    parser.add_argument("--min-vistas", type=int, default=8,
                        help="Número mínimo de vistas para calibrar")
    args = parser.parse_args()
    if args.lado_cuadro <= 0 or not (0 <= args.max_descartes <= 0.5) or args.min_vistas < 3:
        parser.error("Comprueba --lado-cuadro, --max-descartes y --min-vistas")

    carpeta = Path(args.imagenes)
    salida = Path(args.salida)
    detectadas = salida / "esquinas"
    detectadas.mkdir(parents=True, exist_ok=True)
    fotos = sorted(f for f in carpeta.iterdir() if f.is_file() and f.suffix.lower() in EXTENSIONES) if carpeta.is_dir() else []
    if not fotos:
        parser.error(f"No hay imágenes válidas dentro de {carpeta}")

    p3d = np.zeros((TABLERO[0] * TABLERO[1], 3), dtype=np.float32)
    p3d[:, :2] = np.mgrid[0:TABLERO[0], 0:TABLERO[1]].T.reshape(-1, 2)
    p3d *= args.lado_cuadro

    registros = []
    resolucion = None
    for n, ruta in enumerate(fotos, 1):
        imagen = cv2.imread(str(ruta))
        estado = "no_legible"
        esquinas = None
        tamano = None
        if imagen is not None:
            h, w = imagen.shape[:2]
            tamano = (w, h)
            if resolucion is None:
                resolucion = tamano
            if tamano != resolucion:
                estado = "resolucion_incompatible"
            else:
                gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
                esquinas = detectar(gris)
                estado = "detectada" if esquinas is not None else "sin_esquinas"
                if esquinas is not None:
                    cv2.drawChessboardCorners(imagen, TABLERO, esquinas, True)
                    guardado = detectadas / f"{ruta.stem}_esquinas.jpg"
                    if not cv2.imwrite(str(guardado), imagen):
                        raise OSError(f"No se pudo guardar {guardado}")
        registros.append({"ruta": ruta, "estado": estado, "esquinas": esquinas, "tamano": tamano})
        print(f"[{n:3d}/{len(fotos)}] {ruta.name}: {estado}", flush=True)

    validos = [i for i, r in enumerate(registros) if r["esquinas"] is not None]
    print(f"\nFotografías leídas: {len(fotos)} | Tableros detectados: {len(validos)}")
    if len(validos) < args.min_vistas:
        raise SystemExit(f"Faltan vistas válidas: hacen falta al menos {args.min_vistas} (ajustable con --min-vistas).")

    rms_original, k_original, d_original, errores_originales = ajustar(registros, validos, p3d)
    guardar_calibracion(salida / "calibracion_original.yml", k_original, d_original,
                        resolucion, rms_original, len(validos), TABLERO, args.lado_cuadro)
    print(f"RMS con todas las vistas: {rms_original:.4f} px")

    seleccion = validos.copy()
    limite = min(int(len(validos) * args.max_descartes), len(validos) - args.min_vistas)
    mejor = (rms_original, k_original, d_original, errores_originales)
    excluidas = []
    for _ in range(limite):
        peor = max(mejor[3], key=mejor[3].get)
        if mejor[3][peor] <= args.umbral:
            break
        candidata = [i for i in seleccion if i != peor]
        nuevo = ajustar(registros, candidata, p3d)
        if nuevo[0] >= mejor[0] - 0.005:
            break
        excluidas.append(peor)
        seleccion = candidata
        mejor = nuevo
        print(f"  Excluida {registros[peor]['ruta'].name}: "
              f"RMS {mejor[0]:.4f} px, quedan {len(seleccion)} vistas")

    guardar_calibracion(salida / "calibracion.yml", mejor[1], mejor[2],
                        resolucion, mejor[0], len(seleccion), TABLERO, args.lado_cuadro)
    if excluidas:
        guardar_calibracion(salida / "calibracion_filtrada.yml", mejor[1], mejor[2],
                            resolucion, mejor[0], len(seleccion), TABLERO, args.lado_cuadro)

    with (salida / "errores_por_imagen.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["archivo", "estado", "error_original_px", "error_final_px"])
        for i, reg in enumerate(registros):
            estado = "descartada" if i in excluidas else ("usada" if i in seleccion else reg["estado"])
            writer.writerow([reg["ruta"].name, estado,
                             f"{errores_originales[i]:.4f}" if i in errores_originales else "",
                             f"{mejor[3][i]:.4f}" if i in mejor[3] else ""])

    print("\n=== RESULTADOS ===")
    print(f"RMS original: {rms_original:.4f} px")
    print(f"RMS final:    {mejor[0]:.4f} px")
    print(f"Vistas usadas: {len(seleccion)} | descartadas: {len(excluidas)}")
    print("Matriz de cámara:\n", mejor[1])
    print("Distorsión:\n", mejor[2].ravel())
    print(f"Archivo para la práctica: {salida / 'calibracion.yml'}")
    print(f"Imágenes con líneas de colores: {detectadas}")
    print(f"Tabla para revisar las fotos: {salida / 'errores_por_imagen.csv'}")

if __name__ == "__main__":
    main()
