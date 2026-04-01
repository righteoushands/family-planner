import React from "react";
import { Sparkles, ArrowRight, Check, BookOpen, Sun, Cloud, ChevronRight, Menu } from "lucide-react";

export function WarmEditorial() {
  return (
    <div className="min-h-screen font-sans" style={{ backgroundColor: "#F5F0E8", color: "#1C1917" }}>
      {/* SECTION 1: Navigation */}
      <nav style={{ backgroundColor: "#1C1917", color: "#F5F0E8" }} className="h-[52px] w-full flex items-center justify-between px-4 sm:px-6 md:px-8 border-b border-black/10 z-50 sticky top-0">
        <div className="flex items-center gap-2">
          <span className="text-sm opacity-70">✝</span>
          <span className="font-serif text-lg tracking-wide" style={{ fontFamily: "Playfair Display, serif" }}>Sancta Familia</span>
        </div>
        
        <div className="hidden md:flex items-center gap-6 text-sm font-medium">
          <button className="opacity-100 border-b border-[#F5F0E8] pb-1">Today</button>
          <button className="opacity-60 hover:opacity-100 transition-opacity pb-1">Week</button>
          <button className="opacity-60 hover:opacity-100 transition-opacity pb-1">JP</button>
          <button className="opacity-60 hover:opacity-100 transition-opacity pb-1">Joseph</button>
          <button className="opacity-60 hover:opacity-100 transition-opacity pb-1">Michael</button>
          <button className="opacity-60 hover:opacity-100 transition-opacity pb-1">James</button>
          <button className="opacity-60 hover:opacity-100 transition-opacity pb-1">Prayer</button>
          <button className="opacity-60 hover:opacity-100 transition-opacity pb-1">Settings</button>
        </div>

        <div className="flex items-center gap-4">
          <button 
            style={{ backgroundColor: "#B8904A", color: "#1C1917" }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold shadow-sm hover:opacity-90 transition-opacity"
          >
            <Sparkles size={14} className="fill-current" />
            <span>Ask Lucy</span>
          </button>
          <button className="md:hidden opacity-80 hover:opacity-100">
            <Menu size={20} />
          </button>
        </div>
      </nav>

      {/* SECTION 2: Hero / Lucy Banner */}
      <section 
        className="w-full relative px-4 sm:px-6 md:px-8 py-10 md:py-16 overflow-hidden flex flex-col md:flex-row items-center justify-center gap-10 md:gap-20"
        style={{ 
          background: "linear-gradient(to bottom right, #F5F0E8, #EDE8DC)",
          minHeight: "180px",
          borderBottom: "1px solid #E5E0D5"
        }}
      >
        {/* Left side */}
        <div className="flex-1 flex justify-end">
          <div className="max-w-md w-full">
            <h1 
              className="text-4xl md:text-5xl lg:text-[56px] leading-tight text-[#1C1917] mb-2"
              style={{ fontFamily: "Playfair Display, serif" }}
            >
              Good afternoon.
            </h1>
            <p className="text-lg md:text-xl text-[#6B7280] font-medium tracking-wide">
              Wednesday · April 1
            </p>
          </div>
        </div>

        {/* Right side - Lucy */}
        <div className="flex-1 flex justify-start">
          <div className="flex flex-col items-start max-w-md w-full gap-4">
            <div className="flex items-center gap-3">
              <div 
                className="w-12 h-12 rounded-full flex items-center justify-center shadow-md relative"
                style={{ backgroundColor: "#7C5C2E", border: "2px solid #B8904A" }}
              >
                <span className="text-[#F5F0E8] text-xl" style={{ fontFamily: "Playfair Display, serif" }}>L</span>
                <div className="absolute -bottom-1 -right-1 w-4 h-4 rounded-full bg-green-500 border-2 border-[#EDE8DC]" />
              </div>
              <div className="flex flex-col">
                <span className="text-xs font-bold tracking-widest uppercase text-[#7C5C2E]">Lucy</span>
                <span className="text-xs text-[#6B7280]">AI Family Companion</span>
              </div>
            </div>

            <div 
              className="p-4 rounded-xl shadow-sm relative overflow-hidden"
              style={{ backgroundColor: "#FFFFFF", border: "1px solid #E5E0D5", width: "100%" }}
            >
              <div className="absolute top-0 left-0 w-1 h-full" style={{ backgroundColor: "#7C5C2E" }} />
              <p className="text-sm text-[#1C1917] leading-relaxed mb-4 pl-2">
                Ready to plan today? James naps at 11am — good window for focused school.
              </p>
              <div className="flex justify-end">
                <button 
                  className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors group"
                  style={{ color: "#B8904A", backgroundColor: "rgba(184, 144, 74, 0.1)" }}
                >
                  Plan my day
                  <ArrowRight size={14} className="group-hover:translate-x-0.5 transition-transform" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* SECTION 3: Status bar */}
      <div className="w-full bg-white border-b sticky top-[52px] z-40" style={{ borderColor: "#E5E0D5" }}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 md:px-8 py-2.5 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs font-medium text-[#1C1917]">
          <div className="flex items-center gap-1.5">
            <BookOpen size={14} className="text-[#7C5C2E]" />
            <span>Holy Week</span>
          </div>
          <div className="w-[1px] h-3 bg-[#E5E0D5]" />
          <div className="flex items-center gap-1.5">
            <span className="text-[#7C5C2E]">✝</span>
            <span>Feria — Mass Readings</span>
            <ArrowRight size={12} className="text-[#6B7280] ml-0.5" />
          </div>
          <div className="w-[1px] h-3 bg-[#E5E0D5]" />
          <div className="flex items-center gap-1.5">
            <Cloud size={14} className="text-[#6B7280]" />
            <Sun size={14} className="text-[#B8904A] absolute ml-1.5 mt-1 opacity-80" />
            <span className="ml-2">68° Partly Cloudy</span>
          </div>
          <div className="w-[1px] h-3 bg-[#E5E0D5]" />
          <button className="flex items-center gap-1 text-[#7C5C2E] hover:opacity-80 transition-opacity">
            Prayer
            <ArrowRight size={12} />
          </button>
        </div>
      </div>

      {/* SECTION 4: Main Content (Family Cards) */}
      <main className="max-w-6xl mx-auto px-4 sm:px-6 md:px-8 py-10 md:py-12">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          
          {/* Left Column: Mom's Card */}
          <div className="lg:col-span-7">
            <div 
              className="rounded-2xl shadow-sm overflow-hidden"
              style={{ backgroundColor: "#FFFFFF", border: "1px solid #E5E0D5" }}
            >
              {/* Header Row */}
              <div className="p-6 border-b" style={{ borderColor: "#E5E0D5" }}>
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full flex items-center justify-center text-white" style={{ backgroundColor: "#7C5C2E" }}>
                      <span className="text-lg" style={{ fontFamily: "Playfair Display, serif" }}>M</span>
                    </div>
                    <h2 className="text-[22px] text-[#1C1917]" style={{ fontFamily: "Playfair Display, serif" }}>Mom</h2>
                  </div>
                  <div className="flex items-center gap-2 bg-[#F5F0E8] p-1 rounded-full border border-[#E5E0D5]">
                    <button className="px-3 py-1 rounded-full text-xs font-semibold text-[#6B7280] hover:text-[#1C1917]">High</button>
                    <button className="px-3 py-1 rounded-full text-xs font-semibold bg-white shadow-sm text-[#1C1917]">Medium</button>
                    <button className="px-3 py-1 rounded-full text-xs font-semibold text-[#6B7280] hover:text-[#1C1917]">Low</button>
                  </div>
                </div>

                {/* Current Activity Banner */}
                <div className="rounded-xl p-4 flex items-center gap-3 text-white mb-6 shadow-inner" style={{ backgroundColor: "#1C1917" }}>
                  <span className="text-xl">📋</span>
                  <span className="font-medium tracking-wide">Free Time</span>
                  <span className="ml-auto text-xs opacity-70 border border-white/20 px-2 py-1 rounded-md">Until 3:00 PM</span>
                </div>

                {/* Quick Actions */}
                <div className="grid grid-cols-3 gap-3">
                  <button className="flex flex-col items-center justify-center gap-2 p-4 rounded-xl border border-[#E5E0D5] bg-[#F5F0E8] hover:bg-[#EDE8DC] transition-colors text-sm font-medium text-[#1C1917]">
                    <span className="text-xl opacity-80">📅</span>
                    Plan my day
                  </button>
                  <button className="flex flex-col items-center justify-center gap-2 p-4 rounded-xl border border-[#E5E0D5] bg-[#F5F0E8] hover:bg-[#EDE8DC] transition-colors text-sm font-medium text-[#1C1917]">
                    <span className="text-xl opacity-80">📚</span>
                    School plan
                  </button>
                  <button className="flex flex-col items-center justify-center gap-2 p-4 rounded-xl border border-[#E5E0D5] bg-[#F5F0E8] hover:bg-[#EDE8DC] transition-colors text-sm font-medium text-[#1C1917]">
                    <span className="text-xl opacity-80">🌙</span>
                    Evening examen
                  </button>
                </div>
              </div>

              {/* Virtue Prompt */}
              <div className="p-5 flex gap-3 items-start bg-[#FDFBF7]">
                <span className="text-[#7C5C2E] mt-0.5">✝</span>
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-widest text-[#7C5C2E] mb-1">Simplicity</h4>
                  <p className="text-sm text-[#1C1917] italic">What is one layer of complication I can remove today...</p>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: Children Cards */}
          <div className="lg:col-span-5 flex flex-col gap-4">
            {/* JP Card */}
            <div className="rounded-xl p-5 shadow-sm relative overflow-hidden flex flex-col gap-4" style={{ backgroundColor: "#FFFFFF", border: "1px solid #E5E0D5" }}>
              <div className="absolute left-0 top-0 bottom-0 w-[3px]" style={{ backgroundColor: "#DC2626" }} />
              
              <div className="flex items-center justify-between pl-1">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: "#DC2626" }} />
                  <span className="font-semibold text-[#1C1917] text-lg">JP</span>
                </div>
                <button className="text-xs text-[#6B7280] flex items-center gap-1 hover:text-[#1C1917] transition-colors">
                  Full schedule <ArrowRight size={12} />
                </button>
              </div>

              <div className="w-full bg-[#F5F0E8] h-1.5 rounded-full overflow-hidden pl-1">
                <div className="h-full rounded-full" style={{ backgroundColor: "#DC2626", width: "30%" }} />
              </div>

              <div className="flex flex-col gap-3 pl-1">
                <div className="flex items-start gap-3">
                  <button className="w-5 h-5 rounded border mt-0.5 flex items-center justify-center transition-colors" style={{ borderColor: "#E5E0D5", backgroundColor: "#F5F0E8" }}>
                  </button>
                  <div className="flex flex-col">
                    <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: "#DC2626" }}>Math</span>
                    <span className="text-sm text-[#1C1917]">Lesson 42: Fractions</span>
                  </div>
                </div>
                <div className="flex items-start gap-3 opacity-50">
                  <button className="w-5 h-5 rounded border mt-0.5 flex items-center justify-center transition-colors" style={{ borderColor: "#DC2626", backgroundColor: "#DC2626" }}>
                    <Check size={12} className="text-white" />
                  </button>
                  <div className="flex flex-col line-through">
                    <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: "#DC2626" }}>Reading</span>
                    <span className="text-sm text-[#1C1917]">Read aloud 20 mins</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Joseph Card */}
            <div className="rounded-xl p-5 shadow-sm relative overflow-hidden flex flex-col gap-4" style={{ backgroundColor: "#FFFFFF", border: "1px solid #E5E0D5" }}>
              <div className="absolute left-0 top-0 bottom-0 w-[3px]" style={{ backgroundColor: "#16A34A" }} />
              
              <div className="flex items-center justify-between pl-1">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: "#16A34A" }} />
                  <span className="font-semibold text-[#1C1917] text-lg">Joseph</span>
                </div>
                <button className="text-xs text-[#6B7280] flex items-center gap-1 hover:text-[#1C1917] transition-colors">
                  Full schedule <ArrowRight size={12} />
                </button>
              </div>

              <div className="w-full bg-[#F5F0E8] h-1.5 rounded-full overflow-hidden pl-1">
                <div className="h-full rounded-full" style={{ backgroundColor: "#16A34A", width: "0%" }} />
              </div>

              <div className="flex flex-col gap-3 pl-1">
                <div className="flex items-start gap-3">
                  <button className="w-5 h-5 rounded border mt-0.5 flex items-center justify-center transition-colors" style={{ borderColor: "#E5E0D5", backgroundColor: "#F5F0E8" }}>
                  </button>
                  <div className="flex flex-col">
                    <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: "#16A34A" }}>History</span>
                    <span className="text-sm text-[#1C1917]">Chapter 5 Review</span>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <button className="w-5 h-5 rounded border mt-0.5 flex items-center justify-center transition-colors" style={{ borderColor: "#E5E0D5", backgroundColor: "#F5F0E8" }}>
                  </button>
                  <div className="flex flex-col">
                    <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: "#16A34A" }}>Science</span>
                    <span className="text-sm text-[#1C1917]">Nature Walk</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Michael Card */}
            <div className="rounded-xl p-5 shadow-sm relative overflow-hidden flex flex-col gap-4" style={{ backgroundColor: "#FFFFFF", border: "1px solid #E5E0D5" }}>
              <div className="absolute left-0 top-0 bottom-0 w-[3px]" style={{ backgroundColor: "#EA580C" }} />
              
              <div className="flex items-center justify-between pl-1">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: "#EA580C" }} />
                  <span className="font-semibold text-[#1C1917] text-lg">Michael</span>
                </div>
                <button className="text-xs text-[#6B7280] flex items-center gap-1 hover:text-[#1C1917] transition-colors">
                  Full schedule <ArrowRight size={12} />
                </button>
              </div>

              <div className="w-full bg-[#F5F0E8] h-1.5 rounded-full overflow-hidden pl-1">
                <div className="h-full rounded-full" style={{ backgroundColor: "#EA580C", width: "100%" }} />
              </div>

              <div className="flex flex-col gap-3 pl-1">
                <div className="flex items-start gap-3 opacity-50">
                  <button className="w-5 h-5 rounded border mt-0.5 flex items-center justify-center transition-colors" style={{ borderColor: "#EA580C", backgroundColor: "#EA580C" }}>
                    <Check size={12} className="text-white" />
                  </button>
                  <div className="flex flex-col line-through">
                    <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: "#EA580C" }}>Phonics</span>
                    <span className="text-sm text-[#1C1917]">Letter M worksheet</span>
                  </div>
                </div>
                <div className="flex items-start gap-3 opacity-50">
                  <button className="w-5 h-5 rounded border mt-0.5 flex items-center justify-center transition-colors" style={{ borderColor: "#EA580C", backgroundColor: "#EA580C" }}>
                    <Check size={12} className="text-white" />
                  </button>
                  <div className="flex flex-col line-through">
                    <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: "#EA580C" }}>Art</span>
                    <span className="text-sm text-[#1C1917]">Coloring page</span>
                  </div>
                </div>
              </div>
            </div>

          </div>
        </div>
      </main>

      {/* SECTION 5: Footer strip */}
      <footer className="w-full py-8 mt-auto flex justify-center border-t" style={{ borderColor: "#E5E0D5" }}>
        <p className="text-[11px] font-medium tracking-wide uppercase text-[#6B7280] opacity-80">
          McAdams Family · Sancta Familia
        </p>
      </footer>
    </div>
  );
}
