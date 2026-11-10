// On-screen touch controls for a GlitchyGames browser game (touch devices only).
//
// The bundle builder (`python -m scripts.build_browser_bundle`) writes the game's layout into boot_config.json (TOUCH_LAYOUTS):
// a left, center and right cluster of rows of buttons, each naming the key it presses. A held
// button holds its key down: its key events are dispatched on the canvas, from where they reach
// the document, where SDL listens. So the game, its action maps, recordings and replays see
// ordinary key presses (measured 2026-10-24 in Chromium and WebKit: pygame reports the KEYDOWN
// and KEYUP, and pygame.key.get_pressed() holds the key in between; events dispatched on the
// window do not reach SDL).
//
// Several fingers can hold buttons at once, a finger can slide from one button to its
// neighbour in the same cluster (a D-pad), and two buttons pressing the same key keep it down
// until both are released.
(async () => {
  const isTouchDevice = navigator.maxTouchPoints > 0 || matchMedia('(pointer: coarse)').matches;
  if (!isTouchDevice) {
    return;
  }
  const response = await fetch('boot_config.json');
  const layout = (await response.json()).touch_controls;
  if (!layout) {
    return;
  }
  const canvas = document.getElementById('canvas');
  document.body.classList.add('touch');
  const overlayText = document.getElementById('start-overlay');
  if (overlayText) {
    overlayText.textContent = overlayText.textContent.replace('Click', 'Tap');
  }

  // How many held buttons press each key (by code): the key goes up when the last lets go
  const pressCountByCode = new Map();

  function sendKey(type, button) {
    const event = new KeyboardEvent(type, {
      key: button.key, code: button.code, bubbles: true, cancelable: true,
    });
    // keyCode cannot be given to the constructor, and Emscripten passes it to SDL
    Object.defineProperty(event, 'keyCode', { get: () => button.key_code });
    Object.defineProperty(event, 'which', { get: () => button.key_code });
    canvas.dispatchEvent(event);
  }

  // A button looks pressed while any finger holds it (its own count, apart from its key's)
  function press(element) {
    const button = element.buttonData;
    element.holderCount = (element.holderCount || 0) + 1;
    element.classList.add('pressed');
    const count = pressCountByCode.get(button.code) || 0;
    pressCountByCode.set(button.code, count + 1);
    if (count === 0) {
      sendKey('keydown', button);
    }
  }

  function release(element) {
    const button = element.buttonData;
    element.holderCount = Math.max(0, (element.holderCount || 0) - 1);
    if (element.holderCount === 0) {
      element.classList.remove('pressed');
    }
    const count = pressCountByCode.get(button.code) || 0;
    if (count <= 0) {
      return;
    }
    pressCountByCode.set(button.code, count - 1);
    if (count === 1) {
      sendKey('keyup', button);
    }
  }

  function buildCluster(name, rows) {
    const cluster = document.createElement('div');
    cluster.className = `touch-cluster touch-${name}`;
    const columnCount = Math.max(0, ...rows.map((row) => row.length));
    cluster.style.gridTemplateColumns = `repeat(${columnCount}, var(--touch-button-size))`;
    for (const row of rows) {
      for (let column = 0; column < columnCount; column += 1) {
        const button = row[column];
        const cell = document.createElement('div');
        if (button) {
          cell.className = 'touch-button';
          cell.buttonData = button;
          const label = document.createElement('span');
          label.className = 'touch-label';
          label.textContent = button.label;
          cell.append(label);
          if (button.key_name) {
            const keyName = document.createElement('span');
            keyName.className = 'touch-key-name';
            keyName.textContent = button.key_name;
            cell.append(keyName);
          }
        } else {
          cell.className = 'touch-gap';
        }
        cluster.append(cell);
      }
    }
    return cluster;
  }

  const controls = document.createElement('div');
  controls.id = 'touch-controls';
  for (const name of ['left', 'center', 'right']) {
    controls.append(buildCluster(name, layout[name] || []));
  }
  document.getElementById('frame').after(controls);

  // Each finger (pointer id) and the button it holds
  const heldByPointer = new Map();

  function buttonAt(x, y, cluster) {
    const element = document.elementFromPoint(x, y)?.closest('.touch-button');
    return element && element.parentElement === cluster ? element : null;
  }

  controls.addEventListener('pointerdown', (event) => {
    const element = event.target.closest('.touch-button');
    if (!element) {
      return;
    }
    event.preventDefault();
    // Keeps this finger's moves and lift coming here; a browser may refuse it (WebKit for a
    // pointer it did not make), and touch pointers are captured to what they touched anyway
    try {
      controls.setPointerCapture(event.pointerId);
    } catch {
      // Captured implicitly, or not at all: the press still counts
    }
    heldByPointer.set(event.pointerId, element);
    press(element);
  });

  controls.addEventListener('pointermove', (event) => {
    const held = heldByPointer.get(event.pointerId);
    if (!held) {
      return;
    }
    // Slid onto another button of the same cluster: it takes over (a D-pad). Off every button,
    // the held one stays down until the finger lifts
    const under = buttonAt(event.clientX, event.clientY, held.parentElement);
    if (under && under !== held) {
      release(held);
      heldByPointer.set(event.pointerId, under);
      press(under);
    }
  });

  function lift(event) {
    const held = heldByPointer.get(event.pointerId);
    if (held) {
      heldByPointer.delete(event.pointerId);
      release(held);
    }
  }
  controls.addEventListener('pointerup', lift);
  controls.addEventListener('pointercancel', lift);
  controls.addEventListener('lostpointercapture', lift);
  controls.addEventListener('contextmenu', (event) => event.preventDefault());

  // Leaving the page lifts every finger: no key stays down while the game is hidden
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      for (const [pointerId, held] of heldByPointer) {
        heldByPointer.delete(pointerId);
        release(held);
      }
    }
  });
})();
