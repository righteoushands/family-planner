import React from "react";
import { Sparkles, ArrowRight, Check, BookOpen, Cloud, ChevronRight, UtensilsCrossed } from "lucide-react";

export function WarmEditorial() {
  return (
    <div className="min-h-screen font-sans" style={{ backgroundColor: "#F5F0E8", color: "#1C1917", maxWidth: 390, margin: "0 auto" }}>

      {/* NAV */}
      <nav
        className="flex items-center justify-between px-4 sticky top-0 z-50"
        style={{ backgroundColor: "#1C1917", height: 52 }}
      >
        <div className="flex items-center gap-1.5">
          <span className="text-sm opacity-60" style={{ color: "#F5F0E8" }}>✝</span>
          <span className="text-base tracking-wide" style={{ fontFamily: "Playfair Display, serif", color: "#F5F0E8" }}>
            Sancta Familia
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold"
            style={{ backgroundColor: "#8b3a1a", color: "#F5F0E8" }}
          >
            <UtensilsCrossed size={12} />
            Lorenzo
          </button>
          <button
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold"
            style={{ backgroundColor: "#B8904A", color: "#1C1917" }}
          >
            <Sparkles size={12} />
            Ask Lucy
          </button>
        </div>
      </nav>

      {/* LUCY BANNER */}
      <section style={{ background: "linear-gradient(160deg, #EDE8DC, #F5F0E8)", borderBottom: "1px solid #E5E0D5" }} className="px-4 pt-6 pb-5">
        <div className="flex items-center gap-3 mb-4">
          <div
            className="w-11 h-11 rounded-full flex items-center justify-center shrink-0 relative"
            style={{ backgroundColor: "#7C5C2E", border: "2px solid #B8904A", boxShadow: "0 0 12px rgba(184,144,74,0.25)" }}
          >
            <span className="text-lg" style={{ fontFamily: "Playfair Display, serif", color: "#F5F0E8" }}>L</span>
            <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-green-500 border-2" style={{ borderColor: "#EDE8DC" }} />
          </div>
          <div>
            <p className="text-xs font-bold uppercase tracking-widest" style={{ color: "#7C5C2E" }}>Lucy · AI Family Companion</p>
            <h1 className="text-2xl leading-tight" style={{ fontFamily: "Playfair Display, serif" }}>Good evening.</h1>
            <p className="text-xs" style={{ color: "#9CA3AF" }}>Saturday · April 4, 2026</p>
          </div>
        </div>

        <div
          className="rounded-xl p-4 relative overflow-hidden"
          style={{ backgroundColor: "#FFF", border: "1px solid #E5E0D5" }}
        >
          <div className="absolute left-0 top-0 bottom-0 w-[3px] rounded-l-xl" style={{ backgroundColor: "#7C5C2E" }} />
          <p className="text-sm leading-relaxed mb-3 pl-2" style={{ color: "#1C1917" }}>
            "Father, into your hands I commend my spirit." — Lk 23:46
          </p>
          <div className="flex justify-end">
            <button
              className="flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded-lg"
              style={{ color: "#B8904A", backgroundColor: "rgba(184,144,74,0.1)" }}
            >
              Prayer <ArrowRight size={12} />
            </button>
          </div>
        </div>
      </section>

      {/* STATUS STRIP */}
      <div
        className="flex items-center gap-3 px-4 py-2.5 overflow-x-auto"
        style={{ backgroundColor: "#FFF", borderBottom: "1px solid #E5E0D5", whiteSpace: "nowrap" }}
      >
        <div className="flex items-center gap-1.5 text-xs font-semibold shrink-0" style={{ color: "#7C5C2E" }}>
          <BookOpen size={13} /> Holy Week
        </div>
        <div className="w-px h-3 shrink-0" style={{ backgroundColor: "#E5E0D5" }} />
        <div className="flex items-center gap-1 text-xs font-medium shrink-0" style={{ color: "#1C1917" }}>
          <span style={{ color: "#7C5C2E" }}>✝</span> Holy Saturday
          <ArrowRight size={11} style={{ color: "#6B7280" }} />
        </div>
        <div className="w-px h-3 shrink-0" style={{ backgroundColor: "#E5E0D5" }} />
        <div className="flex items-center gap-1 text-xs font-medium shrink-0" style={{ color: "#1C1917" }}>
          <Cloud size={13} style={{ color: "#6B7280" }} /> Mass Readings
        </div>
        <div className="w-px h-3 shrink-0" style={{ backgroundColor: "#E5E0D5" }} />
        <button className="text-xs font-medium shrink-0 flex items-center gap-0.5" style={{ color: "#7C5C2E" }}>
          Plan my day <ArrowRight size={11} />
        </button>
      </div>

      {/* MAIN CONTENT */}
      <main className="px-4 py-4 flex flex-col gap-4">

        {/* MOM CARD */}
        <div className="rounded-2xl overflow-hidden" style={{ backgroundColor: "#FFF", border: "1px solid #E5E0D5" }}>
          <div className="p-4" style={{ borderBottom: "1px solid #E5E0D5" }}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-full flex items-center justify-center text-white text-sm" style={{ backgroundColor: "#7C3AED", fontFamily: "Playfair Display, serif" }}>L</div>
                <span className="text-base font-semibold">Lauren</span>
              </div>
              <div className="flex items-center gap-0.5 p-0.5 rounded-full" style={{ backgroundColor: "#F5F0E8", border: "1px solid #E5E0D5" }}>
                <button className="px-2.5 py-1 rounded-full text-xs font-semibold bg-white shadow-sm" style={{ color: "#1C1917" }}>High</button>
                <button className="px-2.5 py-1 rounded-full text-xs font-medium" style={{ color: "#6B7280" }}>Medium</button>
                <button className="px-2.5 py-1 rounded-full text-xs font-medium" style={{ color: "#6B7280" }}>Low</button>
              </div>
            </div>

            <div className="rounded-xl px-4 py-3 flex items-center gap-3 mb-3" style={{ backgroundColor: "#1C1917", color: "#F5F0E8" }}>
              <span>📋</span>
              <span className="text-sm font-medium">Step: Spiritual</span>
            </div>

            <div className="grid grid-cols-5 gap-2 mb-3">
              {["🙏", "🌙", "📅", "📆", "✅"].map((icon) => (
                <button
                  key={icon}
                  className="flex items-center justify-center py-2 rounded-xl text-lg"
                  style={{ border: "1px solid #E5E0D5", backgroundColor: "#F5F0E8" }}
                >
                  {icon}
                </button>
              ))}
            </div>
            <div className="flex justify-end gap-3">
              {["Prayer", "5AM", "Virtue"].map((label) => (
                <button key={label} className="text-xs font-semibold" style={{ color: "#7C5C2E" }}>{label}</button>
              ))}
            </div>
          </div>
          <div className="px-4 py-3 flex gap-2 items-start" style={{ backgroundColor: "#FDFBF7" }}>
            <span style={{ color: "#7C5C2E" }}>✝</span>
            <div>
              <p className="text-xs font-bold uppercase tracking-widest mb-0.5" style={{ color: "#7C5C2E" }}>Virtue · Simplicity</p>
              <p className="text-xs italic" style={{ color: "#1C1917" }}>What is one layer of complication I can remove today?</p>
            </div>
          </div>
        </div>

        {/* SECTION LABEL */}
        <p className="text-xs font-bold uppercase tracking-widest px-0.5" style={{ color: "#9CA3AF" }}>Children</p>

        {/* CHILDREN */}
        {[
          { name: "JP",      color: "#DC2626", pct: 30,  tasks: [{ subject: "Math",    title: "Lesson 42: Fractions",   done: false }, { subject: "Reading", title: "Read aloud 20 mins",   done: true  }] },
          { name: "Joseph",  color: "#16A34A", pct: 0,   tasks: [{ subject: "History", title: "Chapter 5 Review",       done: false }, { subject: "Science", title: "Nature Walk",           done: false }] },
          { name: "Michael", color: "#EA580C", pct: 100, tasks: [{ subject: "Phonics", title: "Letter M worksheet",     done: true  }, { subject: "Art",     title: "Coloring page",          done: true  }] },
        ].map(({ name, color, pct, tasks }) => (
          <div
            key={name}
            className="rounded-xl p-4 relative overflow-hidden"
            style={{ backgroundColor: "#FFF", border: "1px solid #E5E0D5", borderLeft: `3px solid ${color}` }}
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
                <span className="font-semibold text-base">{name}</span>
              </div>
              <button className="flex items-center gap-0.5 text-xs font-medium" style={{ color: "#6B7280" }}>
                Full schedule <ChevronRight size={13} />
              </button>
            </div>
            <div className="w-full h-1.5 rounded-full mb-3" style={{ backgroundColor: "#F5F0E8" }}>
              <div className="h-full rounded-full" style={{ backgroundColor: color, width: `${pct}%` }} />
            </div>
            <div className="flex flex-col gap-3">
              {tasks.map(({ subject, title, done }) => (
                <div key={subject} className={`flex items-start gap-2.5 ${done ? "opacity-40" : ""}`}>
                  <div
                    className="w-4 h-4 rounded border mt-0.5 flex items-center justify-center shrink-0"
                    style={{
                      borderColor: done ? color : "#E5E0D5",
                      backgroundColor: done ? color : "#F5F0E8",
                    }}
                  >
                    {done && <Check size={10} className="text-white" />}
                  </div>
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wide mb-0.5" style={{ color }}>{subject}</p>
                    <p className={`text-sm ${done ? "line-through" : ""}`} style={{ color: "#1C1917" }}>{title}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}

        {/* FOOTER */}
        <p className="text-center text-xs uppercase tracking-widest py-4" style={{ color: "#9CA3AF" }}>
          McAdams Family · Sancta Familia
        </p>
      </main>
    </div>
  );
}
