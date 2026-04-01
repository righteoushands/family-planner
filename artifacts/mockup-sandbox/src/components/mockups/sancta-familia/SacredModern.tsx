import React from 'react';

export function SacredModern() {
  return (
    <div 
      className="min-h-screen text-[#F5F0E8] font-['Inter',sans-serif] flex flex-col selection:bg-[#C4943A] selection:text-white"
      style={{ backgroundColor: '#0F0E0C' }}
    >
      <style dangerouslySetInnerHTML={{__html: `
        @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500;1,600&family=Inter:wght@300;400;500;600&display=swap');
      `}} />

      {/* Section 1: Navigation */}
      <nav 
        className="flex items-center justify-between px-6 py-4 sticky top-0 z-50 backdrop-blur-md bg-[#0F0E0C]/90"
        style={{ borderBottom: '1px solid #333' }}
      >
        <div className="flex items-center gap-2">
          <span className="text-[#C4943A] text-lg">✝</span>
          <span className="font-['Cormorant_Garamond'] text-xl font-medium tracking-wide text-[#C4943A]">
            Sancta Familia
          </span>
        </div>

        <div className="hidden md:flex items-center gap-6 text-sm font-medium text-[#9CA3AF]">
          <button className="text-[#C4943A] transition-colors">Today</button>
          <button className="hover:text-[#C4943A] transition-colors">Week</button>
          <button className="hover:text-[#F87171] transition-colors">JP</button>
          <button className="hover:text-[#4ADE80] transition-colors">Joseph</button>
          <button className="hover:text-[#FB923C] transition-colors">Michael</button>
          <button className="hover:text-[#60A5FA] transition-colors">James</button>
        </div>

        <div>
          <button 
            className="flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-medium transition-all hover:bg-[#C4943A]/10"
            style={{ 
              color: '#C4943A',
              border: '1px solid rgba(196,148,58,0.3)',
              boxShadow: '0 0 10px rgba(196,148,58,0.1)'
            }}
          >
            <span className="text-xs">✨</span> Lucy
          </button>
        </div>
      </nav>

      <main className="flex-1 flex flex-col pb-20">
        
        {/* Section 2: Lucy Hero */}
        <section 
          className="w-full py-16 px-6 relative overflow-hidden flex justify-center"
          style={{ 
            backgroundColor: '#1A1916',
            background: 'radial-gradient(circle at top center, rgba(196,148,58,0.08) 0%, #1A1916 60%)'
          }}
        >
          <div className="max-w-[1280px] w-full flex flex-col md:flex-row items-center md:items-start gap-10 md:gap-12 relative z-10">
            
            {/* Lucy Avatar */}
            <div className="shrink-0 relative mt-2">
              <div 
                className="w-24 h-24 rounded-full flex items-center justify-center shadow-2xl"
                style={{
                  background: 'radial-gradient(circle at top left, #C4943A, #7C5C2E)',
                  boxShadow: '0 0 30px rgba(196,148,58,0.3), inset 0 2px 4px rgba(255,255,255,0.3)'
                }}
              >
                <span className="font-['Cormorant_Garamond'] italic text-5xl text-white drop-shadow-md pr-1">
                  L
                </span>
              </div>
              <div className="absolute inset-0 rounded-full border border-white/20"></div>
            </div>

            {/* Greeting & Message */}
            <div className="flex-1 flex flex-col items-center md:items-start text-center md:text-left">
              <div className="flex flex-col-reverse md:flex-col gap-1 md:gap-2 mb-6">
                <h1 className="font-['Cormorant_Garamond'] text-4xl md:text-[42px] font-medium leading-tight text-[#F5F0E8] tracking-tight">
                  Good afternoon.
                </h1>
                <div className="text-sm font-medium text-[#6B7280] tracking-wider uppercase flex items-center gap-3 justify-center md:justify-start">
                  Wednesday <span className="text-[#333]">&bull;</span> April 1, 2026
                </div>
              </div>

              <div className="font-['Cormorant_Garamond'] italic text-lg md:text-xl text-[#C4943A]/90 mb-8 max-w-2xl">
                "Not my will, but yours, be done." <span className="text-sm not-italic opacity-70 ml-2 font-['Inter']">— Lk 22:42</span>
              </div>

              {/* Message Card */}
              <div 
                className="max-w-3xl w-full rounded-2xl p-6 flex flex-col sm:flex-row items-start sm:items-center gap-6 justify-between border shadow-lg"
                style={{ 
                  backgroundColor: '#252220',
                  borderColor: 'rgba(255,255,255,0.06)'
                }}
              >
                <p className="text-[#F5F0E8] text-[15px] leading-relaxed">
                  Ready to plan today? James naps at 11am — use that window for focused school with the older boys.
                </p>
                <button 
                  className="shrink-0 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all hover:brightness-110 active:scale-95 text-[#0F0E0C]"
                  style={{ backgroundColor: '#C4943A' }}
                >
                  Plan my day &rarr;
                </button>
              </div>
            </div>
          </div>
        </section>

        {/* Section 3: Status/Info strip */}
        <section 
          className="w-full border-y border-[#333] px-6 py-4 flex justify-center"
          style={{ 
            backgroundColor: '#1A1916',
            borderTopColor: 'rgba(196,148,58,0.3)',
            borderBottomColor: 'rgba(255,255,255,0.05)'
          }}
        >
          <div className="max-w-[1280px] w-full flex flex-wrap items-center gap-3 md:gap-4 text-[13px] font-medium text-[#9CA3AF]">
            
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-[#C4943A]/10 text-[#C4943A] border border-[#C4943A]/20">
              <span>📖</span> Holy Week
            </div>
            
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-[#252220] border border-white/5">
              <span className="text-[#C4943A]">✝</span> Feria
            </div>
            
            <button className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-[#252220] border border-white/5 hover:bg-[#333] transition-colors group">
              <span>📖</span> Mass Readings <span className="opacity-50 group-hover:opacity-100 transition-opacity">&nearr;</span>
            </button>
            
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-[#252220] border border-white/5">
              <span>⛅</span> 68&deg;
            </div>

            <div className="flex-1"></div>

            <button className="flex items-center gap-2 px-4 py-1.5 rounded-md bg-[#252220] border border-white/5 hover:text-[#F5F0E8] transition-colors">
              Prayer &rarr;
            </button>

          </div>
        </section>

        {/* Section 4: Family Grid */}
        <section className="w-full px-6 py-12 flex justify-center flex-1">
          <div className="max-w-[1280px] w-full grid grid-cols-1 lg:grid-cols-[1fr_1.2fr] gap-8">
            
            {/* Left: Mom's Card */}
            <div className="flex flex-col gap-6">
              <div 
                className="rounded-2xl p-8 flex flex-col h-full relative overflow-hidden group"
                style={{ 
                  backgroundColor: '#252220',
                  borderLeft: '4px solid #C4943A',
                  boxShadow: '0 4px 20px rgba(0,0,0,0.2)'
                }}
              >
                <div className="absolute top-0 right-0 w-32 h-32 bg-[#C4943A]/5 rounded-full blur-3xl -mr-10 -mt-10 pointer-events-none"></div>
                
                <div className="flex items-center justify-between mb-8 relative z-10">
                  <div className="flex items-center gap-4">
                    <h2 className="font-['Cormorant_Garamond'] text-4xl font-medium text-[#F5F0E8]">
                      Mom
                    </h2>
                    <div className="flex gap-1.5 opacity-60 mt-2">
                      <div className="w-2 h-2 rounded-full bg-[#C4943A]"></div>
                      <div className="w-2 h-2 rounded-full bg-[#C4943A]"></div>
                      <div className="w-2 h-2 rounded-full bg-[#C4943A]"></div>
                      <div className="w-2 h-2 rounded-full bg-[#444]"></div>
                    </div>
                  </div>
                  
                  <div className="px-3 py-1 rounded-full text-xs font-medium uppercase tracking-wider bg-[#0F0E0C] text-[#9CA3AF] border border-[#333]">
                    Free Time
                  </div>
                </div>

                <div className="flex flex-col gap-3 mb-10 relative z-10">
                  <button className="flex items-center justify-between w-full p-4 rounded-xl bg-[#0F0E0C]/50 hover:bg-[#0F0E0C] border border-transparent hover:border-[#333] transition-all text-left group/btn">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-[#252220] flex items-center justify-center text-[#9CA3AF] border border-[#333]">📝</div>
                      <div>
                        <div className="text-[15px] font-medium text-[#F5F0E8] mb-0.5">Review Math Tests</div>
                        <div className="text-xs text-[#6B7280]">JP & Joseph</div>
                      </div>
                    </div>
                    <div className="w-5 h-5 rounded border border-[#444] group-hover/btn:border-[#C4943A] transition-colors"></div>
                  </button>
                  
                  <button className="flex items-center justify-between w-full p-4 rounded-xl bg-[#0F0E0C]/50 hover:bg-[#0F0E0C] border border-transparent hover:border-[#333] transition-all text-left group/btn">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-[#252220] flex items-center justify-center text-[#9CA3AF] border border-[#333]">🛒</div>
                      <div>
                        <div className="text-[15px] font-medium text-[#F5F0E8] mb-0.5">Order Groceries</div>
                        <div className="text-xs text-[#6B7280]">For next week's meal plan</div>
                      </div>
                    </div>
                    <div className="w-5 h-5 rounded border border-[#444] group-hover/btn:border-[#C4943A] transition-colors"></div>
                  </button>

                  <button className="flex items-center justify-between w-full p-4 rounded-xl bg-[#0F0E0C]/50 hover:bg-[#0F0E0C] border border-transparent hover:border-[#333] transition-all text-left group/btn">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-[#252220] flex items-center justify-center text-[#9CA3AF] border border-[#333]">🧺</div>
                      <div>
                        <div className="text-[15px] font-medium text-[#F5F0E8] mb-0.5">Start Laundry</div>
                        <div className="text-xs text-[#6B7280]">Darks</div>
                      </div>
                    </div>
                    <div className="w-5 h-5 rounded border border-[#444] group-hover/btn:border-[#C4943A] transition-colors"></div>
                  </button>
                </div>

                <div className="mt-auto pt-6 border-t border-[#333] relative z-10">
                  <div className="font-['Cormorant_Garamond'] italic text-[#9CA3AF] text-lg leading-relaxed">
                    "Patience is the companion of wisdom."
                  </div>
                  <div className="text-xs text-[#6B7280] uppercase tracking-wider mt-2 font-medium">Virtue Focus</div>
                </div>
              </div>
            </div>

            {/* Right: Children */}
            <div className="flex flex-col gap-4">
              
              {/* JP */}
              <div 
                className="rounded-xl p-5 flex flex-col md:flex-row md:items-center gap-5 relative overflow-hidden"
                style={{ backgroundColor: '#252220', borderLeft: '4px solid #F87171' }}
              >
                <div className="flex-shrink-0 w-32">
                  <h3 className="font-['Cormorant_Garamond'] text-2xl font-medium text-[#F5F0E8] mb-2">JP</h3>
                  <div className="w-full h-1.5 bg-[#0F0E0C] rounded-full overflow-hidden">
                    <div className="h-full bg-[#F87171]" style={{ width: '60%' }}></div>
                  </div>
                  <div className="text-[11px] text-[#6B7280] mt-1.5 font-medium">60% COMPLETE</div>
                </div>

                <div className="flex-1 flex flex-col gap-2">
                  <div className="flex items-start gap-3 p-2 hover:bg-[#0F0E0C]/40 rounded-lg transition-colors">
                    <div className="mt-0.5 w-4 h-4 rounded border border-[#444] shrink-0"></div>
                    <div>
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-[10px] uppercase tracking-wider font-bold text-[#F87171] bg-[#F87171]/10 px-1.5 py-0.5 rounded">Math</span>
                        <span className="text-sm text-[#F5F0E8]">Lesson 42: Fractions</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-start gap-3 p-2 hover:bg-[#0F0E0C]/40 rounded-lg transition-colors">
                    <div className="mt-0.5 w-4 h-4 rounded border border-[#444] shrink-0"></div>
                    <div>
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-[10px] uppercase tracking-wider font-bold text-[#F87171] bg-[#F87171]/10 px-1.5 py-0.5 rounded">History</span>
                        <span className="text-sm text-[#F5F0E8]">Read chapter 5 (Rome)</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Joseph */}
              <div 
                className="rounded-xl p-5 flex flex-col md:flex-row md:items-center gap-5 relative overflow-hidden"
                style={{ backgroundColor: '#252220', borderLeft: '4px solid #4ADE80' }}
              >
                <div className="flex-shrink-0 w-32">
                  <h3 className="font-['Cormorant_Garamond'] text-2xl font-medium text-[#F5F0E8] mb-2">Joseph</h3>
                  <div className="w-full h-1.5 bg-[#0F0E0C] rounded-full overflow-hidden">
                    <div className="h-full bg-[#4ADE80]" style={{ width: '80%' }}></div>
                  </div>
                  <div className="text-[11px] text-[#6B7280] mt-1.5 font-medium">80% COMPLETE</div>
                </div>

                <div className="flex-1 flex flex-col gap-2">
                  <div className="flex items-start gap-3 p-2 hover:bg-[#0F0E0C]/40 rounded-lg transition-colors">
                    <div className="mt-0.5 w-4 h-4 rounded border border-[#444] shrink-0"></div>
                    <div>
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-[10px] uppercase tracking-wider font-bold text-[#4ADE80] bg-[#4ADE80]/10 px-1.5 py-0.5 rounded">Science</span>
                        <span className="text-sm text-[#F5F0E8]">Botany experiment prep</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-start gap-3 p-2 hover:bg-[#0F0E0C]/40 rounded-lg transition-colors opacity-50">
                    <div className="mt-0.5 w-4 h-4 rounded border border-[#4ADE80] bg-[#4ADE80]/20 flex items-center justify-center shrink-0">
                      <svg width="10" height="8" viewBox="0 0 10 8" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M1 4L3.5 6.5L9 1" stroke="#4ADE80" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </div>
                    <div>
                      <div className="flex items-center gap-2 mb-0.5 line-through">
                        <span className="text-[10px] uppercase tracking-wider font-bold text-[#4ADE80] bg-[#4ADE80]/10 px-1.5 py-0.5 rounded">Latin</span>
                        <span className="text-sm text-[#F5F0E8]">Vocab review</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Michael */}
              <div 
                className="rounded-xl p-5 flex flex-col md:flex-row md:items-center gap-5 relative overflow-hidden"
                style={{ backgroundColor: '#252220', borderLeft: '4px solid #FB923C' }}
              >
                <div className="flex-shrink-0 w-32">
                  <h3 className="font-['Cormorant_Garamond'] text-2xl font-medium text-[#F5F0E8] mb-2">Michael</h3>
                  <div className="w-full h-1.5 bg-[#0F0E0C] rounded-full overflow-hidden">
                    <div className="h-full bg-[#FB923C]" style={{ width: '25%' }}></div>
                  </div>
                  <div className="text-[11px] text-[#6B7280] mt-1.5 font-medium">25% COMPLETE</div>
                </div>

                <div className="flex-1 flex flex-col gap-2">
                  <div className="flex items-start gap-3 p-2 hover:bg-[#0F0E0C]/40 rounded-lg transition-colors">
                    <div className="mt-0.5 w-4 h-4 rounded border border-[#444] shrink-0"></div>
                    <div>
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-[10px] uppercase tracking-wider font-bold text-[#FB923C] bg-[#FB923C]/10 px-1.5 py-0.5 rounded">Reading</span>
                        <span className="text-sm text-[#F5F0E8]">Read aloud with Mom (20m)</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-start gap-3 p-2 hover:bg-[#0F0E0C]/40 rounded-lg transition-colors">
                    <div className="mt-0.5 w-4 h-4 rounded border border-[#444] shrink-0"></div>
                    <div>
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-[10px] uppercase tracking-wider font-bold text-[#FB923C] bg-[#FB923C]/10 px-1.5 py-0.5 rounded">Handwriting</span>
                        <span className="text-sm text-[#F5F0E8]">Copywork sheet</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

            </div>
          </div>
        </section>

      </main>

      {/* Section 5: Bottom Bar */}
      <footer className="w-full py-8 flex flex-col items-center justify-center gap-2 mt-auto">
        <div className="text-[#C4943A] text-sm opacity-60">✝</div>
        <div className="font-['Cormorant_Garamond'] text-[#9CA3AF] text-sm tracking-widest uppercase">
          McAdams Family
        </div>
      </footer>

    </div>
  );
}