/* Page « Scanner un document » du backend : QR code par caméra, ou identifiant saisi. */
(function () {
  var UUID_IN_TEXT = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
  var PLACEHOLDER = '00000000-0000-0000-0000-000000000000';

  var page = document.querySelector('.scan');
  var messages = JSON.parse(document.getElementById('scan-messages').textContent);
  var reader = document.getElementById('qr-reader');
  var cameraMessage = document.getElementById('scan-camera-message');
  var toggle = document.getElementById('scan-toggle');
  var toggleLabel = document.getElementById('scan-toggle-label');
  var result = document.getElementById('scan-result');
  var manualError = document.getElementById('scan-manual-error');

  var scanner = null;
  var handled = false;

  function say(text) {
    cameraMessage.textContent = text || '';
    cameraMessage.hidden = !text;
  }

  // On ne réutilise JAMAIS le texte scanné comme adresse : seul l'UUID extrait compte.
  function extractUuid(text) {
    var match = UUID_IN_TEXT.exec(text);
    return match ? match[0].toLowerCase() : null;
  }

  function stopCamera() {
    var current = scanner;
    scanner = null;
    reader.hidden = true;
    toggleLabel.textContent = messages.start;
    if (!current) return Promise.resolve();
    return current.stop().catch(function () {}).then(function () {
      try { current.clear(); } catch (e) { /* rien à nettoyer */ }
    });
  }

  function showResult(name) {
    result.hidden = false;
    result.querySelectorAll('[data-result]').forEach(function (block) {
      block.hidden = block.dataset.result !== name;
    });
  }

  function setField(name, value) {
    result.querySelector('[data-field="' + name + '"]').textContent = value || '—';
  }

  function verify(uuid) {
    showResult('loading');
    fetch(page.dataset.verifyUrl.replace(PLACEHOLDER, uuid), { headers: { Accept: 'application/json' } })
      .then(function (response) {
        if (response.status === 404) return { status: 'not_found' };
        if (!response.ok) throw new Error('verify');
        return response.json();
      })
      .then(function (data) {
        var document_ = data.document;
        if (data.is_authentic && document_) {
          setField('type', document_.document_type_label);
          setField('holder', (document_.holder_first_name + ' ' + document_.holder_last_name).trim());
          setField('date', new Date(document_.issue_date).toLocaleDateString(document.documentElement.lang));
          setField('id', data.id);
          setField('hash', document_.signature_fingerprint);
          showResult('VALID');
        } else {
          showResult(['REVOKED', 'EXPIRED', 'not_found'].indexOf(data.status) !== -1 ? data.status : 'INVALID');
        }
        result.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      })
      .catch(function () { showResult('error'); });
  }

  function startCamera() {
    say('');
    handled = false;
    result.hidden = true;  // le résultat du document précédent ne doit pas rester affiché
    // getUserMedia n'existe qu'en HTTPS ou sur localhost.
    if (!window.isSecureContext) {
      say(messages.insecure);
      return;
    }
    reader.hidden = false;
    toggle.disabled = true;
    toggleLabel.textContent = messages.starting;
    var current = new Html5Qrcode('qr-reader');
    scanner = current;
    current.start(
      { facingMode: 'environment' },
      { fps: 10, qrbox: { width: 240, height: 240 }, aspectRatio: 1 },
      function (decodedText) {
        if (handled) return;
        var uuid = extractUuid(decodedText);
        if (!uuid) {
          say(messages.unrecognized);
          return;
        }
        handled = true;
        say('');
        stopCamera().then(function () { verify(uuid); });
      },
      function () { /* image sans QR code lisible : on continue de scanner */ }
    ).then(function () {
      toggle.disabled = false;
      toggleLabel.textContent = messages.stop;
    }).catch(function (error) {
      scanner = null;
      reader.hidden = true;
      toggle.disabled = false;
      toggleLabel.textContent = messages.start;
      try { current.clear(); } catch (e) { /* rien à nettoyer */ }
      say(/NotAllowed|Permission|denied/i.test(String(error && error.name) + ' ' + String(error)) ? messages.denied : messages.error);
    });
  }

  toggle.addEventListener('click', function () {
    if (scanner) stopCamera();
    else startCamera();
  });

  document.getElementById('scan-manual').addEventListener('submit', function (event) {
    event.preventDefault();
    var uuid = extractUuid(document.getElementById('scan-id').value);
    manualError.hidden = Boolean(uuid);
    if (!uuid) {
      result.hidden = true;
      return;
    }
    stopCamera().then(function () { verify(uuid); });
  });

  // Libère la caméra quand on quitte la page.
  window.addEventListener('pagehide', function () { stopCamera(); });
})();
