import { useState, useEffect } from "react";

const API = "http://localhost:8000";

const css = `
  @import url('https://fonts.googleapis.com/css2?family=Unbounded:wght@400;600;800&family=Inter:wght@300;400;500&display=swap');
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #0a0a0f; --surface: #13131a; --surface2: #1c1c26;
    --accent: #6c63ff; --accent2: #ff6584; --text: #f0f0f8;
    --muted: #7a7a99; --border: #2a2a3a; --success: #4ade80; --radius: 16px;
  }
  body { background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; min-height: 100vh; overflow-x: hidden; }
  .bg-grid {
    position: fixed; inset: 0; z-index: 0;
    background-image: linear-gradient(rgba(108,99,255,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(108,99,255,0.04) 1px, transparent 1px);
    background-size: 40px 40px; pointer-events: none;
  }
  .glow { position: fixed; width: 600px; height: 600px; border-radius: 50%; background: radial-gradient(circle, rgba(108,99,255,0.12) 0%, transparent 70%); top: -200px; left: -100px; pointer-events: none; z-index: 0; }
  .wrap { position: relative; z-index: 1; max-width: 860px; margin: 0 auto; padding: 40px 20px 80px; }
  .header { text-align: center; margin-bottom: 48px; }
  .header-tag { display: inline-block; font-family: 'Unbounded', sans-serif; font-size: 10px; letter-spacing: 3px; text-transform: uppercase; color: var(--accent); border: 1px solid rgba(108,99,255,0.3); padding: 6px 16px; border-radius: 100px; margin-bottom: 20px; }
  .header h1 { font-family: 'Unbounded', sans-serif; font-size: clamp(26px, 5vw, 44px); font-weight: 800; line-height: 1.15; margin-bottom: 12px; }
  .header h1 span { color: var(--accent); }
  .header p { color: var(--muted); font-size: 15px; }
  .tabs { display: flex; gap: 4px; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 4px; margin-bottom: 28px; }
  .tab { flex: 1; padding: 10px; text-align: center; border-radius: 9px; cursor: pointer; font-family: 'Unbounded', sans-serif; font-size: 11px; font-weight: 600; color: var(--muted); transition: all 0.2s; border: none; background: transparent; }
  .tab.active { background: var(--accent); color: #fff; }
  .tab:hover:not(.active) { color: var(--text); }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 28px; animation: fadeUp 0.35s ease both; margin-bottom: 16px; }
  @keyframes fadeUp { from { opacity:0; transform:translateY(16px); } to { opacity:1; transform:translateY(0); } }
  .card-title { font-family: 'Unbounded', sans-serif; font-size: 13px; font-weight: 600; color: var(--muted); letter-spacing: 1px; text-transform: uppercase; margin-bottom: 20px; }
  .field { margin-bottom: 18px; }
  .field label { display: block; font-size: 13px; color: var(--muted); margin-bottom: 7px; font-weight: 500; }
  .field input { width: 100%; padding: 13px 16px; background: var(--surface2); border: 1px solid var(--border); border-radius: 10px; color: var(--text); font-family: 'Inter', sans-serif; font-size: 15px; outline: none; transition: border-color 0.2s; }
  .field input:focus { border-color: var(--accent); }
  .field input::placeholder { color: var(--muted); }
  .btn { display: inline-flex; align-items: center; justify-content: center; gap: 8px; padding: 13px 24px; border-radius: 10px; border: none; cursor: pointer; font-family: 'Unbounded', sans-serif; font-size: 12px; font-weight: 600; transition: all 0.2s; letter-spacing: 0.5px; }
  .btn-primary { background: var(--accent); color: #fff; width: 100%; }
  .btn-primary:hover { background: #7c74ff; transform: translateY(-1px); }
  .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
  .btn-ghost { background: transparent; color: var(--muted); border: 1px solid var(--border); margin-bottom: 20px; font-size: 11px; padding: 9px 16px; }
  .btn-ghost:hover { color: var(--text); border-color: var(--muted); }
  .dept-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 10px; }
  .dept-card { padding: 18px; background: var(--surface2); border: 1px solid var(--border); border-radius: 12px; cursor: pointer; transition: all 0.2s; text-align: center; }
  .dept-card:hover { border-color: var(--accent); background: rgba(108,99,255,0.08); transform: translateY(-2px); }
  .dept-icon { font-size: 26px; margin-bottom: 8px; }
  .dept-name { font-family: 'Unbounded', sans-serif; font-size: 11px; font-weight: 600; }
  .task-list { display: flex; flex-direction: column; gap: 8px; }
  .task-item { padding: 16px 18px; background: var(--surface2); border: 1px solid var(--border); border-radius: 12px; cursor: pointer; transition: all 0.2s; display: flex; justify-content: space-between; align-items: center; }
  .task-item:hover { border-color: var(--accent); transform: translateX(3px); }
  .task-item.full { opacity: 0.4; cursor: not-allowed; }
  .task-item.full:hover { transform: none; border-color: var(--border); }
  .task-name { font-weight: 500; font-size: 15px; margin-bottom: 3px; }
  .task-sub { font-size: 12px; color: var(--muted); }
  .badge { font-family: 'Unbounded', sans-serif; font-size: 10px; padding: 4px 10px; border-radius: 100px; white-space: nowrap; }
  .badge-open { background: rgba(108,99,255,0.15); color: var(--accent); }
  .badge-full { background: rgba(255,101,132,0.15); color: var(--accent2); }
  .detail-title { font-family: 'Unbounded', sans-serif; font-size: 19px; font-weight: 700; margin-bottom: 10px; }
  .detail-desc { color: var(--muted); line-height: 1.7; margin-bottom: 22px; font-size: 14px; }
  .dates-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 20px; }
  .date-box { background: var(--surface2); border: 1px solid var(--border); border-radius: 10px; padding: 12px; text-align: center; }
  .date-label { font-size: 10px; color: var(--muted); margin-bottom: 5px; text-transform: uppercase; letter-spacing: 1px; }
  .date-val { font-family: 'Unbounded', sans-serif; font-size: 12px; font-weight: 600; }
  .date-val.dl { color: var(--accent2); }
  .team-section { background: var(--surface2); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; margin-bottom: 20px; }
  .team-title { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; }
  .team-member { font-size: 13px; color: var(--text); padding: 3px 0; }
  .team-member span { color: var(--accent); }
  .slots-bar { margin-bottom: 20px; }
  .slots-label { font-size: 12px; color: var(--muted); margin-bottom: 6px; display: flex; justify-content: space-between; }
  .slots-track { height: 6px; background: var(--border); border-radius: 100px; overflow: hidden; }
  .slots-fill { height: 100%; background: var(--accent); border-radius: 100px; transition: width 0.4s; }
  .error-msg { background: rgba(255,101,132,0.1); border: 1px solid rgba(255,101,132,0.3); color: var(--accent2); padding: 11px 15px; border-radius: 10px; font-size: 13px; margin-bottom: 14px; }
  .success-wrap { text-align: center; padding: 16px 0; }
  .success-icon { font-size: 56px; margin-bottom: 16px; animation: pop 0.5s ease; }
  @keyframes pop { 0%{transform:scale(0)} 80%{transform:scale(1.15)} 100%{transform:scale(1)} }
  .success-title { font-family: 'Unbounded', sans-serif; font-size: 20px; font-weight: 800; margin-bottom: 8px; }
  .success-sub { color: var(--muted); font-size: 14px; line-height: 1.6; margin-bottom: 20px; }
  .success-sub span { color: var(--success); font-weight: 500; }
  .loader { text-align: center; color: var(--muted); padding: 36px; font-size: 13px; }
  .section-label { font-family: 'Unbounded', sans-serif; font-size: 11px; color: var(--muted); letter-spacing: 2px; text-transform: uppercase; margin: 24px 0 12px; }
  .closed-item { padding: 16px 18px; background: var(--surface2); border: 1px solid var(--border); border-radius: 12px; margin-bottom: 8px; opacity: 0.7; cursor: pointer; transition: all 0.2s; }
  .closed-item:hover { opacity: 1; border-color: var(--muted); }
`;

const DEPT_ICONS = { "Маркетинг":"📣","IT":"💻","Дизайн":"🎨","PR":"📰","Финансы":"💰","HR":"👥","Аналитика":"📊","Организация":"📋" };
const getIcon = d => DEPT_ICONS[d] || "🏢";

// ── Шаг 1: Данные пользователя ──
function StepUser({ onNext }) {
  const [name, setName] = useState("");
  const [tgId, setTgId] = useState("");
  const [tgUser, setTgUser] = useState("");
  const [error, setError] = useState("");

  const handle = () => {
    if (!name.trim()) return setError("Введи имя и фамилию");
    if (!tgId.trim() || isNaN(tgId)) return setError("Введи корректный Telegram ID");
    if (!tgUser.trim()) return setError("Введи Telegram username");
    setError("");
    const username = tgUser.startsWith("@") ? tgUser.slice(1) : tgUser;
    onNext({ name: name.trim(), telegram_id: parseInt(tgId), telegram_username: username });
  };

  return (
    <div className="card">
      <div className="card-title">Твои данные</div>
      {error && <div className="error-msg">{error}</div>}
      <div className="field">
        <label>Имя и фамилия</label>
        <input value={name} onChange={e=>setName(e.target.value)} placeholder="Иван Иванов" />
      </div>
      <div className="field">
        <label>Telegram ID</label>
        <input value={tgId} onChange={e=>setTgId(e.target.value)} placeholder="Узнай у бота — напиши /start" />
      </div>
      <div className="field">
        <label>Telegram username</label>
        <input value={tgUser} onChange={e=>setTgUser(e.target.value)} placeholder="@username" />
      </div>
      <button className="btn btn-primary" onClick={handle}>Перейти к задачам →</button>
    </div>
  );
}

// ── Шаг 2: Выбор отдела ──
function StepDept({ onNext, onBack }) {
  const [depts, setDepts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/departments`).then(r=>r.json()).then(d=>{setDepts(d.departments);setLoading(false);}).catch(()=>setLoading(false));
  }, []);

  return (
    <div className="card">
      <button className="btn btn-ghost" onClick={onBack}>← Назад</button>
      <div className="card-title">Выбери отдел</div>
      {loading ? <div className="loader">Загружаем...</div> : (
        <div className="dept-grid">
          {depts.map(d => (
            <div className="dept-card" key={d} onClick={()=>onNext(d)}>
              <div className="dept-icon">{getIcon(d)}</div>
              <div className="dept-name">{d}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Шаг 3: Список задач ──
function StepTasks({ dept, user, onSelect, onBack }) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [takenIds, setTakenIds] = useState([]);

  useEffect(() => {
    fetch(`${API}/tasks/${encodeURIComponent(dept)}`).then(r=>r.json()).then(d=>{setTasks(d.tasks);setLoading(false);}).catch(()=>setLoading(false));
    // Узнаём задачи которые уже взял этот пользователь
    if (user?.telegram_id) {
      fetch(`${API}/participant/${user.telegram_id}`).then(r=>r.json()).then(d=>{
        // participant может быть null или первая запись; нужно проверить все участия
        // для простоты помечаем все задачи где он уже есть
      });
    }
  }, [dept]);

  return (
    <div className="card">
      <button className="btn btn-ghost" onClick={onBack}>← Назад</button>
      <div className="card-title">Задачи — {dept}</div>
      {loading ? <div className="loader">Загружаем...</div> : (
        <div className="task-list">
          {tasks.map(t => {
            const free = parseInt(t.max_participants) - parseInt(t.current_participants);
            const full = free <= 0;
            return (
              <div key={t.task_id} className={`task-item ${full?"full":""}`} onClick={()=>!full&&onSelect(t)}>
                <div>
                  <div className="task-name">{t.title}</div>
                  <div className="task-sub">{full ? "Мест нет" : `Свободно: ${free} из ${t.max_participants}`}</div>
                </div>
                <div className={`badge ${full?"badge-full":"badge-open"}`}>
                  {full ? "Закрыта" : `${free} мест`}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Шаг 4: Детали задачи ──
function StepDetail({ task, user, onSuccess, onBack }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [participants, setParticipants] = useState([]);

  useEffect(() => {
    fetch(`${API}/task/${task.task_id}/participants`).then(r=>r.json()).then(d=>setParticipants(d.participants));
  }, [task.task_id]);

  const free = parseInt(task.max_participants) - parseInt(task.current_participants);
  const fillPct = (parseInt(task.current_participants) / parseInt(task.max_participants)) * 100;

  const take = async () => {
    setLoading(true); setError("");
    try {
      const res = await fetch(`${API}/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: user.name, telegram_id: user.telegram_id, telegram_username: user.telegram_username, task_id: task.task_id }),
      });
      if (res.ok) { onSuccess(); }
      else { const d = await res.json(); setError(d.detail || "Ошибка при записи"); }
    } catch { setError("Сервер недоступен. Проверь что запущен main.py"); }
    setLoading(false);
  };

  return (
    <div className="card">
      <button className="btn btn-ghost" onClick={onBack}>← Назад</button>
      <div className="detail-title">{task.title}</div>
      <div className="detail-desc">{task.description}</div>

      <div className="slots-bar">
        <div className="slots-label">
          <span>Мест занято</span>
          <span>{task.current_participants} / {task.max_participants}</span>
        </div>
        <div className="slots-track"><div className="slots-fill" style={{width:`${fillPct}%`}} /></div>
      </div>

      <div className="dates-grid">
        <div className="date-box"><div className="date-label">Проверка 1</div><div className="date-val">{task.check_date_1||"—"}</div></div>
        <div className="date-box"><div className="date-label">Проверка 2</div><div className="date-val">{task.check_date_2||"—"}</div></div>
        <div className="date-box"><div className="date-label">Дедлайн</div><div className="date-val dl">{task.deadline||"—"}</div></div>
      </div>

      {participants.length > 0 && (
        <div className="team-section">
          <div className="team-title">👥 Уже в команде</div>
          {participants.map((p,i) => (
            <div className="team-member" key={i}>{p.name} <span>@{p.telegram_username}</span></div>
          ))}
        </div>
      )}

      {error && <div className="error-msg">{error}</div>}
      <button className="btn btn-primary" onClick={take} disabled={loading || free <= 0}>
        {loading ? "Записываемся..." : free <= 0 ? "Мест нет" : "Взять задачу ✓"}
      </button>
    </div>
  );
}

// ── Успех ──
function StepSuccess({ task, user, onMore }) {
  return (
    <div className="card">
      <div className="success-wrap">
        <div className="success-icon">🎉</div>
        <div className="success-title">Задача взята!</div>
        <div className="success-sub">
          Ты записан на <span>«{task.title}»</span><br />
          Уведомления придут в Telegram.<br />
          Дедлайн: <span>{task.deadline}</span>
        </div>
        <button className="btn btn-primary" style={{maxWidth:280,margin:"0 auto"}} onClick={onMore}>
          Взять ещё задачу →
        </button>
      </div>
    </div>
  );
}

// ── Закрытые задачи ──
function ClosedTasks() {
  const [tasks, setTasks] = useState([]);
  const [selected, setSelected] = useState(null);
  const [participants, setParticipants] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/tasks-all`).then(r=>r.json()).then(d=>{
      const closed = d.tasks.filter(t => parseInt(t.current_participants) >= parseInt(t.max_participants));
      setTasks(closed); setLoading(false);
    }).catch(()=>setLoading(false));
  }, []);

  const open = (t) => {
    setSelected(t);
    fetch(`${API}/task/${t.task_id}/participants`).then(r=>r.json()).then(d=>setParticipants(d.participants));
  };

  if (loading) return <div className="loader">Загружаем...</div>;
  if (tasks.length === 0) return <div className="card"><div style={{color:"var(--muted)",textAlign:"center",padding:"24px"}}>Закрытых задач пока нет</div></div>;

  if (selected) return (
    <div className="card">
      <button className="btn btn-ghost" onClick={()=>setSelected(null)}>← Назад</button>
      <div className="detail-title">{selected.title}</div>
      <div className="detail-desc">{selected.description}</div>
      <div className="dates-grid">
        <div className="date-box"><div className="date-label">Проверка 1</div><div className="date-val">{selected.check_date_1||"—"}</div></div>
        <div className="date-box"><div className="date-label">Проверка 2</div><div className="date-val">{selected.check_date_2||"—"}</div></div>
        <div className="date-box"><div className="date-label">Дедлайн</div><div className="date-val dl">{selected.deadline||"—"}</div></div>
      </div>
      <div className="team-section">
        <div className="team-title">👥 Команда</div>
        {participants.map((p,i)=>(
          <div className="team-member" key={i}>{p.name} <span>@{p.telegram_username}</span></div>
        ))}
      </div>
    </div>
  );

  // Группировка по отделам
  const byDept = {};
  tasks.forEach(t => { if (!byDept[t.department]) byDept[t.department] = []; byDept[t.department].push(t); });

  return (
    <>
      {Object.entries(byDept).map(([dept, dTasks]) => (
        <div key={dept}>
          <div className="section-label">{getIcon(dept)} {dept}</div>
          {dTasks.map(t => (
            <div className="closed-item" key={t.task_id} onClick={()=>open(t)}>
              <div className="task-name">{t.title}</div>
              <div className="task-sub" style={{marginTop:4}}>Команда набрана · {t.max_participants} участников · Дедлайн: {t.deadline}</div>
            </div>
          ))}
        </div>
      ))}
    </>
  );
}

// ── ГЛАВНЫЙ КОМПОНЕНТ ──
export default function App() {
  const [tab, setTab] = useState("tasks"); // tasks | closed
  const [step, setStep] = useState(0); // 0=user,1=dept,2=tasks,3=detail,4=success
  const [user, setUser] = useState(null);
  const [dept, setDept] = useState(null);
  const [task, setTask] = useState(null);

  const takeMore = () => { setStep(1); setDept(null); setTask(null); };

  return (
    <>
      <style>{css}</style>
      <div className="bg-grid" /><div className="glow" />
      <div className="wrap">
        <div className="header">
          <div className="header-tag">Студенческий совет</div>
          <h1>Выбери <span>задачу</span></h1>
          <p>Найди задачу по своему отделу и запишись</p>
        </div>

        <div className="tabs">
          <button className={`tab ${tab==="tasks"?"active":""}`} onClick={()=>setTab("tasks")}>📋 Открытые задачи</button>
          <button className={`tab ${tab==="closed"?"active":""}`} onClick={()=>setTab("closed")}>🔒 Закрытые задачи</button>
        </div>

        {tab === "closed" && <ClosedTasks />}

        {tab === "tasks" && (
          <>
            {step === 0 && <StepUser onNext={u=>{setUser(u);setStep(1);}} />}
            {step === 1 && <StepDept onNext={d=>{setDept(d);setStep(2);}} onBack={()=>setStep(0)} />}
            {step === 2 && <StepTasks dept={dept} user={user} onSelect={t=>{setTask(t);setStep(3);}} onBack={()=>setStep(1)} />}
            {step === 3 && <StepDetail task={task} user={user} onSuccess={()=>setStep(4)} onBack={()=>setStep(2)} />}
            {step === 4 && <StepSuccess task={task} user={user} onMore={takeMore} />}
          </>
        )}
      </div>
    </>
  );
}
