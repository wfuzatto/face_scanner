(() => {
  const video = document.getElementById('video');
  const cameraWrap = document.querySelector('.camera-wrap');
  const verifyButton = document.getElementById('verify');
  const startButton = document.getElementById('startCamera');
  const stopButton = document.getElementById('stopCamera');
  const analyzeButton = document.getElementById('analyze');

  if (!video || !cameraWrap || !verifyButton) return;

  const guide = document.createElement('div');
  guide.id = 'standaloneFaceGuide';
  guide.className = 'face-guide guide-idle hidden';

  const instruction = document.createElement('div');
  instruction.id = 'standaloneCaptureInstruction';
  instruction.className = 'capture-instruction capture-warn hidden';
  instruction.textContent = 'Posicione seu rosto dentro da área indicada.';

  const metrics = document.createElement('div');
  metrics.id = 'standaloneCaptureMetrics';
  metrics.className = 'capture-metrics hidden';
  metrics.textContent = 'Pré-análise parada';

  const countdown = document.createElement('div');
  countdown.id = 'standaloneCaptureCountdown';
  countdown.className = 'capture-countdown hidden';

  cameraWrap.append(guide, instruction, metrics, countdown);

  const tips = document.createElement('div');
  tips.className = 'capture-tips hidden';
  tips.innerHTML = `
    <div class="capture-tip">1. Centralize o rosto</div>
    <div class="capture-tip">2. Ajuste distância e luz</div>
    <div class="capture-tip">3. Fique imóvel para captura</div>
  `;
  cameraWrap.insertAdjacentElement('afterend', tips);

  let timer = null;
  let checking = false;
  let paused = true;
  let readySince = null;
  let countdownTimer = null;
  let cooldownUntil = 0;
  const previewCanvas = document.createElement('canvas');

  function previewEndpoint() {
    return new URL('dashboard-api/face/preview', window.location.href).toString();
  }

  function setVisible(value) {
    for (const element of [guide, instruction, metrics, tips]) {
      element.classList.toggle('hidden', !value);
    }
    if (!value) countdown.classList.add('hidden');
  }

  function setState(state, message, metricText) {
    guide.classList.remove('guide-idle', 'guide-bad', 'guide-warn', 'guide-good');
    guide.classList.add(`guide-${state}`);

    instruction.classList.remove('capture-bad', 'capture-warn', 'capture-good');
    if (state === 'bad') instruction.classList.add('capture-bad');
    else if (state === 'good') instruction.classList.add('capture-good');
    else instruction.classList.add('capture-warn');

    instruction.textContent = message;
    metrics.textContent = metricText || '';
  }

  function cancelCountdown() {
    if (countdownTimer) window.clearInterval(countdownTimer);
    countdownTimer = null;
    countdown.classList.add('hidden');
    countdown.textContent = '';
  }

  function stopGuide(reset = true) {
    if (timer) window.clearInterval(timer);
    timer = null;
    checking = false;
    paused = true;
    readySince = null;
    cancelCountdown();
    if (reset) {
      setState('idle', 'Posicione seu rosto dentro da área indicada.', 'Pré-análise parada');
      setVisible(false);
    }
  }

  function pauseGuide() {
    paused = true;
    readySince = null;
    cancelCountdown();
  }

  function resumeGuide() {
    if (!video.srcObject || video.classList.contains('hidden')) return;
    paused = false;
    readySince = null;
    cooldownUntil = Date.now() + 1200;
    setVisible(true);
    setState('warn', 'Posicione seu rosto dentro da área indicada.', 'Aguardando análise…');
    if (!timer) timer = window.setInterval(checkOnce, 800);
    checkOnce();
  }

  async function frameBlob(maxWidth = 720, jpegQuality = 0.84) {
    if (!video.videoWidth || !video.videoHeight) return null;
    const scale = Math.min(1, maxWidth / video.videoWidth);
    const width = Math.max(1, Math.round(video.videoWidth * scale));
    const height = Math.max(1, Math.round(video.videoHeight * scale));
    previewCanvas.width = width;
    previewCanvas.height = height;
    previewCanvas.getContext('2d', { alpha: false }).drawImage(video, 0, 0, width, height);
    return await new Promise(resolve => previewCanvas.toBlob(resolve, 'image/jpeg', jpegQuality));
  }

  function startCountdown() {
    let count = 3;
    countdown.classList.remove('hidden');
    countdown.textContent = String(count);
    setState('good', 'Perfeito! Não se mexa…', metrics.textContent);

    countdownTimer = window.setInterval(() => {
      count -= 1;
      if (count > 0) {
        countdown.textContent = String(count);
        return;
      }

      cancelCountdown();
      cooldownUntil = Date.now() + 4000;
      pauseGuide();
      if (!verifyButton.disabled && video.srcObject && !video.classList.contains('hidden')) {
        verifyButton.click();
      }
    }, 650);
  }

  function applyResult(result) {
    const quality = result?.quality || {};
    const issues = Array.isArray(quality.issues) ? quality.issues : [];
    const faceCount = Number(result?.face_count || 0);
    const bbox = Array.isArray(result?.bbox) ? result.bbox : null;
    const imageWidth = Number(result?.image_width || 0);
    const imageHeight = Number(result?.image_height || 0);

    let state = 'warn';
    let message = 'Ajuste sua posição.';
    let centered = false;

    if (faceCount === 0) {
      state = 'bad';
      message = 'Posicione seu rosto dentro da área indicada.';
    } else if (faceCount > 1) {
      state = 'bad';
      message = 'Apenas uma pessoa deve aparecer na câmera.';
    } else if (bbox && imageWidth > 0 && imageHeight > 0) {
      const [x, y, width, height] = bbox.map(Number);
      const centerX = (x + width / 2) / imageWidth;
      const centerY = (y + height / 2) / imageHeight;
      centered = Math.abs(centerX - 0.5) <= 0.16 && Math.abs(centerY - 0.48) <= 0.20;

      const faceRatio = Number(quality.face_ratio || 0);
      if (faceRatio < 0.105) {
        message = 'Aproxime um pouco o rosto da câmera.';
      } else if (faceRatio > 0.48) {
        message = 'Afaste um pouco o rosto da câmera.';
      } else if (!centered) {
        message = 'Centralize o rosto dentro da área indicada.';
      } else if (issues.includes('imagem_escura')) {
        message = 'Melhore a iluminação do seu rosto.';
      } else if (issues.includes('imagem_clara_demais')) {
        message = 'Evite luz forte diretamente no rosto.';
      } else if (issues.includes('imagem_desfocada')) {
        message = 'Não se mexa. Aguarde a imagem ficar nítida.';
      } else if (quality.acceptable === true) {
        state = 'good';
        message = 'Perfeito! Olhe para frente e não se mexa.';
      }
    }

    const metricText = faceCount === 1
      ? `nitidez ${Number(quality.blur_score || 0).toFixed(1)} · luz ${Number(quality.brightness || 0).toFixed(0)} · rosto ${(Number(quality.face_ratio || 0) * 100).toFixed(1)}%`
      : `${faceCount} rosto(s) detectado(s)`;

    setState(state, message, metricText);

    const ready = state === 'good' && centered && quality.acceptable === true;
    if (!ready) {
      readySince = null;
      cancelCountdown();
      return;
    }

    if (!readySince) readySince = Date.now();
    if (Date.now() - readySince >= 900 && !countdownTimer && Date.now() >= cooldownUntil) {
      startCountdown();
    }
  }

  async function checkOnce() {
    if (paused || checking || document.hidden) return;
    if (!video.videoWidth || !video.videoHeight) return;

    checking = true;
    try {
      const blob = await frameBlob();
      if (!blob) return;

      const form = new FormData();
      form.append('selfie', blob, 'preview.jpg');
      const response = await fetch(previewEndpoint(), {
        method: 'POST',
        body: form,
        cache: 'no-store'
      });

      let payload = null;
      try { payload = await response.json(); } catch (_) {}
      if (!response.ok) throw new Error(payload?.detail || payload?.error || `HTTP ${response.status}`);
      applyResult(payload || {});
    } catch (error) {
      readySince = null;
      cancelCountdown();
      setState('warn', 'Não se mexa. Tentando avaliar a imagem novamente…', `Pré-análise: ${error.message}`);
    } finally {
      checking = false;
    }
  }

  video.addEventListener('playing', () => {
    setVisible(true);
    resumeGuide();
  });

  verifyButton.addEventListener('click', () => pauseGuide(), true);
  stopButton?.addEventListener('click', () => stopGuide(true), true);
  analyzeButton?.addEventListener('click', () => stopGuide(true), true);
  startButton?.addEventListener('click', () => {
    setState('warn', 'Abrindo câmera…', 'Aguardando vídeo');
  }, true);

  const verifyObserver = new MutationObserver(() => {
    if (!verifyButton.disabled && video.srcObject && !video.classList.contains('hidden') && paused) {
      window.setTimeout(resumeGuide, 900);
    }
  });
  verifyObserver.observe(verifyButton, { attributes: true, attributeFilter: ['disabled'] });

  const videoObserver = new MutationObserver(() => {
    if (video.classList.contains('hidden')) stopGuide(true);
  });
  videoObserver.observe(video, { attributes: true, attributeFilter: ['class'] });

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) pauseGuide();
    else if (video.srcObject && !video.classList.contains('hidden') && !verifyButton.disabled) resumeGuide();
  });

  window.addEventListener('beforeunload', () => stopGuide(false));
})();