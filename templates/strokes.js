// Draws one stroke-order animation per character. Runs inside the Anki card.
// - Stroke data is read from the hidden #hw-data field (no network requests).
// - Colors come from CSS variables (see style.css), so night mode works.
// - Speed and size come from config.toml; the build fills in ANIMATION below.

(function () {
  var ANIMATION = %%ANIMATION%%;
  var LIBRARY = "_hanzi-writer.min.js"; // included in the .apkg as a media file

  // Each time a card is shown, stop the animations of the previous card.
  var run = (window.hwRun || 0) + 1;
  window.hwRun = run;
  (window.hwWriters || []).forEach(function (old) {
    try {
      old.pauseAnimation();
    } catch (error) {
      // already finished, nothing to stop
    }
  });
  window.hwWriters = [];

  function readColor(element, name) {
    return getComputedStyle(element).getPropertyValue(name).trim();
  }

  // Play the animation, wait, play again. Stops when the card is gone.
  function loop(writer, cell) {
    if (run !== window.hwRun || !document.body.contains(cell)) {
      return;
    }
    writer.animateCharacter({
      onComplete: function () {
        setTimeout(function () {
          loop(writer, cell);
        }, ANIMATION.delay_between_loops);
      }
    });
  }

  function drawAll() {
    var box = document.getElementById("hw-strokes");
    var dataElement = document.getElementById("hw-data");
    if (!box || !dataElement) {
      return;
    }

    var payload;
    try {
      payload = JSON.parse(dataElement.textContent);
    } catch (error) {
      return; // empty or broken field: draw nothing
    }

    box.innerHTML = "";

    payload.chars.forEach(function (character) {
      var cell = document.createElement("div");
      cell.className = "hw-cell";
      box.appendChild(cell);

      if (!payload.data[character]) {
        cell.className = "hw-cell hw-missing";
        cell.style.width = ANIMATION.width + "px";
        cell.style.height = ANIMATION.height + "px";
        cell.textContent = character;
        return;
      }

      var writer = HanziWriter.create(cell, character, {
        width: ANIMATION.width,
        height: ANIMATION.height,
        padding: 5,
        showOutline: true,
        strokeAnimationSpeed: ANIMATION.speed,
        delayBetweenStrokes: ANIMATION.delay_between_strokes,
        strokeColor: readColor(box, "--hz-stroke"),
        radicalColor: readColor(box, "--hz-radical"),
        outlineColor: readColor(box, "--hz-outline"),
        highlightColor: readColor(box, "--hz-highlight"),
        charDataLoader: function (char, onComplete) {
          onComplete(payload.data[char]);
        }
      });
      window.hwWriters.push(writer);
      loop(writer, cell);
    });
  }

  function start() {
    if (typeof HanziWriter !== "undefined") {
      drawAll();
      return;
    }
    // The library is a local media file. Load it first, then draw.
    var script = document.createElement("script");
    script.src = LIBRARY;
    script.onload = drawAll;
    document.head.appendChild(script);
  }

  start();
})();
