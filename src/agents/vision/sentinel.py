import cv2
import os
import face_recognition

class SentinelVisionAgent:
    def __init__(self, camera_index=0):
        self.camera_index = camera_index
        print(f"[Sentinel] Inicializando módulo de visión en la cámara {self.camera_index}...")

        # Rutas de las carpetas de rostros
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        self.known_faces_dir = os.path.join(base_dir, "data", "faces", "known")
        self.threats_faces_dir = os.path.join(base_dir, "data", "faces", "threats")

        self.known_face_encodings = []
        self.known_face_names = []
        self.threat_face_encodings = []
        self.threat_face_names = []

        self._load_faces(self.known_faces_dir, self.known_face_encodings, self.known_face_names, "Permitido")
        self._load_faces(self.threats_faces_dir, self.threat_face_encodings, self.threat_face_names, "AMENAZA")

    def _load_faces(self, folder_path, encoding_list, name_list, tag):
        print(f"[Sentinel] Cargando rostros ({tag}) desde: {folder_path}")
        if not os.path.exists(folder_path):
            print(f"[Error Sentinel] La ruta {folder_path} no existe.")
            return

        for filename in os.listdir(folder_path):
            if filename.endswith(".jpg") or filename.endswith(".png"):
                image_path = os.path.join(folder_path, filename)
                image = face_recognition.load_image_file(image_path)
                encodings = face_recognition.face_encodings(image)
                if encodings:
                    encoding_list.append(encodings[0])
                    # Usamos el nombre del archivo sin extensión como etiqueta
                    name_list.append(os.path.splitext(filename)[0])
                    print(f"  + Registrado: {filename}")
                else:
                    print(f"  - No se encontró rostro claro en {filename}")

    def start_pipeline(self):
        print("[Sentinel] Abriendo el stream de video...")
        cap = cv2.VideoCapture(self.camera_index)

        if not cap.isOpened():
            print(f"[Error Sentinel] No se pudo acceder a la cámara (Índice {self.camera_index}).")
            return

        print("[Sentinel] Pipeline en vivo. Presiona 'q' para salir.")
        
        # Reducir frecuencia de procesamiento para optimizar (ej. 1 de caada 3 frames)
        process_this_frame = True

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Redimensionar frame para procesamiento más rápido (1/4 del tamaño)
                small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
                # Convertir color de BGR OpenCV a RGB (face_recognition usa RGB)
                rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

                if process_this_frame:
                    # Buscar todas las caras en el frame actual
                    face_locations = face_recognition.face_locations(rgb_small_frame, model="hog")
                    face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

                    face_names = []
                    for face_encoding in face_encodings:
                        # ----- COMPARAR CON AMENAZAS PRIMERO (Mayor Prioridad) -----
                        matches_threat = face_recognition.compare_faces(self.threat_face_encodings, face_encoding, tolerance=0.5)
                        name = "Desconocido"
                        color = (255, 255, 255) # Blanco para desconocido

                        if True in matches_threat:
                            first_match_index = matches_threat.index(True)
                            name = f"AMENAZA: {self.threat_face_names[first_match_index]}"
                            color = (0, 0, 255) # Rojo para alertas
                            # TODO: Aquí dispararemos el MQTT a The Warden para el Protocolo Cero
                            print(f"\n[ALERTA SENTINEL] Detección de criminal: {name}!")

                        else:
                            # ----- COMPARAR CON PERMITIDOS -----
                            matches_known = face_recognition.compare_faces(self.known_face_encodings, face_encoding, tolerance=0.5)
                            if True in matches_known:
                                first_match_index = matches_known.index(True)
                                name = self.known_face_names[first_match_index]
                                color = (0, 255, 0) # Verde para dueños/permitidos

                        face_names.append((name, color))

                process_this_frame = not process_this_frame

                # Dibujar las cajas y nombres en el HUD
                for (top, right, bottom, left), (name, color) in zip(face_locations, face_names if 'face_names' in locals() else []):
                    # Volver a escalar las posiciones (fueron reducidas al 1/4)
                    top *= 4
                    right *= 4
                    bottom *= 4
                    left *= 4

                    # Dibujar cuadro
                    cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                    
                    # Dibujar etiqueta con nombre
                    cv2.rectangle(frame, (left, bottom - 35), (right, bottom), color, cv2.FILLED)
                    font = cv2.FONT_HERSHEY_DUPLEX
                    cv2.putText(frame, name, (left + 6, bottom - 6), font, 0.7, (255,255,255), 1)

                
                cv2.putText(frame, "Sentinel Vision - FACIAL RECOGNITION ACTIVE", (20, 40), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                cv2.imshow('Sentinel Video Feed', frame)

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("\n[Sentinel] Apagando feed de visión por orden local.")
                    break
                    
        except KeyboardInterrupt:
            print("\n[Sentinel] Interrupción de teclado detectada.")
        finally:
            cap.release()
            cv2.destroyAllWindows()
            print("[Sentinel] Hardware liberado.")

if __name__ == "__main__":
    vision_agent = SentinelVisionAgent()
    vision_agent.start_pipeline()
