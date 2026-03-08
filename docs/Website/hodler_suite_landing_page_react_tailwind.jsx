import React, { useState } from "react";
import { motion } from "framer-motion";
import {
  ArrowRight,
  ShieldCheck,
  Activity,
  LineChart,
  BellRing,
  FileDown,
  Sparkles,
  Check,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const fadeUp = {
  hidden: { opacity: 0, y: 18 },
  show: { opacity: 1, y: 0 },
};

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
};

function Glow() {
  return (
    <>
      {/* Ambient glows */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-24 left-1/2 h-[420px] w-[720px] -translate-x-1/2 rounded-full bg-cyan-500/20 blur-3xl" />
        <div className="absolute top-48 -left-20 h-[360px] w-[360px] rounded-full bg-blue-500/15 blur-3xl" />
        <div className="absolute top-[520px] -right-24 h-[420px] w-[420px] rounded-full bg-indigo-500/15 blur-3xl" />
        <div className="absolute bottom-0 left-1/2 h-[520px] w-[820px] -translate-x-1/2 rounded-full bg-sky-500/10 blur-3xl" />
      </div>
      {/* Subtle grid */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.25]"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, rgba(148,163,184,0.25) 1px, transparent 0)",
          backgroundSize: "28px 28px",
        }}
      />
    </>
  );
}

function Container({ children }) {
  return <div className="mx-auto w-full max-w-6xl px-4 sm:px-6 lg:px-8">{children}</div>;
}

const appMenuLinks = [
  { label: "Homepage", href: "/" },
  { label: "Help Center", href: "/help-center" },
  { label: "FAQ", href: "/faq" },
  { label: "Docs", href: "/docs" },
  { label: "Dashboard", href: "/dashboard" },
  { label: "Live Assessment", href: "/live-assessment" },
  { label: "Settings", href: "/settings" },
  { label: "Support Tickets", href: "/support-tickets" },
  { label: "Account", href: "/account" },
  { label: "Checkout", href: "/checkout" },
];

function SideMenu({ open, onClose }) {
  if (!open) {
    return null;
  }
  return (
    <div className="fixed inset-0 z-[70]">
      <button
        type="button"
        onClick={onClose}
        className="absolute inset-0 bg-slate-950/75 backdrop-blur-sm"
        aria-label="Close navigation menu"
      />
      <aside className="relative h-full w-[300px] border-r border-slate-800/70 bg-slate-950/95 p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="grid h-9 w-9 place-items-center rounded-xl bg-slate-900/60 ring-1 ring-slate-700/60">
              <Sparkles className="h-5 w-5 text-cyan-300" />
            </div>
            <div>
              <div className="text-sm font-semibold text-slate-100">Hodler Suite</div>
              <div className="text-xs text-slate-400">Navigation</div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid h-8 w-8 place-items-center rounded-lg bg-slate-900/50 text-slate-300 ring-1 ring-slate-700/60 hover:bg-slate-900/70"
            aria-label="Close menu"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-6 grid gap-2">
          {appMenuLinks.map((item) => (
            <a
              key={item.href}
              href={item.href}
              onClick={onClose}
              className="rounded-xl px-3 py-2 text-sm text-slate-200 ring-1 ring-transparent transition hover:bg-slate-900/50 hover:text-slate-100 hover:ring-slate-700/60"
            >
              {item.label}
            </a>
          ))}
        </div>

        <div className="mt-6 rounded-2xl bg-slate-900/40 p-4 ring-1 ring-slate-800/70">
          <div className="text-xs uppercase tracking-wide text-slate-400">Free trial</div>
          <p className="mt-2 text-sm text-slate-300">
            New users can activate a free 30-day plan and scan one token contract per day.
          </p>
          <Button
            className="mt-3 w-full bg-cyan-400 text-slate-950 hover:bg-cyan-300"
            onClick={() => {
              window.location.href = "/signup";
            }}
          >
            Register Free Account
          </Button>
        </div>
      </aside>
    </div>
  );
}

function TopNav({ onOpenMenu }) {
  return (
    <div className="sticky top-0 z-50 backdrop-blur-xl">
      <div className="relative">
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-slate-700/60 to-transparent" />
        <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-slate-800/80 to-transparent" />
        <Container>
          <div className="flex h-16 items-center justify-between">
            <button
              type="button"
              onClick={onOpenMenu}
              className="group flex items-center gap-2 rounded-2xl p-1.5 text-left transition hover:bg-slate-900/50"
              aria-label="Open website menu"
            >
              <div className="grid h-9 w-9 place-items-center rounded-xl bg-slate-900/60 ring-1 ring-slate-700/60 shadow-[0_0_0_1px_rgba(15,23,42,0.2)]">
                <Sparkles className="h-5 w-5 text-cyan-300" />
              </div>
              <div className="leading-tight">
                <div className="text-sm font-semibold tracking-tight text-slate-100">Hodler Suite</div>
                <div className="text-xs text-slate-400 group-hover:text-slate-300">Open menu</div>
              </div>
            </button>

            <div className="hidden items-center gap-6 text-sm text-slate-300 md:flex">
              <a className="hover:text-slate-100 transition" href="#features">Features</a>
              <a className="hover:text-slate-100 transition" href="#how">How it works</a>
              <a className="hover:text-slate-100 transition" href="#roadmap">Roadmap</a>
              <a className="hover:text-slate-100 transition" href="#security">Security</a>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                className="hidden sm:inline-flex bg-slate-900/50 text-slate-100 hover:bg-slate-900/70 ring-1 ring-slate-700/60"
                onClick={() => {
                  window.location.href = "#dashboard-sample";
                }}
              >
                View sample report
              </Button>
              <Button
                className="bg-cyan-400 text-slate-950 hover:bg-cyan-300"
                onClick={() => {
                  window.location.href = "/signup";
                }}
              >
                Request a demo <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
          </div>
        </Container>
      </div>
    </div>
  );
}

function Hero() {
  return (
    <section className="relative pt-14 sm:pt-20">
      <Container>
        <motion.div
          initial="hidden"
          animate="show"
          variants={stagger}
          className="relative"
        >
          <motion.div variants={fadeUp} className="flex justify-center">
            <Badge className="bg-slate-900/50 text-slate-200 ring-1 ring-slate-700/60">
              Token risk intelligence • Multi-chain support • Red-flag aware
            </Badge>
          </motion.div>

          <motion.h1
            variants={fadeUp}
            className="mt-6 text-center text-4xl font-semibold tracking-tight text-slate-50 sm:text-6xl"
          >
            Hodler Suite
          </motion.h1>

          <motion.p
            variants={fadeUp}
            className="mx-auto mt-4 max-w-2xl text-center text-lg font-medium text-cyan-300 sm:text-xl"
          >
            Scan token contracts before they become costly surprises.
          </motion.p>

          <motion.p
            variants={fadeUp}
            className="mx-auto mt-4 max-w-2xl text-center text-base leading-relaxed text-slate-300 sm:text-lg"
          >
            Hodler Suite analyzes token contracts, holder behavior, liquidity conditions, and market data in one workflow.
            You get a clear risk score, actionable red flags, and compliance-ready output in minutes.
          </motion.p>

          <motion.div variants={fadeUp} className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button
              size="lg"
              className="bg-cyan-400 text-slate-950 hover:bg-cyan-300 w-full sm:w-auto"
              onClick={() => {
                window.location.href = "/signup";
              }}
            >
              Start free 30-day trial <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
            <Button
              size="lg"
              variant="secondary"
              className="bg-slate-900/50 text-slate-100 hover:bg-slate-900/70 ring-1 ring-slate-700/60 w-full sm:w-auto"
              onClick={() => {
                window.location.href = "#dashboard-sample";
              }}
            >
              View sample report
            </Button>
          </motion.div>

          <motion.div
            variants={fadeUp}
            className="mx-auto mt-10 grid max-w-3xl grid-cols-2 gap-3 sm:grid-cols-4"
          >
            {[
              "Token contract verification",
              "Behavioral scoring",
              "Automated red flags",
              "EU mode support",
            ].map((t) => (
              <div
                key={t}
                className="rounded-2xl bg-slate-900/40 px-4 py-3 text-center text-xs text-slate-200 ring-1 ring-slate-700/50"
              >
                {t}
              </div>
            ))}
          </motion.div>

          {/* Hero panel */}
          <motion.div
            variants={fadeUp}
            id="dashboard-sample"
            className="relative mx-auto mt-12 max-w-5xl"
          >
            <div className="absolute -inset-2 rounded-[28px] bg-gradient-to-r from-cyan-500/15 via-sky-500/10 to-indigo-500/15 blur-2xl" />
            <div className="relative rounded-[28px] bg-slate-950/40 ring-1 ring-slate-800/80 overflow-hidden">
              <div className="flex items-center justify-between border-b border-slate-800/80 px-5 py-4">
                <div className="flex items-center gap-2">
                  <div className="h-2.5 w-2.5 rounded-full bg-slate-700" />
                  <div className="h-2.5 w-2.5 rounded-full bg-slate-700" />
                  <div className="h-2.5 w-2.5 rounded-full bg-slate-700" />
                </div>
                <div className="text-xs text-slate-400">Token Analysis • Behavior • Risk • Reporting</div>
              </div>

              <div className="grid gap-4 p-5 sm:grid-cols-12">
                <div className="sm:col-span-7 rounded-2xl bg-slate-900/40 ring-1 ring-slate-800/70 p-5">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm text-slate-400">Token Intelligence Snapshot</div>
                      <div className="mt-1 text-2xl font-semibold text-slate-50">USDT • 0xdAC17F...13D831ec7</div>
                    </div>
                    <Badge className="bg-emerald-500/15 text-emerald-200 ring-1 ring-emerald-500/20">Risk score 78/100</Badge>
                  </div>

                  <div className="mt-5 grid grid-cols-2 gap-3">
                    {[
                      { k: "Chain coverage", v: "ETH • TRON • BSC" },
                      { k: "Top-10 holder concentration", v: "38.4%" },
                      { k: "24h liquidity depth", v: "+12.4%" },
                      { k: "Behavioral score", v: "74 / 100" },
                    ].map((i) => (
                      <div key={i.k} className="rounded-xl bg-slate-950/40 ring-1 ring-slate-800/70 p-4">
                        <div className="text-xs text-slate-400">{i.k}</div>
                        <div className="mt-1 text-base font-semibold text-slate-100">{i.v}</div>
                      </div>
                    ))}
                  </div>

                  <div className="mt-5 rounded-xl bg-slate-950/40 ring-1 ring-slate-800/70 p-4">
                    <div className="text-xs text-slate-400">Recent token signals</div>
                    <div className="mt-3 space-y-2">
                      {[
                        { a: "Uniswap V3", b: "Liquidity pool depth increase", c: "Verified", d: "4 min ago" },
                        { a: "Top holder", b: "Large transfer to CEX", c: "Flag: review", d: "11 min ago" },
                        { a: "Deployer wallet", b: "Dormant wallet became active", c: "Flag: high", d: "2 hr ago" },
                      ].map((r, idx) => (
                        <div
                          key={idx}
                          className="flex items-center justify-between rounded-lg bg-slate-900/40 ring-1 ring-slate-800/60 px-3 py-2"
                        >
                          <div className="text-sm text-slate-200">
                            <span className="font-semibold">{r.a}</span> • {r.b}
                          </div>
                          <div className="flex items-center gap-2">
                            <span className={`text-xs ${r.c.includes("Flag") ? "text-amber-200" : "text-emerald-200"}`}>
                              {r.c}
                            </span>
                            <span className="text-xs text-slate-500">{r.d}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="sm:col-span-5 grid gap-4">
                  <div className="rounded-2xl bg-slate-900/40 ring-1 ring-slate-800/70 p-5">
                    <div className="text-sm font-semibold text-slate-100">Risk Snapshot</div>
                    <p className="mt-2 text-sm text-slate-300">
                      Contract permissions, holder concentration, and unusual flows surfaced before they impact capital.
                    </p>
                    <div className="mt-4 space-y-3">
                      {[
                        { label: "Contract permission risk", value: "Review" },
                        { label: "Whale concentration", value: "Moderate" },
                        { label: "Liquidity lock stability", value: "Stable" },
                      ].map((x) => (
                        <div key={x.label} className="flex items-center justify-between rounded-xl bg-slate-950/40 ring-1 ring-slate-800/70 px-4 py-3">
                          <div className="text-xs text-slate-400">{x.label}</div>
                          <div className="text-sm font-semibold text-slate-100">{x.value}</div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-2xl bg-slate-900/40 ring-1 ring-slate-800/70 p-5">
                    <div className="text-sm font-semibold text-slate-100">Report Export</div>
                    <p className="mt-2 text-sm text-slate-300">
                      Export token due-diligence reports with market category scores, behavioral categories, and red flags.
                    </p>
                    <div className="mt-4 flex items-center justify-between rounded-xl bg-slate-950/40 ring-1 ring-slate-800/70 px-4 py-3">
                      <div className="text-xs text-slate-400">Latest output</div>
                      <div className="inline-flex items-center gap-2 text-sm font-semibold text-slate-100">
                        PDF / JSON / CSV <FileDown className="h-4 w-4 text-slate-300" />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </motion.div>
      </Container>
    </section>
  );
}

function FeatureCard({
  icon: Icon,
  title,
  desc,
}) {
  return (
    <Card className="bg-slate-950/40 ring-1 ring-slate-800/80 shadow-[0_0_0_1px_rgba(2,6,23,0.25)] rounded-2xl">
      <CardHeader className="pb-2">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-2xl bg-slate-900/60 ring-1 ring-slate-800/70">
            <Icon className="h-5 w-5 text-cyan-300" />
          </div>
          <CardTitle className="text-slate-100 text-base">{title}</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-sm leading-relaxed text-slate-300">{desc}</p>
      </CardContent>
    </Card>
  );
}

function Features() {
  return (
    <section id="features" className="relative py-16 sm:py-24">
      <Container>
        <motion.div initial="hidden" whileInView="show" viewport={{ once: true, amount: 0.2 }} variants={stagger}>
          <motion.div variants={fadeUp} className="flex items-center justify-between gap-4">
            <div>
              <div className="text-sm text-slate-400">Capabilities</div>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight text-slate-50 sm:text-4xl">
                Built for token due diligence. Designed for decisive risk control.
              </h2>
              <p className="mt-3 max-w-2xl text-base text-slate-300">
                Hodler Suite transforms raw token-level blockchain signals into practical intelligence, combining on-chain
                evidence with market context for fast, defensible decisions.
              </p>
            </div>
            <div className="hidden md:flex">
              <Badge className="bg-slate-900/50 text-slate-200 ring-1 ring-slate-700/60">Premium dark fintech UI</Badge>
            </div>
          </motion.div>

          <motion.div variants={fadeUp} className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <FeatureCard
              icon={ShieldCheck}
              title="Contract-first verification"
              desc="Inspect token contract behavior, deployer signals, and transfer patterns from verifiable on-chain sources."
            />
            <FeatureCard
              icon={LineChart}
              title="Market + behavior scoring"
              desc="Get clear category scores for market health and behavioral risk in one standardized report."
            />
            <FeatureCard
              icon={Activity}
              title="Holder concentration analysis"
              desc="Track concentration, whale movement, and suspicious distribution shifts before they escalate."
            />
            <FeatureCard
              icon={BellRing}
              title="Automated red-flag engine"
              desc="Unusual contract interactions, suspicious flows, and anomaly triggers are surfaced with context."
            />
            <FeatureCard
              icon={FileDown}
              title="Compliance-ready exports"
              desc="Generate clean outputs for analysts, risk teams, and governance workflows in JSON, CSV, or PDF."
            />
            <FeatureCard
              icon={Sparkles}
              title="Resilient data ingestion"
              desc="Fallback APIs and configurable refresh controls keep token assessment available during endpoint outages."
            />
          </motion.div>
        </motion.div>
      </Container>
    </section>
  );
}

function HowItWorks() {
  const steps = [
    {
      title: "Enter token contract",
      desc: "Submit the token contract address and choose the supported chain context.",
    },
    {
      title: "Collect and normalize signals",
      desc: "Hodler Suite pulls on-chain, liquidity, and market inputs, then normalizes them into a reliable schema.",
    },
    {
      title: "Generate actionable risk report",
      desc: "Receive category scores, red flags, and detailed evidence you can share or investigate immediately.",
    },
  ];

  return (
    <section id="how" className="relative py-16 sm:py-24">
      <Container>
        <motion.div initial="hidden" whileInView="show" viewport={{ once: true, amount: 0.25 }} variants={stagger}>
          <motion.div variants={fadeUp} className="grid gap-8 lg:grid-cols-12">
            <div className="lg:col-span-5">
              <div className="text-sm text-slate-400">Workflow</div>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight text-slate-50 sm:text-4xl">From contract to conviction</h2>
              <p className="mt-3 text-base text-slate-300">
                Stop stitching explorers and spreadsheets by hand. Get a single risk workflow focused on token contracts.
              </p>
              <div className="mt-6 space-y-3">
                {[
                  "Evidence-first scoring with traceable signals",
                  "Configurable fallback APIs and refresh behavior",
                  "Supports both quick scans and institutional reviews",
                ].map((x) => (
                  <div key={x} className="flex items-start gap-3">
                    <div className="mt-0.5 grid h-6 w-6 place-items-center rounded-lg bg-cyan-500/15 ring-1 ring-cyan-500/20">
                      <Check className="h-4 w-4 text-cyan-300" />
                    </div>
                    <div className="text-sm text-slate-300">{x}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="lg:col-span-7">
              <div className="rounded-[28px] bg-slate-950/40 ring-1 ring-slate-800/80 p-5">
                <div className="grid gap-3 sm:grid-cols-3">
                  {steps.map((s, idx) => (
                    <div key={s.title} className="rounded-2xl bg-slate-900/40 ring-1 ring-slate-800/70 p-5">
                      <div className="text-xs text-slate-400">Step {idx + 1}</div>
                      <div className="mt-2 text-sm font-semibold text-slate-100">{s.title}</div>
                      <div className="mt-2 text-sm leading-relaxed text-slate-300">{s.desc}</div>
                    </div>
                  ))}
                </div>
                <div className="mt-4 rounded-2xl bg-gradient-to-r from-cyan-500/10 via-sky-500/10 to-indigo-500/10 ring-1 ring-slate-800/70 p-5">
                  <div className="text-sm font-semibold text-slate-100">Operationally ready output</div>
                  <p className="mt-2 text-sm text-slate-300">
                    Market scores, behavioral scores, red flags, and source references in a format your team can act on.
                  </p>
                </div>
              </div>
            </div>
          </motion.div>
        </motion.div>
      </Container>
    </section>
  );
}

function Roadmap() {
  const items = [
    {
      q: "Now",
      title: "Token risk core",
      bullets: [
        "Contract-level due diligence workflow",
        "Market + behavioral category scoring",
        "Red-flag output with evidence links",
      ],
      status: "Live",
    },
    {
      q: "Next",
      title: "Coverage expansion",
      bullets: [
        "Broader chain and DEX data adapters",
        "Improved anomaly classification",
        "Faster live scan completion pipeline",
      ],
      status: "In progress",
    },
    {
      q: "Soon",
      title: "Monitoring automation",
      bullets: [
        "Persistent watchlists for critical tokens",
        "Trigger-based alert escalation",
        "Ops dashboards for unresolved high-risk tokens",
      ],
      status: "Planned",
    },
    {
      q: "Later",
      title: "Extended analytics suite",
      bullets: [
        "Wallet exposure module (optional feature set)",
        "Custom integration endpoints",
        "Institutional governance reporting packs",
      ],
      status: "Exploring",
    },
  ];

  return (
    <section id="roadmap" className="relative py-16 sm:py-24">
      <Container>
        <motion.div initial="hidden" whileInView="show" viewport={{ once: true, amount: 0.2 }} variants={stagger}>
          <motion.div variants={fadeUp} className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <div className="text-sm text-slate-400">Roadmap</div>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight text-slate-50 sm:text-4xl">What’s next</h2>
              <p className="mt-3 max-w-2xl text-base text-slate-300">
                Product roadmap aligned to your current token-first engine and near-term platform priorities.
              </p>
            </div>
            <Badge className="w-fit bg-slate-900/50 text-slate-200 ring-1 ring-slate-700/60">Live direction</Badge>
          </motion.div>

          <motion.div variants={fadeUp} className="mt-10 grid gap-4 md:grid-cols-2">
            {items.map((it) => (
              <Card
                key={it.title}
                className="rounded-2xl bg-slate-950/40 ring-1 ring-slate-800/80 shadow-[0_0_0_1px_rgba(2,6,23,0.25)]"
              >
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div className="grid h-10 w-10 place-items-center rounded-2xl bg-slate-900/60 ring-1 ring-slate-800/70">
                        <span className="text-sm font-semibold text-cyan-300">{it.q}</span>
                      </div>
                      <div>
                        <CardTitle className="text-base text-slate-100">{it.title}</CardTitle>
                        <div className="mt-1 text-xs text-slate-400">{it.status}</div>
                      </div>
                    </div>
                    <Badge className="bg-cyan-500/10 text-cyan-200 ring-1 ring-cyan-500/20">{it.q}</Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2 text-sm text-slate-300">
                    {it.bullets.map((b) => (
                      <li key={b} className="flex items-start gap-2">
                        <span className="mt-2 h-1.5 w-1.5 rounded-full bg-slate-500" />
                        <span className="leading-relaxed">{b}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            ))}
          </motion.div>
        </motion.div>
      </Container>
    </section>
  );
}

function Security() {
  return (
    <section id="security" className="relative py-16 sm:py-24">
      <Container>
        <motion.div initial="hidden" whileInView="show" viewport={{ once: true, amount: 0.25 }} variants={stagger}>
          <motion.div variants={fadeUp} className="grid gap-6 lg:grid-cols-12">
            <div className="lg:col-span-6">
              <div className="text-sm text-slate-400">Trust</div>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight text-slate-50 sm:text-4xl">
                Security-first by design
              </h2>
              <p className="mt-3 text-base text-slate-300">
                Hodler Suite handles token intelligence with strict operational boundaries, auditability, and transparent data
                provenance.
              </p>
            </div>

            <div className="lg:col-span-6">
              <div className="rounded-[28px] bg-slate-950/40 ring-1 ring-slate-800/80 p-5">
                <div className="grid gap-3 sm:grid-cols-2">
                  {[
                    {
                      title: "Read-only access",
                      desc: "No trade execution, no custody, and no signing required for standard token scans.",
                    },
                    {
                      title: "Evidence over assumptions",
                      desc: "Scores and findings are tied back to source-level chain and market evidence.",
                    },
                    {
                      title: "Controlled operational settings",
                      desc: "Fine-tune EU mode, API fallback behavior, and refresh settings for your environment.",
                    },
                    {
                      title: "Audit-friendly outputs",
                      desc: "Structured reports keep compliance review and external diligence straightforward.",
                    },
                  ].map((x) => (
                    <div key={x.title} className="rounded-2xl bg-slate-900/40 ring-1 ring-slate-800/70 p-5">
                      <div className="text-sm font-semibold text-slate-100">{x.title}</div>
                      <div className="mt-2 text-sm leading-relaxed text-slate-300">{x.desc}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>
        </motion.div>
      </Container>
    </section>
  );
}

function CTA() {
  return (
    <section className="relative py-16 sm:py-24">
      <Container>
        <motion.div initial="hidden" whileInView="show" viewport={{ once: true, amount: 0.25 }} variants={stagger}>
          <motion.div
            variants={fadeUp}
            className="relative overflow-hidden rounded-[32px] bg-slate-950/40 ring-1 ring-slate-800/80"
          >
            <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/10 via-sky-500/10 to-indigo-500/10" />
            <div className="relative px-6 py-10 sm:px-10 sm:py-14">
              <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <h2 className="text-2xl font-semibold tracking-tight text-slate-50 sm:text-3xl">
                    Make token due diligence your default.
                  </h2>
                  <p className="mt-2 max-w-2xl text-base text-slate-300">
                    Start with a free 30-day account, run your first contract scans, and move to paid plans only when your
                    workflow is ready.
                  </p>
                </div>
                <div className="flex flex-col gap-3 sm:flex-row">
                  <Button
                    size="lg"
                    className="bg-cyan-400 text-slate-950 hover:bg-cyan-300"
                    onClick={() => {
                      window.location.href = "/signup";
                    }}
                  >
                    Start free 30 days <ArrowRight className="ml-2 h-5 w-5" />
                  </Button>
                  <Button
                    size="lg"
                    variant="secondary"
                    className="bg-slate-900/50 text-slate-100 hover:bg-slate-900/70 ring-1 ring-slate-700/60"
                    onClick={() => {
                      window.location.href = "/signup";
                    }}
                  >
                    Request a demo
                  </Button>
                </div>
              </div>
            </div>
          </motion.div>
        </motion.div>
      </Container>
    </section>
  );
}

function Footer() {
  return (
    <footer className="relative border-t border-slate-800/70">
      <Container>
        <div className="flex flex-col gap-4 py-10 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-sm text-slate-400">© {new Date().getFullYear()} Hodler Suite All Rights Reserved</div>
          <div className="flex flex-wrap items-center gap-4 text-sm">
            <a className="text-slate-400 hover:text-slate-200 transition" href="#features">Features</a>
            <a className="text-slate-400 hover:text-slate-200 transition" href="#roadmap">Roadmap</a>
            <a className="text-slate-400 hover:text-slate-200 transition" href="#security">Security</a>
            <a className="text-slate-400 hover:text-slate-200 transition" href="/faq">FAQ</a>
            <a className="text-slate-400 hover:text-slate-200 transition" href="/checkout">Plans</a>
          </div>
        </div>
      </Container>
    </footer>
  );
}

export default function HodlerSuiteLanding() {
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <div className="min-h-screen bg-slate-950 text-slate-50">
      <div className="relative">
        <Glow />
        <TopNav onOpenMenu={() => setMenuOpen(true)} />
        <SideMenu open={menuOpen} onClose={() => setMenuOpen(false)} />
        <main>
          <Hero />
          <Features />
          <HowItWorks />
          <Roadmap />
          <Security />
          <CTA />
        </main>
        <Footer />
      </div>
    </div>
  );
}
