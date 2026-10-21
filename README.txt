
PREPARACIÓN
Requisitos: Python 3, OpenCV con módulo aruco y NumPy.
No se necesita GUI para los resultados guardados. Compatible con OpenCV sin imshow().
Instalación recomendada aislada en Ubuntu/Debian:
  sudo apt install python3-venv
  python3 -m venv .venv
  source .venv/bin/activate
  python -m pip install opencv-contrib-python numpy

DIRECTORIOS
  calibracion.py
  rectificar.py
  aruco.py
  aruco_ros2.py
  vision_utils.py
  imagenes/
    foto01.jpg
    foto02.jpg
    ... (todas las fotografías del tablero)

PASO 1. CALIBRAR
  python calibracion.py --imagenes imagenes

Tablero: 13 x 9 esquinas INTERIORES (117 puntos).
Las fotos que no permitan encontrar las esquinas se notifican.
Se guarda:
  resultados/esquinas/                 cada fotografía válida con líneas de colores
  resultados/calibracion_original.yml  calibración con todas las vistas detectadas
  resultados/calibracion.yml           calibración candidata tras filtrado
  resultados/calibracion_filtrada.yml  si ha habido descartes
  resultados/errores_por_imagen.csv    RMS por fotografía y fotos descartadas



PASO 2. COMPARAR ORIGINAL Y RECTIFICADA
Con una foto tomada por LA MISMA CÁMARA y lente que las fotos de calibración:
  python rectificar.py --imagen imagenes/foto01.jpg

Se crea:
  resultados/rectificacion/original.jpg
  resultados/rectificacion/rectificada.jpg
  resultados/rectificacion/comparacion.jpg
La fotografía debe mostrar el tablero Eurobot 2026 para la demostración.
Alfa=1 prioriza conservar campo de visión, puede mostrar bordes negros.
La calibración deja de ser válida si cambia la lente, zoom o recorte.

PASO 3. ARUCO: IMAGEN O CÁMARA DIRECTA
Indica el tamaño REAL del lado del marcador ArUco, en METROS.
Ejemplo: lado de 4 centímetros = 0.04 m:
  python aruco.py --fuente imagenes/foto01.jpg --lado-marcador 0.04
  python aruco.py --fuente 0 --lado-marcador 0.04 --max-fotogramas 150

Se crea:
  resultados/aruco/aruco_anotado.jpg   para una imagen
  resultados/aruco/aruco_anotado.mp4   para cámara/vídeo

El diccionario debe ser el del código impreso. DICT_4X4_50 es solo un
valor inicial, cambia --diccionario cuando corresponda:
  python aruco.py --fuente foto.jpg --lado-marcador 0.04 --diccionario DICT_6X6_250

Los ejes se dibujan con cv2.drawFrameAxes: X rojo, Y verde, Z azul.
Las fotos de calibración no son garantía de que haya ArUco de ese diccionario.

PASO 4. CÁMARA DEL JETBOT A TRAVÉS DE ROS 2
Solo si la cámara publica el tópico sensor_msgs/Image (no CompressedImage).
Con ROS 2, sensor_msgs y cv_bridge instalados en el entorno del robot:
  python3 aruco_ros2.py --ros-args \
      -p image_topic:=/camera/image_raw \
      -p annotated_topic:=/aruco/image_annotated \
      -p calibration_file:=/ruta/absoluta/resultados/calibracion.yml \
      -p dictionary:=DICT_4X4_50 \
      -p marker_size_m:=0.04

Ver el resultado gráficamente en un equipo con ROS 2:
  ros2 run rqt_image_view rqt_image_view
Seleccionar /aruco/image_annotated.

Comprueba qué publica tu cámara con:
  ros2 topic list
  ros2 topic info /camera/image_raw
