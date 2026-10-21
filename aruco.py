import argparse
from pathlib import Path

import cv2

from vision_utils import cargar_calibracion, calibracion_para_imagen, diccionario_aruco, marcar_aruco, tiene_gui

EXT_IMAGEN = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


def main():
    parser = argparse.ArgumentParser(description="Detecta ArUco en imágenes, vídeos o cámaras, con o sin calibración.")
    parser.add_argument("--fuente", required=True)
    parser.add_argument("--calibracion", default="resultados/calibracion.yml")
    parser.add_argument("--sin-calibracion", action="store_true")
    parser.add_argument("--lado-marcador", type=float, default=None)
    parser.add_argument("--diccionario", default="DICT_4X4_50")
    parser.add_argument("--salida", default="resultados/aruco")
    parser.add_argument("--mostrar", action="store_true")
    parser.add_argument("--max-fotogramas", type=int, default=150)
    parser.add_argument("--ancho", type=int, default=0)
    parser.add_argument("--alto", type=int, default=0)
    args = parser.parse_args()

    if not args.sin_calibracion and (args.lado_marcador is None or args.lado_marcador <= 0):
        parser.error("Para dibujar los ejes 3D, indica --lado-marcador en metros")
    if args.lado_marcador is not None and args.lado_marcador <= 0:
        parser.error("--lado-marcador debe ser positivo")
    if (args.ancho == 0) != (args.alto == 0) or args.ancho < 0 or args.alto < 0:
        parser.error("Usa --ancho y --alto juntos, con valores positivos")
    if args.max_fotogramas < 0:
        parser.error("--max-fotogramas no puede ser negativo")

    if args.sin_calibracion:
        diccionario = diccionario_aruco(args.diccionario)
        detector = cv2.aruco.ArucoDetector(diccionario, cv2.aruco.DetectorParameters())
        k0, distorsion, resolucion = None, None, None
        print("Modo de prueba: detección de ID sin ejes 3D")
    else:
        k0, distorsion, resolucion = cargar_calibracion(args.calibracion)
        detector = None
        print("Modo calibrado: detección de ID y ejes 3D")

    def procesar(imagen):
        if detector is not None:
            anotada = imagen.copy()
            esquinas, identificadores, _ = detector.detectMarkers(imagen)
            encontrados = [] if identificadores is None else [int(i) for i in identificadores.flatten()]
            if identificadores is not None:
                cv2.aruco.drawDetectedMarkers(anotada, esquinas, identificadores)
                for puntos, numero in zip(esquinas, encontrados):
                    x, y = puntos.reshape(4, 2)[0].astype(int)
                    cv2.putText(anotada, f"ID: {numero}", (max(0, x), max(25, y - 12)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 0, 255), 2)
            else:
                cv2.putText(anotada, "ArUco: ninguno detectado", (25, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 0, 255), 2)
            return anotada, encontrados

        alto, ancho = imagen.shape[:2]
        matriz = calibracion_para_imagen(k0, resolucion, (ancho, alto))
        return marcar_aruco(imagen, matriz, distorsion, args.lado_marcador, args.diccionario)

    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    mostrar = args.mostrar and tiene_gui()
    if args.mostrar and not mostrar:
        print("Visualización por ventana no disponible; se guardará el resultado")

    if Path(args.fuente).suffix.lower() in EXT_IMAGEN:
        imagen = cv2.imread(args.fuente)
        if imagen is None:
            parser.error(f"No se puede leer la imagen: {args.fuente}")
        try:
            anotada, encontrados = procesar(imagen)
        except ValueError as error:
            parser.error(str(error))
        ruta = salida / "aruco_anotado.jpg"
        if not cv2.imwrite(str(ruta), anotada):
            raise OSError(f"No se pudo guardar {ruta}")
        print(f"IDs detectados: {encontrados}")
        print(f"Imagen guardada en: {ruta}")
        if mostrar:
            cv2.imshow("ArUco", anotada)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        return

    fuente = int(args.fuente) if args.fuente.isdigit() else args.fuente
    captura = cv2.VideoCapture(fuente)
    if not captura.isOpened():
        parser.error(f"No se puede abrir {args.fuente}")
    if args.ancho and args.alto:
        captura.set(cv2.CAP_PROP_FRAME_WIDTH, args.ancho)
        captura.set(cv2.CAP_PROP_FRAME_HEIGHT, args.alto)

    writer = None
    fotogramas = 0
    vistos = set()
    ruta_video = salida / "aruco_anotado.mp4"
    try:
        while args.max_fotogramas == 0 or fotogramas < args.max_fotogramas:
            ok, imagen = captura.read()
            if not ok:
                break
            alto, ancho = imagen.shape[:2]
            if fotogramas == 0:
                print(f"Resolución real: {ancho}x{alto}")
            try:
                anotada, identificadores = procesar(imagen)
            except ValueError as error:
                raise SystemExit(f"Calibración incompatible: {error}")
            vistos.update(identificadores)
            if writer is None:
                fps = captura.get(cv2.CAP_PROP_FPS)
                if fps < 1 or fps > 240:
                    fps = 20
                writer = cv2.VideoWriter(str(ruta_video), cv2.VideoWriter_fourcc(*"mp4v"), fps, (ancho, alto))
                if not writer.isOpened():
                    raise OSError(f"No se ha podido guardar el vídeo en: {ruta_video}")
            writer.write(anotada)
            if identificadores and (fotogramas == 0 or fotogramas % 30 == 0):
                print(f"Fotograma {fotogramas}: ID {identificadores}")
            if mostrar:
                cv2.imshow("ArUco", anotada)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    fotogramas += 1
                    break
            fotogramas += 1
    except KeyboardInterrupt:
        pass
    finally:
        captura.release()
        if writer is not None:
            writer.release()
        if mostrar:
            cv2.destroyAllWindows()

    print(f"Fotogramas procesados: {fotogramas} | ID detectados: {sorted(vistos)}")
    if writer is not None:
        print(f"Vídeo guardado en: {ruta_video}")


if __name__ == "__main__":
    main()
