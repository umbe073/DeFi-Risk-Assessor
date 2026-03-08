(function () {
  const FADE_OUT_MS = 1500;
  const FADE_IN_MS = 1500;
  const HOLD_AFTER_FADE_IN_MS = 900;

  const rotators = [
    {
      id: "hsl-kicker-rotator",
      intervalMs: 7200,
      phrases: [
        "NFA. But the contract score is 23/100 so maybe reconsider.",
        "We don't tell you what to buy. We tell you what's trying to rob you.",
        "The era of blind aping is over. (Okay, it's not. But at least scan it first.)",
      ],
    },
    {
      id: "hsl-hero-headline",
      intervalMs: 7600,
      phrases: [
        "Stop praying to the chart gods. Start reading the contract.",
        "Your next 100x should survive a rug check first.",
      ],
    },
    {
      id: "hsl-subline-rotator",
      intervalMs: 6200,
      phrases: [
        "Built for degens who don't want to get rekt.",
        "Your bag deserves better than a Discord shill.",
        "Fewer rugs. More gains. Same degeneracy.",
      ],
    },
    {
      id: "hsl-hero-cta-rotator",
      intervalMs: 5400,
      phrases: [
        "Check before you wreck.",
        "30 days free. Test the feeling. Then hop in.",
        "Join the degens who do their homework.",
      ],
    },
    {
      id: "hsl-risk-slogan-rotator",
      intervalMs: 6400,
      phrases: [
        "Because 'trust me bro' is not a risk model.",
        "Holder concentration. Liquidity traps. Contract backdoors. We see it all before you FOMO in.",
      ],
    },
    {
      id: "hsl-signal-slogan-rotator",
      intervalMs: 6400,
      phrases: [
        "The whales move first. We tell you when they do.",
        "Deployer wallet went dormant for 3 years then woke up. That's a flag, not a sign.",
      ],
    },
    {
      id: "hsl-security-rotator",
      intervalMs: 7000,
      phrases: [
        "We don't tell you what to buy. We tell you what's trying to rob you.",
        "Because the blockchain doesn't lie, but the team might.",
      ],
    },
    {
      id: "hsl-bottom-cta-title",
      intervalMs: 7600,
      phrases: [
        "Check before you wreck.",
        "Join the degens who do their homework.",
      ],
    },
    {
      id: "hsl-bottom-cta-copy",
      intervalMs: 6500,
      phrases: [
        "30 days free. Test the feeling. Then hop in.",
        "Fewer rugs. More gains. Same degeneracy.",
      ],
    },
    {
      id: "hsl-bottom-subline-rotator",
      intervalMs: 6400,
      phrases: [
        "Exit liquidity for others. Not for you.",
        "Degen smarter.",
      ],
    },
    {
      id: "hsl-footer-tagline-rotator",
      intervalMs: 6800,
      phrases: [
        "Hodler Suite - On-chain intelligence for the chronically bullish.",
        "Hodler Suite - Because the blockchain doesn't lie, but the team might.",
        "Hodler Suite - Degen smarter.",
        "Hodler Suite - Exit liquidity for others. Not for you.",
      ],
    },
  ];

  function wait(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
  }

  function nextFrame() {
    return new Promise((resolve) => {
      window.requestAnimationFrame(() => {
        window.requestAnimationFrame(resolve);
      });
    });
  }

  async function animateSwap(node, nextText) {
    node.classList.add("is-fading-out");
    await wait(FADE_OUT_MS);

    node.classList.add("is-fading-in-start");
    node.textContent = nextText;
    await nextFrame();

    node.classList.remove("is-fading-out");
    node.classList.add("is-fading-in");
    await wait(FADE_IN_MS + HOLD_AFTER_FADE_IN_MS);

    node.classList.remove("is-fading-in");
    node.classList.remove("is-fading-in-start");
  }

  function runRotator(config) {
    const node = document.getElementById(config.id);
    if (!node || !Array.isArray(config.phrases) || config.phrases.length === 0) {
      return;
    }
    let idx = 0;
    node.textContent = config.phrases[idx];
    if (config.phrases.length < 2) {
      return;
    }

    const cycle = (delayOverrideMs) => {
      const waitMs =
        typeof delayOverrideMs === "number"
          ? Math.max(delayOverrideMs, 1200)
          : Math.max(config.intervalMs || 9000, 5200);
      window.setTimeout(async () => {
        if (!document.body.contains(node)) {
          return;
        }
        idx = (idx + 1) % config.phrases.length;
        await animateSwap(node, config.phrases[idx]);
        cycle();
      }, waitMs);
    };

    const initialDelay = Math.max(Math.floor((config.intervalMs || 9000) * 0.45), 2200) + Math.floor(Math.random() * 800);
    cycle(initialDelay);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      rotators.forEach(runRotator);
    });
  } else {
    rotators.forEach(runRotator);
  }
})();
