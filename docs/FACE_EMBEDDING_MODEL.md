# Modelo de embedding facial

O provider interno fornecido usa `face_recognition_sface_2021dec.onnx` com
`cv2.FaceRecognizerSF`. O alinhamento de entrada é exclusivamente
`FaceRecognizerSF.alignCrop()` usando a linha completa do YuNet; o preview de
224×224 não entra no embedding.

- Modelo: OpenCV SFace 2021dec, 128 dimensões.
- Métrica: similaridade cosseno.
- SHA-256: `0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79`.
- Tamanho: 38.696.353 bytes.

O modelo é baixado e validado somente durante o build da imagem. Não há
download na inicialização do container. Thresholds continuam externos e não
são definidos neste repositório.
