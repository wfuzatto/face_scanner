let verificationId = null;
let stream = null;
let lastCaptureCanvas = null;
const blobUrls = new Map();
const $ = id => document.getElementById(id);

function endpoint(path) {
  return new URL(path.replace(/^\//, ''), window.location.href).toString();
}

async function fetchJson(path, options = {}) {
  const response = await fetch(endpoint(path), { cache: 'no-store', ...options });
  let payload = null;
  try { payload = await response.json(); } catch (_) {}
  if (!response.ok) throw new Error(payload?.detail || payload?.error || `HTTP ${response.status}`);
  return payload;
}

function setStatus(element, text, kind = 'muted') {
  element.className = `status ${kind}`;
  element.textContent = text;
}

async function refreshHealth() {
  const health = $('health');
  try {
    const data = await fetchJson('api/v1/health');
    health.textContent = data.status === 'ok' ? 'Face Scanner pronto' : 'Face Scanner degradado';
    health.className = `pill ${data.status === 'ok' ? 'ok' : 'bad'}`;
    health.title = JSON.stringify(data, null, 2);
    $('version').textContent = `v${data.version || '?'} · provider ${data.provider_configured ? 'configurado' : 'não configurado'} · thresholds ${data.thresholds_configured ? 'ativos' : 'não configurados'}`;
  } catch (error) {
    health.textContent = 'Face Scanner indisponível';
    health.className = 'pill bad';
    $('version').textContent = error.message;
  }
}

function revokePreview(key) {
  const old = blobUrls.get(key);
  if (old) URL.revokeObjectURL(old);
  blobUrls.delete(key);
}

function clearPreviews() {
  for (const key of ['documentFace', 'documentAligned', 'liveAligned', 'liveFace']) {
    revokePreview(key);
    const img = $(`${key}Img`);
    const placeholder = $(`${key}Placeholder`);
    if (img) {
      img.removeAttribute('src');
      img.classList.add('hidden');
    }
    if (placeholder) placeholder.classList.remove('hidden');
  }
  $('documentFaceMeta').textContent = 'Aguardando detecção no documento.';
  $('documentAlignedMeta').textContent = 'Aguardando alinhamento do documento.';
  $('liveAlignedMeta').textContent = 'Aguardando alinhamento da webcam.';
  $('liveFaceMeta').textContent = 'Aguardando captura da webcam.';
  $('comparison').classList.add('hidden');
  $('metrics').classList.add('hidden');
}

function decodeAlignedJpeg(value) {
  let encoded = String(value || '').trim();
  if (!encoded) throw new Error('sem dados JPEG');
  encoded = encoded
    .replace(/^data:image\/[a-z0-9.+-]+;base64,/i, '')
    .replace(/\s+/g, '')
    .replace(/-/g, '+')
    .replace(/_/g, '/');
  while (encoded.length % 4) encoded += '=';
  const binary = atob(encoded);
  if (binary.length < 4) throw new Error('JPEG vazio');
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  if (bytes[0] !== 0xff || bytes[1] !== 0xd8) throw new Error('payload não contém JPEG válido');
  return new Blob([bytes], { type: 'image/jpeg' });
}

function showAligned(prefix, alignment, label) {
  const img = $(`${prefix}Img`);
  const placeholder = $(`${prefix}Placeholder`);
  const meta = $(`${prefix}Meta`);
  if (!alignment?.success || !alignment?.jpeg_base64) {
    meta.textContent = alignment?.message || 'Preview alinhado não disponível.';
    return;
  }
  try {
    revokePreview(prefix);
    const blob = decodeAlignedJpeg(alignment.jpeg_base64);
    const url = URL.createObjectURL(blob);
    blobUrls.set(prefix, url);
    img.onload = () => {
      img.classList.remove('hidden');
      placeholder.classList.add('hidden');
      meta.textContent = `${label} · ${alignment.width || '?'}×${alignment.height || '?'} px`;
    };
    img.onerror = () => {
      img.classList.add('hidden');
      placeholder.classList.remove('hidden');
      meta.textContent = 'Falha ao renderizar o JPEG alinhado.';
    };
    img.src = url;
  } catch (error) {
    img.classList.add('hidden');
    placeholder.classList.remove('hidden');
    meta.textContent = `Preview alinhado inválido: ${error.message}`;
  }
}

function loadImage(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => { URL.revokeObjectURL(url); resolve(image); };
    image.onerror = () => { URL.revokeObjectURL(url); reject(new Error('Não foi possível abrir a imagem.')); };
    image.src = url;
  });
}

function cropFace(source, sourceWidth, sourceHeight, bbox, analyzedWidth, analyzedHeight) {
  if (!source || !bbox || bbox.length < 4 || !analyzedWidth || !analyzedHeight) return null;
  const [bx, by, bw, bh] = bbox.map(Number);
  if (![bx, by, bw, bh].every(Number.isFinite) || bw <= 0 || bh <= 0) return null;
  const scaleX = sourceWidth / analyzedWidth;
  const scaleY = sourceHeight / analyzedHeight;
  const x = bx * scaleX;
  const y = by * scaleY;
  const w = bw * scaleX;
  const h = bh * scaleY;
  const centerX = x + w / 2;
  const centerY = y + h / 2;
  let size = Math.max(w * 1.75, h * 1.55);
  size = Math.min(size, sourceWidth, sourceHeight);
  let sx = Math.max(0, Math.min(centerX - size / 2, sourceWidth - size));
  let sy = Math.max(0, Math.min(centerY - size / 2, sourceHeight - size));
  const out = document.createElement('canvas');
  out.width = 360;
  out.height = 360;
  out.getContext('2d', { alpha: false }).drawImage(source, sx, sy, size, size, 0, 0, 360, 360);
  return out.toDataURL('image/jpeg', 0.94);
}

async function renderDocumentPreviews(result, frontFile, backFile) {
  const portrait = result?.portrait;
  if (!portrait?.found || !portrait?.bbox || !portrait?.image_width || !portrait?.image_height) return;
  const sourceFile = portrait.source === 'back' ? backFile : frontFile;
  if (!sourceFile) return;
  try {
    const image = await loadImage(sourceFile);
    const dataUrl = cropFace(image, image.naturalWidth, image.naturalHeight, portrait.bbox, portrait.image_width, portrait.image_height);
    if (dataUrl) {
      $('documentFaceImg').src = dataUrl;
      $('documentFaceImg').classList.remove('hidden');
      $('documentFacePlaceholder').classList.add('hidden');
      $('documentFaceMeta').textContent = `Rosto recortado pelo detector · origem: ${portrait.source}`;
    }
    showAligned('documentAligned', portrait.alignment, 'Face alinhada recebida do Face Scanner');
    $('comparison').classList.remove('hidden');
  } catch (error) {
    $('documentFaceMeta').textContent = error.message;
    $('comparison').classList.remove('hidden');
  }
}

function renderLivePreviews(result, canvas) {
  if (result?.bbox && result?.image_width && result?.image_height && canvas?.width && canvas?.height) {
    const dataUrl = cropFace(canvas, canvas.width, canvas.height, result.bbox, result.image_width, result.image_height);
    if (dataUrl) {
      $('liveFaceImg').src = dataUrl;
      $('liveFaceImg').classList.remove('hidden');
      $('liveFacePlaceholder').classList.add('hidden');
      $('liveFaceMeta').textContent = 'Rosto recortado da captura da webcam.';
    }
  }
  showAligned('liveAligned', result?.alignment, 'Face alinhada recebida do Face Scanner');
  $('comparison').classList.remove('hidden');
}

function renderMetrics(result) {
  const value = (id, item, suffix = '') => { $(id).textContent = item == null ? '—' : `${item}${suffix}`; };
  value('metricProvider', result.provider);
  value('metricModel', result.model);
  value('metricVersion', result.model_version);
  value('metricSimilarity', result.similarity);
  value('metricReview', result.review_threshold);
  value('metricMatch', result.match_threshold);
  value('metricAttempts', `${result.attempts_used ?? 0}/${result.max_attempts ?? 3}`);
  value('metricRemaining', result.attempts_remaining);
  value('metricLiveness', result.liveness?.status);
  value('metricGate', result.checkin_gate?.allowed === true ? 'liberado' : 'bloqueado');
  value('metricProcessing', result.processing_ms, ' ms');
  $('metrics').classList.remove('hidden');
}

function stopCamera() {
  if (stream) stream.getTracks().forEach(track => track.stop());
  stream = null;
  $('video').srcObject = null;
  $('video').classList.add('hidden');
  $('cameraPlaceholder').classList.remove('hidden');
  $('verify').disabled = true;
  $('stopCamera').disabled = true;
  $('startCamera').disabled = !verificationId;
}

$('analyze').addEventListener('click', async () => {
  const front = $('front').files[0];
  const back = $('back').files[0];
  const expectedName = $('expectedName').value.trim();
  if (!expectedName) return alert('Informe o nome esperado.');
  if (!front) return alert('Selecione a foto do documento.');

  clearPreviews();
  verificationId = null;
  stopCamera();
  $('analyze').disabled = true;
  setStatus($('documentDecision'), 'Analisando documento…');
  $('documentResult').textContent = 'Processando OCR, nome e foto do documento…';

  const form = new FormData();
  form.append('expected_name', expectedName);
  form.append('reservation_id', $('reservationId').value.trim());
  form.append('document_type', $('documentType').value);
  form.append('front', front);
  if (back) form.append('back', back);

  try {
    const result = await fetchJson('dashboard-api/document/analyze', { method: 'POST', body: form });
    verificationId = result.verification_id || null;
    $('documentResult').textContent = JSON.stringify(result, null, 2);
    await renderDocumentPreviews(result, front, back);

    const nameStatus = result?.name_validation?.status || 'unknown';
    if (result.can_verify_face && verificationId) {
      setStatus($('documentDecision'), `Documento liberado para biometria · nome ${nameStatus}`, nameStatus === 'match' ? 'ok' : 'warn');
      $('startCamera').disabled = false;
      $('faceResult').textContent = 'Documento apto. Abra a câmera para a comparação biométrica.';
    } else {
      setStatus($('documentDecision'), `Documento não liberou a etapa facial · nome ${nameStatus}`, 'bad');
      $('startCamera').disabled = true;
      $('faceResult').textContent = 'O documento não liberou a etapa facial.';
    }
  } catch (error) {
    setStatus($('documentDecision'), `Falha na análise: ${error.message}`, 'bad');
    $('documentResult').textContent = error.message;
  } finally {
    $('analyze').disabled = false;
  }
});

$('startCamera').addEventListener('click', async () => {
  if (!verificationId) return;
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
    setStatus($('faceDecision'), 'Câmera bloqueada: use HTTPS com certificado confiável.', 'bad');
    return;
  }
  stopCamera();
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 960 }, frameRate: { ideal: 30 } },
      audio: false
    });
    $('video').srcObject = stream;
    await $('video').play();
    $('video').classList.remove('hidden');
    $('cameraPlaceholder').classList.add('hidden');
    $('verify').disabled = false;
    $('stopCamera').disabled = false;
    $('startCamera').disabled = true;
    setStatus($('faceDecision'), 'Câmera aberta. Olhe para frente e capture quando estiver bem enquadrado.', 'ok');
  } catch (error) {
    setStatus($('faceDecision'), `Não foi possível abrir a câmera: ${error.message}`, 'bad');
  }
});

$('stopCamera').addEventListener('click', stopCamera);

$('verify').addEventListener('click', async () => {
  if (!verificationId || !stream) return;
  const video = $('video');
  if (!video.videoWidth || !video.videoHeight) return alert('A câmera ainda está inicializando.');

  const canvas = $('canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext('2d', { alpha: false }).drawImage(video, 0, 0, canvas.width, canvas.height);
  lastCaptureCanvas = canvas;
  const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.94));
  if (!blob) return;

  $('verify').disabled = true;
  setStatus($('faceDecision'), 'Comparando captura com a foto do documento…');
  $('faceResult').textContent = 'Processando captura…';

  const form = new FormData();
  form.append('verification_id', verificationId);
  form.append('selfie', blob, 'live-capture.jpg');

  try {
    const result = await fetchJson('dashboard-api/face/verify', { method: 'POST', body: form });
    $('faceResult').textContent = JSON.stringify(result, null, 2);
    renderLivePreviews(result, lastCaptureCanvas);
    renderMetrics(result);

    if (result.status === 'match' && result.identity_verified === true) {
      setStatus($('faceDecision'), `IDENTIDADE CONFERE · similaridade ${result.similarity ?? '—'}`, 'ok');
      stopCamera();
      verificationId = null;
      return;
    }

    if (result.status === 'review') {
      if (result.retry_allowed === true) {
        setStatus($('faceDecision'), `REVISÃO · ${result.message || 'Refaça a captura.'} · tentativas restantes: ${result.attempts_remaining ?? '—'}`, 'warn');
        $('verify').disabled = false;
      } else {
        setStatus($('faceDecision'), result.message || 'REVISÃO MANUAL NECESSÁRIA.', 'warn');
        stopCamera();
        verificationId = null;
      }
      return;
    }

    if (result.status === 'mismatch') {
      if (result.retry_allowed === true) {
        setStatus($('faceDecision'), `IDENTIDADE NÃO CONFERE · ${result.message || 'Refaça a captura.'} · tentativas restantes: ${result.attempts_remaining ?? '—'}`, 'bad');
        $('verify').disabled = false;
      } else {
        setStatus($('faceDecision'), result.message || 'IDENTIDADE NÃO CONFERE · solicite atendimento da recepção.', 'bad');
        stopCamera();
        verificationId = null;
      }
      return;
    }

    setStatus($('faceDecision'), result.message || `Resultado: ${result.status}`, 'warn');
    if (result.retry_allowed === true) $('verify').disabled = false;
    else {
      stopCamera();
      verificationId = null;
    }
  } catch (error) {
    setStatus($('faceDecision'), `Falha na captura: ${error.message}`, 'bad');
    $('faceResult').textContent = error.message;
    $('verify').disabled = false;
  }
});

window.addEventListener('beforeunload', () => {
  stopCamera();
  for (const url of blobUrls.values()) URL.revokeObjectURL(url);
});

clearPreviews();
refreshHealth();
