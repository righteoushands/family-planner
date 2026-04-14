import React from "react";
import { Sparkles, ArrowRight, Check, BookOpen, Cloud, ChevronRight, UtensilsCrossed } from "lucide-react";

export function WarmEditorial() {
  return (
    <div className="min-h-screen font-sans" style={{ backgroundColor: "#F5F0E8", color: "#1C1917", maxWidth: 390, margin: "0 auto" }}>

      {/* NAV */}
      <nav
        className="flex items-center justify-between px-4 sticky top-0 z-50"
        style={{ backgroundColor: "#1C1917", height: 48 }}
      >
        <div className="flex items-center gap-1.5">
          <span className="text-sm opacity-60" style={{ color: "#F5F0E8" }}>✝</span>
          <span className="text-base tracking-wide" style={{ fontFamily: "Playfair Display, serif", color: "#F5F0E8" }}>
            Sancta Familia
          </span>
        </div>
      </nav>

      {/* AI COMPANIONS STRIP */}
      <div className="px-4 py-2.5" style={{ backgroundColor: "#1C1917", borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
        <p className="text-xs mb-2" style={{ color: "rgba(245,240,232,0.5)", letterSpacing: "0.04em" }}>Your AI companions</p>
        <div className="flex gap-2">
          <button
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold flex-1 justify-center"
            style={{ backgroundColor: "#8b3a1a", color: "#F5F0E8" }}
          >
            <UtensilsCrossed size={11} />
            <span>Lorenzo <span style={{ opacity: 0.7, fontWeight: 400 }}>· Personal Chef</span></span>
          </button>
          <button
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold flex-1 justify-center"
            style={{ backgroundColor: "#5b3a8a", color: "#F5F0E8" }}
          >
            <Sparkles size={11} />
            <span>Lucy <span style={{ opacity: 0.7, fontWeight: 400 }}>· Family Guide</span></span>
          </button>
        </div>
      </div>

      {/* LUCY BANNER */}
      <section style={{ background: "linear-gradient(160deg, #EDE8DC, #F5F0E8)", borderBottom: "1px solid #E5E0D5" }} className="px-4 pt-4 pb-3">
        <div className="flex items-center gap-3 mb-3">
          <div
            className="w-10 h-10 rounded-full flex items-center justify-center shrink-0 relative"
            style={{ backgroundColor: "#7C5C2E", border: "2px solid #B8904A", boxShadow: "0 0 10px rgba(184,144,74,0.2)" }}
          >
            <span className="text-base" style={{ fontFamily: "Playfair Display, serif", color: "#F5F0E8" }}>L</span>
            <div className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-green-500 border-2" style={{ borderColor: "#EDE8DC" }} />
          </div>
          <div>
            <p className="text-xs font-bold uppercase tracking-widest" style={{ color: "#7C5C2E" }}>Lucy · AI Family Companion</p>
            <h1 className="text-3xl leading-tight" style={{ fontFamily: "Playfair Display, serif" }}>Good evening.</h1>
            <p className="text-xs" style={{ color: "#9CA3AF" }}>Tuesday · April 14, 2026</p>
          </div>
        </div>

        <div
          className="rounded-xl p-3 relative overflow-hidden"
          style={{ backgroundColor: "#FFF", border: "1px solid #E5E0D5" }}
        >
          <div className="absolute left-0 top-0 bottom-0 w-[3px] rounded-l-xl" style={{ backgroundColor: "#7C5C2E" }} />
          <p className="text-sm leading-snug mb-2 pl-2" style={{ color: "#1C1917" }}>
            "Father, into your hands I commend my spirit." — Lk 23:46
          </p>
          <div className="flex justify-end">
            <button
              className="flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-lg"
              style={{ color: "#B8904A", backgroundColor: "rgba(184,144,74,0.1)" }}
            >
              Prayer <ArrowRight size={11} />
            </button>
          </div>
        </div>
      </section>

      {/* STATUS STRIP — single row, all items fit */}
      <div
        className="flex items-center px-4 py-2"
        style={{ backgroundColor: "#FFF", borderBottom: "1px solid #E5E0D5" }}
      >
        <div className="flex items-center gap-1 text-xs font-semibold shrink-0" style={{ color: "#7C5C2E" }}>
          <BookOpen size={11} /> Holy Week
        </div>
        <div className="w-px h-3 mx-2.5 shrink-0" style={{ backgroundColor: "#E5E0D5" }} />
        <div className="flex items-center gap-1 text-xs font-medium shrink-0" style={{ color: "#1C1917" }}>
          <span style={{ color: "#7C5C2E" }}>✝</span> Easter Octave
        </div>
        <div className="w-px h-3 mx-2.5 shrink-0" style={{ backgroundColor: "#E5E0D5" }} />
        <div className="flex items-center gap-1 text-xs font-medium shrink-0" style={{ color: "#1C1917" }}>
          <Cloud size={11} style={{ color: "#6B7280" }} /> Mass Readings
        </div>
        <button className="text-xs font-semibold ml-auto shrink-0 flex items-center gap-0.5" style={{ color: "#7C5C2E" }}>
          Plan my day <ArrowRight size={10} />
        </button>
      </div>

      {/* MAIN CONTENT */}
      <main className="px-3 py-3 flex flex-col gap-3">

        {/* MOM CARD */}
        <div className="rounded-xl overflow-hidden" style={{ backgroundColor: "#FFF", border: "1px solid #E5E0D5" }}>
          <div className="p-3" style={{ borderBottom: "1px solid #E5E0D5" }}>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-full flex items-center justify-center text-white text-sm" style={{ backgroundColor: "#7C3AED", fontFamily: "Playfair Display, serif" }}>L</div>
                <span className="text-sm font-semibold">Lauren</span>
              </div>
              <div className="flex items-center gap-0.5 p-0.5 rounded-full" style={{ backgroundColor: "#F5F0E8", border: "1px solid #E5E0D5" }}>
                <button className="px-2 py-0.5 rounded-full text-xs font-semibold bg-white shadow-sm" style={{ color: "#1C1917" }}>High</button>
                <button className="px-2 py-0.5 rounded-full text-xs font-medium" style={{ color: "#6B7280" }}>Medium</button>
                <button className="px-2 py-0.5 rounded-full text-xs font-medium" style={{ color: "#6B7280" }}>Low</button>
              </div>
            </div>

            <div className="rounded-lg px-3 py-2 flex items-center gap-2 mb-2" style={{ backgroundColor: "#1C1917", color: "#F5F0E8" }}>
              <span className="text-sm">📋</span>
              <span className="text-sm font-medium">Step: Spiritual</span>
            </div>

            <div className="grid grid-cols-5 gap-1.5 mb-2">
              {["🙏", "🌙", "📅", "📆", "✅"].map((icon) => (
                <button
                  key={icon}
                  className="flex items-center justify-center py-1.5 rounded-lg text-base"
                  style={{ border: "1px solid #E5E0D5", backgroundColor: "#F5F0E8" }}
                >
                  {icon}
                </button>
              ))}
            </div>

            {/* Today's Menu Card */}
            <div className="rounded-lg overflow-hidden mb-2" style={{ border: "1px solid #E5E0D5" }}>
              <div className="flex items-center justify-between px-2.5 py-1.5" style={{ backgroundColor: "#F5F0E8", borderBottom: "1px solid #E5E0D5" }}>
                <span className="text-xs font-bold uppercase tracking-widest" style={{ color: "#8b3a1a", letterSpacing: "0.08em" }}>🍽️ Today's Menu</span>
                <span className="text-xs" style={{ color: "#9CA3AF" }}>edit →</span>
              </div>
              {[
                { icon: "☀️", label: "Breakfast", val: "Eggs, cereal, fruit" },
                { icon: "🥗", label: "Lunch", val: "Out (Bible Study)" },
                { icon: "🍽️", label: "Dinner", val: "Leftovers: beef stew" },
                { icon: "🍮", label: "Dessert", val: "Canned peaches + whipped cream" },
              ].map(({ icon, label, val }) => (
                <div key={label} className="flex items-start gap-2 px-2.5 py-1" style={{ borderBottom: "1px solid #F5F0E8" }}>
                  <span className="text-xs shrink-0 font-semibold" style={{ color: "#9CA3AF", width: 68 }}>{icon} {label}</span>
                  <span className="text-xs flex-1 leading-snug" style={{ color: "#1C1917" }}>{val}</span>
                </div>
              ))}
              <div className="px-2.5 py-1.5" style={{ backgroundColor: "#FFF9F0", borderTop: "1px solid #E5E0D5" }}>
                <span className="text-xs" style={{ color: "#7C5C2E" }}>👦 Quick reheat — low capacity day</span>
              </div>
            </div>

            <div className="flex justify-end gap-3">
              {["Prayer", "5AM", "Virtue"].map((label) => (
                <button key={label} className="text-xs font-semibold" style={{ color: "#7C5C2E" }}>{label}</button>
              ))}
            </div>
          </div>
          <div className="px-3 py-2 flex gap-2 items-start" style={{ backgroundColor: "#FDFBF7" }}>
            <span className="text-xs" style={{ color: "#7C5C2E" }}>✝</span>
            <div>
              <p className="text-xs font-bold uppercase tracking-widest" style={{ color: "#7C5C2E" }}>Virtue · Simplicity</p>
              <p className="text-xs italic" style={{ color: "#1C1917" }}>What is one layer of complication I can remove today?</p>
            </div>
          </div>
        </div>

        {/* SECTION LABEL */}
        <p className="text-xs font-bold uppercase tracking-widest px-0.5" style={{ color: "#9CA3AF" }}>Children</p>

        {/* CHILDREN */}
        {[
          { name: "JP",      color: "#DC2626", pct: 30,  tasks: [{ subject: "Math",    title: "Lesson 71",  done: false }, { subject: "Reading", title: "Read for about 1 hour",  done: true  }] },
          { name: "Joseph",  color: "#16A34A", pct: 0,   tasks: [{ subject: "Math 87", title: "Quarterly Assessment 2 (replaces Test 11)", done: false }, { subject: "Religion 7", title: "Read Chapter 19 of Acts; Friendly Defender cards", done: false }, { subject: "Latin III", title: "Lesson 19 — Take Quiz 19", done: false }, { subject: "History & Geog 7", title: "Read pp. 51–59 Old World & America and pp. 64–71 The Greeks", done: false }, { subject: "Science 6", title: "Read Geology Ch. 16 § 16.3; answer workbook questions", done: false }, { subject: "Spelling & Vocab 8", title: "Write one paragraph using as many Lessons 7 & 8 Key Words as possible", done: false }, { subject: "Poetry 8", title: "Work on next 4½ lines up to '…justice'; review 5th grade poems", done: false }, { subject: "Reading 7", title: "Read for about 1 hour", done: false }] },
          { name: "Michael", color: "#EA580C", pct: 100, tasks: [{ subject: "Phonics", title: "Letter M worksheet",    done: true  }, { subject: "Art",     title: "Coloring page",         done: true  }] },
        ].map(({ name, color, pct, tasks }) => (
          <div
            key={name}
            className="rounded-xl p-3"
            style={{ backgroundColor: "#FFF", border: "1px solid #E5E0D5", borderLeft: `3px solid ${color}` }}
          >
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
                <span className="font-semibold text-sm">{name}</span>
              </div>
              <button className="flex items-center gap-0.5 text-xs font-medium" style={{ color: "#6B7280" }}>
                Full schedule <ChevronRight size={12} />
              </button>
            </div>
            <div className="w-full h-1 rounded-full mb-2" style={{ backgroundColor: "#F5F0E8" }}>
              <div className="h-full rounded-full" style={{ backgroundColor: color, width: `${pct}%` }} />
            </div>
            <div className="flex flex-col gap-2">
              {tasks.map(({ subject, title, done }) => (
                <div key={subject} className={`flex items-start gap-2 ${done ? "opacity-40" : ""}`}>
                  <div
                    className="w-3.5 h-3.5 rounded border mt-0.5 flex items-center justify-center shrink-0"
                    style={{ borderColor: done ? color : "#E5E0D5", backgroundColor: done ? color : "#F5F0E8" }}
                  >
                    {done && <Check size={9} className="text-white" />}
                  </div>
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wide" style={{ color }}>{subject}</p>
                    <p className={`text-xs ${done ? "line-through" : ""}`} style={{ color: "#1C1917" }}>{title}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}

        {/* FOOTER */}
        <p className="text-center text-xs uppercase tracking-widest py-2" style={{ color: "#9CA3AF" }}>
          McAdams Family · Sancta Familia
        </p>
      </main>
    </div>
  );
}
