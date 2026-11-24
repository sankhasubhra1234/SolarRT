// SolarRT Aurora Splash Animation
// A beautiful aurora borealis animation in a landscape backdrop
// Plays on page load for ~3 seconds, then fades out

(function() {
  "use strict";

  // Check if we're on a page with the splash screen
  const splashScreen = document.getElementById("splashScreen");
  const splashCanvas = document.getElementById("splashCanvas");
  const splashAscii = document.getElementById("splashAscii");
  const splashName = document.getElementById("splashName");
  const splashSub = document.getElementById("splashSub");

  if (!splashCanvas) return;

  // Configuration
  const config = {
    particleCount: 200,
    colorPalette: [
      "#00ff88", // green lime
      "#43d98a", // teal
      "#96ffb8", // light green
      "#ff6b35", // orange
      "#ffa020", // amber
      "#d03cff", // purple
    ],
    minSize: 2,
    maxSize: 8,
    baseSpeed: 0.5,
    variation: 0.3,
    landscapeHeight: 100,
    landscapeColor: "#05051a",
  };

  // Check if canvas is supported
  const canvas = splashCanvas;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  // Set canvas size
  function resizeCanvas() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }
  resizeCanvas();
  window.addEventListener("resize", resizeCanvas);

  // Aurora particle
  class AuroraParticle {
    constructor() {
      this.reset();
    }

    reset() {
      this.x = Math.random() * canvas.width;
      this.y = Math.random() * canvas.height * 0.6; // mainly in upper area
      this.size = Math.random() * (config.maxSize - config.minSize) + config.minSize;
      this.speed = (config.baseSpeed + Math.random() * config.variation) * 0.5;
      this.opacity = 0.3 + Math.random() * 0.7;
      this.colorIndex = Math.floor(Math.random() * config.colorPalette.length);
    }

    update() {
      this.y += this.speed;
      if (this.y > canvas.height) {
        this.reset();
      }
    }

    draw() {
      ctx.fillStyle = config.colorPalette[this.colorIndex];
      ctx.globalAlpha = this.opacity;
      ctx.fillRect(this.x, this.y, this.size, this.size * 0.5);
      ctx.globalAlpha = 1;
    }
  }

  // Landscape layer
  function drawLandscape() {
    ctx.fillStyle = config.landscapeColor;
    ctx.fillRect(0, config.landscapeHeight, canvas.width, canvas.height - config.landscapeHeight);

    // Draw ground/snow line
    ctx.fillStyle = "#0a0a1a";
    ctx.fillRect(0, canvas.height - 20, canvas.width, 20);

    // Simple mountain silhouette
    ctx.fillStyle = "#0d0d20";
    ctx.beginPath();
    ctx.moveTo(0, canvas.height - 20);
    for (let i = 0; i < canvas.width; i += 50) {
      const h = Math.random() * 40 + 20;
      ctx.lineTo(i, canvas.height - 20 - h);
    }
    ctx.lineTo(canvas.width, canvas.height - 20);
    ctx.lineTo(0, canvas.height - 20);
    ctx.fill();
  }

  // Initialize particles
  const particles = [];
  for (let i = 0; i < config.particleCount; i++) {
    particles.push(new AuroraParticle());
  }

  // Animation loop
  let animationId = null;
  let elapsed = 0;

  function animate() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw landscape first
    drawLandscape();

    // Update and draw particles
    particles.forEach((particle) => {
      particle.update();
      particle.draw();
    });

    animationId = requestAnimationFrame(animate);
    elapsed += 16;

    // Auto-stop after 3 seconds
    if (elapsed > 3000) {
      cancelAnimationFrame(animationId);
      fadeOutSplash();
    }
  }

  function fadeOutSplash() {
    let opacity = 1;
    const fadeId = setInterval(() => {
      opacity -= 0.05;
      if (opacity <= 0) {
        clearInterval(fadeId);
        splashScreen.style.display = "none";
        // Initialize the main app after splash
        setTimeout(() => {
          if (window.init) window.init();
        }, 500);
      } else {
        splashScreen.style.opacity = opacity;
        splashScreen.style.transition = "opacity 1s ease-out";
      }
    }, 20);
  }

  // Start animation
  animate();
})();