import { useState, useEffect, useCallback } from "react";

const API = "https://taskbot-backend-srm4.onrender.com";
// Секрет организатора — в реальной ситуации не хранить в коде фронта,
// но для внутреннего инструмента студсовета это приемлемо.
const ADMIN_SECRET = import.meta.env.VITE_ADMIN_SECRET || "";

const css = `
  @import url('https://fonts.googleapis.com/css2?family=Unbounded:wght@400;600;800&family=Inter:wght@300;400;500&display=swap');
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #0a0a0f; --surface: #13131a; --surface2: #1c1c26;
    --accent: #6c63ff; --accent2: #ff6584; --text: #f0f0f8;
    --muted: #7a7a99; --border: #2a2a3a; --success: #4ade80;
    --warn: #facc15; --radius: 16px;
  }
  body { background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; min-height: 100vh; overflow-x: hidden; }
  .bg-grid { position: fixed; inset: 0; z-index: 0; background-image: linear-gradient(rgba(108,99,255,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(108,99,255,0.04) 1px, transparent 1px); background-size: 40px 40px; pointer-events: none; }
  .glow { position: fixed; width: 600px; height: 600px; border-radius: 50%; background: radial-gradient(circle, rgba(108,99,255,0.12) 0%, transparent 70%); top: -200px; left: -100px; pointer-events: none; z-index: 0; }
  .wrap { position: relative; z-index: 1; max-width: 900px; margin: 0 auto; padding: 36px 20px 80px; }
  .header { text-align: center; margin-bottom: 36px; }
  .header-tag { display: inline-block; font-family: 'Unbounded', sans-serif; font-size: 10px; letter-spacing: 3px; text-transform: uppercase; color: var(--accent); border: 1px solid rgba(108,99,255,0.3); padding: 6px 16px; border-radius: 100px; margin-bottom: 16px; }
  .header h1 { font-family: 'Unbounded', sans-serif; font-size: clamp(22px,5vw,40px); font-weight: 800; line-height: 1.15; margin-bottom: 8px; }
  .header h1 span { color: var(--accent); }
  .header p { color: var(--muted); font-size: 14px; }
  .tabs { display: flex; gap: 4px; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 4px; margin-bottom: 24px; flex-wrap: wrap; }
  .tab { flex: 1; min-width: 80px; padding: 10px 8px; text-align: center; border-radius: 9px; cursor: pointer; font-family: 'Unbounded', sans-serif; font-size: 10px; font-weight: 600; color: var(--muted); transition: all 0.2s; border: none; background: transparent; }
  .tab.active { background: var(--accent); color: #fff; }
  .tab:hover:not(.active) { color: var(--text); }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 24px; animation: fadeUp 0.3s ease both; margin-bottom: 14px; }
  @keyframes fadeUp { from { opacity:0;transform:translateY(12px); } to { opacity:1;transform:none; } }
  .card-title { font-family: 'Unbounded', sans-serif; font-size: 12px; font-weight: 600; color: var(--muted); letter-spacing: 1px; text-transform: uppercase; margin-bottom: 18px; }
  .field { margin-bottom: 16px; }
  .field label { display: block; font-size: 13px; color: var(--muted); margin-bottom: 6px; font-weight: 500; }
  .field input, .field select, .field textarea { width: 100%; padding: 12px 15px; background: var(--surface2); border: 1px solid var(--border); border-radius: 10px; color: var(--text); font-family: 'Inter', sans-serif; font-size: 14px; outline: none; transition: border-color 0.2s; }
  .field input:focus, .field select:focus, .field textarea:focus { border-color: var(--accent); }
  .field input::placeholder, .field textarea::placeholder { color: var(--muted); }
  .field select option { background: var(--surface2); }
  .field textarea { resize: vertical; min-height: 80px; }
  .btn { display: inline-flex; align-items: center; justify-content: center; gap: 8px; padding: 12px 22px; border-radius: 10px; border: none; cursor: pointer; font-family: 'Unbounded', sans-serif; font-size: 11px; font-weight: 600; transition: all 0.2s; letter-spacing: 0.5px; }
  .btn-primary { background: var(--accent); color: #fff; width: 100%; }
  .btn-primary:hover { background: #7c74ff; transform: translateY(-1px); }
  .btn-primary:disabled { opacity: 0.45; cursor: not-allowed; transform: none; }
  .btn-ghost { background: transparent; color: var(--muted); border: 1px solid var(--border); margin-bottom: 18px; font-size: 11px; padding: 9px 15px; }
  .btn-ghost:hover { color: var(--text); border-color: var(--muted); }
  .btn-sm { padding: 8px 14px; font-size: 10px; }
  .btn-danger { background: rgba(255,101,132,0.15); color: var(--accent2); border: 1px solid rgba(255,101,132,0.3); }
  .btn-danger:hover { background: rgba(255,101,132,0.25); }
  .btn-success { background: rgba(74,222,128,0.15); color: var(--success); border: 1px solid rgba(74,222,128,0.3); }
  .btn-success:hover { background: rgba(74,222,128,0.25); }
  .dept-grid { display: grid; grid-template-columns: repeat(auto-fill,minmax(140px,1fr)); gap: 10px; }
  .dept-card { padding: 18px; background: var(--surface2); border: 1px solid var(--border); border-radius: 12px; cursor: pointer; transition: all 0.2s; text-align: center; }
  .dept-card:hover { border-color: var(--accent); background: rgba(108,99,255,0.08); transform: translateY(-2px); }
  .dept-icon { font-size: 24px; margin-bottom: 7px; }
  .dept-name { font-family: 'Unbounded', sans-serif; font-size: 11px; font-weight: 600; }
  .task-list { display: flex; flex-direction: column; gap: 8px; }
  .task-item { padding: 15px 17px; background: var(--surface2); border: 1px solid var(--border); border-radius: 12px; cursor: pointer; transition: all 0.2s; display: flex; justify-content: space-between; align-items: center; }
  .task-item:hover { border-color: var(--accent); transform: translateX(3px); }
  .task-item.full { opacity: 0.4; cursor: not-allowed; }
  .task-item.full:hover { transform: none; border-color: var(--border); }
  .task-name { font-weight: 500; font-size: 15px; margin-bottom: 3px; }
  .task-sub { font-size: 12px; color: var(--muted); }
  .badge { font-family: 'Unbounded', sans-serif; font-size: 10px; padding: 4px 10px; border-radius: 100px; white-space: nowrap; }
  .badge-open { background: rgba(108,99,255,0.15); color: var(--accent); }
  .badge-full { background: rgba(255,101,132,0.15); color: var(--accent2); }
  .badge-intern { background: rgba(250,204,21,0.15); color: var(--warn); }
  .badge-member { background: rgba(74,222,128,0.15); color: var(--success); }
  .badge-admin { background: rgba(108,99,255,0.2); color: var(--accent); }
  .detail-title { font-family: 'Unbounded', sans-serif; font-size: 18px; font-weight: 700; margin-bottom: 8px; }
  .detail-desc { color: var(--muted); line-height: 1.7; margin-bottom: 20px; font-size: 14px; }
  .checkpoints { display: flex; flex-direction: column; gap: 6px; margin-bottom: 20px; }
  .cp-row { display: flex; align-items: center; gap: 10px; background: var(--surface2); border: 1px solid var(--border); border-radius: 10px; padding: 10px 14px; }
  .cp-row.deadline { border-color: rgba(255,101,132,0.3); }
  .cp-icon { font-size: 16px; flex-shrink: 0; }
  .cp-label { font-size: 12px; color: var(--muted); flex: 1; }
  .cp-date { font-family: 'Unbounded', sans-serif; font-size: 12px; font-weight: 600; }
  .cp-date.dl { color: var(--accent2); }
  .team-section { background: var(--surface2); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; margin-bottom: 18px; }
  .team-title { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; }
  .team-member { font-size: 13px; color: var(--text); padding: 3px 0; }
  .team-member span { color: var(--accent); }
  .slots-bar { margin-bottom: 18px; }
  .slots-label { font-size: 12px; color: var(--muted); margin-bottom: 6px; display: flex; justify-content: space-between; }
  .slots-track { height: 6px; background: var(--border); border-radius: 100px; overflow: hidden; }
  .slots-fill { height: 100%; background: var(--accent); border-radius: 100px; transition: width 0.4s; }
  .error-msg { background: rgba(255,101,132,0.1); border: 1px solid rgba(255,101,132,0.3); color: var(--accent2); padding: 11px 15px; border-radius: 10px; font-size: 13px; margin-bottom: 14px; }
  .info-msg { background: rgba(108,99,255,0.1); border: 1px solid rgba(108,99,255,0.3); color: var(--accent); padding: 11px 15px; border-radius: 10px; font-size: 13px; margin-bottom: 14px; }
  .success-wrap { text-align: center; padding: 16px 0; }
  .success-icon { font-size: 52px; margin-bottom: 14px; animation: pop 0.5s ease; }
  @keyframes pop { 0%{transform:scale(0)} 80%{transform:scale(1.15)} 100%{transform:scale(1)} }
  .success-title { font-family: 'Unbounded', sans-serif; font-size: 20px; font-weight: 800; margin-bottom: 8px; }
  .success-sub { color: var(--muted); font-size: 14px; line-height: 1.6; margin-bottom: 20px; }
  .success-sub span { color: var(--success); font-weight: 500; }
  .loader { text-align: center; color: var(--muted); padding: 36px; font-size: 13px; }
  .section-label { font-family: 'Unbounded', sans-serif; font-size: 11px; color: var(--muted); letter-spacing: 2px; text-transform: uppercase; margin: 20px 0 10px; }
  .closed-item { padding: 15px 17px; background: var(--surface2); border: 1px solid var(--border); border-radius: 12px; margin-bottom: 8px; opacity: 0.7; cursor: pointer; transition: all 0.2s; }
  .closed-item:hover { opacity: 1; border-color: var(--muted); }
  .stat-grid { display: grid; grid-template-columns: repeat(auto-fill,minmax(140px,1fr)); gap: 10px; margin-bottom: 20px; }
  .stat-box { background: var(--surface2); border: 1px solid var(--border); border-radius: 12px; padding: 16px; text-align: center; }
  .stat-val { font-family: 'Unbounded', sans-serif; font-size: 26px; font-weight: 800; color: var(--accent); margin-bottom: 5px; }
  .stat-label { font-size: 11px; color: var(--muted); }
  .lb-row { display: flex; align-items: center; gap: 14px; padding: 12px 16px; background: var(--surface2); border: 1px solid var(--border); border-radius: 12px; margin-bottom: 8px; }
  .lb-medal { font-size: 20px; width: 28px; text-align: center; flex-shrink: 0; }
  .lb-name { flex: 1; font-weight: 500; }
  .lb-pts { font-family: 'Unbounded', sans-serif; font-size: 12px; color: var(--accent); }
  .lb-tasks { font-size: 11px; color: var(--muted); }
  .admin-task-row { padding: 14px 16px; background: var(--surface2); border: 1px solid var(--border); border-radius: 12px; margin-bottom: 8px; }
  .admin-task-row-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; margin-bottom: 8px; }
  .admin-actions { display: flex; gap: 6px; flex-wrap: wrap; }
  .participant-row { display: flex; align-items: center; gap: 12px; padding: 10px 14px; background: var(--surface2); border: 1px solid var(--border); border-radius: 10px; margin-bottom: 6px; }
  .participant-name { flex: 1; font-size: 14px; }
  .cp-add-row { display: flex; gap: 8px; margin-bottom: 8px; }
  .cp-add-row input { flex: 1; padding: 10px 12px; background: var(--surface2); border: 1px solid var(--border); border-radius: 8px; color: var(--text); font-family: 'Inter', sans-serif; font-size: 14px; outline: none; }
  .cp-add-row input:focus { border-color: var(--accent); }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
  .chip { font-size: 12px; padding: 4px 10px; border-radius: 20px; background: var(--surface2); border: 1px solid var(--border); display: inline-flex; align-items: center; gap: 5px; }
  .chip-del { cursor: pointer; color: var(--accent2); }
  .role-sel { display: flex; gap: 6px; }
  .role-btn { flex: 1; padding: 8px; border-radius: 8px; border: 1px solid var(--border); background: var(--surface2); color: var(--muted); cursor: pointer; font-family: 'Unbounded', sans-serif; font-size: 10px; text-align: center; transition: all 0.2s; }
  .role-btn.active { border-color: var(--accent); background: rgba(108,99,255,0.15); color: var(--text); }
`;

const DEPT_ICONS = {
  "Маркетинг":"📣","IT":"💻","Дизайн":"🎨","PR":"📰","Финансы":"💰",
  "HR":"👥","Аналитика":"📊","Организация":"📋","Стажёры":"🎓",
};
const getIcon = d => DEPT_ICONS[d] || "🏢";

const ROLE_LABELS = { intern: "Стажёр", member: "Участник", admin: "Организатор" };
const ROLE_BADGE = { intern: "badge-intern", member: "badge-member", admin: "badge-admin" };

function formatCheckpoints(cps = []) {
  if (!cps?.length) return null;
  return (
    <div className="checkpoints">
      {cps.map((cp, i) => (
        <div key={i} className={`cp-row ${cp.type === "deadline" ? "deadline" : ""}`}>
          <span className="cp-icon">{cp.type === "deadline" ? "🏁" : "🔍"}</span>
          <span className="cp-label">{cp.label}</span>
          <span className={`cp-date ${cp.type === "deadline" ? "dl" : ""}`}>{cp.date}</span>
        </div>
      ))}
    </div>
  );
}

async function apiFetch(path, opts = {}) {
  const r = await fetch(`${API}${path}`, opts);
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    throw new Error(d.detail || `HTTP ${r.status}`);
  }
  return r.json();
}

function adminHeaders() {
  return { "Content-Type": "application/json", "X-Admin-Secret": ADMIN_SECRET };
}

// ── Шаг 1: Данные пользователя ──────────────────────────────
function StepUser({ savedUser, onNext }) {
  const [name, setName] = useState(savedUser?.name || "");
  const [tgId, setTgId] = useState(savedUser?.telegram_id ? String(savedUser.telegram_id) : "");
  const [tgUser, setTgUser] = useState(savedUser?.telegram_username || "");
  const [error, setError] = useState("");

  const handle = () => {
    if (!name.trim()) return setError("Введи имя и фамилию");
    if (!tgId.trim() || isNaN(tgId)) return setError("Введи корректный Telegram ID");
    if (!tgUser.trim()) return setError("Введи Telegram username");
    const username = tgUser.startsWith("@") ? tgUser.slice(1) : tgUser;
    onNext({ name: name.trim(), telegram_id: parseInt(tgId), telegram_username: username });
  };

  return (
    <div className="card">
      <div className="card-title">Твои данные</div>
      {savedUser && <div className="info-msg">Данные сохранены. Можно изменить если нужно.</div>}
      {error && <div className="error-msg">{error}</div>}
      <div className="field"><label>Имя и фамилия</label>
        <input value={name} onChange={e=>setName(e.target.value)} placeholder="Иван Иванов" /></div>
      <div className="field"><label>Telegram ID</label>
        <input value={tgId} onChange={e=>setTgId(e.target.value)} placeholder="Узнай у бота — /start" /></div>
      <div className="field"><label>Telegram username</label>
        <input value={tgUser} onChange={e=>setTgUser(e.target.value)} placeholder="@username" /></div>
      <button className="btn btn-primary" onClick={handle}>Продолжить →</button>
    </div>
  );
}

// ── Шаг 2: Отдел ─────────────────────────────────────────────
function StepDept({ user, onNext, onBack }) {
  const [depts, setDepts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [role, setRole] = useState("intern");

  useEffect(() => {
    apiFetch(`/departments?telegram_id=${user.telegram_id}`)
      .then(d => { setDepts(d.departments); setLoading(false); })
      .catch(() => setLoading(false));
    apiFetch(`/profile/${user.telegram_id}`)
      .then(d => setRole(d.role || "intern"))
      .catch(() => {});
  }, [user.telegram_id]);

  return (
    <div className="card">
      <button className="btn btn-ghost" onClick={onBack}>← Назад</button>
      <div className="card-title">Выбери отдел</div>
      {role === "intern" && (
        <div className="info-msg">🎓 Стажёрам доступны задачи отдела «Стажёры»</div>
      )}
      {loading ? <div className="loader">Загружаем...</div> : (
        <div className="dept-grid">
          {depts.map(d => (
            <div className="dept-card" key={d} onClick={() => onNext(d)}>
              <div className="dept-icon">{getIcon(d)}</div>
              <div className="dept-name">{d}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Шаг 3: Задачи ────────────────────────────────────────────
function StepTasks({ dept, user, onSelect, onBack }) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch(`/tasks/${encodeURIComponent(dept)}?telegram_id=${user.telegram_id}`)
      .then(d => { setTasks(d.tasks); setLoading(false); })
      .catch(() => setLoading(false));
  }, [dept, user.telegram_id]);

  return (
    <div className="card">
      <button className="btn btn-ghost" onClick={onBack}>← Назад</button>
      <div className="card-title">Задачи — {dept}</div>
      {loading ? <div className="loader">Загружаем...</div> : (
        tasks.length === 0
          ? <div className="loader">Нет задач в этом отделе</div>
          : <div className="task-list">
              {tasks.map(t => {
                const free = parseInt(t.max_participants) - parseInt(t.current_participants);
                const full = free <= 0;
                return (
                  <div key={t.task_id} className={`task-item ${full?"full":""}`}
                       onClick={() => !full && onSelect(t)}>
                    <div>
                      <div className="task-name">{t.title}</div>
                      <div className="task-sub">{full ? "Мест нет" : `Свободно: ${free} из ${t.max_participants}`}</div>
                    </div>
                    <div className={`badge ${full?"badge-full":"badge-open"}`}>
                      {full ? "Нет мест" : `${free} мест`}
                    </div>
                  </div>
                );
              })}
            </div>
      )}
    </div>
  );
}

// ── Шаг 4: Детали задачи ──────────────────────────────────────
function StepDetail({ task, user, onSuccess, onBack }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [participants, setParticipants] = useState([]);

  useEffect(() => {
    apiFetch(`/task/${task.task_id}/participants`).then(d => setParticipants(d.participants));
  }, [task.task_id]);

  const free = parseInt(task.max_participants) - parseInt(task.current_participants);
  const fillPct = (parseInt(task.current_participants) / parseInt(task.max_participants)) * 100;

  const take = async () => {
    setLoading(true); setError("");
    try {
      await apiFetch("/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: user.name, telegram_id: user.telegram_id,
          telegram_username: user.telegram_username, task_id: task.task_id,
        }),
      });
      onSuccess();
    } catch (e) { setError(e.message); }
    setLoading(false);
  };

  return (
    <div className="card">
      <button className="btn btn-ghost" onClick={onBack}>← Назад</button>
      <div className="detail-title">{task.title}</div>
      <div className="detail-desc">{task.description || "Описание не указано"}</div>

      <div className="slots-bar">
        <div className="slots-label"><span>Мест занято</span><span>{task.current_participants}/{task.max_participants}</span></div>
        <div className="slots-track"><div className="slots-fill" style={{width:`${fillPct}%`}} /></div>
      </div>

      {formatCheckpoints(task.checkpoints)}

      {participants.length > 0 && (
        <div className="team-section">
          <div className="team-title">👥 Уже в команде</div>
          {participants.map((p, i) => (
            <div className="team-member" key={i}>{p.name} <span>@{p.telegram_username}</span></div>
          ))}
        </div>
      )}

      {error && <div className="error-msg">{error}</div>}
      <button className="btn btn-primary" onClick={take} disabled={loading || free <= 0}>
        {loading ? "Записываем..." : free <= 0 ? "Мест нет" : "Взять задачу ✓"}
      </button>
    </div>
  );
}

function StepSuccess({ task, onMore }) {
  const deadline = task.checkpoints?.find(c => c.type === "deadline")?.date || "—";
  return (
    <div className="card">
      <div className="success-wrap">
        <div className="success-icon">🎉</div>
        <div className="success-title">Задача взята!</div>
        <div className="success-sub">
          Ты записан на <span>«{task.title}»</span><br/>
          Уведомления придут в Telegram.<br/>
          Дедлайн: <span>{deadline}</span>
        </div>
        <button className="btn btn-primary" style={{maxWidth:260,margin:"0 auto"}} onClick={onMore}>
          Взять ещё задачу →
        </button>
      </div>
    </div>
  );
}

// ── Вкладка: Задачи (многошаговый флоу) ──────────────────────
function TabTasks({ user, setUser }) {
  const [step, setStep] = useState(user ? 1 : 0);
  const [dept, setDept] = useState(null);
  const [task, setTask] = useState(null);

  return (
    <>
      {step === 0 && <StepUser savedUser={user} onNext={u => { setUser(u); setStep(1); }} />}
      {step === 1 && <StepDept user={user} onNext={d => { setDept(d); setStep(2); }} onBack={() => setStep(0)} />}
      {step === 2 && <StepTasks dept={dept} user={user} onSelect={t => { setTask(t); setStep(3); }} onBack={() => setStep(1)} />}
      {step === 3 && <StepDetail task={task} user={user} onSuccess={() => setStep(4)} onBack={() => setStep(2)} />}
      {step === 4 && <StepSuccess task={task} onMore={() => { setStep(1); setDept(null); setTask(null); }} />}
    </>
  );
}

// ── Вкладка: Архив ───────────────────────────────────────────
function TabArchive() {
  const [tasks, setTasks] = useState([]);
  const [selected, setSelected] = useState(null);
  const [participants, setParticipants] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch("/tasks-closed")
      .then(d => { setTasks(d.tasks); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const open = t => {
    setSelected(t);
    apiFetch(`/task/${t.task_id}/participants`).then(d => setParticipants(d.participants));
  };

  if (loading) return <div className="loader">Загружаем...</div>;
  if (tasks.length === 0) return (
    <div className="card"><div style={{color:"var(--muted)",textAlign:"center",padding:"24px"}}>Закрытых задач пока нет</div></div>
  );

  if (selected) return (
    <div className="card">
      <button className="btn btn-ghost" onClick={() => setSelected(null)}>← Назад</button>
      <div className="detail-title">{selected.title}</div>
      <div className="detail-desc">{selected.description}</div>
      {formatCheckpoints(selected.checkpoints)}
      <div className="team-section">
        <div className="team-title">👥 Команда</div>
        {participants.map((p,i) => (
          <div className="team-member" key={i}>{p.name} <span>@{p.telegram_username}</span></div>
        ))}
      </div>
    </div>
  );

  const byDept = {};
  tasks.forEach(t => { if (!byDept[t.department]) byDept[t.department] = []; byDept[t.department].push(t); });

  return (
    <>
      {Object.entries(byDept).map(([dept, dTasks]) => (
        <div key={dept}>
          <div className="section-label">{getIcon(dept)} {dept}</div>
          {dTasks.map(t => (
            <div className="closed-item" key={t.task_id} onClick={() => open(t)}>
              <div className="task-name">{t.title}</div>
              <div className="task-sub" style={{marginTop:4}}>
                Закрыта · {t.max_participants} участников
                {t.checkpoints?.find(c=>c.type==="deadline") &&
                  ` · Дедлайн: ${t.checkpoints.find(c=>c.type==="deadline").date}`}
              </div>
            </div>
          ))}
        </div>
      ))}
    </>
  );
}

// ── Вкладка: Профиль ─────────────────────────────────────────
function TabProfile({ user, setUser }) {
  const [stats, setStats] = useState(null);
  const [myTasks, setMyTasks] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(null);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (!user) { setLoading(false); return; }
    Promise.all([
      apiFetch(`/profile/${user.telegram_id}`),
      apiFetch(`/my-tasks/${user.telegram_id}`),
    ]).then(([s, t]) => { setStats(s); setMyTasks(t); setLoading(false); })
      .catch(() => setLoading(false));
  }, [user?.telegram_id]);

  const submitTask = async taskId => {
    setSubmitting(taskId); setMsg("");
    try {
      await apiFetch(`/task/${taskId}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ telegram_id: user.telegram_id }),
      });
      setMsg("📤 Заявка отправлена! Ждём одобрения организатора.");
    } catch (e) { setMsg(`❌ ${e.message}`); }
    setSubmitting(null);
  };

  if (!user) return (
    <div className="card">
      <div className="card-title">Профиль</div>
      <div style={{color:"var(--muted)",textAlign:"center",padding:"24px"}}>
        Перейди на вкладку «Задачи» и введи свои данные, чтобы увидеть профиль.
      </div>
    </div>
  );

  if (loading) return <div className="loader">Загружаем профиль...</div>;

  const role = stats?.role || "intern";
  const medals = ["🥇","🥈","🥉"];

  return (
    <>
      <div className="card">
        <div className="card-title">👤 Профиль</div>
        <div style={{display:"flex",alignItems:"center",gap:14,marginBottom:20}}>
          <div style={{fontSize:40}}>🧑‍💻</div>
          <div>
            <div style={{fontWeight:600,fontSize:16}}>{stats?.name || user.name}</div>
            <div style={{display:"flex",gap:8,marginTop:6}}>
              <span className={`badge ${ROLE_BADGE[role]}`}>{ROLE_LABELS[role]}</span>
              <span className="badge badge-open">⭐ {stats?.points || 0} баллов</span>
            </div>
          </div>
        </div>
        <div className="stat-grid">
          <div className="stat-box"><div className="stat-val">{stats?.active_tasks||0}</div><div className="stat-label">Активных</div></div>
          <div className="stat-box"><div className="stat-val">{stats?.completed_tasks||0}</div><div className="stat-label">Выполнено</div></div>
          <div className="stat-box"><div className="stat-val">{stats?.total_tasks||0}</div><div className="stat-label">Всего</div></div>
          <div className="stat-box"><div className="stat-val">{stats?.points||0}</div><div className="stat-label">Баллов</div></div>
        </div>
        {role === "intern" && (
          <div className="info-msg">🎓 Ты стажёр. Когда организатор повысит тебя, откроются задачи всех отделов.</div>
        )}
        <button className="btn btn-ghost btn-sm" onClick={() => setUser(null)}>
          Сменить аккаунт
        </button>
      </div>

      {myTasks?.active?.length > 0 && (
        <div className="card">
          <div className="card-title">📋 Активные задачи</div>
          {msg && <div className={msg.startsWith("❌") ? "error-msg" : "info-msg"}>{msg}</div>}
          {myTasks.active.map(t => (
            <div key={t.task_id} style={{marginBottom:14}}>
              <div style={{fontWeight:500,marginBottom:6}}>{t.title}</div>
              <div style={{color:"var(--muted)",fontSize:12,marginBottom:8}}>{t.department}</div>
              {formatCheckpoints(t.checkpoints)}
              <button
                className="btn btn-success btn-sm"
                onClick={() => submitTask(t.task_id)}
                disabled={submitting === t.task_id}
              >
                {submitting === t.task_id ? "Отправляем..." : "📤 Сдать задачу"}
              </button>
            </div>
          ))}
        </div>
      )}

      {myTasks?.history?.length > 0 && (
        <div className="card">
          <div className="card-title">📁 История задач</div>
          {myTasks.history.map(t => (
            <div key={t.task_id} className="closed-item" style={{cursor:"default",opacity:1}}>
              <div style={{fontWeight:500}}>✅ {t.title}</div>
              <div style={{color:"var(--muted)",fontSize:12,marginTop:3}}>{t.department}</div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

// ── Вкладка: Рейтинг ─────────────────────────────────────────
function TabLeaderboard() {
  const [lb, setLb] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch("/leaderboard")
      .then(d => { setLb(d.leaderboard); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="loader">Загружаем рейтинг...</div>;

  const medals = ["🥇","🥈","🥉"];

  return (
    <div className="card">
      <div className="card-title">🏆 Рейтинг участников</div>
      {lb.length === 0
        ? <div style={{color:"var(--muted)",textAlign:"center",padding:24}}>Рейтинг пока пуст</div>
        : lb.map((p, i) => (
          <div key={i} className="lb-row">
            <div className="lb-medal">{i < 3 ? medals[i] : `${i+1}.`}</div>
            <div className="lb-name">
              {p.name}
              {p.telegram_username && <div style={{fontSize:11,color:"var(--muted)"}}>@{p.telegram_username}</div>}
            </div>
            <div style={{textAlign:"right"}}>
              <div className="lb-pts">⭐ {p.points}</div>
              <div className="lb-tasks">{p.tasks} задач</div>
            </div>
          </div>
        ))
      }
    </div>
  );
}

// ── Вкладка: Управление (admin) ──────────────────────────────
function TabAdmin({ user }) {
  const [subTab, setSubTab] = useState("tasks");
  const [tasks, setTasks] = useState([]);
  const [participants, setParticipants] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState("");

  // Форма создания задачи
  const [form, setForm] = useState({
    title:"", department:"Стажёры", description:"", max_participants:"",
  });
  const [checks, setChecks] = useState([]);
  const [checkInput, setCheckInput] = useState({ date:"", label:"" });
  const [deadlineDate, setDeadlineDate] = useState("");

  const refresh = useCallback(() => {
    setLoading(true);
    Promise.all([
      apiFetch("/tasks-all", { headers: adminHeaders() }),
      apiFetch("/participants-all", { headers: adminHeaders() }),
    ]).then(([t, p]) => {
      setTasks(t.tasks);
      setParticipants(p.participants);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const addCheck = () => {
    if (!checkInput.date || !checkInput.label) return;
    setChecks([...checks, { ...checkInput, type: "check" }]);
    setCheckInput({ date:"", label:"" });
  };

  const createTask = async () => {
    setMsg("");
    if (!form.title || !form.max_participants || !deadlineDate) {
      setMsg("❌ Заполни название, макс. участников и дедлайн."); return;
    }
    const checkpoints = [
      ...checks,
      { label:"Дедлайн", date: deadlineDate, type:"deadline" },
    ];
    try {
      await apiFetch("/task", {
        method: "POST",
        headers: adminHeaders(),
        body: JSON.stringify({ ...form, max_participants: parseInt(form.max_participants), checkpoints }),
      });
      setMsg("✅ Задача создана!");
      setForm({ title:"", department:"Стажёры", description:"", max_participants:"" });
      setChecks([]); setDeadlineDate("");
      refresh();
    } catch (e) { setMsg(`❌ ${e.message}`); }
  };

  const closeTaskAdmin = async id => {
    if (!confirm("Закрыть задачу?")) return;
    try {
      await apiFetch(`/task/${id}/close`, { method:"POST", headers: adminHeaders() });
      setMsg("✅ Задача закрыта"); refresh();
    } catch (e) { setMsg(`❌ ${e.message}`); }
  };

  const deleteTaskAdmin = async id => {
    if (!confirm("Удалить задачу? Это нельзя отменить!")) return;
    try {
      await apiFetch(`/task/${id}`, { method:"DELETE", headers: adminHeaders() });
      setMsg("✅ Задача удалена"); refresh();
    } catch (e) { setMsg(`❌ ${e.message}`); }
  };

  const setRole = async (telegram_id, role) => {
    try {
      await apiFetch(`/participant/${telegram_id}/role`, {
        method:"POST",
        headers: adminHeaders(),
        body: JSON.stringify({ role }),
      });
      setMsg(`✅ Роль изменена`); refresh();
    } catch (e) { setMsg(`❌ ${e.message}`); }
  };

  const openTasks = tasks.filter(t => String(t.status||"").toLowerCase() !== "closed");
  const closedTasks = tasks.filter(t => String(t.status||"").toLowerCase() === "closed");
  const allDepts = [...new Set(tasks.map(t => t.department))];
  if (!allDepts.includes("Стажёры")) allDepts.unshift("Стажёры");

  return (
    <>
      <div className="tabs" style={{marginBottom:16}}>
        {[["tasks","📋 Задачи"],["create","➕ Создать"],["users","👥 Участники"],["stats","📊 Статистика"]].map(([k,l]) => (
          <button key={k} className={`tab ${subTab===k?"active":""}`} onClick={()=>setSubTab(k)}>{l}</button>
        ))}
      </div>

      {msg && <div className={msg.startsWith("❌")?"error-msg":"info-msg"} style={{marginBottom:12}}>{msg}</div>}

      {loading && <div className="loader">Загружаем...</div>}

      {/* ─ Список задач ─ */}
      {!loading && subTab === "tasks" && (
        <>
          <div className="section-label">Открытые ({openTasks.length})</div>
          {openTasks.map(t => (
            <div key={t.task_id} className="admin-task-row">
              <div className="admin-task-row-head">
                <div>
                  <div style={{fontWeight:500}}>{t.title}</div>
                  <div style={{fontSize:12,color:"var(--muted)",marginTop:3}}>
                    {t.department} · {t.current_participants}/{t.max_participants} участников
                  </div>
                </div>
              </div>
              {formatCheckpoints(t.checkpoints)}
              <div className="admin-actions">
                <button className="btn btn-danger btn-sm" onClick={()=>closeTaskAdmin(t.task_id)}>❌ Закрыть</button>
                <button className="btn btn-ghost btn-sm" onClick={()=>deleteTaskAdmin(t.task_id)}>🗑 Удалить</button>
              </div>
            </div>
          ))}
          <div className="section-label" style={{marginTop:20}}>Закрытые ({closedTasks.length})</div>
          {closedTasks.map(t => (
            <div key={t.task_id} className="admin-task-row" style={{opacity:0.6}}>
              <div style={{fontWeight:500}}>✅ {t.title}</div>
              <div style={{fontSize:12,color:"var(--muted)",marginTop:3}}>{t.department} · {t.max_participants} участников</div>
              <div className="admin-actions" style={{marginTop:8}}>
                <button className="btn btn-ghost btn-sm" onClick={()=>deleteTaskAdmin(t.task_id)}>🗑 Удалить</button>
              </div>
            </div>
          ))}
        </>
      )}

      {/* ─ Создать задачу ─ */}
      {subTab === "create" && (
        <div className="card">
          <div className="card-title">➕ Новая задача</div>
          <div className="field"><label>Название</label>
            <input value={form.title} onChange={e=>setForm({...form,title:e.target.value})} placeholder="Например: Сделать баннер" /></div>
          <div className="field"><label>Отдел</label>
            <select value={form.department} onChange={e=>setForm({...form,department:e.target.value})}>
              {allDepts.map(d=><option key={d} value={d}>{d}</option>)}
              <option value="__custom">Другой...</option>
            </select>
          </div>
          {form.department === "__custom" && (
            <div className="field"><label>Название отдела</label>
              <input onChange={e=>setForm({...form,department:e.target.value})} placeholder="Новый отдел" /></div>
          )}
          <div className="field"><label>Описание (необязательно)</label>
            <textarea value={form.description} onChange={e=>setForm({...form,description:e.target.value})} placeholder="Что нужно сделать..." /></div>
          <div className="field"><label>Максимум участников</label>
            <input type="number" min="1" value={form.max_participants} onChange={e=>setForm({...form,max_participants:e.target.value})} placeholder="3" /></div>

          <div className="field">
            <label>Промежуточные проверки</label>
            <div className="chips">
              {checks.map((c,i)=>(
                <span key={i} className="chip">🔍 {c.label} — {c.date}
                  <span className="chip-del" onClick={()=>setChecks(checks.filter((_,j)=>j!==i))}>×</span>
                </span>
              ))}
            </div>
            <div className="cp-add-row">
              <input type="date" value={checkInput.date} onChange={e=>setCheckInput({...checkInput,date:e.target.value})} />
              <input value={checkInput.label} onChange={e=>setCheckInput({...checkInput,label:e.target.value})} placeholder="Название проверки" />
              <button className="btn btn-ghost btn-sm" onClick={addCheck}>＋</button>
            </div>
          </div>

          <div className="field"><label>Дедлайн *</label>
            <input type="date" value={deadlineDate} onChange={e=>setDeadlineDate(e.target.value)} /></div>

          <button className="btn btn-primary" onClick={createTask}>Опубликовать задачу 🚀</button>
        </div>
      )}

      {/* ─ Участники и роли ─ */}
      {!loading && subTab === "users" && (
        <div className="card">
          <div className="card-title">👥 Участники ({participants.length})</div>
          {participants.map(p => (
            <div key={p.telegram_id} className="participant-row">
              <div className="participant-name">
                <div style={{fontWeight:500}}>{p.name}</div>
                <div style={{fontSize:11,color:"var(--muted)"}}>@{p.telegram_username}</div>
              </div>
              <div className="role-sel">
                {["intern","member","admin"].map(r => (
                  <button key={r} className={`role-btn ${p.role===r?"active":""}`}
                          onClick={()=>p.role!==r && setRole(p.telegram_id, r)}>
                    {ROLE_LABELS[r]}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ─ Статистика ─ */}
      {!loading && subTab === "stats" && (
        <div className="card">
          <div className="card-title">📊 Статистика</div>
          <div className="stat-grid">
            <div className="stat-box"><div className="stat-val">{openTasks.length}</div><div className="stat-label">Открытых задач</div></div>
            <div className="stat-box"><div className="stat-val">{closedTasks.length}</div><div className="stat-label">Закрытых задач</div></div>
            <div className="stat-box"><div className="stat-val">{participants.length}</div><div className="stat-label">Участников</div></div>
            <div className="stat-box">
              <div className="stat-val">{participants.filter(p=>p.role==="intern").length}</div>
              <div className="stat-label">Стажёров</div>
            </div>
          </div>
          <div className="section-label">По ролям</div>
          {["intern","member","admin"].map(r=>(
            <div key={r} style={{display:"flex",justifyContent:"space-between",padding:"8px 0",borderBottom:"1px solid var(--border)"}}>
              <span>{ROLE_LABELS[r]}</span>
              <span style={{color:"var(--accent)"}}>{participants.filter(p=>p.role===r).length}</span>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

// ── ГЛАВНЫЙ КОМПОНЕНТ ─────────────────────────────────────────
export default function App() {
  // Сохраняем пользователя в localStorage
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem("tgUser")) || null; }
    catch { return null; }
  });
  const [userRole, setUserRole] = useState("intern");
  const [tab, setTab] = useState("tasks");

  const saveUser = u => {
    setUser(u);
    if (u) localStorage.setItem("tgUser", JSON.stringify(u));
    else localStorage.removeItem("tgUser");
  };

  useEffect(() => {
    if (user?.telegram_id) {
      apiFetch(`/profile/${user.telegram_id}`)
        .then(d => setUserRole(d.role || "intern"))
        .catch(() => {});
    }
  }, [user?.telegram_id]);

  const isAdmin = userRole === "admin";

  const tabs = [
    ["tasks","📋 Задачи"],
    ["archive","🔒 Архив"],
    ["profile","👤 Профиль"],
    ["leaderboard","🏆 Рейтинг"],
    ...(isAdmin ? [["admin","⚙️ Управление"]] : []),
  ];

  return (
    <>
      <style>{css}</style>
      <div className="bg-grid" /><div className="glow" />
      <div className="wrap">
        <div className="header">
          <div className="header-tag">Студенческий совет СПбГАСУ</div>
          <h1>Задачи <span>студсовета</span></h1>
          <p>Записывайся на задачи, следи за дедлайнами, зарабатывай баллы</p>
        </div>

        <div className="tabs">
          {tabs.map(([k,l]) => (
            <button key={k} className={`tab ${tab===k?"active":""}`} onClick={()=>setTab(k)}>{l}</button>
          ))}
        </div>

        {tab === "tasks"       && <TabTasks user={user} setUser={saveUser} />}
        {tab === "archive"     && <TabArchive />}
        {tab === "profile"     && <TabProfile user={user} setUser={saveUser} />}
        {tab === "leaderboard" && <TabLeaderboard />}
        {tab === "admin"       && isAdmin && <TabAdmin user={user} />}
        {tab === "admin"       && !isAdmin && (
          <div className="card"><div style={{color:"var(--muted)",textAlign:"center",padding:24}}>⛔ Нет доступа</div></div>
        )}
      </div>
    </>
  );
}
