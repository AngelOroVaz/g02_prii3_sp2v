import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

from vision_utils import (cargar_calibracion, calibracion_para_imagen, marcar_aruco)

class DetectorAruco(Node):
    def __init__(self):
        super().__init__("detector_aruco")
        self.declare_parameter("image_topic", "/camera/image_raw")
        self.declare_parameter("annotated_topic", "/aruco/image_annotated")
        self.declare_parameter("calibration_file", "resultados/calibracion.yml")
        self.declare_parameter("dictionary", "DICT_4X4_50")
        self.declare_parameter("marker_size_m", 0.04)

        ruta = self.get_parameter("calibration_file").value
        self.k, self.d, self.resolucion_calibracion = cargar_calibracion(ruta)
        self.diccionario = self.get_parameter("dictionary").value
        self.lado = float(self.get_parameter("marker_size_m").value)
        if self.lado <= 0:
            raise ValueError("marker_size_m debe ser mayor que 0")

        self.bridge = CvBridge()
        topic = self.get_parameter("image_topic").value
        topic_salida = self.get_parameter("annotated_topic").value
        self.publicador = self.create_publisher(Image, topic_salida, 10)
        self.suscripcion = self.create_subscription(Image, topic, self.callback, 10)
        self.ultimo_log = 0.0
        self.get_logger().info(f"Recibiendo cámara: {topic} | mostrando ArUco en: {topic_salida}")

    def callback(self, mensaje):
        try:
            imagen = self.bridge.imgmsg_to_cv2(mensaje, desired_encoding="bgr8")
            h, w = imagen.shape[:2]
            k = calibracion_para_imagen(self.k, self.resolucion_calibracion, (w, h))
            anotada, ids = marcar_aruco(imagen, k, self.d, self.lado, self.diccionario)
            salida = self.bridge.cv2_to_imgmsg(anotada, encoding="bgr8")
            salida.header = mensaje.header
            self.publicador.publish(salida)
            ahora = time.monotonic()
            if ahora - self.ultimo_log >= 1:
                if ids:
                    self.get_logger().info(f"IDs ArUco detectados: {ids}")
                self.ultimo_log = ahora
        except Exception as exc:
            self.get_logger().error(f"Error de procesamiento: {exc}")

def main():
    rclpy.init()
    nodo = None
    try:
        nodo = DetectorAruco()
        rclpy.spin(nodo)
    except KeyboardInterrupt:
        pass
    finally:
        if nodo is not None:
            nodo.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()
