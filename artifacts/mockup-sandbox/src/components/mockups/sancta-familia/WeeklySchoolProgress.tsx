export default function WeeklySchoolProgress() {
  const days = ["M", "T", "W", "T", "F"];
  const dayLabels = ["Mon", "Tue", "Wed", "Thu", "Fri"];
  const dates = ["Apr 6", "Apr 7", "Apr 8", "Apr 9", "Apr 10"];
  const todayIdx = 1; // Tuesday

  // 'done' | 'missed' | 'skip' | 'future'
  type Status = "done" | "missed" | "skip" | "future";
  type SubjectRow = { subject: string; days: Status[] };

  const jpSubjects: SubjectRow[] = [
    { subject: "Algebra 1/2",         days: ["done","done","future","future","future"] },
    { subject: "Editing 7",           days: ["done","future","future","future","future"] },
    { subject: "Spelling & Vocab 8",  days: ["done","done","future","future","future"] },
    { subject: "Beginning Latin III", days: ["done","missed","future","future","future"] },
    { subject: "Science 7",           days: ["skip","done","future","future","future"] },
    { subject: "History & Geog 8",    days: ["done","future","future","future","future"] },
    { subject: "Poetry 8",            days: ["skip","done","future","future","future"] },
    { subject: "Reading 8",           days: ["done","done","future","future","future"] },
  ];

  const josephSubjects: SubjectRow[] = [
    { subject: "Math 87",             days: ["done","done","future","future","future"] },
    { subject: "English 8",           days: ["done","missed","future","future","future"] },
    { subject: "Spelling & Vocab 8",  days: ["done","done","future","future","future"] },
    { subject: "Beginning Latin III", days: ["done","future","future","future","future"] },
    { subject: "History & Geog 7",    days: ["done","future","future","future","future"] },
    { subject: "Reading 7",           days: ["done","done","future","future","future"] },
  ];

  function countDone(rows: SubjectRow[]) {
    let total = 0, done = 0;
    rows.forEach(r => r.days.forEach(d => {
      if (d === "done" || d === "missed") total++;
      if (d === "done") done++;
    }));
    return { done, total };
  }

  function Cell({ status }: { status: Status }) {
    if (status === "done") return (
      <div className="flex items-center justify-center w-7 h-7 rounded-full bg-emerald-100">
        <span className="text-emerald-700 text-[11px] font-bold">✓</span>
      </div>
    );
    if (status === "missed") return (
      <div className="flex items-center justify-center w-7 h-7 rounded-full bg-red-50">
        <span className="text-red-400 text-[11px] font-bold">✗</span>
      </div>
    );
    if (status === "skip") return (
      <div className="flex items-center justify-center w-7 h-7">
        <span className="text-gray-300 text-[11px]">—</span>
      </div>
    );
    return (
      <div className="flex items-center justify-center w-7 h-7">
        <span className="text-gray-200 text-[10px]">·</span>
      </div>
    );
  }

  function ChildBlock({
    child, color, bgLight, subjects
  }: {
    child: string; color: string; bgLight: string; subjects: SubjectRow[];
  }) {
    const { done, total } = countDone(subjects);
    const pct = total > 0 ? Math.round(done / total * 100) : 0;

    return (
      <div className="mb-4 rounded-xl overflow-hidden border border-gray-200 bg-white shadow-sm">
        {/* Header */}
        <div className={`px-4 py-3 flex items-center justify-between ${bgLight}`}>
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
            <span className="font-bold text-sm" style={{ color }}>
              {child}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-1.5 w-24 bg-white/60 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${pct}%`, background: color, opacity: 0.8 }}
              />
            </div>
            <span className="text-xs font-semibold" style={{ color }}>
              {done}/{total}
            </span>
          </div>
        </div>

        {/* Day header row */}
        <div className="flex items-center px-3 pt-2 pb-1 border-b border-gray-100">
          <div className="flex-1 text-[10px] text-gray-400 font-semibold tracking-wide uppercase">
            Subject
          </div>
          {days.map((d, i) => (
            <div
              key={i}
              className={`w-7 text-center text-[10px] font-bold tracking-wide ${
                i === todayIdx ? "text-amber-600" : "text-gray-400"
              }`}
            >
              {d}
            </div>
          ))}
        </div>

        {/* Subject rows */}
        <div className="divide-y divide-gray-50">
          {subjects.map((row, ri) => (
            <div key={ri} className="flex items-center px-3 py-1">
              <div className="flex-1 text-[12px] text-gray-700 truncate pr-2">
                {row.subject}
              </div>
              {row.days.map((s, di) => (
                <div key={di} className="w-7 flex justify-center">
                  <Cell status={s} />
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        fontFamily: "'Inter', system-ui, sans-serif",
        background: "#faf7f2",
        minHeight: "100vh",
        padding: "0",
      }}
    >
      {/* Page header */}
      <div
        style={{
          background: "#1C1917",
          padding: "14px 16px 12px",
          position: "sticky",
          top: 0,
          zIndex: 10,
        }}
      >
        <div style={{ fontSize: "0.62em", fontWeight: 800, letterSpacing: "0.1em", textTransform: "uppercase", color: "rgba(245,240,232,0.45)", marginBottom: 3 }}>
          Father Gregory · Headmaster
        </div>
        <div style={{ fontSize: "1.1em", fontWeight: 700, color: "#faf7f2" }}>
          Weekly School Progress
        </div>
        <div style={{ fontSize: "0.72em", color: "rgba(245,240,232,0.55)", marginTop: 2 }}>
          Apr 6 – Apr 10, 2026
        </div>
      </div>

      {/* Week nav + day date row */}
      <div style={{ background: "#fff", borderBottom: "1px solid #e5e0d8", padding: "8px 14px" }}>
        {/* Day column labels */}
        <div style={{ display: "flex", alignItems: "center" }}>
          <div style={{ flex: 1 }} />
          {dayLabels.map((d, i) => (
            <div
              key={i}
              style={{
                width: 28,
                textAlign: "center",
                fontSize: "0.65em",
                fontWeight: i === todayIdx ? 800 : 600,
                color: i === todayIdx ? "#92400e" : "#9ca3af",
                padding: "0 0 2px",
              }}
            >
              <div>{d}</div>
              <div style={{
                fontSize: "0.85em",
                fontWeight: 600,
                color: i === todayIdx ? "#b45309" : "#d1d5db",
                marginTop: 1,
              }}>
                {dates[i].split(" ")[1]}
              </div>
              {i === todayIdx && (
                <div style={{
                  width: 4, height: 4, borderRadius: "50%",
                  background: "#b45309", margin: "2px auto 0",
                }} />
              )}
            </div>
          ))}
        </div>
      </div>

      <div style={{ padding: "12px 12px 80px" }}>

        {/* Legend */}
        <div style={{
          display: "flex", gap: 10, alignItems: "center",
          marginBottom: 14, padding: "6px 10px",
          background: "white", borderRadius: 10, border: "1px solid #e5e0d8",
        }}>
          <span style={{ fontSize: "0.65em", fontWeight: 700, color: "#9ca3af", letterSpacing: "0.06em", textTransform: "uppercase" }}>Key:</span>
          <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ fontSize: "0.75em", color: "#059669", fontWeight: 700 }}>✓</span>
            <span style={{ fontSize: "0.68em", color: "#6b7280" }}>Done</span>
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ fontSize: "0.75em", color: "#f87171", fontWeight: 700 }}>✗</span>
            <span style={{ fontSize: "0.68em", color: "#6b7280" }}>Missed</span>
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ fontSize: "0.75em", color: "#d1d5db" }}>—</span>
            <span style={{ fontSize: "0.68em", color: "#6b7280" }}>No class</span>
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ fontSize: "0.75em", color: "#e5e7eb" }}>·</span>
            <span style={{ fontSize: "0.68em", color: "#6b7280" }}>Upcoming</span>
          </span>
        </div>

        {/* JP Block */}
        <div style={{ marginBottom: 14 }}>
          <div style={{
            fontSize: "0.62em", fontWeight: 800, letterSpacing: "0.1em",
            textTransform: "uppercase", color: "#9ca3af", marginBottom: 6
          }}>JP · Grade 8</div>
          <div style={{ background: "white", borderRadius: 12, border: "1px solid #e5e0d8", overflow: "hidden", boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
            {/* Header */}
            <div style={{ background: "#eef1f8", padding: "10px 14px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#1e3566" }} />
                <span style={{ fontSize: "0.85em", fontWeight: 800, color: "#1e3566" }}>JP</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <div style={{ height: 5, width: 80, background: "#c7d0e8", borderRadius: 3, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: "85%", background: "#1e3566", borderRadius: 3, opacity: 0.7 }} />
                </div>
                <span style={{ fontSize: "0.72em", fontWeight: 700, color: "#1e3566" }}>13/15 done</span>
              </div>
            </div>
            {/* Column labels */}
            <div style={{ display: "flex", alignItems: "center", padding: "6px 12px 4px", borderBottom: "1px solid #f3f4f6" }}>
              <div style={{ flex: 1, fontSize: "0.62em", fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", color: "#9ca3af" }}>Subject</div>
              {["M","T","W","T","F"].map((d,i) => (
                <div key={i} style={{ width: 28, textAlign: "center", fontSize: "0.65em", fontWeight: i===1?800:600, color: i===1?"#b45309":"#9ca3af" }}>{d}</div>
              ))}
            </div>
            {/* Rows */}
            {jpSubjects.map((row, ri) => (
              <div key={ri} style={{ display: "flex", alignItems: "center", padding: "5px 12px", borderBottom: ri < jpSubjects.length-1 ? "1px solid #fafafa" : "none" }}>
                <div style={{ flex: 1, fontSize: "0.78em", color: "#374151", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", paddingRight: 6 }}>{row.subject}</div>
                {row.days.map((s, di) => (
                  <div key={di} style={{ width: 28, display: "flex", justifyContent: "center" }}>
                    {s === "done"   && <div style={{ width: 22, height: 22, borderRadius: "50%", background: "#dcfce7", display: "flex", alignItems: "center", justifyContent: "center" }}><span style={{ fontSize: "0.7em", color: "#15803d", fontWeight: 800 }}>✓</span></div>}
                    {s === "missed" && <div style={{ width: 22, height: 22, borderRadius: "50%", background: "#fef2f2", display: "flex", alignItems: "center", justifyContent: "center" }}><span style={{ fontSize: "0.7em", color: "#ef4444", fontWeight: 700 }}>✗</span></div>}
                    {s === "skip"   && <span style={{ fontSize: "0.7em", color: "#d1d5db" }}>—</span>}
                    {s === "future" && <span style={{ fontSize: "0.65em", color: "#e5e7eb" }}>·</span>}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>

        {/* Joseph Block */}
        <div style={{ marginBottom: 14 }}>
          <div style={{
            fontSize: "0.62em", fontWeight: 800, letterSpacing: "0.1em",
            textTransform: "uppercase", color: "#9ca3af", marginBottom: 6
          }}>Joseph · Grade 7</div>
          <div style={{ background: "white", borderRadius: 12, border: "1px solid #e5e0d8", overflow: "hidden", boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
            <div style={{ background: "#edf5f0", padding: "10px 14px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#14532d" }} />
                <span style={{ fontSize: "0.85em", fontWeight: 800, color: "#14532d" }}>Joseph</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <div style={{ height: 5, width: 80, background: "#bbf7d0", borderRadius: 3, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: "70%", background: "#14532d", borderRadius: 3, opacity: 0.7 }} />
                </div>
                <span style={{ fontSize: "0.72em", fontWeight: 700, color: "#14532d" }}>9/12 done</span>
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", padding: "6px 12px 4px", borderBottom: "1px solid #f3f4f6" }}>
              <div style={{ flex: 1, fontSize: "0.62em", fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", color: "#9ca3af" }}>Subject</div>
              {["M","T","W","T","F"].map((d,i) => (
                <div key={i} style={{ width: 28, textAlign: "center", fontSize: "0.65em", fontWeight: i===1?800:600, color: i===1?"#b45309":"#9ca3af" }}>{d}</div>
              ))}
            </div>
            {josephSubjects.map((row, ri) => (
              <div key={ri} style={{ display: "flex", alignItems: "center", padding: "5px 12px", borderBottom: ri < josephSubjects.length-1 ? "1px solid #fafafa" : "none" }}>
                <div style={{ flex: 1, fontSize: "0.78em", color: "#374151", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", paddingRight: 6 }}>{row.subject}</div>
                {row.days.map((s, di) => (
                  <div key={di} style={{ width: 28, display: "flex", justifyContent: "center" }}>
                    {s === "done"   && <div style={{ width: 22, height: 22, borderRadius: "50%", background: "#dcfce7", display: "flex", alignItems: "center", justifyContent: "center" }}><span style={{ fontSize: "0.7em", color: "#15803d", fontWeight: 800 }}>✓</span></div>}
                    {s === "missed" && <div style={{ width: 22, height: 22, borderRadius: "50%", background: "#fef2f2", display: "flex", alignItems: "center", justifyContent: "center" }}><span style={{ fontSize: "0.7em", color: "#ef4444", fontWeight: 700 }}>✗</span></div>}
                    {s === "skip"   && <span style={{ fontSize: "0.7em", color: "#d1d5db" }}>—</span>}
                    {s === "future" && <span style={{ fontSize: "0.65em", color: "#e5e7eb" }}>·</span>}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>

        {/* Father Gregory insight card */}
        <div style={{
          background: "white", borderRadius: 12, border: "1px solid #e5e0d8",
          padding: "12px 14px", boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
          borderLeft: "3px solid #7c3aed"
        }}>
          <div style={{ fontSize: "0.62em", fontWeight: 800, letterSpacing: "0.08em", textTransform: "uppercase", color: "#7c3aed", marginBottom: 6 }}>
            Fr. Gregory · Week Notes
          </div>
          <div style={{ fontSize: "0.8em", color: "#374151", lineHeight: 1.55 }}>
            JP missed Latin on Tuesday — likely needs a double session Wednesday. Joseph's English missed mark; check if assignment was understood. Both boys are strong in Math this week.
          </div>
          <div style={{ marginTop: 8, display: "flex", justifyContent: "flex-end" }}>
            <button style={{
              fontSize: "0.72em", fontWeight: 700, color: "#7c3aed",
              background: "rgba(124,58,237,0.08)", border: "none", borderRadius: 8,
              padding: "5px 12px", cursor: "pointer"
            }}>
              Ask Father Gregory →
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
