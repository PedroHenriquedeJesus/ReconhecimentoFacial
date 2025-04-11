import cv2
import os
from deepface import DeepFace

# Caminho da pasta com as imagens do banco
path = "base_rostos"

print("Carregando imagens do banco...")
database = {}

# Carrega e armazena os embeddings das imagens do banco
for img_name in os.listdir(path):
    if img_name.lower().endswith(('.png', '.jpg', '.jpeg')):
        img_path = os.path.join(path, img_name)
        try:
            embedding = DeepFace.represent(img_path=img_path, model_name='Facenet')[0]["embedding"]
            name = os.path.splitext(img_name)[0]  # Nome do arquivo sem extensão
            database[name] = embedding
        except Exception as e:
            print(f"Erro ao processar {img_name}: {e}")

print("Imagens carregadas com sucesso!")

# Inicializa webcam
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    try:
        # Reconhece rosto na imagem atual
        result = DeepFace.find(img_path=frame, db_path=path, model_name='Facenet', enforce_detection=False, detector_backend='opencv')

        if len(result) > 0 and len(result[0]) > 0:
            person_name = os.path.basename(result[0].iloc[0]['identity']).split('.')[0]
            cv2.putText(frame, person_name, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        else:
            cv2.putText(frame, "Desconhecido", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

    except Exception as e:
        print(f"Erro no reconhecimento: {e}")

    cv2.imshow("Reconhecimento Facial", frame)

    if cv2.waitKey(1) == 27:  # Tecla ESC para sair
        break

cap.release()
cv2.destroyAllWindows()
