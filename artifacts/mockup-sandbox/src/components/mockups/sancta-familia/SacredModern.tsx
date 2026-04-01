import React from "react";

export function SacredModern() {
  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ backgroundColor: "#0F0E0C", color: "#F5F0E8", maxWidth: 390, margin: "0 auto", fontFamily: "Inter, sans-serif" }}
    >
      <style dangerouslySetInnerHTML={{ __html: `
        @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400;1,600&family=Inter:wght@300;400;500;600&display=swap');
        .cg { font-family: 'Cormorant Garamond', serif; }
      ` }} />

      {/* NAV */}
      <nav
        className="flex items-center justify-between px-4 sticky top-0 z-50"
        style={{ height: 52, backgroundColor: "#0F0E0C", borderBottom: "1px solid rgba(255,255,255,0.08)" }}
      >
        <div className="flex items-center gap-1.5">
          <span style={{ color: "#C4943A", fontSize: 14 }}>✝</span>
          <span className="cg text-lg font-medium tracking-wide" style={{ color: "#C4943A" }}>Sancta Familia</span>
        </div>
        <button
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium"
          style={{ color: "#C4943A", border: "1px solid rgba(196,148,58,0.35)", boxShadow: "0 0 10px rgba(196,148,58,0.1)" }}
        >
          ✨ Lucy
        </button>
      </nav>

      {/* LUCY HERO */}
      <section
        className="px-4 pt-6 pb-5"
        style={{ background: "radial-gradient(ellipse at top, rgba(196,148,58,0.1) 0%, #1A1916 60%)", backgroundColor: "#1A1916" }}
      >
        {/* Avatar + greeting row */}
        <div className="flex items-center gap-3 mb-4">
          <div
            className="rounded-full flex items-center justify-center shrink-0"
            style={{
              width: 56, height: 56,
              background: "radial-gradient(circle at top left, #C4943A, #7C5C2E)",
              boxShadow: "0 0 24px rgba(196,148,58,0.35), inset 0 1px 3px rgba(255,255,255,0.25)"
            }}
          >
            <span className="cg italic text-white" style={{ fontSize: 32, paddingRight: 2 }}>L</span>
          </div>
          <div>
            <h1 className="cg text-3xl leading-tight" style={{ color: "#F5F0E8" }}>Good afternoon.</h1>
            <p className="text-[11px] font-medium uppercase tracking-wider mt-0.5" style={{ color: "#6B7280" }}>
              Wednesday · April 1, 2026
            </p>
          </div>
        </div>

        {/* Quote */}
        <p className="cg italic text-base mb-4 px-1" style={{ color: "rgba(196,148,58,0.85)", lineHeight: 1.5 }}>
          "Not my will, but yours, be done."
          <span className="text-xs not-italic ml-2" style={{ fontFamily: "Inter, sans-serif", color: "#6B7280" }}>— Lk 22:42</span>
        </p>

        {/* Lucy message card */}
        <div
          className="rounded-2xl p-4"
          style={{ backgroundColor: "#252220", border: "1px solid rgba(255,255,255,0.06)" }}
        >
          <p className="text-sm leading-relaxed mb-3" style={{ color: "#F5F0E8" }}>
            Ready to plan today? James naps at 11am — use that window for focused school with the older boys.
          </p>
          <button
            className="w-full py-2.5 rounded-xl text-sm font-semibold"
            style={{ backgroundColor: "#C4943A", color: "#0F0E0C" }}
          >
            Plan my day →
          </button>
        </div>
      </section>

      {/* STATUS STRIP */}
      <div
        className="flex items-center gap-2 px-4 py-2.5 overflow-x-auto"
        style={{ backgroundColor: "#1A1916", borderTop: "1px solid rgba(196,148,58,0.2)", borderBottom: "1px solid rgba(255,255,255,0.05)", whiteSpace: "nowrap" }}
      >
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium shrink-0" style={{ backgroundColor: "rgba(196,148,58,0.1)", color: "#C4943A", border: "1px solid rgba(196,148,58,0.2)" }}>
          📖 Holy Week
        </div>
        <div className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium shrink-0" style={{ backgroundColor: "#252220", color: "#9CA3AF", border: "1px solid rgba(255,255,255,0.05)" }}>
          <span style={{ color: "#C4943A" }}>✝</span> Feria
        </div>
        <button className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium shrink-0" style={{ backgroundColor: "#252220", color: "#9CA3AF", border: "1px solid rgba(255,255,255,0.05)" }}>
          📖 Mass Readings ↗
        </button>
        <div className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium shrink-0" style={{ backgroundColor: "#252220", color: "#9CA3AF", border: "1px solid rgba(255,255,255,0.05)" }}>
          ⛅ 68°
        </div>
        <button className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium shrink-0" style={{ backgroundColor: "#252220", color: "#9CA3AF", border: "1px solid rgba(255,255,255,0.05)" }}>
          Prayer →
        </button>
      </div>

      {/* FAMILY CARDS */}
      <main className="px-4 py-4 flex flex-col gap-3 flex-1">

        {/* MOM */}
        <div
          className="rounded-2xl p-4 relative overflow-hidden"
          style={{ backgroundColor: "#252220", borderLeft: "4px solid #C4943A" }}
        >
          <div className="absolute top-0 right-0 w-24 h-24 rounded-full pointer-events-none" style={{ background: "radial-gradient(circle, rgba(196,148,58,0.08), transparent)", transform: "translate(30%, -30%)" }} />

          <div className="flex items-center justify-between mb-3 relative">
            <span className="cg text-3xl font-medium" style={{ color: "#F5F0E8" }}>Mom</span>
            <div className="flex gap-1">
              {[1,2,3].map(i => (
                <div key={i} className="w-2 h-2 rounded-full" style={{ backgroundColor: i <= 3 ? "#C4943A" : "#444", opacity: i <= 3 ? 0.8 : 0.3 }} />
              ))}
              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: "#444", opacity: 0.3 }} />
            </div>
          </div>

          <div className="px-3 py-2 rounded-xl flex items-center gap-2 mb-3" style={{ backgroundColor: "rgba(15,14,12,0.5)", border: "1px solid rgba(255,255,255,0.05)" }}>
            <span className="text-sm">📋</span>
            <span className="text-sm font-medium" style={{ color: "#F5F0E8" }}>Free Time</span>
            <span className="ml-auto text-[10px]" style={{ color: "#6B7280" }}>Until 3:00 PM</span>
          </div>

          <div className="flex flex-col gap-2 mb-4">
            {[
              { icon: "📅", title: "Plan my day", sub: "Lucy-assisted" },
              { icon: "📚", title: "School plan", sub: "JP & Joseph" },
              { icon: "🌙", title: "Evening examen", sub: "5 min reflection" },
            ].map(({ icon, title, sub }) => (
              <button
                key={title}
                className="flex items-center gap-3 w-full text-left px-3 py-2.5 rounded-xl"
                style={{ backgroundColor: "rgba(15,14,12,0.5)", border: "1px solid rgba(255,255,255,0.05)" }}
              >
                <span>{icon}</span>
                <div className="flex-1">
                  <p className="text-sm font-medium" style={{ color: "#F5F0E8" }}>{title}</p>
                  <p className="text-[10px]" style={{ color: "#6B7280" }}>{sub}</p>
                </div>
                <div className="w-4 h-4 rounded border" style={{ borderColor: "#444" }} />
              </button>
            ))}
          </div>

          <div className="pt-3 relative" style={{ borderTop: "1px solid rgba(255,255,255,0.07)" }}>
            <p className="cg italic text-base leading-snug" style={{ color: "#9CA3AF" }}>"Patience is the companion of wisdom."</p>
            <p className="text-[10px] uppercase tracking-wider mt-1" style={{ color: "#6B7280" }}>Virtue Focus</p>
          </div>
        </div>

        {/* CHILDREN */}
        {[
          { name: "JP", color: "#F87171", pct: 60, tasks: [{ s: "Math", t: "Lesson 42: Fractions", done: false }, { s: "History", t: "Read chapter 5", done: false }] },
          { name: "Joseph", color: "#4ADE80", pct: 80, tasks: [{ s: "Science", t: "Botany experiment", done: false }, { s: "Latin", t: "Vocab review", done: true }] },
          { name: "Michael", color: "#FB923C", pct: 25, tasks: [{ s: "Reading", t: "Read aloud with Mom", done: false }, { s: "Handwriting", t: "Copywork sheet", done: false }] },
        ].map(({ name, color, pct, tasks }) => (
          <div
            key={name}
            className="rounded-xl p-4"
            style={{ backgroundColor: "#252220", borderLeft: `3px solid ${color}` }}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="cg text-2xl font-medium" style={{ color: "#F5F0E8" }}>{name}</span>
              <div className="text-right">
                <div className="text-[10px] font-bold uppercase tracking-wider" style={{ color }}>{pct}% done</div>
              </div>
            </div>
            <div className="w-full h-1 rounded-full mb-3" style={{ backgroundColor: "#0F0E0C" }}>
              <div className="h-full rounded-full" style={{ backgroundColor: color, width: `${pct}%` }} />
            </div>
            <div className="flex flex-col gap-2">
              {tasks.map(({ s, t, done }) => (
                <div key={s} className={`flex items-start gap-2.5 ${done ? "opacity-40" : ""}`}>
                  <div
                    className="mt-0.5 w-4 h-4 rounded border flex items-center justify-center shrink-0"
                    style={{ borderColor: done ? color : "#444", backgroundColor: done ? `${color}22` : "transparent" }}
                  >
                    {done && (
                      <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
                        <path d="M1 4L3.5 6.5L9 1" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    )}
                  </div>
                  <div className={done ? "line-through" : ""}>
                    <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded mr-1" style={{ color, backgroundColor: `${color}18` }}>{s}</span>
                    <span className="text-xs" style={{ color: "#F5F0E8" }}>{t}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}

        {/* FOOTER */}
        <div className="flex flex-col items-center py-4 gap-1">
          <span style={{ color: "#C4943A", fontSize: 13, opacity: 0.5 }}>✝</span>
          <p className="cg text-xs uppercase tracking-widest" style={{ color: "#6B7280" }}>McAdams Family</p>
        </div>
      </main>
    </div>
  );
}
